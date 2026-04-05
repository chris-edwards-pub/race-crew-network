"""Add bio and yacht_club to users

Revision ID: n4d5e6f7a8b9
Revises: m3c4d5e6f7a8
Create Date: 2026-04-05
"""

import sqlalchemy as sa
from alembic import op

revision = "n4d5e6f7a8b9"
down_revision = "m3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("yacht_club", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "bio")
    op.drop_column("users", "yacht_club")
