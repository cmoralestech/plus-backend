"""add member verification

Stores outcomes, not evidence: no documents, amounts or bands live here.

Revision ID: e5c1f83a2b40
Revises: d4b8c2e5a917
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5c1f83a2b40"
down_revision: Union[str, None] = "d4b8c2e5a917"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_type=False on the column so create_table doesn't emit a second
    # CREATE TYPE after the explicit create.
    method = postgresql.ENUM(
        "income", "assets", "manual", name="verification_method", create_type=False
    )
    result = postgresql.ENUM(
        "pending", "qualified", "not_qualified", name="qualification_result", create_type=False
    )
    postgresql.ENUM("income", "assets", "manual", name="verification_method").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(
        "pending", "qualified", "not_qualified", name="qualification_result"
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "member_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("identity_verified", sa.Boolean(), nullable=True),
        sa.Column("identity_verified_at", sa.DateTime(), nullable=True),
        sa.Column("financially_verified", sa.Boolean(), nullable=True),
        sa.Column("financial_verified_at", sa.DateTime(), nullable=True),
        sa.Column("financial_verification_method", method, nullable=True),
        sa.Column("qualification_result", result, nullable=True),
        sa.Column("identity_reference", sa.String(length=120), nullable=True),
        sa.Column("financial_reference", sa.String(length=120), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_member_verification_user"),
    )
    op.create_index("ix_member_verifications_user_id", "member_verifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("member_verifications")
    sa.Enum(name="qualification_result").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="verification_method").drop(op.get_bind(), checkfirst=True)
