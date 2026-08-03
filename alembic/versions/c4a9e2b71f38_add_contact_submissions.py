"""Persist contact form submissions

Submissions were only ever emailed. With no MX record on the domain that mail
went nowhere, and the sender was told they would hear back within 24 hours.

Revision ID: c4a9e2b71f38
Revises: b3f8d1e6a274
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa


revision = "c4a9e2b71f38"
down_revision = "b3f8d1e6a274"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        # Indexes are created explicitly below; declaring index=True here too
        # emits the same name twice and the migration aborts.
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contact_submissions_email", "contact_submissions", ["email"])
    op.create_index("ix_contact_submissions_created_at", "contact_submissions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_submissions_created_at", table_name="contact_submissions")
    op.drop_index("ix_contact_submissions_email", table_name="contact_submissions")
    op.drop_table("contact_submissions")
