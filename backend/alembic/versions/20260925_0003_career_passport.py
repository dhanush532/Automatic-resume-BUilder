"""Add normalized Career Passport entities.

Revision ID: 20260925_0003
Revises: 20260925_0002
Create Date: 2026-09-25 00:02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0003"
down_revision: str | Sequence[str] | None = "20260925_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _user_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE")


def upgrade() -> None:
    op.add_column("profiles", sa.Column("full_name", sa.String(length=120), nullable=True))
    op.add_column("profiles", sa.Column("headline", sa.String(length=160), nullable=True))
    op.add_column("profiles", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("profile_photo_key", sa.String(length=512), nullable=True))
    op.add_column("profiles", sa.Column("other_links", sa.JSON(), nullable=True))

    op.create_table(
        "career_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("desired_job_titles", sa.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("industries", sa.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("preferred_locations", sa.ARRAY(sa.String(length=120)), nullable=False, server_default="{}"),
        sa.Column("work_arrangements", sa.ARRAY(sa.String(length=20)), nullable=False, server_default="{}"),
        sa.Column("employment_types", sa.ARRAY(sa.String(length=20)), nullable=False, server_default="{}"),
        sa.Column("expected_salary_min", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_salary_max", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("willing_to_relocate", sa.Boolean(), nullable=True),
        sa.Column("preferred_company_sizes", sa.ARRAY(sa.String(length=30)), nullable=False, server_default="{}"),
        sa.Column("company_preferences", sa.Text(), nullable=True),
        sa.Column("exclusions", sa.ARRAY(sa.String(length=160)), nullable=False, server_default="{}"),
        *_timestamps(),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_career_preferences_user_id"),
        sa.CheckConstraint(
            "expected_salary_min IS NULL OR expected_salary_max IS NULL OR expected_salary_min <= expected_salary_max",
            name="ck_career_preferences_salary_range",
        ),
    )

    op.create_table(
        "professional_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        *_timestamps(),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "label", name="uq_professional_links_user_label"),
    )

    op.create_table(
        "education",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("institution", sa.String(length=180), nullable=False),
        sa.Column("degree", sa.String(length=160), nullable=False),
        sa.Column("field_of_study", sa.String(length=160), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grade", sa.String(length=40), nullable=True),
        sa.Column("coursework", sa.Text(), nullable=True),
        sa.Column("achievements", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_education_dates"),
    )
    op.create_index("ix_education_user_id", "education", ["user_id"], unique=False)

    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_skills_name"),
    )
    op.create_table(
        "user_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("proficiency", sa.String(length=20), nullable=False),
        sa.Column("experience_months", sa.Integer(), nullable=True),
        sa.Column("last_used", sa.Date(), nullable=True),
        *_timestamps(),
        _user_fk(),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "skill_id", name="uq_user_skills_user_skill"),
        sa.CheckConstraint("experience_months IS NULL OR experience_months >= 0", name="ck_user_skills_experience"),
    )
    op.create_index("ix_user_skills_user_id", "user_skills", ["user_id"], unique=False)

    op.create_table(
        "experiences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("employment_type", sa.String(length=30), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("achievements", sa.Text(), nullable=True),
        sa.Column("technology_notes", sa.Text(), nullable=True),
        *_timestamps(),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_experiences_dates"),
    )
    op.create_index("ix_experiences_user_id", "experiences", ["user_id"], unique=False)
    op.create_table(
        "experience_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experience_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["experience_id"], ["experiences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experience_id", "skill_id", name="uq_experience_skills_experience_skill"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("problem_solved", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=160), nullable=True),
        sa.Column("technology_notes", sa.Text(), nullable=True),
        sa.Column("features", sa.Text(), nullable=True),
        sa.Column("github_url", sa.String(length=2048), nullable=True),
        sa.Column("live_url", sa.String(length=2048), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("team_or_individual", sa.String(length=20), nullable=False, server_default="individual"),
        sa.Column("results", sa.Text(), nullable=True),
        *_timestamps(),
        _user_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_projects_dates"),
        sa.CheckConstraint("team_or_individual IN ('team', 'individual')", name="ck_projects_team_type"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)
    op.create_table(
        "project_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "skill_id", name="uq_project_skills_project_skill"),
    )

    simple_tables = {
        "certifications": [
            sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(180), nullable=False),
            sa.Column("issuer", sa.String(180), nullable=False), sa.Column("issue_date", sa.Date()),
            sa.Column("expiry_date", sa.Date()), sa.Column("credential_id", sa.String(160)),
            sa.Column("credential_url", sa.String(2048)), sa.Column("description", sa.Text()),
            sa.CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date", name="ck_certifications_dates"),
        ],
        "courses": [
            sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(180), nullable=False),
            sa.Column("provider", sa.String(180), nullable=False), sa.Column("completion_date", sa.Date()),
            sa.Column("credential_url", sa.String(2048)), sa.Column("description", sa.Text()),
        ],
        "achievements": [
            sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(180), nullable=False),
            sa.Column("organization", sa.String(180)), sa.Column("achieved_on", sa.Date()),
            sa.Column("description", sa.Text()), sa.Column("evidence_url", sa.String(2048)),
        ],
        "languages": [
            sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("language", sa.String(80), nullable=False),
            sa.Column("proficiency", sa.String(20), nullable=False),
            sa.UniqueConstraint("user_id", "language", name="uq_languages_user_language"),
        ],
        "open_source_contributions": [
            sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("repository", sa.String(255), nullable=False),
            sa.Column("contribution", sa.String(180), nullable=False), sa.Column("technology_notes", sa.Text()),
            sa.Column("url", sa.String(2048), nullable=False), sa.Column("start_date", sa.Date()),
            sa.Column("end_date", sa.Date()), sa.Column("description", sa.Text()),
            sa.UniqueConstraint("user_id", "repository", "contribution", name="uq_open_source_user_repo_contribution"),
            sa.CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_open_source_dates"),
        ],
    }
    for table_name, columns in simple_tables.items():
        op.create_table(
            table_name,
            sa.Column("id", sa.Uuid(), nullable=False),
            *columns,
            *_timestamps(),
            _user_fk(),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"], unique=False)


def downgrade() -> None:
    for table_name in ("open_source_contributions", "languages", "achievements", "courses", "certifications"):
        op.drop_index(f"ix_{table_name}_user_id", table_name=table_name)
        op.drop_table(table_name)
    op.drop_table("project_skills")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("experience_skills")
    op.drop_index("ix_experiences_user_id", table_name="experiences")
    op.drop_table("experiences")
    op.drop_index("ix_user_skills_user_id", table_name="user_skills")
    op.drop_table("user_skills")
    op.drop_table("skills")
    op.drop_index("ix_education_user_id", table_name="education")
    op.drop_table("education")
    op.drop_table("professional_links")
    op.drop_table("career_preferences")
    for column_name in ("other_links", "profile_photo_key", "bio", "headline", "full_name"):
        op.drop_column("profiles", column_name)
