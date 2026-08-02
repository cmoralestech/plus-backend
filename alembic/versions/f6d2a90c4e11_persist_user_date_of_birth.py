"""persist user date of birth

Registration validated the date for the 18+ check and then discarded it, so
onboarding had nothing to send and profile creation failed with a 422 for
every account.

Revision ID: f6d2a90c4e11
Revises: e5c1f83a2b40
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6d2a90c4e11"
down_revision: Union[str, None] = "e5c1f83a2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    # Existing accounts that did manage to create a profile have the date there.
    op.execute(
        """
        UPDATE users u
        SET date_of_birth = p.date_of_birth
        FROM profiles p
        WHERE p.user_id = u.id AND u.date_of_birth IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("users", "date_of_birth")
