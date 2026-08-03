"""Add automated moderation columns to photos

Existing photos are backfilled as "unscanned" and left unflagged, so nothing
already on the platform disappears when this deploys. Screening applies to
uploads from here on; a backfill pass over historical photos is a separate job.

Revision ID: b3f8d1e6a274
Revises: a7e4b1c9d503
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa


revision = "b3f8d1e6a274"
down_revision = "a7e4b1c9d503"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("moderation_status", sa.String(20), nullable=False, server_default="unscanned"),
    )
    op.add_column("photos", sa.Column("moderation_labels", sa.JSON(), nullable=True))
    op.add_column("photos", sa.Column("moderation_score", sa.Float(), nullable=True))
    op.add_column("photos", sa.Column("moderated_at", sa.DateTime(), nullable=True))
    op.add_column(
        "photos",
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("photos", sa.Column("flag_reason", sa.String(200), nullable=True))
    op.add_column("photos", sa.Column("reviewed_at", sa.DateTime(), nullable=True))

    # The review queue reads exactly this predicate on every admin page load.
    op.create_index(
        "ix_photos_pending_review",
        "photos",
        ["is_flagged", "reviewed_at"],
        postgresql_where=sa.text("is_flagged = true AND reviewed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_photos_pending_review", table_name="photos")
    op.drop_column("photos", "reviewed_at")
    op.drop_column("photos", "flag_reason")
    op.drop_column("photos", "is_flagged")
    op.drop_column("photos", "moderated_at")
    op.drop_column("photos", "moderation_score")
    op.drop_column("photos", "moderation_labels")
    op.drop_column("photos", "moderation_status")
