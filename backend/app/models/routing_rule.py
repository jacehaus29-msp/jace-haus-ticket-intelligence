from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    category = Column(
        String(100),
        nullable=False
    )

    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True
    )

    team = Column(
        String(100),
        nullable=False
    )

    priority = Column(
        String(50),
        nullable=True
    )

    keywords = Column(
        JSONB,
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )