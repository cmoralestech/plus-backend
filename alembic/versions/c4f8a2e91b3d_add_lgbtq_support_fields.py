"""add lgbtq support fields

Revision ID: c4f8a2e91b3d
Revises: 2e8a39bf2f64
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4f8a2e91b3d'
down_revision: Union[str, None] = '2e8a39bf2f64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types first
    sexual_orientation_enum = sa.Enum(
        'STRAIGHT', 'GAY', 'LESBIAN', 'BISEXUAL', 'PANSEXUAL',
        'QUEER', 'ASEXUAL', 'PREFER_NOT_TO_SAY',
        name='sexualorientation',
    )
    sexual_orientation_enum.create(op.get_bind(), checkfirst=True)

    pronouns_enum = sa.Enum(
        'HE_HIM', 'SHE_HER', 'THEY_THEM', 'HE_THEY',
        'SHE_THEY', 'OTHER', 'PREFER_NOT_TO_SAY',
        name='pronouns',
    )
    pronouns_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('profiles', sa.Column('sexual_orientation', sexual_orientation_enum, nullable=True))
    op.add_column('profiles', sa.Column('pronouns', pronouns_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('profiles', 'pronouns')
    op.drop_column('profiles', 'sexual_orientation')

    # Drop enum types
    sa.Enum(name='pronouns').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='sexualorientation').drop(op.get_bind(), checkfirst=True)
