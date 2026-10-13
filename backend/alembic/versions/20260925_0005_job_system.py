"""Add the real-job system foundation.

Revision ID: 20260925_0005
Revises: 20260925_0004
Create Date: 2026-09-25 00:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, JSONB

from alembic import op

revision: str = "20260925_0005"
down_revision: str | Sequence[str] | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def upgrade() -> None:
    op.create_table(
        "job_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="api"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("configuration", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_job_sources_source_key"),
        sa.CheckConstraint("source_type IN ('api', 'feed', 'licensed_api', 'authorized_feed')", name="ck_job_sources_type"),
    )
    op.create_index("ix_job_sources_enabled", "job_sources", ["is_enabled"], unique=False)

    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("normalized_name", sa.String(length=180), nullable=False),
        sa.Column("website", sa.String(length=2048)),
        sa.Column("logo_url", sa.String(length=2048)),
        sa.Column("description", sa.Text()),
        sa.Column("headquarters", sa.String(length=180)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_companies_normalized_name"),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("identity_key", sa.String(length=768), nullable=False),
        sa.Column("external_job_id", sa.String(length=255)),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=240)),
        sa.Column("normalized_location", sa.String(length=240)),
        sa.Column("remote_type", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("employment_type", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("experience_requirements", sa.Text()),
        sa.Column("education_requirements", sa.Text()),
        sa.Column("salary_min", sa.Numeric(12, 2)),
        sa.Column("salary_max", sa.Numeric(12, 2)),
        sa.Column("salary_currency", sa.String(length=3)),
        sa.Column("salary_period", sa.String(length=20)),
        sa.Column("application_url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048)),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="UNVERIFIED"),
        sa.Column("source_metadata", JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("identity_key", name="uq_jobs_identity_key"),
        sa.UniqueConstraint("source_id", "external_job_id", name="uq_jobs_source_external_id"),
        sa.CheckConstraint("remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')", name="ck_jobs_remote_type"),
        sa.CheckConstraint("employment_type IN ('full_time', 'part_time', 'contract', 'internship', 'temporary', 'freelance', 'volunteer', 'unknown')", name="ck_jobs_employment_type"),
        sa.CheckConstraint("salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max", name="ck_jobs_salary_range"),
        sa.CheckConstraint("salary_period IS NULL OR salary_period IN ('hour', 'day', 'week', 'month', 'year')", name="ck_jobs_salary_period"),
        sa.CheckConstraint("status IN ('ACTIVE', 'CLOSED', 'EXPIRED', 'UNVERIFIED')", name="ck_jobs_status"),
    )
    op.create_index("ix_jobs_status_last_verified", "jobs", ["status", "last_verified_at"], unique=False)
    op.create_index("ix_jobs_source_posted", "jobs", ["source_id", "posted_at"], unique=False)
    op.create_index("ix_jobs_company_status", "jobs", ["company_id", "status"], unique=False)
    op.create_index("ix_jobs_location", "jobs", ["normalized_location"], unique=False)

    op.create_table(
        "job_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "normalized_name", name="uq_job_skills_job_name"),
    )
    op.create_index("ix_job_skills_normalized_name", "job_skills", ["normalized_name"], unique=False)

    op.create_table(
        "saved_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_saved_jobs_user_job"),
    )
    op.create_index("ix_saved_jobs_user_created", "saved_jobs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_jobs_user_created", table_name="saved_jobs")
    op.drop_table("saved_jobs")
    op.drop_index("ix_job_skills_normalized_name", table_name="job_skills")
    op.drop_table("job_skills")
    op.drop_index("ix_jobs_location", table_name="jobs")
    op.drop_index("ix_jobs_company_status", table_name="jobs")
    op.drop_index("ix_jobs_source_posted", table_name="jobs")
    op.drop_index("ix_jobs_status_last_verified", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
    op.drop_index("ix_job_sources_enabled", table_name="job_sources")
    op.drop_table("job_sources")
