import re
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models.team import Team
from app.models.technician import Technician
from app.models.ticket import Ticket
from app.models.routing_rule import RoutingRule
from app.models.notification import Notification
from app.models.user import User
from app.core.auth import get_current_user

router = APIRouter(
    prefix="/teams",
    tags=["Dynamic Team Management"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_slug(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.strip().lower()).strip('-')
    return slug or "team"


# -------------------------------------------------------------
# RBAC PERMISSION HELPERS
# -------------------------------------------------------------

def require_internal_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Customers do not have permission to access internal team management."
        )
    return current_user


def require_admin_or_manager(current_user: User = Depends(require_internal_user)) -> User:
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Admins and Managers have permission to modify team configurations."
        )
    return current_user


def require_admin_only(current_user: User = Depends(require_internal_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrator privileges required for this action."
        )
    return current_user


# -------------------------------------------------------------
# PYDANTIC SCHEMAS
# -------------------------------------------------------------

class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = ""
    team_lead_id: Optional[int] = None
    business_hours_start: Optional[str] = "08:00"
    business_hours_end: Optional[str] = "18:00"
    timezone: Optional[str] = "America/New_York"
    work_days: Optional[str] = "MON,TUE,WED,THU,FRI"
    is_active: Optional[bool] = True


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    team_lead_id: Optional[int] = None
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    work_days: Optional[str] = None
    is_active: Optional[bool] = None


class TeamStatusRequest(BaseModel):
    is_active: bool
    force: Optional[bool] = False


class TeamMembersRequest(BaseModel):
    technician_ids: List[int]


# -------------------------------------------------------------
# HELPER: Compute Team Metrics
# -------------------------------------------------------------

def compute_team_active_workload(db: Session, team: Team) -> int:
    return db.query(Ticket).filter(
        (Ticket.assigned_team_id == team.id) | (func.lower(Ticket.assigned_team) == team.name.lower()),
        Ticket.status.in_(["new", "in_progress"])
    ).count()


# -------------------------------------------------------------
# 1. GET /teams/ (List Teams)
# -------------------------------------------------------------

@router.get("/")
def get_teams(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    include_members: bool = Query(True, description="Include member details"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_user)
):
    query = db.query(Team)
    if is_active is not None:
        query = query.filter(Team.is_active == is_active)

    teams = query.order_by(Team.name.asc()).all()

    results = []
    for t in teams:
        data = t.to_dict(include_members=include_members, db=db)
        data["active_workload"] = compute_team_active_workload(db, t)
        results.append(data)

    return {
        "count": len(results),
        "teams": results
    }


# -------------------------------------------------------------
# 2. GET /teams/{team_id} (Team Details)
# -------------------------------------------------------------

@router.get("/{team_id}")
def get_team_by_id(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal_user)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    data = team.to_dict(include_members=True, db=db)
    data["active_workload"] = compute_team_active_workload(db, team)

    # Active open tickets summary
    active_tickets = db.query(Ticket).filter(
        (Ticket.assigned_team_id == team.id) | (func.lower(Ticket.assigned_team) == team.name.lower()),
        Ticket.status.in_(["new", "in_progress"])
    ).order_by(Ticket.created_at.desc()).limit(15).all()

    data["active_tickets"] = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "assigned_technician": t.assigned_technician,
            "sla_status": t.sla_status,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in active_tickets
    ]

    return data


# -------------------------------------------------------------
# 3. POST /teams/ (Create Team - Admin Only)
# -------------------------------------------------------------

