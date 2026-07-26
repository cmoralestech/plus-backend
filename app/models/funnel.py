"""Funnel analytics — tracks user journey from signup to payment."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON

from app.database import Base


class FunnelEvent(Base):
    __tablename__ = "funnel_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    user_type = Column(String(20), nullable=True)  # "sugar" or "attractive"
    event = Column(String(50), nullable=False, index=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
