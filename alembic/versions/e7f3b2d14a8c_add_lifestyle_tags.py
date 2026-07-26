"""Add lifestyle_tags column to profiles.

Revision ID: e7f3b2d14a8c
Revises: d5e2f1a93c7b
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "e7f3b2d14a8c"
down_revision: Union[str, None] = "d5e2f1a93c7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("lifestyle_tags", ARRAY(sa.String(50)), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "lifestyle_tags")
