"""Add password reset fields to users

Revision ID: m3c4d5e6f7a8
Revises: l2b3c4d5e6f7
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

revision = "m3c4d5e6f7a8"
down_revision = "l2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("reset_token", sa.String(64), unique=True, nullable=True)
    )
    op.add_column(
        "users", sa.Column("reset_token_expires_at", sa.DateTime(), nullable=True)
    )


def downgrade():
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token")
