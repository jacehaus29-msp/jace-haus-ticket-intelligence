from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Team Lead (References a Technician)
    team_lead_id = Column(Integer, ForeignKey("technicians.id", ondelete="SET NULL"), nullable=True)
    
    # Operating / Business Hours Configuration (Phase 7 configuration fields)
    business_hours_start = Column(String(10), default="08:00", nullable=False)
    business_hours_end = Column(String(10), default="18:00", nullable=False)
    timezone = Column(String(50), default="America/New_York", nullable=False)
    work_days = Column(String(50), default="MON,TUE,WED,THU,FRI", nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    team_lead = relationship("Technician", foreign_keys=[team_lead_id], post_update=True, lazy="joined")
    members = relationship("Technician", foreign_keys="Technician.team_id", back_populates="team_rel", lazy="select")
    routing_rules = relationship("RoutingRule", foreign_keys="RoutingRule.team_id", lazy="select")
    tickets = relationship("Ticket", foreign_keys="Ticket.assigned_team_id", lazy="select")

    def to_dict(self, include_members: bool = False, db = None):
        """Serialize team data with operational metrics and lead info."""
        lead_name = self.team_lead.name if self.team_lead else None
        lead_email = self.team_lead.email if self.team_lead else None

        member_list = []
        if include_members and self.members:
            for m in self.members:
                member_list.append({
                    "id": m.id,
                    "name": m.name,
                    "email": m.email,
                    "is_active": m.is_active,
                    "is_lead": m.id == self.team_lead_id
                })

        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description or "",
            "team_lead_id": self.team_lead_id,
            "team_lead_name": lead_name,
            "team_lead_email": lead_email,
            "business_hours_start": self.business_hours_start,
            "business_hours_end": self.business_hours_end,
            "timezone": self.timezone,
            "work_days": self.work_days,
            "is_active": self.is_active,
            "member_count": len(self.members) if self.members else 0,
            "members": member_list,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
