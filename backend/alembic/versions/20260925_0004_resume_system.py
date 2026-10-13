"""Add deterministic Resume System tables and built-in templates.

Revision ID: 20260925_0004
Revises: 20260925_0003
Create Date: 2026-09-25 00:04:00
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20260925_0004"
down_revision: str | Sequence[str] | None = "20260925_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def upgrade() -> None:
    op.create_table(
        "resume_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("template_key", sa.String(length=120), nullable=False),
        sa.Column("preview_image_key", sa.String(length=512)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_resume_templates_slug"),
    )
    op.create_table(
        "resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False, server_default="master"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["resume_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("type IN ('master', 'job_specific')", name="ck_resumes_type"),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name="ck_resumes_status"),
    )
    op.create_index("ix_resumes_user_id_updated_at", "resumes", ["user_id", "updated_at"], unique=False)
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("content_snapshot", JSONB(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("restored_from_version_id", sa.Uuid(), nullable=True),
        sa.Column("change_summary", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["resume_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["restored_from_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_id", "version_number", name="uq_resume_versions_resume_number"),
        sa.CheckConstraint("version_number > 0", name="ck_resume_versions_positive_number"),
        sa.CheckConstraint("source IN ('passport', 'manual', 'restore', 'duplicate', 'ai_suggestion', 'ai_approved')", name="ck_resume_versions_source"),
    )
    op.create_index("ix_resume_versions_resume_id_created_at", "resume_versions", ["resume_id", "created_at"], unique=False)
    op.create_table(
        "resume_customizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("base_version_id", sa.Uuid(), nullable=False),
        sa.Column("generated_content", sa.JSON(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("provider_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["base_version_id"], ["resume_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('pending_review', 'approved', 'rejected')", name="ck_resume_customizations_status"),
    )
    op.create_index("ix_resume_customizations_resume_id_created_at", "resume_customizations", ["resume_id", "created_at"], unique=False)

    templates = [
        ("Modern", "modern", "Balanced hierarchy with a contemporary two-column emphasis.", "modern"),
        ("Professional", "professional", "Traditional business layout with clear section rhythm.", "professional"),
        ("Minimal", "minimal", "Quiet typography and generous whitespace for focused reading.", "minimal"),
        ("Student", "student", "Education-forward layout for early-career profiles.", "student"),
        ("Developer", "developer", "Technical hierarchy for projects, skills, and experience.", "developer"),
        ("Creative", "creative", "Expressive but printable hierarchy for portfolio-led careers.", "creative"),
        ("ATS-readable", "ats-readable", "Plain, structured layout designed for human readability.", "ats_readable"),
    ]
    op.bulk_insert(
        sa.table(
            "resume_templates",
            sa.column("id", sa.Uuid()),
            sa.column("name", sa.String()),
            sa.column("slug", sa.String()),
            sa.column("description", sa.Text()),
            sa.column("template_key", sa.String()),
            sa.column("is_active", sa.Boolean()),
        ),
        [
            {"id": uuid4(), "name": name, "slug": slug, "description": description, "template_key": key, "is_active": True}
            for name, slug, description, key in templates
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_resume_customizations_resume_id_created_at", table_name="resume_customizations")
    op.drop_table("resume_customizations")
    op.drop_index("ix_resume_versions_resume_id_created_at", table_name="resume_versions")
    op.drop_table("resume_versions")
    op.drop_index("ix_resumes_user_id_updated_at", table_name="resumes")
    op.drop_table("resumes")
    op.drop_table("resume_templates")