@router.post("/", status_code=201)
def create_team(
    payload: TeamCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only)
):
    clean_name = payload.name.strip()
    existing = db.query(Team).filter(func.lower(Team.name) == clean_name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Team with name '{clean_name}' already exists.")

    slug = generate_slug(clean_name)
    existing_slug = db.query(Team).filter(Team.slug == slug).first()
    if existing_slug:
        slug = f"{slug}-{int(func.extract('epoch', func.now()))}"

    # Validate team lead if specified
    if payload.team_lead_id:
        lead_tech = db.query(Technician).filter(Technician.id == payload.team_lead_id).first()
        if not lead_tech:
            raise HTTPException(status_code=400, detail="Specified team lead technician does not exist.")
        if not lead_tech.is_active:
            raise HTTPException(status_code=400, detail="Cannot assign inactive technician as team lead.")

    new_team = Team(
        name=clean_name,
        slug=slug,
        description=payload.description.strip() if payload.description else "",
        team_lead_id=payload.team_lead_id,
        business_hours_start=payload.business_hours_start or "08:00",
        business_hours_end=payload.business_hours_end or "18:00",
        timezone=payload.timezone or "America/New_York",
        work_days=payload.work_days or "MON,TUE,WED,THU,FRI",
        is_active=payload.is_active if payload.is_active is not None else True
    )
    db.add(new_team)
    db.commit()
    db.refresh(new_team)

    # If team lead assigned, synchronize technician membership
    if new_team.team_lead_id:
        lead_tech = db.query(Technician).filter(Technician.id == new_team.team_lead_id).first()
        if lead_tech:
            lead_tech.team_id = new_team.id
            lead_tech.team = new_team.name
            db.commit()

    return {
        "message": f"Team '{new_team.name}' created successfully",
        "team": new_team.to_dict(include_members=True, db=db)
    }


# -------------------------------------------------------------
# 4. PUT /teams/{team_id} (Update Team - Admin & Manager)
# -------------------------------------------------------------

@router.put("/{team_id}")
def update_team(
    team_id: int,
    payload: TeamUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    old_name = team.name

    if payload.name is not None:
        clean_name = payload.name.strip()
        if clean_name.lower() != old_name.lower():
            dup = db.query(Team).filter(func.lower(Team.name) == clean_name.lower(), Team.id != team.id).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"Another team with name '{clean_name}' already exists.")
            team.name = clean_name
            team.slug = generate_slug(clean_name)

            # Synchronize name across existing linked technicians, rules, and tickets
            db.query(Technician).filter((Technician.team_id == team.id) | (Technician.team == old_name)).update(
                {"team": clean_name, "team_id": team.id}, synchronize_session=False
            )
            db.query(RoutingRule).filter((RoutingRule.team_id == team.id) | (RoutingRule.team == old_name)).update(
                {"team": clean_name, "team_id": team.id}, synchronize_session=False
            )
            db.query(Ticket).filter((Ticket.assigned_team_id == team.id) | (Ticket.assigned_team == old_name)).update(
                {"assigned_team": clean_name, "assigned_team_id": team.id}, synchronize_session=False
            )

    if payload.description is not None:
        team.description = payload.description.strip()

    if payload.team_lead_id is not None:
        if payload.team_lead_id == 0:
            team.team_lead_id = None
        else:
            lead_tech = db.query(Technician).filter(Technician.id == payload.team_lead_id).first()
            if not lead_tech:
                raise HTTPException(status_code=400, detail="Specified team lead technician does not exist.")
            if not lead_tech.is_active:
                raise HTTPException(status_code=400, detail="Cannot assign inactive technician as team lead.")
            team.team_lead_id = lead_tech.id
            lead_tech.team_id = team.id
            lead_tech.team = team.name

    if payload.business_hours_start is not None:
        team.business_hours_start = payload.business_hours_start
    if payload.business_hours_end is not None:
        team.business_hours_end = payload.business_hours_end
    if payload.timezone is not None:
        team.timezone = payload.timezone
    if payload.work_days is not None:
        team.work_days = payload.work_days
    if payload.is_active is not None:
        team.is_active = payload.is_active

    db.commit()
    db.refresh(team)

    return {
        "message": f"Team '{team.name}' updated successfully",
        "team": team.to_dict(include_members=True, db=db)
    }


# -------------------------------------------------------------
# 5. PATCH /teams/{team_id}/status (Activate / Deactivate)
# -------------------------------------------------------------

@router.patch("/{team_id}/status")
def toggle_team_status(
    team_id: int,
    payload: TeamStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if not payload.is_active and not payload.force:
        # Check active workload & active routing rules
        open_tickets_count = db.query(Ticket).filter(
            (Ticket.assigned_team_id == team.id) | (func.lower(Ticket.assigned_team) == team.name.lower()),
            Ticket.status.in_(["new", "in_progress"])
        ).count()

        active_rules_count = db.query(RoutingRule).filter(
            (RoutingRule.team_id == team.id) | (func.lower(RoutingRule.team) == team.name.lower()),
            RoutingRule.is_active == True
        ).count()

        if open_tickets_count > 0 or active_rules_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Cannot deactivate team '{team.name}' because it has active workload or active routing rules.",
                    "open_tickets_count": open_tickets_count,
                    "active_rules_count": active_rules_count,
                    "requires_force": True
                }
            )

    team.is_active = payload.is_active
    db.commit()
    db.refresh(team)

    status_label = "activated" if team.is_active else "deactivated"
    return {
        "message": f"Team '{team.name}' has been {status_label}",
        "team": team.to_dict(include_members=True, db=db)
    }


# -------------------------------------------------------------
# 6. POST /teams/{team_id}/members (Assign Technicians)
# -------------------------------------------------------------

@router.post("/{team_id}/members")
def assign_team_members(
    team_id: int,
    payload: TeamMembersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_manager)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    updated_techs = []
    for tech_id in payload.technician_ids:
        tech = db.query(Technician).filter(Technician.id == tech_id).first()
        if tech:
            tech.team_id = team.id
            tech.team = team.name
            updated_techs.append(tech.name)

    db.commit()
    db.refresh(team)

    return {
        "message": f"Assigned {len(updated_techs)} technician(s) to team '{team.name}'",
        "team": team.to_dict(include_members=True, db=db)
    }


# -------------------------------------------------------------
# 7. DELETE /teams/{team_id} (Delete Team - Admin Only)
# -------------------------------------------------------------

@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_only)
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Safety checks: do not delete if referenced by tickets or routing rules
    tickets_count = db.query(Ticket).filter(
        (Ticket.assigned_team_id == team.id) | (func.lower(Ticket.assigned_team) == team.name.lower())
    ).count()
    if tickets_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete team '{team.name}' because {tickets_count} ticket(s) reference it. Please reassign tickets first or deactivate the team."
        )

    rules_count = db.query(RoutingRule).filter(
        (RoutingRule.team_id == team.id) | (func.lower(RoutingRule.team) == team.name.lower())
    ).count()
    if rules_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete team '{team.name}' because {rules_count} routing rule(s) route to it. Please reassign or delete routing rules first."
        )

    # Detach technicians
    db.query(Technician).filter(Technician.team_id == team.id).update(
        {"team_id": None, "team": "Service Desk"}, synchronize_session=False
    )

    db.delete(team)
    db.commit()

    return {
        "message": f"Team '{team.name}' deleted successfully"
    }
