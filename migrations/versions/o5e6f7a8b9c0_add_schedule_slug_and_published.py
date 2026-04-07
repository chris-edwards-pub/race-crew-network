"""Add schedule_slug and schedule_published to users

Revision ID: o5e6f7a8b9c0
Revises: n4d5e6f7a8b9
Create Date: 2026-04-06
"""

import sqlalchemy as sa
from alembic import op

revision = "o5e6f7a8b9c0"
down_revision = "n4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("schedule_slug", sa.String(100), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "schedule_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_unique_constraint("uq_users_schedule_slug", "users", ["schedule_slug"])


def downgrade():
    op.drop_constraint("uq_users_schedule_slug", "users", type_="unique")
    op.drop_column("users", "schedule_published")
    op.drop_column("users", "schedule_slug")
