"""Add notification system

Revision ID: i9e0f1a2b3c4
Revises: h8d9e0f1a2b3
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from alembic import op

revision = "i9e0f1a2b3c4"
down_revision = "h8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("regatta_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("trigger_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["regatta_id"], ["regattas.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notification_type_regatta",
        "notification_log",
        ["notification_type", "regatta_id"],
    )
    op.add_column("users", sa.Column("notification_prefs", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "notification_prefs")
    op.drop_index("ix_notification_type_regatta", table_name="notification_log")
    op.drop_table("notification_log")
