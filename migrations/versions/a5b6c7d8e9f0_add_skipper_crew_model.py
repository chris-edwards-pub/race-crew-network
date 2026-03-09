"""Add skipper/crew multi-user model

Revision ID: a5b6c7d8e9f0
Revises: 1f34ac0f8204
Create Date: 2026-03-09

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a5b6c7d8e9f0"
down_revision = "d4b5e6f7a8c9"
branch_labels = None
depends_on = None


def upgrade():
    # Add is_skipper and invited_by columns to users
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_skipper",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(sa.Column("invited_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_invited_by", "users", ["invited_by"], ["id"]
        )

    # Create skipper_crew association table
    op.create_table(
        "skipper_crew",
        sa.Column(
            "skipper_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True
        ),
        sa.Column("crew_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Data migration: set existing admins as skippers
    op.execute("UPDATE users SET is_skipper = 1 WHERE is_admin = 1")


def downgrade():
    op.drop_table("skipper_crew")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("fk_users_invited_by", type_="foreignkey")
        batch_op.drop_column("invited_by")
        batch_op.drop_column("is_skipper")
