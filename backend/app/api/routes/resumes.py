from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import AuthenticatedRequest, require_authenticated_request
from app.core.database import get_db_session
from app.models.resume import Resume, ResumeCustomization, ResumeTemplate, ResumeVersion
from app.schemas.resume import (
    JobDescriptionInput,
    ResumeContentEdit,
    ResumeCreate,
    ResumeCustomizationCreate,
    ResumeCustomizationResponse,
    ResumePreviewResponse,
    ResumeResponse,
    ResumeTemplateResponse,
    ResumeUpdate,
    ResumeVersionCreate,
    ResumeVersionResponse,
)
from app.services.ai import AIProviderUnavailable, get_ai_provider
from app.services.pdf import render_pdf, render_preview_html
from app.services.resume_snapshots import (
    apply_content_edit,
    build_passport_snapshot,
    passport_source_ids,
)

router = APIRouter(prefix="/resumes")


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found.")


def _owned_resume(db: Session, user_id: UUID, resume_id: UUID) -> Resume:
    resume = db.scalar(
        select(Resume).options(joinedload(Resume.template)).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    if not resume:
        raise _not_found()
    return resume


def _template(db: Session, template_id: UUID, *, active_only: bool = True) -> ResumeTemplate:
    query = select(ResumeTemplate).where(ResumeTemplate.id == template_id)
    if active_only:
        query = query.where(ResumeTemplate.is_active.is_(True))
    template = db.scalar(query)
    if not template:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Selected resume template is not available.")
    return template


def _latest_version(db: Session, resume_id: UUID) -> ResumeVersion | None:
    return db.scalar(select(ResumeVersion).where(ResumeVersion.resume_id == resume_id).order_by(ResumeVersion.version_number.desc()).limit(1))


def _version_response(version: ResumeVersion) -> ResumeVersionResponse:
    return ResumeVersionResponse.model_validate(version)


def _resume_response(db: Session, resume: Resume) -> ResumeResponse:
    latest = _latest_version(db, resume.id)
    version_count = db.query(ResumeVersion).filter(ResumeVersion.resume_id == resume.id).count()
    return ResumeResponse.model_validate({
        "id": resume.id,
        "user_id": resume.user_id,
        "name": resume.name,
        "template_id": resume.template_id,
        "type": resume.type,
        "status": resume.status,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
        "template": resume.template,
        "latest_version": _version_response(latest) if latest else None,
        "version_count": version_count,
    })


def _version_for_owner(db: Session, user_id: UUID, resume_id: UUID, version_id: UUID) -> ResumeVersion:
    version = db.scalar(
        select(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(ResumeVersion.id == version_id, ResumeVersion.resume_id == resume_id, Resume.user_id == user_id)
    )
    if not version:
        raise _not_found()
    return version


def _next_version_number(db: Session, resume_id: UUID) -> int:
    latest = _latest_version(db, resume_id)
    return latest.version_number + 1 if latest else 1


@router.get("/templates", response_model=list[ResumeTemplateResponse])
def list_templates(
    _: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[ResumeTemplateResponse]:
    templates = db.scalars(select(ResumeTemplate).where(ResumeTemplate.is_active.is_(True)).order_by(ResumeTemplate.name)).all()
    return [ResumeTemplateResponse.model_validate(template) for template in templates]


@router.get("", response_model=list[ResumeResponse])
def list_resumes(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[ResumeResponse]:
    resumes = db.scalars(select(Resume).options(joinedload(Resume.template)).where(Resume.user_id == authenticated.user.id).order_by(Resume.updated_at.desc())).all()
    return [_resume_response(db, resume) for resume in resumes]


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
def create_resume(
    payload: ResumeCreate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeResponse:
    template = _template(db, payload.template_id)
    resume = Resume(user_id=authenticated.user.id, name=payload.name.strip(), template_id=template.id, type=payload.type, status="draft")
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        resume_id=resume.id,
        version_number=1,
        source="passport",
        content_snapshot=build_passport_snapshot(db, authenticated.user.id),
        template_id=template.id,
        created_by=authenticated.user.id,
        change_summary="Initial version derived from Career Passport",
    )
    db.add(version)
    db.commit()
    db.refresh(resume)
    return _resume_response(db, resume)


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeResponse:
    return _resume_response(db, _owned_resume(db, authenticated.user.id, resume_id))


@router.patch("/{resume_id}", response_model=ResumeResponse)
def update_resume(
    resume_id: UUID,
    payload: ResumeUpdate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    if payload.template_id is not None and payload.template_id != resume.template_id:
        _template(db, payload.template_id)
        resume.template_id = payload.template_id
    if payload.name is not None:
        resume.name = payload.name.strip()
    if payload.status is not None:
        resume.status = payload.status
    latest = _latest_version(db, resume.id)
    if latest:
        db.add(ResumeVersion(
            resume_id=resume.id,
            version_number=_next_version_number(db, resume.id),
            source="manual",
            content_snapshot=latest.content_snapshot,
            template_id=resume.template_id,
            created_by=authenticated.user.id,
            change_summary="Resume settings updated",
        ))
    db.commit()
    db.refresh(resume)
    return _resume_response(db, resume)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> Response:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    db.delete(resume)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{resume_id}/duplicate", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
def duplicate_resume(
    resume_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeResponse:
    original = _owned_resume(db, authenticated.user.id, resume_id)
    latest = _latest_version(db, original.id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume has no version to duplicate.")
    duplicate = Resume(user_id=authenticated.user.id, name=f"{original.name} (Copy)", template_id=original.template_id, type=original.type, status="draft")
    db.add(duplicate)
    db.flush()
    db.add(ResumeVersion(
        resume_id=duplicate.id,
        version_number=1,
        source="duplicate",
        content_snapshot=latest.content_snapshot,
        template_id=latest.template_id,
        created_by=authenticated.user.id,
        change_summary=f"Duplicated from {original.name}",
    ))
    db.commit()
    db.refresh(duplicate)
    return _resume_response(db, duplicate)


@router.get("/{resume_id}/versions", response_model=list[ResumeVersionResponse])
def list_versions(
    resume_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[ResumeVersionResponse]:
    _owned_resume(db, authenticated.user.id, resume_id)
    versions = db.scalars(select(ResumeVersion).where(ResumeVersion.resume_id == resume_id).order_by(ResumeVersion.version_number.desc())).all()
    return [_version_response(version) for version in versions]


@router.post("/{resume_id}/versions", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
def create_version(
    resume_id: UUID,
    payload: ResumeVersionCreate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeVersionResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(422, "Give your resume a name.")
        resume.name = payload.name.strip()
    if payload.template_id is not None:
        resume.template_id = _template(db, payload.template_id).id
    edit = ResumeContentEdit.model_validate(payload.model_dump(exclude={"change_summary", "name", "template_id"}))
    latest = _latest_version(db, resume.id)
    base = latest.content_snapshot if latest and latest.content_snapshot.get("source") == "document_import" else build_passport_snapshot(db, authenticated.user.id)
    try:
        snapshot = apply_content_edit(base, edit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    resume.updated_at = datetime.now(UTC)
    version = ResumeVersion(
        resume_id=resume.id,
        version_number=_next_version_number(db, resume.id),
        source="manual",
        content_snapshot=snapshot,
        template_id=resume.template_id,
        created_by=authenticated.user.id,
        change_summary=payload.change_summary or "Resume content saved",
    )
    db.add(version)
    try:
        db.commit()
        db.refresh(version)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume version could not be created.") from error
    return _version_response(version)


@router.post("/{resume_id}/versions/{version_id}/restore", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
def restore_version(
    resume_id: UUID,
    version_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeVersionResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    source_version = _version_for_owner(db, authenticated.user.id, resume.id, version_id)
    resume.template_id = source_version.template_id
    version = ResumeVersion(
        resume_id=resume.id,
        version_number=_next_version_number(db, resume.id),
        source="restore",
        content_snapshot=source_version.content_snapshot,
        template_id=source_version.template_id,
        created_by=authenticated.user.id,
        restored_from_version_id=source_version.id,
        change_summary=f"Restored version {source_version.version_number}",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_response(version)


def _selected_version(db: Session, user_id: UUID, resume_id: UUID, version_id: UUID | None) -> ResumeVersion:
    resume = _owned_resume(db, user_id, resume_id)
    if version_id is not None:
        return _version_for_owner(db, user_id, resume.id, version_id)
    latest = _latest_version(db, resume.id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume has no version to preview.")
    return latest


@router.get("/{resume_id}/preview", response_model=ResumePreviewResponse)
def preview_resume(
    resume_id: UUID,
    version_id: UUID | None = Query(default=None),
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumePreviewResponse:
    version = _selected_version(db, authenticated.user.id, resume_id, version_id)
    template = db.get(ResumeTemplate, version.template_id)
    if not template:
        raise _not_found()
    return ResumePreviewResponse(resume_id=resume_id, version_id=version.id, template_key=template.template_key, html=render_preview_html(version.content_snapshot, template.template_key))


@router.get("/{resume_id}/pdf")
def export_pdf(
    resume_id: UUID,
    version_id: UUID | None = Query(default=None),
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    version = _selected_version(db, authenticated.user.id, resume_id, version_id)
    template = db.get(ResumeTemplate, version.template_id)
    if not template:
        raise _not_found()
    pdf = render_pdf(version.content_snapshot, template.template_key)
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="resume-{resume_id}.pdf"'})


@router.get("/{resume_id}/customizations", response_model=list[ResumeCustomizationResponse])
def list_customizations(
    resume_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[ResumeCustomizationResponse]:
    _owned_resume(db, authenticated.user.id, resume_id)
    records = db.scalars(select(ResumeCustomization).where(ResumeCustomization.resume_id == resume_id).order_by(ResumeCustomization.created_at.desc())).all()
    return [ResumeCustomizationResponse.model_validate(record) for record in records]


@router.post("/{resume_id}/customizations", response_model=ResumeCustomizationResponse, status_code=status.HTTP_201_CREATED)
def create_customization_review(
    resume_id: UUID,
    payload: ResumeCustomizationCreate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeCustomizationResponse:
    _owned_resume(db, authenticated.user.id, resume_id)
    base_version = _version_for_owner(db, authenticated.user.id, resume_id, payload.base_version_id)
    source_ids = passport_source_ids(build_passport_snapshot(db, authenticated.user.id))
    unknown = {str(source_id) for source_id in payload.generated_content.source_evidence} - source_ids
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Customization evidence must reference current Career Passport records.")
    record = ResumeCustomization(
        resume_id=resume_id,
        base_version_id=base_version.id,
        generated_content=payload.generated_content.model_dump(mode="json"),
        changes={"items": payload.changes, "missing_requirements": payload.generated_content.missing_requirements},
        provider_metadata=payload.provider_metadata,
        status="pending_review",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ResumeCustomizationResponse.model_validate(record)


@router.post("/{resume_id}/customizations/generate", response_model=ResumeCustomizationResponse)
def generate_customization(
    resume_id: UUID,
    payload: JobDescriptionInput,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeCustomizationResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    latest = _latest_version(db, resume.id)
    if not latest:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resume has no version to customize.")
    try:
        get_ai_provider().customize_resume(job_description=payload.job_description, resume_snapshot=latest.content_snapshot)
    except AIProviderUnavailable as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No AI provider is configured.")


@router.post("/{resume_id}/customizations/{customization_id}/approve", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
def approve_customization(
    resume_id: UUID,
    customization_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeVersionResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    customization = db.scalar(select(ResumeCustomization).where(ResumeCustomization.id == customization_id, ResumeCustomization.resume_id == resume.id))
    if not customization:
        raise _not_found()
    if customization.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending customizations can be approved.")
    generated = customization.generated_content
    source_ids = passport_source_ids(build_passport_snapshot(db, authenticated.user.id))
    if set(generated.get("source_evidence", [])) - source_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customization evidence is no longer present in the Career Passport.")
    edit = ResumeContentEdit(headline_override=generated.get("headline_override"), summary_override=generated.get("summary_override"))
    version = ResumeVersion(
        resume_id=resume.id,
        version_number=_next_version_number(db, resume.id),
        source="ai_approved",
        content_snapshot=apply_content_edit(build_passport_snapshot(db, authenticated.user.id), edit),
        template_id=resume.template_id,
        created_by=authenticated.user.id,
        change_summary="Approved reviewed customization",
    )
    customization.status = "approved"
    db.add(version)
    db.commit()
    db.refresh(version)
    return _version_response(version)


@router.post("/{resume_id}/customizations/{customization_id}/reject", response_model=ResumeCustomizationResponse)
def reject_customization(
    resume_id: UUID,
    customization_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ResumeCustomizationResponse:
    resume = _owned_resume(db, authenticated.user.id, resume_id)
    customization = db.scalar(select(ResumeCustomization).where(ResumeCustomization.id == customization_id, ResumeCustomization.resume_id == resume.id))
    if not customization:
        raise _not_found()
    customization.status = "rejected"
    db.commit()
    db.refresh(customization)
    return ResumeCustomizationResponse.model_validate(customization)


@router.get("/{resume_id}/preview/html", response_class=HTMLResponse, include_in_schema=False)
def preview_html(
    resume_id: UUID,
    version_id: UUID | None = Query(default=None),
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> HTMLResponse:
    version = _selected_version(db, authenticated.user.id, resume_id, version_id)
    template = db.get(ResumeTemplate, version.template_id)
    if not template:
        raise _not_found()
    return HTMLResponse(render_preview_html(version.content_snapshot, template.template_key))
