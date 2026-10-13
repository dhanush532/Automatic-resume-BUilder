from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_url(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if len(value) > 2048 or not value.lower().startswith(("https://", "http://")):
        raise ValueError("URL must start with http:// or https://.")
    return value


def validate_dates(start: date | None, end: date | None, current: bool) -> None:
    if start and end and end < start:
        raise ValueError("End date cannot be before start date.")
    if current and end:
        raise ValueError("Current records should not have an end date.")


class PassportModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=120)
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    profile_photo_key: str | None = Field(default=None, max_length=512)
    other_links: list[dict[str, str]] = Field(default_factory=list, max_length=20)

    @field_validator("linkedin_url", "github_url", "portfolio_url")
    @classmethod
    def valid_urls(cls, value: str | None) -> str | None:
        return validate_url(value)


class ProfileResponse(ProfileUpdate, PassportModel):
    id: UUID
    user_id: UUID
    email: str
    username: str
    phone: str | None
    created_at: datetime
    updated_at: datetime


class ProfessionalLinkInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    url: str

    @field_validator("url")
    @classmethod
    def valid_link_url(cls, value: str) -> str:
        result = validate_url(value)
        if result is None:
            raise ValueError("A link URL is required.")
        return result


class ProfessionalLinkResponse(ProfessionalLinkInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class CareerPreferencesUpdate(BaseModel):
    desired_job_titles: list[str] = Field(default_factory=list, max_length=30)
    industries: list[str] = Field(default_factory=list, max_length=30)
    preferred_locations: list[str] = Field(default_factory=list, max_length=30)
    work_arrangements: list[str] = Field(default_factory=list, max_length=3)
    employment_types: list[str] = Field(default_factory=list, max_length=6)
    expected_salary_min: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    expected_salary_max: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    willing_to_relocate: bool | None = None
    preferred_company_sizes: list[str] = Field(default_factory=list, max_length=6)
    company_preferences: str | None = Field(default=None, max_length=3000)
    exclusions: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("work_arrangements")
    @classmethod
    def valid_work_arrangements(cls, values: list[str]) -> list[str]:
        allowed = {"remote", "hybrid", "on_site"}
        if any(value not in allowed for value in values):
            raise ValueError("Work arrangement must be remote, hybrid, or on_site.")
        return values

    @field_validator("employment_types")
    @classmethod
    def valid_employment_types(cls, values: list[str]) -> list[str]:
        allowed = {"full_time", "part_time", "internship", "contract", "temporary", "freelance"}
        if any(value not in allowed for value in values):
            raise ValueError("Employment type is not supported.")
        return values

    @field_validator("salary_currency")
    @classmethod
    def normalized_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def salary_range_is_valid(self) -> "CareerPreferencesUpdate":
        if self.expected_salary_min is not None and self.expected_salary_max is not None and self.expected_salary_min > self.expected_salary_max:
            raise ValueError("Minimum salary cannot exceed maximum salary.")
        return self


class CareerPreferencesResponse(CareerPreferencesUpdate, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class EducationInput(BaseModel):
    institution: str = Field(min_length=1, max_length=180)
    degree: str = Field(min_length=1, max_length=160)
    field_of_study: str | None = Field(default=None, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    grade: str | None = Field(default=None, max_length=40)
    coursework: str | None = Field(default=None, max_length=10000)
    achievements: str | None = Field(default=None, max_length=10000)
    description: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def valid_date_range(self) -> "EducationInput":
        validate_dates(self.start_date, self.end_date, self.is_current)
        return self


class EducationResponse(EducationInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class SkillInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=80)
    proficiency: str = Field(pattern="^(beginner|intermediate|advanced|expert)$")
    experience_months: int | None = Field(default=None, ge=0, le=1200)
    last_used: date | None = None


class SkillResponse(SkillInput, PassportModel):
    id: UUID
    skill_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class ExperienceInput(BaseModel):
    company: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=160)
    employment_type: str = Field(pattern="^(full_time|part_time|internship|contract|temporary|freelance)$")
    location: str | None = Field(default=None, max_length=120)
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=15000)
    achievements: str | None = Field(default=None, max_length=15000)
    technology_notes: str | None = Field(default=None, max_length=5000)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def valid_date_range(self) -> "ExperienceInput":
        validate_dates(self.start_date, self.end_date, self.is_current)
        return self


class ExperienceResponse(ExperienceInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=15000)
    problem_solved: str | None = Field(default=None, max_length=10000)
    role: str | None = Field(default=None, max_length=160)
    technology_notes: str | None = Field(default=None, max_length=5000)
    features: str | None = Field(default=None, max_length=10000)
    github_url: str | None = None
    live_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    team_or_individual: str = Field(default="individual", pattern="^(team|individual)$")
    results: str | None = Field(default=None, max_length=10000)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("github_url", "live_url")
    @classmethod
    def valid_urls(cls, value: str | None) -> str | None:
        return validate_url(value)

    @model_validator(mode="after")
    def valid_date_range(self) -> "ProjectInput":
        validate_dates(self.start_date, self.end_date, self.is_current)
        return self


class ProjectResponse(ProjectInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class CertificationInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    issuer: str = Field(min_length=1, max_length=180)
    issue_date: date | None = None
    expiry_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=160)
    credential_url: str | None = None
    description: str | None = Field(default=None, max_length=10000)

    @field_validator("credential_url")
    @classmethod
    def valid_credential_url(cls, value: str | None) -> str | None:
        return validate_url(value)

    @model_validator(mode="after")
    def valid_date_range(self) -> "CertificationInput":
        validate_dates(self.issue_date, self.expiry_date, False)
        return self


class CertificationResponse(CertificationInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class CourseInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    provider: str = Field(min_length=1, max_length=180)
    completion_date: date | None = None
    credential_url: str | None = None
    description: str | None = Field(default=None, max_length=10000)

    @field_validator("credential_url")
    @classmethod
    def valid_credential_url(cls, value: str | None) -> str | None:
        return validate_url(value)


class CourseResponse(CourseInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class AchievementInput(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    organization: str | None = Field(default=None, max_length=180)
    achieved_on: date | None = None
    description: str | None = Field(default=None, max_length=10000)
    evidence_url: str | None = None

    @field_validator("evidence_url")
    @classmethod
    def valid_evidence_url(cls, value: str | None) -> str | None:
        return validate_url(value)


class AchievementResponse(AchievementInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class LanguageInput(BaseModel):
    language: str = Field(min_length=1, max_length=80)
    proficiency: str = Field(pattern="^(basic|conversational|professional|fluent|native)$")


class LanguageResponse(LanguageInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class OpenSourceInput(BaseModel):
    repository: str = Field(min_length=1, max_length=255)
    contribution: str = Field(min_length=1, max_length=180)
    technology_notes: str | None = Field(default=None, max_length=5000)
    url: str
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = Field(default=None, max_length=10000)

    @field_validator("url")
    @classmethod
    def valid_contribution_url(cls, value: str) -> str:
        result = validate_url(value)
        if result is None:
            raise ValueError("Contribution URL is required.")
        return result

    @model_validator(mode="after")
    def valid_date_range(self) -> "OpenSourceInput":
        validate_dates(self.start_date, self.end_date, False)
        return self


class OpenSourceResponse(OpenSourceInput, PassportModel):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class PassportResponse(BaseModel):
    profile: ProfileResponse | None
    career_preferences: CareerPreferencesResponse | None
    professional_links: list[ProfessionalLinkResponse]
    education: list[EducationResponse]
    skills: list[SkillResponse]
    experience: list[ExperienceResponse]
    projects: list[ProjectResponse]
    certifications: list[CertificationResponse]
    courses: list[CourseResponse]
    achievements: list[AchievementResponse]
    languages: list[LanguageResponse]
    open_source_contributions: list[OpenSourceResponse]
    completeness: int
