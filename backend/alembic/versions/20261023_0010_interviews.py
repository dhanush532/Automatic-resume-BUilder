"""Add owner-scoped interview sessions. Additive; no existing data is rewritten."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261023_0010"
down_revision = "20261013_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Uuid(), sa.ForeignKey("resumes.id", ondelete="SET NULL")),
        sa.Column("role", sa.String(160), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("interview_type", sa.String(30), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("turns", postgresql.JSONB(), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("running_since", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed')", name="ck_interview_status"),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_interview_difficulty"),
        sa.CheckConstraint("question_count BETWEEN 1 AND 20", name="ck_interview_count"),
        sa.CheckConstraint("duration_minutes BETWEEN 5 AND 90", name="ck_interview_duration"),
        sa.CheckConstraint("elapsed_seconds >= 0", name="ck_interview_elapsed"),
    )
    op.create_index("ix_interview_user_created", "interview_sessions", ["user_id", "created_at"])


def downgrade():
    op.drop_table("interview_sessions")
