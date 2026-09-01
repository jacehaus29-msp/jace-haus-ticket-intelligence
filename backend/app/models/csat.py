from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class CSATRating(Base):
    __tablename__ = "csat_ratings"

    id = Column(Integer, primary_key=True, index=True)

    ticket_id = Column(
        Integer,
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    rating = Column(
        Integer,
        nullable=False,
        index=True
    )

    feedback = Column(Text, nullable=True)

    submitted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_csat_rating_range"),
        UniqueConstraint("ticket_id", "customer_id", name="uq_ticket_customer_csat"),
    )
