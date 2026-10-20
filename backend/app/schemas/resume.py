from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResumeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ResumeType = Literal["master", "job_specific"]
ResumeStatus = Literal["draft", "active", "archived"]
ResumeSource = Literal["passport", "manual", "restore", "duplicate", "ai_suggestion", "ai_approved"]


class ResumeTemplateResponse(ResumeModel):
    id: UUID
    name: str
    slug: str
    description: str
    template_key: str
    preview_image_key: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ResumeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    template_id: UUID
    type: ResumeType = "master"


class ResumeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    template_id: UUID | None = None
    status: ResumeStatus | None = None


class ResumeContentEdit(BaseModel):
    imported_text: str | None = Field(default=None, min_length=80, max_length=60000)
    headline_override: str | None = Field(default=None, max_length=160)
    summary_override: str | None = Field(default=None, max_length=5000)
    hidden_sections: list[str] | None = Field(default=None, max_length=20)
    section_order: list[str] | None = Field(default=None, max_length=20)

    @field_validator("hidden_sections", "section_order")
    @classmethod
    def valid_section_names(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        allowed = {
            "profile",
            "professional_links",
            "career_preferences",
            "education",
            "skills",
            "experience",
            "projects",
            "certifications",
            "courses",
            "achievements",
            "languages",
            "open_source_contributions",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unknown resume section(s): {', '.join(sorted(unknown))}.")
        if len(values) != len(set(values)):
            raise ValueError("Resume sections must not be repeated.")
        return values


class ResumeVersionCreate(ResumeContentEdit):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    template_id: UUID | None = None
    change_summary: str | None = Field(default=None, max_length=500)


class ResumeVersionResponse(ResumeModel):
    id: UUID
    resume_id: UUID
    version_number: int
    source: str
    content_snapshot: dict[str, Any]
    template_id: UUID
    created_at: datetime
    created_by: UUID | None
    restored_from_version_id: UUID | None
    change_summary: str | None


class ResumeResponse(ResumeModel):
    id: UUID
    user_id: UUID
    name: str
    template_id: UUID
    type: str
    status: str
    created_at: datetime
    updated_at: datetime
    template: ResumeTemplateResponse
    latest_version: ResumeVersionResponse | None
    version_count: int


class ResumeCustomizationSuggestion(BaseModel):
    headline_override: str | None = Field(default=None, max_length=160)
    summary_override: str | None = Field(default=None, max_length=5000)
    source_evidence: list[UUID] = Field(min_length=1, max_length=100)
    missing_requirements: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("missing_requirements")
    @classmethod
    def valid_missing_requirements(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class ResumeCustomizationCreate(BaseModel):
    base_version_id: UUID
    generated_content: ResumeCustomizationSuggestion
    changes: list[str] = Field(default_factory=list, max_length=100)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider_metadata")
    @classmethod
    def no_secrets_in_metadata(cls, values: dict[str, Any]) -> dict[str, Any]:
        blocked = ("password", "secret", "token", "api_key", "access_key")
        def contains_blocked_key(value: Any) -> bool:
            if isinstance(value, dict):
                return any(any(term in str(key).casefold() for term in blocked) or contains_blocked_key(item) for key, item in value.items())
            if isinstance(value, list):
                return any(contains_blocked_key(item) for item in value)
            return False

        if contains_blocked_key(values):
            raise ValueError("Provider metadata must not contain credentials or tokens.")
        return values


class ResumeCustomizationResponse(ResumeModel):
    id: UUID
    resume_id: UUID
    job_id: UUID | None
    base_version_id: UUID
    generated_content: dict[str, Any]
    changes: dict[str, Any]
    provider_metadata: dict[str, Any]
    status: str
    created_at: datetime


class JobDescriptionInput(BaseModel):
    job_description: str = Field(min_length=20, max_length=30000)


class ResumePreviewResponse(BaseModel):
    resume_id: UUID
    version_id: UUID
    template_key: str
    html: str
