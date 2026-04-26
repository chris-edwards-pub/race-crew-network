"""Add invite_sent_at to users

Revision ID: p6f7a8b9c0d1
Revises: o5e6f7a8b9c0
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op

revision = "p6f7a8b9c0d1"
down_revision = "o5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("invite_sent_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("users", "invite_sent_at")
