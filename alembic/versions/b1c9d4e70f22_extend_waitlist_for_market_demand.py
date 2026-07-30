"""extend waitlist for market demand tracking

Adds metro/country, per-entry share codes for pre-signup referrals, UTM
attribution, and updated_at. The pre-existing `referral_code` column held the
code an entry *arrived through*, so it is renamed to `referred_by_code` to make
room for `share_code` (the entry's own code).

Revision ID: b1c9d4e70f22
Revises: f8a4c3e25b9d
"""
from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "b1c9d4e70f22"
down_revision: Union[str, None] = "f8a4c3e25b9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("waitlist", sa.Column("metro", sa.String(length=100), nullable=True))
    op.add_column("waitlist", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column("waitlist", sa.Column("utm_source", sa.String(length=100), nullable=True))
    op.add_column("waitlist", sa.Column("utm_medium", sa.String(length=100), nullable=True))
    op.add_column("waitlist", sa.Column("utm_campaign", sa.String(length=100), nullable=True))
    op.add_column(
        "waitlist",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    # Drop the old index before renaming, so it isn't left behind under the old
    # name alongside the new one. Environments disagree on what this index is
    # called — production has "ix_waitlist_referral" while a create_all-built
    # database gets "ix_waitlist_referral_code" — so drop either, if present.
    for index_name in ("ix_waitlist_referral_code", "ix_waitlist_referral"):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
    op.alter_column("waitlist", "referral_code", new_column_name="referred_by_code")
    op.alter_column(
        "waitlist",
        "referred_by_code",
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        existing_nullable=True,
    )

    # Added nullable, backfilled, then made NOT NULL so existing rows survive.
    op.add_column("waitlist", sa.Column("share_code", sa.String(length=20), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM waitlist WHERE share_code IS NULL")).fetchall()
    for (row_id,) in rows:
        conn.execute(
            sa.text("UPDATE waitlist SET share_code = :code WHERE id = :id"),
            {"code": uuid.uuid4().hex[:10], "id": row_id},
        )
    op.alter_column("waitlist", "share_code", existing_type=sa.String(length=20), nullable=False)

    op.create_index("ix_waitlist_metro", "waitlist", ["metro"])
    op.create_index("ix_waitlist_utm_source", "waitlist", ["utm_source"])
    op.create_index("ix_waitlist_share_code", "waitlist", ["share_code"], unique=True)
    op.create_index("ix_waitlist_referred_by_code", "waitlist", ["referred_by_code"])


def downgrade() -> None:
    for index_name in (
        "ix_waitlist_referred_by_code",
        "ix_waitlist_share_code",
        "ix_waitlist_utm_source",
        "ix_waitlist_metro",
    ):
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    op.drop_column("waitlist", "share_code")
    op.alter_column(
        "waitlist",
        "referred_by_code",
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column("waitlist", "referred_by_code", new_column_name="referral_code")
    op.create_index("ix_waitlist_referral_code", "waitlist", ["referral_code"])

    op.drop_column("waitlist", "updated_at")
    op.drop_column("waitlist", "utm_campaign")
    op.drop_column("waitlist", "utm_medium")
    op.drop_column("waitlist", "utm_source")
    op.drop_column("waitlist", "country")
    op.drop_column("waitlist", "metro")
