"""Extend account security while preserving every existing UUID and record."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261013_0007"
down_revision = "20261013_0006"
branch_labels = None
depends_on = None


def upgrade():
    # Creating the unique index aborts the transaction safely if historical case
    # collisions exist. Never merge or delete conflicting user records.
    op.create_index("uq_users_normalized_email", "users", [sa.text("lower(btrim(email))")], unique=True)
    op.drop_constraint("uq_users_phone_e164", "users", type_="unique")
    op.add_column("users", sa.Column("account_status", sa.String(16), nullable=False, server_default="ACTIVE"))
    op.execute("UPDATE users SET account_status = CASE WHEN deleted_at IS NOT NULL THEN 'DELETED' WHEN NOT is_active THEN 'DISABLED' WHEN email_verified_at IS NULL THEN 'PENDING' ELSE 'ACTIVE' END")
    op.create_check_constraint("account_status", "users", "account_status IN ('PENDING','ACTIVE','DISABLED','DELETED')")
    op.add_column("user_sessions", sa.Column("recent_auth_at", sa.DateTime(timezone=True)))
    op.create_table("email_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False), sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("otp_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)), sa.Column("delivery_failed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("pending_values", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 5", name="attempts"),
        sa.CheckConstraint("purpose IN ('REGISTRATION','EMAIL_CHANGE')", name="purpose"))
    op.create_index("ix_email_challenges_user_purpose_created", "email_challenges", ["user_id", "purpose", "created_at"])
    op.create_table("auth_rate_buckets", sa.Column("key", sa.String(64), primary_key=True),
                    sa.Column("count", sa.Integer(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_rate_buckets_expires_at", "auth_rate_buckets", ["expires_at"])
    op.create_table("oauth_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False), sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("browser_hash", sa.String(64), nullable=False), sa.Column("encrypted_verifier", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_sessions.id", ondelete="CASCADE")),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("provider IN ('google','github','linkedin')", name="provider"),
        sa.CheckConstraint("mode IN ('login','link','reauth')", name="mode"))
    op.create_index("ix_oauth_attempts_expires_at", "oauth_attempts", ["expires_at"])


def downgrade():
    raise RuntimeError("Authentication downgrade requires a reviewed restore plan; non-unique phones and identity changes must not be reversed automatically.")
