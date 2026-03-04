"""Add source_url to regattas

Revision ID: b2c3d4e5f678
Revises: a1b2c3d4e567
Create Date: 2026-03-03
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f678"
down_revision = "a1b2c3d4e567"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "regattas", sa.Column("source_url", sa.String(length=500), nullable=True)
    )


def downgrade():
    op.drop_column("regattas", "source_url")
