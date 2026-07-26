from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class PollVote(Base):
    __tablename__ = "poll_votes"

    id = Column(Integer, primary_key=True, index=True)
    poll_slug = Column(String(100), nullable=False, index=True)
    option_index = Column(Integer, nullable=False)
    voter_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
