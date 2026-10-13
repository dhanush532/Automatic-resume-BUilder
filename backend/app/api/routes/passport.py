from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedRequest, require_authenticated_request
from app.core.database import get_db_session
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
    Skill,
    UserSkill,
)
from app.models.user import Profile
from app.schemas.passport import (
    AchievementInput,
    AchievementResponse,
    CareerPreferencesResponse,
    CareerPreferencesUpdate,
    CertificationInput,
    CertificationResponse,
    CourseInput,
    CourseResponse,
    EducationInput,
    EducationResponse,
    ExperienceInput,
    ExperienceResponse,
    LanguageInput,
    LanguageResponse,
    OpenSourceInput,
    OpenSourceResponse,
    PassportResponse,
    ProfessionalLinkInput,
    ProfessionalLinkResponse,
    ProfileResponse,
    ProfileUpdate,
    ProjectInput,
    ProjectResponse,
    SkillInput,
    SkillResponse,
)
from app.services.resume_snapshots import ensure_default_resume

router = APIRouter(prefix="/passport")


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def profile_response(profile: Profile, authenticated: AuthenticatedRequest) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name or authenticated.user.full_name,
        headline=profile.headline or profile.professional_headline,
        bio=profile.bio or profile.professional_summary,
        location=profile.location,
        linkedin_url=profile.linkedin_url,
        github_url=profile.github_url,
        portfolio_url=profile.portfolio_url,
        profile_photo_key=profile.profile_photo_key or profile.photo_storage_key,
        other_links=profile.other_links or [],
        email=authenticated.user.email,
        username=authenticated.user.username,
        phone=authenticated.user.phone_e164,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _skill_response(user_skill: UserSkill) -> SkillResponse:
    return SkillResponse(
        id=user_skill.id,
        skill_id=user_skill.skill_id,
        user_id=user_skill.user_id,
        name=user_skill.skill.name,
        category=user_skill.skill.category,
        proficiency=user_skill.proficiency,
        experience_months=user_skill.experience_months,
        last_used=user_skill.last_used,
        created_at=user_skill.created_at,
        updated_at=user_skill.updated_at,
    )


def _skill_ids(db: Session, *, user_id: UUID, requested: list[UUID]) -> list[UUID]:
    if not requested:
        return []
    owned = set(
        db.scalars(select(UserSkill.skill_id).where(UserSkill.user_id == user_id, UserSkill.skill_id.in_(requested)))
    )
    if owned != set(requested):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Every related skill must belong to your Passport.")
    return list(dict.fromkeys(requested))


def _replace_experience_skills(db: Session, *, experience_id: UUID, user_id: UUID, skill_ids: list[UUID]) -> None:
    db.query(ExperienceSkill).filter(ExperienceSkill.experience_id == experience_id).delete(synchronize_session=False)
    for skill_id in _skill_ids(db, user_id=user_id, requested=skill_ids):
        db.add(ExperienceSkill(experience_id=experience_id, skill_id=skill_id))


def _replace_project_skills(db: Session, *, project_id: UUID, user_id: UUID, skill_ids: list[UUID]) -> None:
    db.query(ProjectSkill).filter(ProjectSkill.project_id == project_id).delete(synchronize_session=False)
    for skill_id in _skill_ids(db, user_id=user_id, requested=skill_ids):
        db.add(ProjectSkill(project_id=project_id, skill_id=skill_id))


def _related_skill_ids(db: Session, *, model: type[ExperienceSkill] | type[ProjectSkill], parent_column: Any, parent_id: UUID) -> list[UUID]:
    return list(db.scalars(select(model.skill_id).where(parent_column == parent_id)))


def _serialize_record(record: Any, schema: type[Any], *, skill_ids: list[UUID] | None = None) -> Any:
    data = schema.model_validate(record).model_dump()
    if skill_ids is not None:
        data["skill_ids"] = skill_ids
    return schema.model_validate(data)


