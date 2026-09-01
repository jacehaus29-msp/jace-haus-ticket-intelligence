from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)

    description = Column(Text, nullable=False)

    category = Column(String(100), nullable=True)

    assigned_team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)

    assigned_team = Column(String(100), nullable=True)

    priority = Column(String(50), nullable=True)

    status = Column(
        String(50),
        nullable=True,
        default="new"
    )

    routing_method = Column(String(50), nullable=True)

    # SLA tracking timestamps & status
    response_due_at = Column(DateTime(timezone=True), nullable=True)

    resolution_due_at = Column(DateTime(timezone=True), nullable=True)

    responded_at = Column(DateTime(timezone=True), nullable=True)

    resolved_at = Column(DateTime(timezone=True), nullable=True)

    sla_status = Column(String(50), nullable=True, default="on_track")

    # Resolution tracking details
    resolution_summary = Column(String(255), nullable=True)

    resolution_details = Column(Text, nullable=True)

    # Technician Assignment
    assigned_technician_id = Column(
        Integer,
        ForeignKey("technicians.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    assigned_technician = Column(String(100), nullable=True)

    # Multi-level Escalation (1: Normal, 2: Team Escalation, 3: Specialist Escalation)
    escalation_level = Column(Integer, nullable=False, default=1)

    escalation_reason = Column(Text, nullable=True)

    escalated_at = Column(DateTime(timezone=True), nullable=True)

    escalated_by = Column(String(100), nullable=True)

    # Customer Ownership / Portal Integration
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    customer_name = Column(String(100), nullable=True)

    customer_email = Column(String(150), nullable=True)

    customer_company = Column(String(150), nullable=True)

    # Ticket Channel / Origin ("portal", "email", "manual")
    source = Column(String(50), nullable=True, default="portal")

    # Email Channel Identifiers (Optional)
    email_message_id = Column(String(255), nullable=True, index=True)

    email_conversation_id = Column(String(255), nullable=True, index=True)

    email_sender = Column(String(150), nullable=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )