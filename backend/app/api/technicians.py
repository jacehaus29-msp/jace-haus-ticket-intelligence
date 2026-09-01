from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models.technician import Technician
from app.models.team import Team
from app.models.ticket import Ticket
from app.models.user import User
from app.core.auth import get_optional_current_user


router = APIRouter(
    prefix="/technicians",
    tags=["Technicians"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_technicians_read_permission(user: Optional[User]):
    if isinstance(user, User) and user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Customers do not have permission to view technician information."
        )


def check_technicians_write_permission(user: Optional[User]):
    if isinstance(user, User) and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Admins have permission to create or modify technician accounts."
        )


class TechnicianCreateRequest(BaseModel):
    name: str
    email: str
    team: str
    is_active: Optional[bool] = True


class TechnicianUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    team: Optional[str] = None
    is_active: Optional[bool] = None


def get_technician_workload(db: Session, technician_id: int):
    """
    Calculate real-time workload for a given technician.
    Active workload includes tickets with status 'new' or 'in_progress'.
    Resolved tickets are excluded from active workload.
    """
    active_tickets = (
        db.query(Ticket)
        .filter(
            Ticket.assigned_technician_id == technician_id,
            Ticket.status.in_(["new", "in_progress"])
        )
        .all()
    )
    
    critical_count = sum(1 for t in active_tickets if (t.priority or "").lower() == "critical")
    high_count = sum(1 for t in active_tickets if (t.priority or "").lower() == "high")
    total_assigned = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.assigned_technician_id == technician_id)
        .scalar() or 0
    )

    return {
        "active_workload": len(active_tickets),
        "critical_workload": critical_count,
        "high_workload": high_count,
        "total_assigned": total_assigned,
        "active_ticket_ids": [t.id for t in active_tickets]
    }


# -------------------------------------------------------------
# GET /technicians/
# -------------------------------------------------------------
@router.get("/")
def get_technicians(
    team: Optional[str] = Query(None, description="Filter by team"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_technicians_read_permission(current_user)
    query = db.query(Technician)

    if isinstance(team, str) and team.lower() != "all":
        query = query.filter(Technician.team == team)

    if isinstance(is_active, bool):
        query = query.filter(Technician.is_active == is_active)

    technicians = query.order_by(Technician.team.asc(), Technician.name.asc()).all()

    # Compute live workloads for each technician
    results = []
    for tech in technicians:
        workload = get_technician_workload(db, tech.id)
        results.append({
            "id": tech.id,
            "name": tech.name,
            "email": tech.email,
            "team": tech.team,
            "is_active": tech.is_active,
            "active_workload": workload["active_workload"],
            "critical_workload": workload["critical_workload"],
            "high_workload": workload["high_workload"],
            "total_assigned": workload["total_assigned"],
            "created_at": tech.created_at.isoformat() if tech.created_at else None
        })

    return {
        "count": len(results),
        "technicians": results
    }


# -------------------------------------------------------------
# GET /technicians/{id}
# -------------------------------------------------------------
@router.get("/{technician_id}")
def get_technician_by_id(
    technician_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_technicians_read_permission(current_user)
    tech = db.query(Technician).filter(Technician.id == technician_id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")

    workload = get_technician_workload(db, tech.id)

    # Fetch active tickets details
    active_tickets = (
        db.query(Ticket)
        .filter(
            Ticket.assigned_technician_id == tech.id,
            Ticket.status.in_(["new", "in_progress"])
        )
        .order_by(Ticket.created_at.desc())
        .all()
    )

    tickets_data = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "sla_status": t.sla_status,
            "escalation_level": t.escalation_level or 1,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in active_tickets
    ]

    return {
        "id": tech.id,
        "name": tech.name,
        "email": tech.email,
        "team": tech.team,
        "is_active": tech.is_active,
        "active_workload": workload["active_workload"],
        "critical_workload": workload["critical_workload"],
        "high_workload": workload["high_workload"],
        "total_assigned": workload["total_assigned"],
        "active_tickets": tickets_data,
        "created_at": tech.created_at.isoformat() if tech.created_at else None
    }


# -------------------------------------------------------------
# GET /technicians/{id}/workload
# -------------------------------------------------------------
@router.get("/{technician_id}/workload")
def get_technician_workload_endpoint(
    technician_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_technicians_read_permission(current_user)
    tech = db.query(Technician).filter(Technician.id == technician_id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")

    workload = get_technician_workload(db, tech.id)

    return {
        "technician_id": tech.id,
        "technician_name": tech.name,
        "team": tech.team,
        "is_active": tech.is_active,
        "active_workload": workload["active_workload"],
        "critical_workload": workload["critical_workload"],
        "high_workload": workload["high_workload"],
        "total_assigned": workload["total_assigned"]
    }


# -------------------------------------------------------------
# POST /technicians/
# -------------------------------------------------------------
@router.post("/", status_code=201)
def create_technician(
    payload: TechnicianCreateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_technicians_write_permission(current_user)
    existing = db.query(Technician).filter(Technician.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Technician with this email already exists")

    clean_team = payload.team.strip()
    team_entity = db.query(Team).filter(func.lower(Team.name) == clean_team.lower()).first()
    team_id = team_entity.id if team_entity else None
    team_name = team_entity.name if team_entity else clean_team

    new_tech = Technician(
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        team_id=team_id,
        team=team_name,
        is_active=payload.is_active if payload.is_active is not None else True
    )
    db.add(new_tech)
    db.commit()
    db.refresh(new_tech)

    return {
        "message": f"Technician '{new_tech.name}' created successfully",
        "technician": {
            "id": new_tech.id,
            "name": new_tech.name,
            "email": new_tech.email,
            "team_id": new_tech.team_id,
            "team": new_tech.team,
            "is_active": new_tech.is_active,
            "created_at": new_tech.created_at.isoformat() if new_tech.created_at else None
        }
    }


# -------------------------------------------------------------
# PATCH /technicians/{id}
# -------------------------------------------------------------
@router.patch("/{technician_id}")
def update_technician(
    technician_id: int,
    payload: TechnicianUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_technicians_write_permission(current_user)
    tech = db.query(Technician).filter(Technician.id == technician_id).first()
    if not tech:
        raise HTTPException(status_code=404, detail="Technician not found")

    if payload.name is not None:
        tech.name = payload.name.strip()
    if payload.email is not None:
        tech.email = payload.email.strip().lower()
    if payload.team is not None:
        clean_team = payload.team.strip()
        team_entity = db.query(Team).filter(func.lower(Team.name) == clean_team.lower()).first()
        tech.team_id = team_entity.id if team_entity else None
        tech.team = team_entity.name if team_entity else clean_team
    if payload.is_active is not None:
        tech.is_active = payload.is_active

    db.commit()
    db.refresh(tech)

    return {
        "message": f"Technician '{tech.name}' updated successfully",
        "technician": {
            "id": tech.id,
            "name": tech.name,
            "email": tech.email,
            "team_id": tech.team_id,
            "team": tech.team,
            "is_active": tech.is_active,
            "created_at": tech.created_at.isoformat() if tech.created_at else None
        }
    }
