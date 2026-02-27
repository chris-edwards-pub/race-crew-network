"""Add boat_class to regattas

Revision ID: f5a3d8e1b234
Revises: e4b2c7f9a123
Create Date: 2026-02-27
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f5a3d8e1b234"
down_revision = "e4b2c7f9a123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "regattas",
        sa.Column(
            "boat_class",
            sa.String(length=100),
            nullable=False,
            server_default="TBD",
        ),
    )


def downgrade():
    op.drop_column("regattas", "boat_class")
