"""Add task_results table

Revision ID: d4b5e6f7a8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-08
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4b5e6f7a8c9"
down_revision = "1f34ac0f8204"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("result_type", sa.String(length=20), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("task_results")
