"""Add phone to users

Revision ID: e4b2c7f9a123
Revises: d3a1f5e8b901
Create Date: 2026-02-15
"""
from alembic import op
import sqlalchemy as sa

revision = "e4b2c7f9a123"
down_revision = "d3a1f5e8b901"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column("users", "phone")