def _completeness(passport: dict[str, Any]) -> int:
    checks = [
        bool(passport["profile"] and passport["profile"].headline),
        bool(passport["profile"] and passport["profile"].bio),
        bool(passport["career_preferences"]),
        bool(passport["education"]),
        bool(passport["skills"]),
        bool(passport["experience"]),
        bool(passport["projects"]),
        bool(passport["certifications"]),
        bool(passport["courses"]),
        bool(passport["achievements"]),
        bool(passport["languages"]),
        bool(passport["open_source_contributions"]),
    ]
    return round(sum(checks) / len(checks) * 100)


@router.get("", response_model=PassportResponse)
def get_passport(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> PassportResponse:
    user_id = authenticated.user.id
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    preferences = db.scalar(select(CareerPreference).where(CareerPreference.user_id == user_id))
    professional_links = list(db.scalars(select(ProfessionalLink).where(ProfessionalLink.user_id == user_id).order_by(ProfessionalLink.label)))
    education = list(db.scalars(select(Education).where(Education.user_id == user_id).order_by(Education.start_date.desc().nullslast())))
    skills = list(db.scalars(select(UserSkill).where(UserSkill.user_id == user_id).order_by(UserSkill.created_at.desc())))
    experience = list(db.scalars(select(Experience).where(Experience.user_id == user_id).order_by(Experience.start_date.desc())))
    projects = list(db.scalars(select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())))
    certifications = list(db.scalars(select(Certification).where(Certification.user_id == user_id).order_by(Certification.issue_date.desc().nullslast())))
    courses = list(db.scalars(select(Course).where(Course.user_id == user_id).order_by(Course.completion_date.desc().nullslast())))
    achievements = list(db.scalars(select(Achievement).where(Achievement.user_id == user_id).order_by(Achievement.achieved_on.desc().nullslast())))
    languages = list(db.scalars(select(Language).where(Language.user_id == user_id).order_by(Language.language)))
    open_source = list(db.scalars(select(OpenSourceContribution).where(OpenSourceContribution.user_id == user_id).order_by(OpenSourceContribution.start_date.desc().nullslast())))
    payload: dict[str, Any] = {
        "profile": profile_response(profile, authenticated) if profile else None,
        "career_preferences": CareerPreferencesResponse.model_validate(preferences) if preferences else None,
        "professional_links": [ProfessionalLinkResponse.model_validate(item) for item in professional_links],
        "education": [EducationResponse.model_validate(item) for item in education],
        "skills": [_skill_response(item) for item in skills],
        "experience": [_serialize_record(item, ExperienceResponse, skill_ids=_related_skill_ids(db, model=ExperienceSkill, parent_column=ExperienceSkill.experience_id, parent_id=item.id)) for item in experience],
        "projects": [_serialize_record(item, ProjectResponse, skill_ids=_related_skill_ids(db, model=ProjectSkill, parent_column=ProjectSkill.project_id, parent_id=item.id)) for item in projects],
        "certifications": [CertificationResponse.model_validate(item) for item in certifications],
        "courses": [CourseResponse.model_validate(item) for item in courses],
        "achievements": [AchievementResponse.model_validate(item) for item in achievements],
        "languages": [LanguageResponse.model_validate(item) for item in languages],
        "open_source_contributions": [OpenSourceResponse.model_validate(item) for item in open_source],
    }
    payload["completeness"] = _completeness(payload)
    return PassportResponse.model_validate(payload)


