"""Add source health and auditable job verification; preserve all existing rows."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261013_0006"
down_revision = "20260925_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("last_attempt_at", "last_success_at", "sync_locked_until"):
        op.add_column("job_sources", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("job_sources", sa.Column("last_error", sa.String(240)))
    op.add_column("job_sources", sa.Column("last_job_count", sa.Integer()))
    op.add_column("job_sources", sa.Column("sync_lease", postgresql.UUID(as_uuid=True)))
    op.add_column("jobs", sa.Column("verification_status", sa.String(24), nullable=False, server_default="UNVERIFIED"))
    statuses = "verification_status IN ('VERIFIED', 'LIKELY_LEGITIMATE', 'UNVERIFIED', 'SUSPICIOUS', 'EXPIRED', 'CLOSED')"
    op.create_check_constraint("verification_status", "jobs", statuses)
    op.create_index("ix_jobs_status_last_seen", "jobs", ["status", "last_seen_at"])
    op.create_table(
        "job_verification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verification_status", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.String(2048), nullable=False),
        sa.CheckConstraint(statuses, name="verification_status"),
    )
    op.create_index("ix_job_verification_events_job_checked", "job_verification_events", ["job_id", "checked_at"])


def downgrade() -> None:
    # An explicit operator downgrade removes M6 evidence; never used for normal updates.
    op.drop_table("job_verification_events")
    op.drop_index("ix_jobs_status_last_seen", table_name="jobs")
    op.drop_constraint("ck_jobs_verification_status", "jobs", type_="check")
    op.drop_column("jobs", "verification_status")
    for name in ("last_attempt_at", "last_success_at", "sync_locked_until", "last_error", "last_job_count", "sync_lease"):
        op.drop_column("job_sources", name)
