from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import (
    AuthenticatedRequest,
    require_authenticated_request,
    require_same_site_mutation,
)
from app.core.database import get_db_session
from app.models.jobs import Company, Job, JobSkill, JobSource, SavedJob
from app.schemas.jobs import (
    CompanyPage,
    CompanyResponse,
    JobMatchResponse,
    JobPage,
    JobRecommendationPage,
    JobRecommendationResponse,
    JobResponse,
    JobSkillResponse,
    JobSourceInfo,
    SavedJobCreate,
    SavedJobPage,
    SavedJobResponse,
    SkillGapResponse,
)
from app.services.arbeitnow import configured_registry
from app.services.job_matching import SKILL_NORMALIZATION_RULE, match_job, skill_gaps
from app.services.job_sources import normalize_token, validate_url
from app.services.job_verification import effective_status_expression, effective_verification

jobs_router = APIRouter(prefix="/jobs")
saved_router = APIRouter(prefix="/saved-jobs")
companies_router = APIRouter(prefix="/companies")
recommendations_router = APIRouter(prefix="/job-recommendations")


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    return (page - 1) * page_size, page_size


def _job_query() -> Any:
    return select(Job).options(joinedload(Job.company), joinedload(Job.source), selectinload(Job.skills))


def _job_response(job: Job, *, is_saved: bool = False) -> JobResponse:
    availability, verification, reason = effective_verification(job)
    try:
        validate_url(job.application_url, field="application_url")
        safe_url = True
    except ValueError:
        safe_url = False
    return JobResponse.model_validate(
        {
            "id": job.id,
            "company": job.company,
            "source": job.source,
            "external_job_id": job.external_job_id,
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "normalized_location": job.normalized_location,
            "remote_type": job.remote_type,
            "employment_type": job.employment_type,
            "experience_requirements": job.experience_requirements,
            "education_requirements": job.education_requirements,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "salary_period": job.salary_period,
            "application_url": job.application_url,
            "canonical_url": job.canonical_url,
            "source_url": job.source_url,
            "posted_at": job.posted_at,
            "deadline_at": job.deadline_at,
            "first_seen_at": job.first_seen_at,
            "last_seen_at": job.last_seen_at,
            "last_verified_at": job.last_verified_at,
            "status": availability,
            "verification_status": verification,
            "application_link_allowed": safe_url and availability == "ACTIVE" and job.verification_status != "SUSPICIOUS",
            "verification_reason": reason,
            "skills": [JobSkillResponse.model_validate(skill) for skill in job.skills],
            "is_saved": is_saved,
        }
    )


def _saved_ids(db: Session, user_id: UUID, job_ids: list[UUID]) -> set[UUID]:
    if not job_ids:
        return set()
    return set(db.scalars(select(SavedJob.job_id).where(SavedJob.user_id == user_id, SavedJob.job_id.in_(job_ids))))


def _apply_job_filters(
    query: Any,
    *,
    keyword: str | None,
    title: str | None,
    company: str | None,
    location: str | None,
    remote_type: str | None,
    employment_type: str | None,
    experience: str | None,
    education: str | None,
    skill: str | None,
    min_salary: Decimal | None,
    max_salary: Decimal | None,
    status_filter: str | None,
    include_unverified: bool,
) -> Any:
    availability = effective_status_expression()
    if status_filter:
        query = query.where(availability == status_filter)
    elif include_unverified:
        query = query.where(availability.in_(["ACTIVE", "UNVERIFIED"]))
    else:
        query = query.where(availability == "ACTIVE", Job.verification_status != "SUSPICIOUS")
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.where(or_(Job.title.ilike(term), Job.description.ilike(term), Company.name.ilike(term)))
    if title:
        query = query.where(Job.title.ilike(f"%{title.strip()}%"))
    if company:
        query = query.where(Company.name.ilike(f"%{company.strip()}%"))
    if location:
        query = query.where(or_(Job.location.ilike(f"%{location.strip()}%"), Job.normalized_location.ilike(f"%{normalize_token(location)}%")))
    if remote_type:
        query = query.where(Job.remote_type == remote_type)
    if employment_type:
        query = query.where(Job.employment_type == employment_type)
    if experience:
        query = query.where(Job.experience_requirements.ilike(f"%{experience.strip()}%"))
    if education:
        query = query.where(Job.education_requirements.ilike(f"%{education.strip()}%"))
    if skill:
        query = query.where(Job.id.in_(select(JobSkill.job_id).where(JobSkill.normalized_name.ilike(f"%{normalize_token(skill)}%"))))
    if min_salary is not None:
        query = query.where(Job.salary_max.is_not(None), Job.salary_max >= min_salary)
    if max_salary is not None:
        query = query.where(Job.salary_min.is_not(None), Job.salary_min <= max_salary)
    return query


