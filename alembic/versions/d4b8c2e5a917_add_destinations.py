"""add destinations and member interest

Revision ID: d4b8c2e5a917
Revises: c3a7e1f04b88
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4b8c2e5a917"
down_revision: Union[str, None] = "c3a7e1f04b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Curated rather than user-created: a free-text field would fragment into
# hundreds of one-person "destinations" and lose the shared context that makes
# matching on them worthwhile. Dates are null for places that are a standing
# idea rather than a fixed event.
DESTINATIONS = [
    ("miami-art-week", "Miami Art Week", "Miami", "Basel week, and everything around it.", 10),
    ("monaco-grand-prix", "Monaco Grand Prix", "Monaco", "The only race where the paddock is a harbour.", 20),
    ("cannes", "Cannes Film Festival", "Côte d'Azur", "Two weeks of premieres and long dinners.", 30),
    ("wimbledon", "Wimbledon", "London", "Strawberries, and someone to argue about line calls with.", 40),
    ("ibiza", "Ibiza", "Balearics", "For the summer, or a long weekend of it.", 50),
    ("capri", "Capri", "Italy", "Slow mornings, and a boat by the afternoon.", 60),
    ("aspen", "Aspen", "Colorado", "Ski season, or the quiet part of the year.", 70),
    ("st-barts", "St. Barts", "Caribbean", "New Year's, or any excuse before it.", 80),
]


def upgrade() -> None:
    op.create_table(
        "destinations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("blurb", sa.String(length=240), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_destinations_slug", "destinations", ["slug"], unique=True)

    interest_level = sa.Enum("going", "want_to_go", name="interest_level")
    interest_level.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "destination_interests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("level", interest_level, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destination_id"], ["destinations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "destination_id", name="uq_destination_interest"),
    )
    op.create_index("ix_destination_interests_profile_id", "destination_interests", ["profile_id"])
    op.create_index(
        "ix_destination_interests_destination_id", "destination_interests", ["destination_id"]
    )

    op.bulk_insert(
        sa.table(
            "destinations",
            sa.column("slug", sa.String),
            sa.column("name", sa.String),
            sa.column("location", sa.String),
            sa.column("blurb", sa.String),
            sa.column("sort_order", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {
                "slug": slug,
                "name": name,
                "location": location,
                "blurb": blurb,
                "sort_order": order,
                "is_active": True,
            }
            for slug, name, location, blurb, order in DESTINATIONS
        ],
    )


def downgrade() -> None:
    op.drop_table("destination_interests")
    op.drop_table("destinations")
    sa.Enum(name="interest_level").drop(op.get_bind(), checkfirst=True)
