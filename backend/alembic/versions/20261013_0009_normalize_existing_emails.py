"""Normalize historical email values without changing account identity."""
from alembic import op

revision = "20261013_0009"
down_revision = "20261013_0008"
branch_labels = None
depends_on = None


def upgrade():
    # The already-installed functional unique index proves this cannot merge
    # accounts; each existing UUID and every foreign-key association is retained.
    op.execute("UPDATE users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email))")


def downgrade():
    # Normalized casing is intentional; do not invent historical spelling.
    pass
