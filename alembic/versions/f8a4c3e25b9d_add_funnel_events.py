"""Add funnel_events table for conversion tracking.

Revision ID: f8a4c3e25b9d
Revises: e7f3b2d14a8c
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f8a4c3e25b9d"
down_revision: Union[str, None] = "e7f3b2d14a8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funnel_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("user_type", sa.String(20), nullable=True),
        sa.Column("event", sa.String(50), nullable=False, index=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("funnel_events")
