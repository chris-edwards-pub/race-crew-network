"""Add site_settings table

Revision ID: 9a8b7c6d5e4f
Revises: b2c3d4e5f678
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9a8b7c6d5e4f"
down_revision = "b2c3d4e5f678"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_site_settings_key"), "site_settings", ["key"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_site_settings_key"), table_name="site_settings")
    op.drop_table("site_settings")
