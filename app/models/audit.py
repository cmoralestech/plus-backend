from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    actor_type = Column(String(50), nullable=False)  # "user", "admin", "system"
    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)  # "user", "profile", "message", "report"
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # old/new values, reason, matched keywords
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
