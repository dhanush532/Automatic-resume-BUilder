from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


JobStatus = Literal["ACTIVE", "CLOSED", "EXPIRED", "UNVERIFIED"]
RemoteType = Literal["remote", "hybrid", "onsite", "unknown"]
EmploymentType = Literal["full_time", "part_time", "contract", "internship", "temporary", "freelance", "volunteer", "unknown"]


class JobSourceResponse(JobModel):
    id: UUID
    source_key: str
    name: str
    source_type: str


class CompanyResponse(JobModel):
    id: UUID
    name: str
    normalized_name: str
    website: str | None
    logo_url: str | None
    description: str | None
    headquarters: str | None


class JobSkillResponse(JobModel):
    id: UUID
    name: str
    is_required: bool


class JobResponse(JobModel):
    id: UUID
    company: CompanyResponse
    source: JobSourceResponse
    external_job_id: str | None
    title: str
    description: str
    location: str | None
    normalized_location: str | None
    remote_type: RemoteType
    employment_type: EmploymentType
    experience_requirements: str | None
    education_requirements: str | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    salary_currency: str | None
    salary_period: str | None
    application_url: str
    canonical_url: str | None
    source_url: str
    posted_at: datetime | None
    deadline_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_verified_at: datetime | None
    status: JobStatus
    verification_status: Literal["VERIFIED", "LIKELY_LEGITIMATE", "UNVERIFIED", "SUSPICIOUS", "EXPIRED", "CLOSED"]
    application_method: Literal["MANUAL_APPLICATION"] = "MANUAL_APPLICATION"
    application_link_allowed: bool
    verification_reason: str | None
    skills: list[JobSkillResponse]
    is_saved: bool = False


class JobPage(BaseModel):
    items: list[JobResponse]
    page: int
    page_size: int
    total: int
    has_next: bool


class SavedJobCreate(BaseModel):
    job_id: UUID


class SavedJobResponse(BaseModel):
    job: JobResponse
    saved_at: datetime


class SavedJobPage(BaseModel):
    items: list[SavedJobResponse]
    page: int
    page_size: int
    total: int
    has_next: bool


class JobMatchResponse(BaseModel):
    job_id: UUID
    score: int = Field(ge=0, le=100)
    score_method: str
    matching_skills: list[str]
    missing_skills: list[str]
    uncertain_skills: list[str]
    reasons: list[str]
    conflicts: list[str]


class SkillGapResponse(BaseModel):
    job_id: UUID
    matched_skills: list[str]
    missing_skills: list[str]
    uncertain_skills: list[str]
    normalization_rule: str


class JobRecommendationResponse(BaseModel):
    job: JobResponse
    match: JobMatchResponse


class JobRecommendationPage(BaseModel):
    items: list[JobRecommendationResponse]
    page: int
    page_size: int
    total: int
    has_next: bool


class CompanyPage(BaseModel):
    items: list[CompanyResponse]
    page: int
    page_size: int
    total: int
    has_next: bool


class JobFilters(BaseModel):
    keyword: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote_type: RemoteType | None = None
    employment_type: EmploymentType | None = None
    experience: str | None = None
    education: str | None = None
    skill: str | None = None
    min_salary: Decimal | None = Field(default=None, ge=0)
    max_salary: Decimal | None = Field(default=None, ge=0)
    status: JobStatus | None = None
    include_unverified: bool = False


class JobSourceSyncSummary(BaseModel):
    source_key: str
    ingested: int
    live_source_configured: bool
    message: str


class JobSourceInfo(BaseModel):
    source_key: str
    name: str
    configured: bool
    enabled: bool = False
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_job_count: int | None = None
    attribution_url: str | None = None
