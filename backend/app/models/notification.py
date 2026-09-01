from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(Integer, nullable=True, index=True)

    type = Column(String(50), nullable=False, index=True)
    # Types: SLA_AT_RISK, SLA_BREACHED, ESCALATION, TICKET_ASSIGNED, PRIORITY_CHANGED, STATUS_CHANGED

    severity = Column(String(20), nullable=False, default="info")
    # Severities: info, warning, critical

    title = Column(String(255), nullable=False)

    message = Column(Text, nullable=False)

    is_read = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )
