"""Add city_state column to regattas table

Revision ID: k1a2b3c4d5e6
Revises: j0f1a2b3c4d5
Create Date: 2026-03-20
"""

import sqlalchemy as sa
from alembic import op

revision = "k1a2b3c4d5e6"
down_revision = "j0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("regattas", sa.Column("city_state", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("regattas", "city_state")
