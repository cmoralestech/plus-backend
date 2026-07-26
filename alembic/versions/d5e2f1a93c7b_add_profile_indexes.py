"""Add indexes on commonly queried profile columns.

Revision ID: d5e2f1a93c7b
Revises: c4f8a2e91b3d
Create Date: 2026-06-21 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e2f1a93c7b"
down_revision: Union[str, None] = "c4f8a2e91b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for the main discover query filter
    op.create_index(
        "ix_profiles_discover",
        "profiles",
        ["is_active", "is_hidden", "user_id"],
    )
    # City lookup (search, discover by location)
    op.create_index("ix_profiles_city", "profiles", ["city"])
    # Gender filter
    op.create_index("ix_profiles_gender", "profiles", ["gender"])
    # Created at for "new members" sorting
    op.create_index("ix_profiles_created_at", "profiles", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_profiles_created_at", table_name="profiles")
    op.drop_index("ix_profiles_gender", table_name="profiles")
    op.drop_index("ix_profiles_city", table_name="profiles")
    op.drop_index("ix_profiles_discover", table_name="profiles")
