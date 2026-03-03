"""Add import_cache table

Revision ID: a1b2c3d4e567
Revises: f5a3d8e1b234
Create Date: 2026-03-03
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e567"
down_revision = "f5a3d8e1b234"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "import_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=False),
        sa.Column("regatta_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )


def downgrade():
    op.drop_table("import_cache")
