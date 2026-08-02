"""rename user types: sugar -> established, attractive -> plus

The values shipped in every API response, so "sugar" was visible to anyone
inspecting network traffic — including app store and ads reviewers, for a
category both prohibit. The visible copy was already changed; this is the
last place the old positioning asserted itself.

Also switches storage from enum member names (SUGAR) to values (established),
so what's in the column matches what's in the JSON.

Revision ID: a7e4b1c9d503
Revises: f6d2a90c4e11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7e4b1c9d503"
down_revision: Union[str, None] = "f6d2a90c4e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Old -> new. Old rows hold member names; new rows hold values.
FORWARD = {"SUGAR": "established", "ATTRACTIVE": "plus"}
BACKWARD = {v: k for k, v in FORWARD.items()}


def _case(mapping: dict, column: str) -> str:
    whens = " ".join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column}::text {whens} END"


def upgrade() -> None:
    # Postgres can add enum values but not remove them, so the type is
    # recreated and the column rewritten through an explicit mapping.
    op.execute("ALTER TYPE usertype RENAME TO usertype_old")
    sa.Enum("established", "plus", name="usertype").create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE users ALTER COLUMN user_type TYPE usertype "
        f"USING ({_case(FORWARD, 'user_type')})::usertype"
    )
    op.execute("DROP TYPE usertype_old")

    # funnel_events stores the same concept as free text.
    op.execute(
        "UPDATE funnel_events SET user_type = "
        + _case({"sugar": "established", "attractive": "plus"}, "user_type")
        + " WHERE user_type IN ('sugar', 'attractive')"
    )


def downgrade() -> None:
    op.execute("ALTER TYPE usertype RENAME TO usertype_new")
    sa.Enum("SUGAR", "ATTRACTIVE", name="usertype").create(op.get_bind(), checkfirst=True)
    op.execute(
        "ALTER TABLE users ALTER COLUMN user_type TYPE usertype "
        f"USING ({_case(BACKWARD, 'user_type')})::usertype"
    )
    op.execute("DROP TYPE usertype_new")

    op.execute(
        "UPDATE funnel_events SET user_type = "
        + _case({"established": "sugar", "plus": "attractive"}, "user_type")
        + " WHERE user_type IN ('established', 'plus')"
    )
