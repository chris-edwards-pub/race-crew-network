"""Add ai_usage_log table

Revision ID: l2b3c4d5e6f7
Revises: k1a2b3c4d5e6
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

revision = "l2b3c4d5e6f7"
down_revision = "k1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("function_name", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("ai_usage_log")