@jobs_router.get("", response_model=JobPage)
def list_jobs(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    keyword: str | None = Query(default=None, max_length=160),
    title: str | None = Query(default=None, max_length=160),
    company: str | None = Query(default=None, max_length=160),
    location: str | None = Query(default=None, max_length=160),
    remote_type: str | None = Query(default=None, pattern="^(remote|hybrid|onsite|unknown)$"),
    employment_type: str | None = Query(default=None, pattern="^(full_time|part_time|contract|internship|temporary|freelance|volunteer|unknown)$"),
    experience: str | None = Query(default=None, max_length=160),
    education: str | None = Query(default=None, max_length=160),
    skill: str | None = Query(default=None, max_length=120),
    min_salary: Decimal | None = Query(default=None, ge=0),
    max_salary: Decimal | None = Query(default=None, ge=0),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(ACTIVE|CLOSED|EXPIRED|UNVERIFIED)$"),
    include_unverified: bool = False,
    sort: str = Query(default="newest", pattern="^(newest|oldest|salary_high|salary_low)$"),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> JobPage:
    query = _apply_job_filters(
        _job_query().join(Company), keyword=keyword, title=title, company=company, location=location,
        remote_type=remote_type, employment_type=employment_type, experience=experience,
        education=education, skill=skill, min_salary=min_salary, max_salary=max_salary,
        status_filter=status_filter, include_unverified=include_unverified,
    )
    if sort == "oldest":
        query = query.order_by(Job.posted_at.asc().nulls_last(), Job.created_at.asc())
    elif sort == "salary_high":
        query = query.order_by(Job.salary_max.desc().nullslast(), Job.posted_at.desc().nullslast(), Job.created_at.desc())
    elif sort == "salary_low":
        query = query.order_by(Job.salary_min.asc().nulls_last(), Job.posted_at.desc().nullslast(), Job.created_at.desc())
    else:
        query = query.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc())
    total_query = _apply_job_filters(select(func.count(Job.id)).join(Company), keyword=keyword, title=title, company=company, location=location, remote_type=remote_type, employment_type=employment_type, experience=experience, education=education, skill=skill, min_salary=min_salary, max_salary=max_salary, status_filter=status_filter, include_unverified=include_unverified)
    total = int(db.scalar(total_query) or 0)
    offset, limit = _pagination(page, page_size)
    jobs = db.scalars(query.offset(offset).limit(limit)).unique().all()
    saved = _saved_ids(db, authenticated.user.id, [job.id for job in jobs])
    return JobPage(items=[_job_response(job, is_saved=job.id in saved) for job in jobs], page=page, page_size=page_size, total=total, has_next=offset + len(jobs) < total)


