"""note attached to a like

Revision ID: f6a3c82d5e14
Revises: e5f2a91c4b73
Create Date: 2026-08-09

Hand-written. Autogenerate re-emits indexes that already exist on this table
and aborts the release command mid-deploy.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a3c82d5e14"
down_revision = "e5f2a91c4b73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("likes", sa.Column("comment", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("likes", "comment")
