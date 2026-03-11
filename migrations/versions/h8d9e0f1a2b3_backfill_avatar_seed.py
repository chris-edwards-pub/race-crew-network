"""Backfill avatar_seed for existing users

Revision ID: h8d9e0f1a2b3
Revises: g7c8d9e0f1a2
Create Date: 2026-03-11
"""

from alembic import op

revision = "h8d9e0f1a2b3"
down_revision = "g7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE users SET avatar_seed = email WHERE avatar_seed IS NULL")


def downgrade():
    op.execute("UPDATE users SET avatar_seed = NULL WHERE avatar_seed = email")
