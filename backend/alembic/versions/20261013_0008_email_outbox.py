"""Durable encrypted email delivery outbox."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261013_0008"
down_revision = "20261013_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("email_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_challenges.id", ondelete="CASCADE")),
        sa.Column("purpose", sa.String(32), nullable=False), sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("encrypted_payload", sa.Text()), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("lease", postgresql.UUID(as_uuid=True)), sa.Column("provider", sa.String(16)),
        sa.Column("provider_message_id", sa.String(200)), sa.Column("error_code", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('QUEUED','SENDING','RETRYING','ACCEPTED','FAILED','EXPIRED','CANCELLED','UNCERTAIN')", name="status"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 6", name="attempts"))
    op.create_index("ix_email_deliveries_user_id", "email_deliveries", ["user_id"])
    op.create_index("ix_email_deliveries_challenge_id", "email_deliveries", ["challenge_id"])
    op.create_index("ix_email_deliveries_status_next", "email_deliveries", ["status", "next_attempt_at"])


def downgrade():
    raise RuntimeError("Email outbox contains delivery evidence; downgrade requires a reviewed backup/restore plan.")