@router.get("/profile", response_model=ProfileResponse | None)
def get_profile(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ProfileResponse | None:
    profile = db.scalar(select(Profile).where(Profile.user_id == authenticated.user.id))
    return profile_response(profile, authenticated) if profile else None


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> ProfileResponse:
    profile = db.scalar(select(Profile).where(Profile.user_id == authenticated.user.id))
    data = payload.model_dump()
    if not profile:
        profile = Profile(user_id=authenticated.user.id)
        db.add(profile)
    authenticated.user.full_name = payload.full_name
    profile.full_name = payload.full_name
    profile.headline = payload.headline
    profile.bio = payload.bio
    profile.profile_photo_key = payload.profile_photo_key
    profile.other_links = payload.other_links
    profile.professional_headline = payload.headline
    profile.professional_summary = payload.bio
    for field in ("location", "linkedin_url", "github_url", "portfolio_url"):
        setattr(profile, field, data[field])
    ensure_default_resume(db, authenticated.user.id)
    db.commit()
    db.refresh(profile)
    return profile_response(profile, authenticated)


@router.put("/preferences", response_model=CareerPreferencesResponse)
def update_preferences(
    payload: CareerPreferencesUpdate,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> CareerPreferencesResponse:
    preference = db.scalar(select(CareerPreference).where(CareerPreference.user_id == authenticated.user.id))
    if not preference:
        preference = CareerPreference(user_id=authenticated.user.id)
        db.add(preference)
    for key, value in payload.model_dump().items():
        setattr(preference, key, value)
    ensure_default_resume(db, authenticated.user.id)
    db.commit()
    db.refresh(preference)
    return CareerPreferencesResponse.model_validate(preference)


def _collection_routes(
    *,
    path: str,
    model: type[Any],
    input_schema: type[Any],
    response_schema: type[Any],
    unique_message: str | None = None,
    skill_model: type[Any] | None = None,
    skill_parent_field: Any | None = None,
) -> None:
    @router.get(f"/{path}", response_model=list[response_schema])
    def list_records(authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> list[Any]:
        records = list(db.scalars(select(model).where(model.user_id == authenticated.user.id).order_by(model.created_at.desc())))
        if skill_model and skill_parent_field:
            return [_serialize_record(record, response_schema, skill_ids=_related_skill_ids(db, model=skill_model, parent_column=skill_parent_field, parent_id=record.id)) for record in records]
        return [response_schema.model_validate(record) for record in records]

    @router.post(f"/{path}", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    def create_record(payload: input_schema, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> Any:
        data = payload.model_dump(exclude={"skill_ids"})
        record = model(user_id=authenticated.user.id, **data)
        db.add(record)
        try:
            db.flush()
            if skill_model and skill_parent_field:
                replace_fn = _replace_experience_skills if model is Experience else _replace_project_skills
                replace_fn(db, experience_id=record.id, user_id=authenticated.user.id, skill_ids=payload.skill_ids) if model is Experience else replace_fn(db, project_id=record.id, user_id=authenticated.user.id, skill_ids=payload.skill_ids)
            ensure_default_resume(db, authenticated.user.id)
            db.commit()
            db.refresh(record)
        except IntegrityError as error:
            db.rollback()
            raise conflict(unique_message or "That record conflicts with an existing Passport entry.") from error
        if skill_model and skill_parent_field:
            return _serialize_record(record, response_schema, skill_ids=_related_skill_ids(db, model=skill_model, parent_column=skill_parent_field, parent_id=record.id))
        return response_schema.model_validate(record)

    @router.patch(f"/{path}/{{record_id}}", response_model=response_schema)
    def update_record(record_id: UUID, payload: input_schema, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> Any:
        record = db.scalar(select(model).where(model.id == record_id, model.user_id == authenticated.user.id))
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport record not found.")
        for key, value in payload.model_dump(exclude={"skill_ids"}).items():
            setattr(record, key, value)
        try:
            if skill_model and skill_parent_field:
                replace_fn = _replace_experience_skills if model is Experience else _replace_project_skills
                replace_fn(db, experience_id=record.id, user_id=authenticated.user.id, skill_ids=payload.skill_ids) if model is Experience else replace_fn(db, project_id=record.id, user_id=authenticated.user.id, skill_ids=payload.skill_ids)
            db.commit()
            db.refresh(record)
        except IntegrityError as error:
            db.rollback()
            raise conflict(unique_message or "That record conflicts with an existing Passport entry.") from error
        if skill_model and skill_parent_field:
            return _serialize_record(record, response_schema, skill_ids=_related_skill_ids(db, model=skill_model, parent_column=skill_parent_field, parent_id=record.id))
        return response_schema.model_validate(record)

    @router.delete(f"/{path}/{{record_id}}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_record(record_id: UUID, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> None:
        record = db.scalar(select(model).where(model.id == record_id, model.user_id == authenticated.user.id))
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport record not found.")
        db.delete(record)
        db.commit()


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> list[SkillResponse]:
    return [_skill_response(item) for item in db.scalars(select(UserSkill).where(UserSkill.user_id == authenticated.user.id).order_by(UserSkill.created_at.desc()))]


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillInput, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> SkillResponse:
    normalized_name = payload.name.strip().casefold()
    skill = db.scalar(select(Skill).where(Skill.name == normalized_name))
    if not skill:
        skill = Skill(name=normalized_name, category=payload.category.strip())
        db.add(skill)
        db.flush()
    existing = db.scalar(select(UserSkill).where(UserSkill.user_id == authenticated.user.id, UserSkill.skill_id == skill.id))
    if existing:
        raise conflict("You already have this skill in your Passport.")
    user_skill = UserSkill(user_id=authenticated.user.id, skill_id=skill.id, proficiency=payload.proficiency, experience_months=payload.experience_months, last_used=payload.last_used)
    db.add(user_skill)
    try:
        ensure_default_resume(db, authenticated.user.id)
        db.commit()
        db.refresh(user_skill)
    except IntegrityError as error:
        db.rollback()
        raise conflict("That skill conflicts with an existing Passport entry.") from error
    return _skill_response(user_skill)


@router.patch("/skills/{record_id}", response_model=SkillResponse)
def update_skill(record_id: UUID, payload: SkillInput, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> SkillResponse:
    user_skill = db.scalar(select(UserSkill).where(UserSkill.id == record_id, UserSkill.user_id == authenticated.user.id))
    if not user_skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport record not found.")
    normalized_name = payload.name.strip().casefold()
    skill = db.scalar(select(Skill).where(Skill.name == normalized_name))
    if not skill:
        skill = Skill(name=normalized_name, category=payload.category.strip())
        db.add(skill)
        db.flush()
    duplicate = db.scalar(select(UserSkill).where(UserSkill.user_id == authenticated.user.id, UserSkill.skill_id == skill.id, UserSkill.id != record_id))
    if duplicate:
        raise conflict("You already have this skill in your Passport.")
    user_skill.skill_id = skill.id
    user_skill.proficiency = payload.proficiency
    user_skill.experience_months = payload.experience_months
    user_skill.last_used = payload.last_used
    ensure_default_resume(db, authenticated.user.id)
    db.commit()
    db.refresh(user_skill)
    return _skill_response(user_skill)


@router.delete("/skills/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(record_id: UUID, authenticated: AuthenticatedRequest = Depends(require_authenticated_request), db: Session = Depends(get_db_session)) -> None:
    user_skill = db.scalar(select(UserSkill).where(UserSkill.id == record_id, UserSkill.user_id == authenticated.user.id))
    if not user_skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport record not found.")
    db.delete(user_skill)
    db.commit()


_collection_routes(path="education", model=Education, input_schema=EducationInput, response_schema=EducationResponse)
_collection_routes(path="links", model=ProfessionalLink, input_schema=ProfessionalLinkInput, response_schema=ProfessionalLinkResponse, unique_message="You already have a link with that label.")
_collection_routes(path="experience", model=Experience, input_schema=ExperienceInput, response_schema=ExperienceResponse, skill_model=ExperienceSkill, skill_parent_field=ExperienceSkill.experience_id)
_collection_routes(path="projects", model=Project, input_schema=ProjectInput, response_schema=ProjectResponse, skill_model=ProjectSkill, skill_parent_field=ProjectSkill.project_id)
_collection_routes(path="certifications", model=Certification, input_schema=CertificationInput, response_schema=CertificationResponse)
_collection_routes(path="courses", model=Course, input_schema=CourseInput, response_schema=CourseResponse)
_collection_routes(path="achievements", model=Achievement, input_schema=AchievementInput, response_schema=AchievementResponse)
_collection_routes(path="languages", model=Language, input_schema=LanguageInput, response_schema=LanguageResponse, unique_message="You already have this language in your Passport.")
_collection_routes(path="open-source", model=OpenSourceContribution, input_schema=OpenSourceInput, response_schema=OpenSourceResponse, unique_message="You already have this contribution in your Passport.")
