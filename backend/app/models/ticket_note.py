from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class TicketNote(Base):
    __tablename__ = "ticket_notes"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    note_type = Column(
        String(50),
        nullable=False,
        default="internal",
        index=True
    )  # "internal" (technician work note) vs "customer" (customer update)

    content = Column(Text, nullable=False)

    author = Column(String(100), nullable=False, default="Technician")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
