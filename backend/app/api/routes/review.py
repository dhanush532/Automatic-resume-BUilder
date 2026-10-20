from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedRequest, require_authenticated_request
from app.auth.shared_limits import enforce
from app.core.database import get_db_session
from app.models.resume import Resume, ResumeTemplate, ResumeVersion
from app.services.pdf import render_pdf
from app.services.resume_review import MAX_FILE_BYTES, MAX_TEXT, extract_document, review_resume

router = APIRouter(prefix="/review")


class ReviewInput(BaseModel):
    text: str = Field(min_length=80, max_length=MAX_TEXT)
    job_description: str = Field(default="", max_length=20000)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        value = value.replace("\x00", "").strip()
        if len(value) < 80:
            raise ValueError("Add at least 80 characters of readable resume text.")
        return value


class ImportInput(ReviewInput):
    name: str = Field(default="Imported resume", min_length=1, max_length=160)
    template_id: UUID | None = None


def review_limit(request: Request, db: Session = Depends(get_db_session)):
    # Use a shared database bucket across serverless instances, not process memory.
    enforce(db, "resume-review:" + (request.client.host if request.client else "unknown"), limit=30, seconds=3600)


@router.post("/extract", dependencies=[Depends(review_limit)])
async def extract(response: Response, file: UploadFile = File(...)):
    response.headers["Cache-Control"] = "no-store"
    try:
        data = await file.read(MAX_FILE_BYTES + 1)
        text = await run_in_threadpool(extract_document, data, file.filename or "")
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@router.post("", dependencies=[Depends(review_limit)])
def evaluate(payload: ReviewInput, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return review_resume(payload.text, payload.job_description)


@router.post("/pdf", dependencies=[Depends(review_limit)])
def export_pdf(payload: ReviewInput):
    content = render_pdf({"source": "document_import", "imported_text": payload.text}, "ats_readable")
    return Response(content, media_type="application/pdf", headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="resume.pdf"'})


@router.post("/save", status_code=201)
def save_import(payload: ImportInput, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    if not payload.name.strip():
        raise HTTPException(422, "Give your resume a name.")
    query = select(ResumeTemplate).where(ResumeTemplate.is_active.is_(True))
    if payload.template_id:
        query = query.where(ResumeTemplate.id == payload.template_id)
    else:
        query = query.order_by((ResumeTemplate.template_key == "ats_readable").desc(), ResumeTemplate.name)
    template = db.scalar(query.limit(1))
    if not template:
        raise HTTPException(422, "No active resume template is available.")
    result = review_resume(payload.text, payload.job_description)
    resume = Resume(user_id=authenticated.user.id, name=payload.name.strip(), template_id=template.id, type="master", status="draft")
    db.add(resume)
    db.flush()
    # Preserve original extracted content rather than inventing employers, dates, or credentials.
    snapshot = {"schema_version": 1, "source": "document_import", "profile": {"full_name": result["profile"]["full_name"] or authenticated.user.full_name},
                "imported_text": payload.text, "resume_meta": {"hidden_sections": [], "section_order": []}}
    db.add(ResumeVersion(resume_id=resume.id, version_number=1, source="manual", content_snapshot=snapshot,
                         template_id=template.id, created_by=authenticated.user.id, change_summary="Imported and reviewed resume text"))
    db.commit()
    return {"id": str(resume.id)}