@jobs_router.get("/sources", response_model=list[JobSourceInfo])
def list_job_sources(
    _: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[JobSourceInfo]:
    registry = configured_registry()
    sources = {source.source_key: source for source in db.scalars(select(JobSource).order_by(JobSource.name))}
    result = []
    for key in sorted(set(sources) | set(registry.keys())):
        source, adapter = sources.get(key), registry.get(key)
        result.append(JobSourceInfo(source_key=key, name=source.name if source else adapter.source_name,
                      configured=adapter is not None, enabled=adapter is not None and (source is None or source.is_enabled),
                      last_attempt_at=source.last_attempt_at if source else None, last_success_at=source.last_success_at if source else None,
                      last_error=source.last_error if source else None, last_job_count=source.last_job_count if source else None,
                      attribution_url="https://www.arbeitnow.com" if key == "arbeitnow" else None))
    return result


@jobs_router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> JobResponse:
    job = db.execute(_job_query().where(Job.id == job_id)).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return _job_response(job, is_saved=bool(db.scalar(select(SavedJob.id).where(SavedJob.user_id == authenticated.user.id, SavedJob.job_id == job.id))))


@jobs_router.get("/{job_id}/match", response_model=JobMatchResponse)
def get_job_match(
    job_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> JobMatchResponse:
    job = db.execute(_job_query().where(Job.id == job_id)).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    result = match_job(db, user_id=authenticated.user.id, job=job)
    return JobMatchResponse(job_id=job.id, score=result.score, score_method="Weighted heuristic: skills 50%, role 20%, location 10%, employment 10%, salary 10%; unavailable criteria are excluded and remaining weights are renormalized.", matching_skills=result.matching_skills, missing_skills=result.missing_skills, uncertain_skills=result.uncertain_skills, reasons=result.reasons, conflicts=result.conflicts)


@jobs_router.get("/{job_id}/skill-gaps", response_model=SkillGapResponse)
def get_job_skill_gaps(
    job_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> SkillGapResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    gaps = skill_gaps(db, user_id=authenticated.user.id, job=job)
    return SkillGapResponse(job_id=job.id, matched_skills=gaps.matched, missing_skills=gaps.missing, uncertain_skills=gaps.uncertain, normalization_rule=SKILL_NORMALIZATION_RULE)


@saved_router.get("", response_model=SavedJobPage)
def list_saved_jobs(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SavedJobPage:
    total = int(db.scalar(select(func.count(SavedJob.id)).where(SavedJob.user_id == authenticated.user.id)) or 0)
    offset, limit = _pagination(page, page_size)
    records = db.scalars(select(SavedJob).options(joinedload(SavedJob.job).joinedload(Job.company), joinedload(SavedJob.job).joinedload(Job.source), joinedload(SavedJob.job).selectinload(Job.skills)).where(SavedJob.user_id == authenticated.user.id).order_by(SavedJob.created_at.desc()).offset(offset).limit(limit)).unique().all()
    saved_items = [SavedJobResponse(job=_job_response(record.job, is_saved=True), saved_at=record.created_at) for record in records]
    return SavedJobPage(items=saved_items, page=page, page_size=page_size, total=total, has_next=offset + len(records) < total)


@saved_router.post("", response_model=SavedJobResponse, status_code=status.HTTP_201_CREATED)
def save_job(
    payload: SavedJobCreate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    _: None = Depends(require_same_site_mutation),
    db: Session = Depends(get_db_session),
) -> SavedJobResponse:
    job = db.execute(_job_query().where(Job.id == payload.job_id)).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    record = db.scalar(select(SavedJob).where(SavedJob.user_id == authenticated.user.id, SavedJob.job_id == job.id))
    if not record:
        record = SavedJob(user_id=authenticated.user.id, job_id=job.id)
        db.add(record)
        db.commit()
        db.refresh(record)
    return SavedJobResponse(job=_job_response(job, is_saved=True), saved_at=record.created_at)


@saved_router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_job(
    job_id: UUID,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    _: None = Depends(require_same_site_mutation),
    db: Session = Depends(get_db_session),
) -> Response:
    record = db.scalar(select(SavedJob).where(SavedJob.user_id == authenticated.user.id, SavedJob.job_id == job_id))
    if record:
        db.delete(record)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@companies_router.get("", response_model=CompanyPage)
def list_companies(
    _: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    keyword: str | None = Query(default=None, max_length=160),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CompanyPage:
    query = select(Company).order_by(Company.name)
    if keyword:
        query = query.where(Company.name.ilike(f"%{keyword.strip()}%"))
    count_query = select(func.count(Company.id))
    if keyword:
        count_query = count_query.where(Company.name.ilike(f"%{keyword.strip()}%"))
    total = int(db.scalar(count_query) or 0)
    offset, limit = _pagination(page, page_size)
    companies = db.scalars(query.offset(offset).limit(limit)).all()
    return CompanyPage(items=[CompanyResponse.model_validate(company) for company in companies], page=page, page_size=page_size, total=total, has_next=offset + len(companies) < total)


@companies_router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: UUID,
    _: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> CompanyResponse:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return CompanyResponse.model_validate(company)


@recommendations_router.get("", response_model=JobRecommendationPage)
def list_recommendations(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> JobRecommendationPage:
    jobs = db.scalars(_job_query().join(Company).where(effective_status_expression() == "ACTIVE", Job.verification_status != "SUSPICIOUS").order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).limit(500)).unique().all()
    ranked = sorted(((job, match_job(db, user_id=authenticated.user.id, job=job)) for job in jobs), key=lambda item: (-item[1].score, item[0].posted_at is None, item[0].title.casefold()))
    total = len(ranked)
    offset, limit = _pagination(page, page_size)
    saved = _saved_ids(db, authenticated.user.id, [job.id for job, _ in ranked[offset:offset + limit]])
    items = [JobRecommendationResponse(job=_job_response(job, is_saved=job.id in saved), match=JobMatchResponse(job_id=job.id, score=result.score, score_method="Weighted heuristic: skills 50%, role 20%, location 10%, employment 10%, salary 10%; unavailable criteria are excluded and remaining weights are renormalized.", matching_skills=result.matching_skills, missing_skills=result.missing_skills, uncertain_skills=result.uncertain_skills, reasons=result.reasons, conflicts=result.conflicts)) for job, result in ranked[offset:offset + limit]]
    return JobRecommendationPage(items=items, page=page, page_size=page_size, total=total, has_next=offset + len(items) < total)
