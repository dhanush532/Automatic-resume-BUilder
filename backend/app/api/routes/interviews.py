from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedRequest, require_authenticated_request
from app.auth.shared_limits import enforce
from app.core.config import get_settings
from app.core.database import get_db_session
from app.models.interview import InterviewSession
from app.models.resume import Resume, ResumeVersion
from app.schemas.interview import AnswerInput, InterviewControl, InterviewCreate
from app.services import interview_ai
from app.services.pdf import resume_content
from app.services.resume_review import MAX_FILE_BYTES, extract_document

router = APIRouter(prefix="/interviews")


def no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


router.dependencies.append(Depends(no_cache))


def schema_available(db):
    return db.scalar(select(func.to_regclass("interview_sessions"))) is not None


def require_interview_schema(auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    if not schema_available(db):
        raise HTTPException(503, "Interview database setup is pending. The operator must apply migration 20261023_0010 before interviews can be used.")


router.dependencies.append(Depends(require_interview_schema))


def ai_limit(auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    enforce(db, f"interview-ai:{auth.user.id}", limit=100, seconds=3600)


def owned(db, user_id, interview_id):
    session = db.scalar(select(InterviewSession).where(InterviewSession.id == interview_id, InterviewSession.user_id == user_id))
    if not session:
        raise HTTPException(404, "Interview not found.")
    return session


def elapsed(session):
    return session.elapsed_seconds + (max(0, int((datetime.now(UTC) - session.running_since).total_seconds())) if session.running_since else 0)


def persist(db, session, **values):
    revision = session.revision
    values.update(revision=revision + 1, updated_at=datetime.now(UTC))
    changed = db.execute(update(InterviewSession).where(InterviewSession.id == session.id, InterviewSession.revision == revision).values(**values).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This interview changed in another tab. Reload to continue; your typed answer is kept in this tab.")
    db.commit()
    db.refresh(session)


def expire(db, session):
    if session.status == "active" and elapsed(session) >= session.duration_minutes * 60:
        persist(db, session, status="completed", running_since=None, elapsed_seconds=session.duration_minutes * 60)


def ai_call(callback, *args):
    try:
        return callback(*args)
    except interview_ai.InterviewAIError as exc:
        raise HTTPException(exc.status, str(exc), headers={"Retry-After": "60"} if exc.status == 429 else None) from exc


def report(session):
    answered = [turn for turn in session.turns if turn.get("evaluation")]
    evaluations = [turn["evaluation"] for turn in answered]
    def mean(key):
        return round(sum(item[key] for item in evaluations) / len(evaluations)) if evaluations else None
    def unique(key):
        return list(dict.fromkeys(line for item in evaluations for line in item[key]))[:12]
    return {"score": mean("score"), "accuracy": mean("accuracy"), "relevance": mean("relevance"), "clarity": mean("clarity"),
            "answered": len(answered), "planned": session.question_count,
            "strengths": unique("strengths"), "weaknesses": unique("weaknesses"), "recommendations": unique("recommendations"),
            "note": "AI practice feedback based only on submitted text. Not a hiring prediction or assessment of personality, honesty or intelligence."}


def public(session, detail=True):
    result = {"id": str(session.id), "resume_id": str(session.resume_id) if session.resume_id else None,
              "role": session.role, "interview_type": session.interview_type, "difficulty": session.difficulty,
              "duration_minutes": session.duration_minutes, "question_count": session.question_count,
              "status": session.status, "elapsed_seconds": min(elapsed(session), session.duration_minutes * 60),
              "created_at": session.created_at, "revision": session.revision, "model": session.model,
              "report": report(session)}
    if detail:
        result["turns"] = session.turns
    return result


def context_for(snapshot):
    content = resume_content(snapshot)
    lines = []
    # Do not transmit the name/contact header or links. Use only career evidence.
    for section in content["sections"]:
        if section["key"] in {"professional_links", "languages"}:
            continue
        lines.append(section["label"])
        for entry in section["entries"]:
            lines.extend(str(value) for value in [entry.get("lead"), *entry.get("pre_details", []), *entry["lines"], *entry.get("details", [])] if value)
    context = interview_ai.redact("\n".join(lines))[:16000]
    if len(context.strip()) < 80:
        raise HTTPException(422, "This resume has too little career evidence. Add your skills, projects or experience first.")
    return context


def start(db, user_id, config, context, resume_id=None):
    settings = get_settings()
    session = InterviewSession(user_id=user_id, resume_id=resume_id, role=interview_ai.redact(config.role),
                               job_description=interview_ai.redact(config.job_description), context=context,
                               interview_type=config.interview_type, difficulty=config.difficulty,
                               duration_minutes=config.duration_minutes, question_count=config.question_count,
                               turns=[], model=settings.gemini_interview_model, status="active", revision=1, elapsed_seconds=0)
    first = ai_call(interview_ai.next_question, session)
    session.turns = [{**first, "id": str(uuid4())}]
    session.running_since = datetime.now(UTC)
    db.add(session)
    db.commit()
    db.refresh(session)
    return public(session)


@router.get("/capabilities")
def capabilities(auth: AuthenticatedRequest = Depends(require_authenticated_request)):
    settings = get_settings()
    return {"configured": bool(settings.gemini_api_key), "provider": "gemini", "model": settings.gemini_interview_model}


@router.post("/extract", dependencies=[Depends(ai_limit)])
async def extract_resume(file: UploadFile = File(...)):
    from fastapi.concurrency import run_in_threadpool
    try:
        data = await file.read(MAX_FILE_BYTES + 1)
        if not (file.filename or "").lower().endswith(".pdf"):
            raise ValueError("Choose a text-based PDF resume (up to 3 MB).")
        text = await run_in_threadpool(extract_document, data, file.filename)
        return {"text": text}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@router.get("")
def history(auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session), offset: int = 0):
    if offset < 0 or offset > 100000:
        raise HTTPException(422, "Invalid history offset.")
    sessions = db.scalars(select(InterviewSession).where(InterviewSession.user_id == auth.user.id).order_by(InterviewSession.created_at.desc()).offset(offset).limit(50)).all()
    for session in sessions:
        expire(db, session)
    return [public(session, False) for session in sessions]


@router.post("", status_code=201, dependencies=[Depends(ai_limit)])
def create(payload: InterviewCreate, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    if payload.resume_id:
        resume = db.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == auth.user.id))
        if not resume:
            raise HTTPException(404, "Resume not found.")
        version = db.scalar(select(ResumeVersion).where(ResumeVersion.resume_id == resume.id).order_by(ResumeVersion.version_number.desc()).limit(1))
        if not version:
            raise HTTPException(422, "This resume has no saved version.")
        snapshot = version.content_snapshot
    else:
        snapshot = {"source": "document_import", "imported_text": payload.resume_text}
    return start(db, auth.user.id, payload, context_for(snapshot), payload.resume_id)


@router.get("/{interview_id}")
def detail(interview_id: UUID, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    session = owned(db, auth.user.id, interview_id)
    expire(db, session)
    return public(session)


@router.post("/{interview_id}/answers", dependencies=[Depends(ai_limit)])
def answer(interview_id: UUID, payload: AnswerInput, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    session = owned(db, auth.user.id, interview_id)
    # An identical retry after a lost HTTP response is safe, even for the last turn.
    previous = next((turn for turn in session.turns if turn["id"] == str(payload.question_id)), None)
    text = payload.answer.strip()
    if previous and previous.get("evaluation"):
        if previous["answer"] == text:
            return public(session)
        raise HTTPException(409, "This question already has a saved answer.")
    expire(db, session)
    if session.status != "active":
        raise HTTPException(409, "Resume the interview before answering, or open its completed report.")
    if not text:
        raise HTTPException(422, "Type or dictate an answer first.")
    if not session.turns or session.turns[-1]["id"] != str(payload.question_id):
        raise HTTPException(409, "Answer the current question. Reload to synchronize your session.")
    evaluation = ai_call(interview_ai.evaluate_answer, session, session.turns[-1], text)
    turns = deepcopy(session.turns)
    turns[-1].update(answer=text, evaluation=evaluation, answered_at=datetime.now(UTC).isoformat())
    finished = len(turns) >= session.question_count or elapsed(session) >= session.duration_minutes * 60
    values = {"turns": turns}
    if finished:
        values.update(status="completed", elapsed_seconds=min(elapsed(session), session.duration_minutes * 60), running_since=None)
    persist(db, session, **values)
    return public(session)


@router.post("/{interview_id}/next", dependencies=[Depends(ai_limit)])
def next_turn(interview_id: UUID, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    session = owned(db, auth.user.id, interview_id)
    expire(db, session)
    if session.status != "active":
        raise HTTPException(409, "This interview is paused or completed.")
    if session.turns and not session.turns[-1].get("evaluation"):
        return public(session)
    if len(session.turns) >= session.question_count:
        raise HTTPException(409, "All planned questions are complete.")
    question = ai_call(interview_ai.next_question, session)
    persist(db, session, turns=[*session.turns, {**question, "id": str(uuid4())}], difficulty=question["difficulty"])
    return public(session)


@router.post("/{interview_id}/control")
def control(interview_id: UUID, payload: InterviewControl, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    session = owned(db, auth.user.id, interview_id)
    expire(db, session)
    if payload.action == "end" and session.status != "completed":
        persist(db, session, status="completed", elapsed_seconds=elapsed(session), running_since=None)
    elif payload.action == "pause" and session.status == "active":
        persist(db, session, status="paused", elapsed_seconds=elapsed(session), running_since=None)
    elif payload.action == "resume" and session.status == "paused":
        persist(db, session, status="active", running_since=datetime.now(UTC))
    return public(session)


@router.post("/{interview_id}/retake", status_code=201, dependencies=[Depends(ai_limit)])
def retake(interview_id: UUID, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    original = owned(db, auth.user.id, interview_id)
    return start(db, auth.user.id, original, original.context, original.resume_id)


@router.delete("/{interview_id}", status_code=204)
def remove(interview_id: UUID, auth: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    db.delete(owned(db, auth.user.id, interview_id))
    db.commit()
