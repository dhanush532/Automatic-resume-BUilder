from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.passport import (
    Achievement,
    CareerPreference,
    Certification,
    Course,
    Education,
    Experience,
    ExperienceSkill,
    Language,
    OpenSourceContribution,
    ProfessionalLink,
    Project,
    ProjectSkill,
    UserSkill,
)
from app.models.resume import Resume, ResumeTemplate, ResumeVersion
from app.models.user import Profile, User
from app.schemas.resume import ResumeContentEdit

SECTION_ORDER = [
    "profile",
    "professional_links",
    "career_preferences",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "courses",
    "achievements",
    "languages",
    "open_source_contributions",
]


def _value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    return value


def _record(record: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {"source_id": str(record.id), **{field: _value(getattr(record, field)) for field in fields}}


def _skill_ids(db: Session, model: type[Any], column: Any, parent_id: UUID) -> list[str]:
    return [str(skill_id) for skill_id in db.scalars(select(model.skill_id).where(column == parent_id))]


def build_passport_snapshot(db: Session, user_id: UUID) -> dict[str, Any]:
    user = db.get(User, user_id)
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    preferences = db.scalar(select(CareerPreference).where(CareerPreference.user_id == user_id))
    education = list(db.scalars(select(Education).where(Education.user_id == user_id).order_by(Education.start_date)))
    skills = list(db.scalars(select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.created_at)))
    experience = list(db.scalars(select(Experience).where(Experience.user_id == user_id).order_by(Experience.start_date)))
    projects = list(db.scalars(select(Project).where(Project.user_id == user_id).order_by(Project.created_at)))
    certifications = list(db.scalars(select(Certification).where(Certification.user_id == user_id).order_by(Certification.issue_date)))
    courses = list(db.scalars(select(Course).where(Course.user_id == user_id).order_by(Course.completion_date)))
    achievements = list(db.scalars(select(Achievement).where(Achievement.user_id == user_id).order_by(Achievement.achieved_on)))
    languages = list(db.scalars(select(Language).where(Language.user_id == user_id).order_by(Language.language)))
    links = list(db.scalars(select(ProfessionalLink).where(ProfessionalLink.user_id == user_id).order_by(ProfessionalLink.label)))
    open_source = list(db.scalars(select(OpenSourceContribution).where(OpenSourceContribution.user_id == user_id).order_by(OpenSourceContribution.start_date)))

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "source": "career_passport",
        "profile": {
            "source_id": str(profile.id) if profile else None,
            "full_name": profile.full_name if profile and profile.full_name else user.full_name if user else "",
            "headline": (profile.headline or profile.professional_headline) if profile else None,
            "bio": (profile.bio or profile.professional_summary) if profile else None,
            "location": profile.location if profile else None,
            "linkedin_url": profile.linkedin_url if profile else None,
            "github_url": profile.github_url if profile else None,
            "portfolio_url": profile.portfolio_url if profile else None,
            "email": user.email if user else None,
            "username": user.username if user else None,
        },
        "professional_links": [_record(link, ("label", "url")) for link in links],
        "career_preferences": _record(preferences, ("desired_job_titles", "industries", "preferred_locations", "work_arrangements", "employment_types", "expected_salary_min", "expected_salary_max", "salary_currency", "willing_to_relocate", "preferred_company_sizes", "company_preferences", "exclusions")) if preferences else None,
        "education": [_record(item, ("institution", "degree", "field_of_study", "start_date", "end_date", "is_current", "grade", "coursework", "achievements", "description")) for item in education],
        "skills": [
            {"source_id": str(item.id), "skill_id": str(item.skill_id), "name": item.skill.name, "category": item.skill.category, "proficiency": item.proficiency, "experience_months": item.experience_months, "last_used": _value(item.last_used)}
            for item in skills
        ],
        "experience": [
            {**_record(item, ("company", "title", "employment_type", "location", "start_date", "end_date", "is_current", "description", "achievements", "technology_notes")), "skill_ids": _skill_ids(db, ExperienceSkill, ExperienceSkill.experience_id, item.id)}
            for item in experience
        ],
        "projects": [
            {**_record(item, ("name", "description", "problem_solved", "role", "technology_notes", "features", "github_url", "live_url", "start_date", "end_date", "is_current", "team_or_individual", "results")), "skill_ids": _skill_ids(db, ProjectSkill, ProjectSkill.project_id, item.id)}
            for item in projects
        ],
        "certifications": [_record(item, ("name", "issuer", "issue_date", "expiry_date", "credential_id", "credential_url", "description")) for item in certifications],
        "courses": [_record(item, ("name", "provider", "completion_date", "credential_url", "description")) for item in courses],
        "achievements": [_record(item, ("title", "organization", "achieved_on", "description", "evidence_url")) for item in achievements],
        "languages": [_record(item, ("language", "proficiency")) for item in languages],
        "open_source_contributions": [_record(item, ("repository", "contribution", "technology_notes", "url", "start_date", "end_date", "description")) for item in open_source],
        "resume_meta": {"hidden_sections": [], "section_order": SECTION_ORDER},
    }
    return snapshot


def ensure_default_resume(db: Session, user_id: UUID) -> Resume | None:
    """Create the user's first master resume from the current Passport snapshot."""

    existing = db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.type == "master")
        .order_by(Resume.created_at.asc())
        .limit(1)
    )
    if existing:
        return existing

    template = db.scalar(
        select(ResumeTemplate)
        .where(ResumeTemplate.is_active.is_(True))
        .order_by(ResumeTemplate.slug.asc())
        .limit(1)
    )
    if not template:
        return None

    resume = Resume(
        user_id=user_id,
        name="My resume",
        template_id=template.id,
        type="master",
        status="draft",
    )
    db.add(resume)
    db.flush()
    db.add(
        ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            source="passport",
            content_snapshot=build_passport_snapshot(db, user_id),
            template_id=template.id,
            created_by=user_id,
            change_summary="Created automatically from Career Passport",
        )
    )
    return resume


def passport_source_ids(snapshot: dict[str, Any]) -> set[str]:
    source_ids: set[str] = set()
    for value in snapshot.values():
        if isinstance(value, dict) and value.get("source_id"):
            source_ids.add(str(value["source_id"]))
        elif isinstance(value, list):
            source_ids.update(str(item["source_id"]) for item in value if isinstance(item, dict) and item.get("source_id"))
    return source_ids


def apply_content_edit(snapshot: dict[str, Any], edit: ResumeContentEdit) -> dict[str, Any]:
    result = deepcopy(snapshot)
    meta = result.setdefault("resume_meta", {})
    if edit.design is not None:
        meta["design"] = edit.design.model_dump(mode="json")
    if edit.headline_override is not None:
        result["profile"]["headline"] = edit.headline_override
    if edit.summary_override is not None:
        result["profile"]["bio"] = edit.summary_override
    if edit.imported_text is not None:
        if result.get("source") != "document_import":
            raise ValueError("Text editing is only supported for imported resumes.")
        result["imported_text"] = edit.imported_text
    if edit.hidden_sections is not None:
        meta["hidden_sections"] = edit.hidden_sections
    if edit.section_order is not None:
        meta["section_order"] = edit.section_order
    return result
