"""Add profile image key to users

Revision ID: f6b7c8d9e0f1
Revises: a5b6c7d8e9f0
Create Date: 2026-03-09
"""

import sqlalchemy as sa
from alembic import op

revision = "f6b7c8d9e0f1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("profile_image_key", sa.String(length=255), nullable=True)
    )


def downgrade():
    op.drop_column("users", "profile_image_key")
