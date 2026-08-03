"""Contact form submissions.

These were previously emailed and never stored, so when the domain had no MX
record every message was lost silently while the sender was told they would
hear back within 24 hours. The database is now the record of truth and email is
only a notification — if delivery fails the message is still here.
"""
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContactSubmission(Base):
    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)

    # Whether the notification email actually went out. False means someone has
    # to read this from the admin queue instead.
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
