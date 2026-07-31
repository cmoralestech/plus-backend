"""add context to likes

Lets a like carry what prompted it — a specific photo or prompt answer —
so the recipient sees why rather than just that it happened.

Revision ID: c3a7e1f04b88
Revises: b1c9d4e70f22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a7e1f04b88"
down_revision: Union[str, None] = "b1c9d4e70f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("likes", sa.Column("context", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("likes", "context")
