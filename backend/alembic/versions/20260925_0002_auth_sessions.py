"""Add authentication, session, and security-event persistence.

Revision ID: 20260925_0002
Revises: 20260925_0001
Create Date: 2026-09-25 00:01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260925_0002"
down_revision: str | Sequence[str] | None = "20260925_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    session_status = sa.Enum("ACTIVE", "REVOKED", "EXPIRED", name="session_status")
    security_event_type = sa.Enum(
        "LOGIN_SUCCESS",
        "LOGIN_FAILURE",
        "LOGOUT",
        "SESSION_REVOKED",
        "PASSWORD_CHANGED",
        "PASSWORD_RESET",
        "EMAIL_VERIFIED",
        "EMAIL_CHANGED",
        "OAUTH_LINKED",
        "OAUTH_DISCONNECTED",
        "ACCOUNT_DELETED",
        name="security_event_type",
    )
    security_token_purpose = sa.Enum(
        "EMAIL_VERIFICATION", "PASSWORD_RESET", name="security_token_purpose"
    )

    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_users_email_normalized", "users", "email = lower(email)")
    op.create_check_constraint("ck_users_username_normalized", "users", "username = lower(username)")
    op.create_index("ix_users_email_verified", "users", ["email_verified_at"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", session_status, nullable=False, server_default="ACTIVE"),
        sa.Column("device_type", sa.String(length=32), nullable=True),
        sa.Column("browser", sa.String(length=64), nullable=True),
        sa.Column("operating_system", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_user_status", "user_sessions", ["user_id", "status"], unique=False)
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)

    op.create_table(
        "login_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", security_event_type, nullable=False),
        sa.Column("identifier", sa.String(length=320), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=1024), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_events_user_created", "login_events", ["user_id", "created_at"], unique=False)
    op.create_index("ix_login_events_identifier_created", "login_events", ["identifier", "created_at"], unique=False)

    op.create_table(
        "security_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", security_token_purpose, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_security_tokens_token_hash"),
    )
    op.create_index("ix_security_tokens_user_purpose", "security_tokens", ["user_id", "purpose"], unique=False)
    op.create_index("ix_security_tokens_expires_at", "security_tokens", ["expires_at"], unique=False)

    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_identities_provider_subject"),
    )
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
    op.drop_index("ix_security_tokens_expires_at", table_name="security_tokens")
    op.drop_index("ix_security_tokens_user_purpose", table_name="security_tokens")
    op.drop_table("security_tokens")
    op.drop_index("ix_login_events_identifier_created", table_name="login_events")
    op.drop_index("ix_login_events_user_created", table_name="login_events")
    op.drop_table("login_events")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_status", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email_verified", table_name="users")
    op.drop_constraint("ck_users_username_normalized", "users", type_="check")
    op.drop_constraint("ck_users_email_normalized", "users", type_="check")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "terms_accepted_at")
    sa.Enum(name="security_token_purpose").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="security_event_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="session_status").drop(op.get_bind(), checkfirst=True)
