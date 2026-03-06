"""Set blank default for regatta boat_class

Revision ID: c3d4e5f6a7b8
Revises: 9a8b7c6d5e4f
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "9a8b7c6d5e4f"
branch_labels = None
depends_on = None


def upgrade():
    # Normalize existing placeholder values to empty string.
    op.execute("UPDATE regattas SET boat_class = '' WHERE boat_class = 'TBD'")

    op.alter_column(
        "regattas",
        "boat_class",
        existing_type=sa.String(length=100),
        nullable=False,
        server_default="",
    )


def downgrade():
    # Restore placeholder for rows that were blanked by this migration.
    op.execute("UPDATE regattas SET boat_class = 'TBD' WHERE boat_class = ''")

    op.alter_column(
        "regattas",
        "boat_class",
        existing_type=sa.String(length=100),
        nullable=False,
        server_default="TBD",
    )
