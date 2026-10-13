from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_sources"

    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(240))
    last_job_count: Mapped[int | None] = mapped_column()
    sync_lease: Mapped[UUID | None] = mapped_column()
    sync_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    is_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint("source_type IN ('api', 'feed', 'licensed_api', 'authorized_feed')", name="ck_job_sources_type"),
        Index("ix_job_sources_enabled", "is_enabled"),
    )


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(180), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(2048))
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    headquarters: Mapped[str | None] = mapped_column(String(180))

    __table_args__ = (Index("ix_companies_name", "name"),)


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("job_sources.id", ondelete="RESTRICT"), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(768), nullable=False, unique=True)
    external_job_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(240))
    normalized_location: Mapped[str | None] = mapped_column(String(240))
    remote_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    employment_type: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    experience_requirements: Mapped[str | None] = mapped_column(Text)
    education_requirements: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[str | None] = mapped_column(String(20))
    application_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNVERIFIED")
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED")
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    company: Mapped[Company] = relationship()
    source: Mapped[JobSource] = relationship()
    skills: Mapped[list[JobSkill]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("source_id", "external_job_id", name="uq_jobs_source_external_id"),
        CheckConstraint("remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')", name="ck_jobs_remote_type"),
        CheckConstraint(
            "employment_type IN ('full_time', 'part_time', 'contract', 'internship', 'temporary', 'freelance', 'volunteer', 'unknown')",
            name="ck_jobs_employment_type",
        ),
        CheckConstraint("salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max", name="ck_jobs_salary_range"),
        CheckConstraint("salary_period IS NULL OR salary_period IN ('hour', 'day', 'week', 'month', 'year')", name="ck_jobs_salary_period"),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED', 'EXPIRED', 'UNVERIFIED')", name="ck_jobs_status"),
        CheckConstraint("verification_status IN ('VERIFIED', 'LIKELY_LEGITIMATE', 'UNVERIFIED', 'SUSPICIOUS', 'EXPIRED', 'CLOSED')", name="verification_status"),
        Index("ix_jobs_status_last_seen", "status", "last_seen_at"),
        Index("ix_jobs_status_last_verified", "status", "last_verified_at"),
        Index("ix_jobs_source_posted", "source_id", "posted_at"),
        Index("ix_jobs_company_status", "company_id", "status"),
        Index("ix_jobs_location", "normalized_location"),
    )


class JobSkill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_skills"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    job: Mapped[Job] = relationship(back_populates="skills")

    __table_args__ = (
        UniqueConstraint("job_id", "normalized_name", name="uq_job_skills_job_name"),
        Index("ix_job_skills_normalized_name", "normalized_name"),
    )


class JobVerificationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_verification_events"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    __table_args__ = (
        Index("ix_job_verification_events_job_checked", "job_id", "checked_at"),
        CheckConstraint("verification_status IN ('VERIFIED', 'LIKELY_LEGITIMATE', 'UNVERIFIED', 'SUSPICIOUS', 'EXPIRED', 'CLOSED')", name="verification_status"),
    )


class SavedJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "saved_jobs"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    job: Mapped[Job] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_saved_jobs_user_job"),
        Index("ix_saved_jobs_user_created", "user_id", "created_at"),
    )
