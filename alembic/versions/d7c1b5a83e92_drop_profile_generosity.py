"""Drop the profiles.generosity column

Onboarding asked "How important is generosity in the relationship you're
looking for?" with answers up to "Essential", stored the result, and never
used it. It was not shown on profiles, not used in ranking, matching or
search, and appeared nowhere outside schema plumbing.

So it was friction on the longest step of signup for no return, it collected
personal data with no purpose, and it was the most financially loaded
question in a product whose acceptable use policy prohibits companionship
for money.

lifestyle_expectation already covers this ground and describes a lifestyle
rather than an expectation of someone else's spending.

Revision ID: d7c1b5a83e92
Revises: c4a9e2b71f38
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa


revision = "d7c1b5a83e92"
down_revision = "c4a9e2b71f38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded so the migration is safe against a database where the column was
    # never created, which is the case for any environment built from a schema
    # snapshot rather than the full migration chain.
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS generosity")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("generosity", sa.String(50), nullable=True))
