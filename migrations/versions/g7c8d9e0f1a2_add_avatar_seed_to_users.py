"""Add avatar_seed to users

Revision ID: g7c8d9e0f1a2
Revises: f6b7c8d9e0f1
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op

revision = "g7c8d9e0f1a2"
down_revision = "f6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("avatar_seed", sa.String(length=100), nullable=True)
    )


def downgrade():
    op.drop_column("users", "avatar_seed")
