from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ResumeTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resume_templates"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    preview_image_key: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Resume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("resume_templates.id", ondelete="RESTRICT"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="master")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")

    template: Mapped[ResumeTemplate] = relationship()
    versions: Mapped[list[ResumeVersion]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", order_by="ResumeVersion.version_number"
    )
    customizations: Mapped[list[ResumeCustomization]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("type IN ('master', 'job_specific')", name="ck_resumes_type"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_resumes_status"),
        Index("ix_resumes_user_id_updated_at", "user_id", "updated_at"),
    )


class ResumeVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resume_versions"

    resume_id: Mapped[UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    content_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("resume_templates.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    restored_from_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL")
    )
    change_summary: Mapped[str | None] = mapped_column(String(500))

    resume: Mapped[Resume] = relationship(back_populates="versions", foreign_keys=[resume_id])
    template: Mapped[ResumeTemplate] = relationship(foreign_keys=[template_id])

    __table_args__ = (
        UniqueConstraint("resume_id", "version_number", name="uq_resume_versions_resume_number"),
        CheckConstraint("version_number > 0", name="ck_resume_versions_positive_number"),
        CheckConstraint(
            "source IN ('passport', 'manual', 'restore', 'duplicate', 'ai_suggestion', 'ai_approved')",
            name="ck_resume_versions_source",
        ),
        Index("ix_resume_versions_resume_id_created_at", "resume_id", "created_at"),
    )


class ResumeCustomization(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resume_customizations"

    resume_id: Mapped[UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[UUID | None]
    base_version_id: Mapped[UUID] = mapped_column(ForeignKey("resume_versions.id", ondelete="CASCADE"), nullable=False)
    generated_content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP")

    resume: Mapped[Resume] = relationship(back_populates="customizations")
    base_version: Mapped[ResumeVersion] = relationship()

    __table_args__ = (
        CheckConstraint("status IN ('pending_review', 'approved', 'rejected')", name="ck_resume_customizations_status"),
        Index("ix_resume_customizations_resume_id_created_at", "resume_id", "created_at"),
    )
