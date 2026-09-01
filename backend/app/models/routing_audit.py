from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func

from app.database import Base


class RoutingAudit(Base):
    __tablename__ = "routing_audits"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(Integer, nullable=False, index=True)

    rule = Column(String, nullable=True)

    matched_keywords = Column(JSON, nullable=True)

    match_location = Column(String, nullable=True)

    score = Column(Integer, nullable=True)

    confidence = Column(Integer, nullable=True)

    team = Column(String, nullable=False)

    priority = Column(String, nullable=False)

    category = Column(String, nullable=False)

    routing_method = Column(String, nullable=False)

    reason = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )