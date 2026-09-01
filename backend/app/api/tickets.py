from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.models.technician import Technician
from app.models.team import Team
from app.models.user import User
from app.core.auth import get_optional_current_user
from app.database import SessionLocal
from app.models.ticket import Ticket
from app.models.ticket_note import TicketNote
from app.services.routing_service import route_ticket
from app.services.sla_service import calculate_sla_deadlines, compute_ticket_sla_details
from app.services.notification_service import (
    notify_ticket_created,
    notify_priority_changed,
    notify_status_changed,
    notify_technician_assigned,
    notify_ticket_escalated,
    notify_ticket_resolved,
    check_and_generate_sla_notifications
)


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_internal_ticket_access(user: Optional[User]):
    if isinstance(user, User) and user.role == "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Customers must use the Client Portal to access and manage tickets."
        )


class TicketRequest(BaseModel):
    title: str
    description: str


# --------------------------------
# POST /tickets/route
# --------------------------------

@router.post("/route")
def route_ticket_endpoint(
    ticket: TicketRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)

    # Run routing engine
    result = route_ticket(
        ticket.model_dump(),
        db
    )

    # Calculate initial SLA deadlines based on priority
    deadlines = calculate_sla_deadlines(None, result.get("priority"))

    # Create database record
    new_ticket = Ticket(
        title=ticket.title,
        description=ticket.description,
        category=result.get("category"),
        assigned_team=result["team"],
        priority=result["priority"],
        routing_method=result["routing_method"],
        response_due_at=deadlines["response_due_at"],
        resolution_due_at=deadlines["resolution_due_at"],
        sla_status="on_track"
    )

    # Save to PostgreSQL
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    # Save routing decision to audit history
    audit = RoutingAudit(
        ticket_id=new_ticket.id,
        rule=result.get("rule"),
        matched_keywords=result.get("matched_keywords", []),
        match_location=result.get("match_location"),
        score=result.get("score", 0),
        confidence=result.get("confidence", 0),
        team=result.get("team"),
        priority=result.get("priority"),
        category=result.get("category"),
        routing_method=result.get("routing_method"),
        reason=result.get("reason")
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    # Generate assignment notification and check SLA
    try:
        notify_ticket_created(db, new_ticket, result)
        check_and_generate_sla_notifications(db, target_ticket_id=new_ticket.id)
    except Exception as e:
        print(f"Notification error on ticket creation: {e}")

    sla_details = compute_ticket_sla_details(new_ticket)

    return {
        "ticket_id": new_ticket.id,
        "ticket": {
            "title": new_ticket.title,
            "description": new_ticket.description
        },
        "decision": {
            "team": new_ticket.assigned_team,
            "priority": new_ticket.priority,
            "routing_method": new_ticket.routing_method,
            "category": new_ticket.category,
            "matched_keywords": result.get("matched_keywords", []),
            "match_location": result.get("match_location"),
            "confidence": result.get("confidence"),
            "reason": result.get("reason"),
            "score": result.get("score"),
            "rule": result.get("rule")
        },
        "sla": sla_details,
        "status": "saved"
    }


# --------------------------------
# GET /tickets/
# --------------------------------

@router.get("/")
def get_tickets(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)

    tickets = (
        db.query(Ticket)
        .order_by(Ticket.id.desc())
        .all()
    )

    ticket_list = []
    for ticket in tickets:
        sla_info = compute_ticket_sla_details(ticket)
        ticket_list.append({
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "category": ticket.category,
            "assigned_team": ticket.assigned_team,
            "assigned_technician_id": ticket.assigned_technician_id,
            "assigned_technician": ticket.assigned_technician,
            "escalation_level": ticket.escalation_level or 1,
            "escalation_reason": ticket.escalation_reason,
            "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
            "escalated_by": ticket.escalated_by,
            "priority": ticket.priority,
            "status": ticket.status,
            "source": ticket.source or "manual",
            "customer_id": ticket.customer_id,
            "customer_name": ticket.customer_name,
            "customer_email": ticket.customer_email,
            "customer_company": ticket.customer_company,
            "email_sender": ticket.email_sender,
            "routing_method": ticket.routing_method,
            "response_due_at": ticket.response_due_at,
            "resolution_due_at": ticket.resolution_due_at,
            "responded_at": ticket.responded_at,
            "resolved_at": ticket.resolved_at,
            "resolution_summary": ticket.resolution_summary,
            "resolution_details": ticket.resolution_details,
            "sla_status": sla_info["overall_status"],
            "sla": sla_info,
            "created_at": ticket.created_at
        })

    return {
        "count": len(tickets),
        "tickets": ticket_list
    }


# --------------------------------
# GET /tickets/{ticket_id}
# --------------------------------

@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)

    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        return {
            "error": "Ticket not found"
        }

    sla_info = compute_ticket_sla_details(ticket)

    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "assigned_team": ticket.assigned_team,
        "assigned_technician_id": ticket.assigned_technician_id,
        "assigned_technician": ticket.assigned_technician,
        "escalation_level": ticket.escalation_level or 1,
        "escalation_reason": ticket.escalation_reason,
        "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
        "escalated_by": ticket.escalated_by,
        "priority": ticket.priority,
        "status": ticket.status,
        "source": ticket.source or "manual",
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "customer_company": ticket.customer_company,
        "email_sender": ticket.email_sender,
        "routing_method": ticket.routing_method,
        "response_due_at": ticket.response_due_at,
        "resolution_due_at": ticket.resolution_due_at,
        "responded_at": ticket.responded_at,
        "resolved_at": ticket.resolved_at,
        "resolution_summary": ticket.resolution_summary,
        "resolution_details": ticket.resolution_details,
        "sla_status": sla_info["overall_status"],
        "sla": sla_info,
        "created_at": ticket.created_at
    }

# --------------------------------
# GET /tickets/{ticket_id}/audit
# --------------------------------

@router.get("/{ticket_id}/audit")
def get_ticket_audit(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)
    audit = (
        db.query(RoutingAudit)
        .filter(
            RoutingAudit.ticket_id == ticket_id,
            RoutingAudit.routing_method == "rule_engine"
        )
        .order_by(RoutingAudit.id.desc())
        .first()
    )

    if not audit:
        return {
            "error": "No routing audit found for this ticket"
        }

    return {
        "id": audit.id,
        "ticket_id": audit.ticket_id,
        "rule": audit.rule,
        "matched_keywords": audit.matched_keywords or [],
        "match_location": audit.match_location,
        "score": audit.score,
        "confidence": audit.confidence,
        "team": audit.team,
        "priority": audit.priority,
        "category": audit.category,
        "routing_method": audit.routing_method,
        "reason": audit.reason,
        "created_at": audit.created_at
    }
# --------------------------------
# GET /tickets/{ticket_id}/audit/history
# --------------------------------

@router.get("/{ticket_id}/audit/history")
def get_ticket_audit_history(
    ticket_id: int,
    db: Session = Depends(get_db)
):
    audits = (
        db.query(RoutingAudit)
        .filter(RoutingAudit.ticket_id == ticket_id)
        .order_by(RoutingAudit.id.desc())
        .all()
    )

    return {
        "ticket_id": ticket_id,
        "count": len(audits),
        "history": [
            {
                "id": audit.id,
                "rule": audit.rule,
                "matched_keywords": audit.matched_keywords or [],
                "match_location": audit.match_location,
                "score": audit.score,
                "confidence": audit.confidence,
                "team": audit.team,
                "priority": audit.priority,
                "category": audit.category,
                "routing_method": audit.routing_method,
                "reason": audit.reason,
                "created_at": audit.created_at
            }
            for audit in audits
        ]
    }


# --------------------------------
# GET /tickets/{ticket_id}/notifications
# --------------------------------

@router.get("/{ticket_id}/notifications")
def get_ticket_notifications(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)
    try:
        check_and_generate_sla_notifications(db, target_ticket_id=ticket_id)
    except Exception as e:
        print(f"Error checking ticket SLA notification: {e}")

    notifications = (
        db.query(Notification)
        .filter(Notification.ticket_id == ticket_id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    return {
        "ticket_id": ticket_id,
        "count": len(notifications),
        "notifications": [
            {
                "id": n.id,
                "ticket_id": n.ticket_id,
                "type": n.type,
                "severity": n.severity,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ]
    }


# --------------------------------
# PATCH /tickets/{ticket_id}/status
# --------------------------------

class StatusUpdate(BaseModel):
    status: str
    resolution_summary: Optional[str] = None
    resolution_details: Optional[str] = None


@router.patch("/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    status_update: StatusUpdate,
    db: Session = Depends(get_db)
):

    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        return {
            "error": "Ticket not found"
        }

    allowed_statuses = [
        "new",
        "in_progress",
        "resolved"
    ]

    if status_update.status not in allowed_statuses:
        return {
            "error": "Invalid status",
            "allowed_statuses": allowed_statuses
        }
    if ticket.status == status_update.status and status_update.status != "resolved":
        return {
            "error": "Ticket is already in this status",
            "status": ticket.status
        }
    old_status = ticket.status
    new_status = status_update.status

    ticket.status = new_status

    # Manage response, resolution timestamps & resolution details
    now_utc = func.now()
    audit_rule = "Status Change"
    if new_status == "in_progress":
        if not ticket.responded_at:
            ticket.responded_at = now_utc
        if old_status == "resolved":
            ticket.resolved_at = None
            audit_rule = "Ticket Reopened"
            audit_reason = f"Ticket reopened: status transitioned from {old_status} to {new_status}."
        else:
            audit_reason = f"Ticket status changed from {old_status} to {new_status}."
    elif new_status == "resolved":
        if not ticket.responded_at:
            ticket.responded_at = now_utc
        ticket.resolved_at = now_utc
        if status_update.resolution_summary is not None:
            ticket.resolution_summary = status_update.resolution_summary
        if status_update.resolution_details is not None:
            ticket.resolution_details = status_update.resolution_details
        audit_rule = "Ticket Resolved"
        audit_reason = (
            f"Ticket resolved: {ticket.resolution_summary}"
            if ticket.resolution_summary
            else "Ticket resolved by technician."
        )
    elif new_status == "new":
        if old_status == "resolved":
            ticket.resolved_at = None
            audit_rule = "Ticket Reopened"
            audit_reason = f"Ticket reopened: status reset to new."
        else:
            ticket.resolved_at = None
            audit_reason = f"Ticket status changed from {old_status} to {new_status}."

    # Create an audit record for the status change or resolution
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule=audit_rule,
        matched_keywords=[],
        match_location="status",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="status_update",
        reason=audit_reason
    )

    db.add(audit)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit)

    sla_info = compute_ticket_sla_details(ticket)
    ticket.sla_status = sla_info["overall_status"]
    db.commit()
    db.refresh(ticket)

    # Generate status change notification and check SLA
    try:
        notify_status_changed(db, ticket, old_status, new_status)
        if new_status == "resolved":
            notify_ticket_resolved(db, ticket)
        check_and_generate_sla_notifications(db, target_ticket_id=ticket.id)
    except Exception as e:
        print(f"Notification error on status change: {e}")

    return {
        "id": ticket.id,
        "status": ticket.status,
        "responded_at": ticket.responded_at,
        "resolved_at": ticket.resolved_at,
        "resolution_summary": ticket.resolution_summary,
        "resolution_details": ticket.resolution_details,
        "sla_status": ticket.sla_status,
        "sla": sla_info,
        "message": f"Ticket {new_status} updated successfully"
    }


# --------------------------------
# WORK NOTES & CUSTOMER UPDATES
# --------------------------------

class NoteCreate(BaseModel):
    note_type: str = "internal"  # "internal" or "customer"
    content: str
    author: str = "Technician"


class NoteUpdate(BaseModel):
    content: str
    author: Optional[str] = None


@router.get("/{ticket_id}/notes")
def get_ticket_notes(
    ticket_id: int,
    db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"error": "Ticket not found", "count": 0, "notes": []}

    notes = (
        db.query(TicketNote)
        .filter(TicketNote.ticket_id == ticket_id)
        .order_by(TicketNote.created_at.desc())
        .all()
    )

    return {
        "ticket_id": ticket_id,
        "count": len(notes),
        "notes": [
            {
                "id": n.id,
                "ticket_id": n.ticket_id,
                "note_type": n.note_type,
                "content": n.content,
                "author": n.author,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in notes
        ]
    }


@router.post("/{ticket_id}/notes")
def add_ticket_note(
    ticket_id: int,
    note_data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"error": "Ticket not found"}

    note_type = (note_data.note_type or "internal").lower().strip()
    if note_type not in ["internal", "customer"]:
        note_type = "internal"

    author = note_data.author
    if isinstance(current_user, User) and current_user.name:
        author = current_user.name
    elif not author:
        author = "Technician"

    note = TicketNote(
        ticket_id=ticket_id,
        note_type=note_type,
        content=note_data.content,
        author=author
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Record in Activity Timeline
    rule_label = "Work Note Added" if note_type == "internal" else "Customer Update Added"
    snippet = note.content[:120] + ("..." if len(note.content) > 120 else "")
    audit = RoutingAudit(
        ticket_id=ticket_id,
        rule=rule_label,
        matched_keywords=[],
        match_location="note",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="technician_note",
        reason=f"[{'Internal Work Note' if note_type == 'internal' else 'Customer Update'}] {note.author}: {snippet}"
    )
    db.add(audit)
    db.commit()

    return {
        "id": note.id,
        "ticket_id": note.ticket_id,
        "note_type": note.note_type,
        "content": note.content,
        "author": note.author,
        "email_dispatched": False,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "message": "Note added successfully"
    }


@router.put("/{ticket_id}/notes/{note_id}")
def update_ticket_note(
    ticket_id: int,
    note_id: int,
    note_data: NoteUpdate,
    db: Session = Depends(get_db)
):
    note = (
        db.query(TicketNote)
        .filter(TicketNote.id == note_id, TicketNote.ticket_id == ticket_id)
        .first()
    )
    if not note:
        return {"error": "Note not found"}

    note.content = note_data.content
    if note_data.author:
        note.author = note_data.author
    note.updated_at = func.now()
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "ticket_id": note.ticket_id,
        "note_type": note.note_type,
        "content": note.content,
        "author": note.author,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "message": "Note updated successfully"
    }


@router.delete("/{ticket_id}/notes/{note_id}")
def delete_ticket_note(
    ticket_id: int,
    note_id: int,
    db: Session = Depends(get_db)
):
    note = (
        db.query(TicketNote)
        .filter(TicketNote.id == note_id, TicketNote.ticket_id == ticket_id)
        .first()
    )
    if not note:
        return {"error": "Note not found"}

    db.delete(note)
    db.commit()
    return {"message": "Note deleted successfully", "id": note_id}


# --------------------------------
# PATCH /tickets/{ticket_id}/team
# --------------------------------

class TeamUpdate(BaseModel):
    team: str


@router.patch("/{ticket_id}/team")
def update_ticket_team(
    ticket_id: int,
    team_update: TeamUpdate,
    db: Session = Depends(get_db)
):

    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        return {
            "error": "Ticket not found"
        }

    active_team_records = db.query(Team).filter(Team.is_active == True).all()
    active_teams_map = {t.name.lower(): t for t in active_team_records}
    
    if not active_teams_map:
        fallback_list = ["M365 Support", "Network Team", "Security Team", "Endpoint Team", "Backup Team", "Application Support", "Service Desk"]
        active_teams_map = {name.lower(): None for name in fallback_list}

    matched_team = active_teams_map.get(team_update.team.strip().lower())
    if matched_team is None and team_update.team.strip().lower() not in active_teams_map:
        allowed_names = [t.name for t in active_team_records] or ["M365 Support", "Network Team", "Security Team", "Endpoint Team", "Backup Team", "Application Support", "Service Desk"]
        return {
            "error": "Invalid team",
            "allowed_teams": allowed_names
        }

    ticket.assigned_team = matched_team.name if matched_team else team_update.team.strip()
    ticket.assigned_team_id = matched_team.id if matched_team else None

    # Mark that this ticket was manually routed
    ticket.routing_method = "manual"

    # Create an audit record for the manual routing decision
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Manual Reassignment",
        matched_keywords=[],
        match_location="manual",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="manual",
        reason=(
            f"Ticket manually re-routed to "
            f"{ticket.assigned_team}."
        )
    )

    db.add(audit)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit)

    sla_info = compute_ticket_sla_details(ticket)

    return {
        "id": ticket.id,
        "assigned_team": ticket.assigned_team,
        "routing_method": ticket.routing_method,
        "sla": sla_info,
        "message": "Ticket re-routed successfully"
    }


# --------------------------------
# PATCH /tickets/{ticket_id}/priority
# --------------------------------

class PriorityUpdate(BaseModel):
    priority: str


@router.patch("/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: int,
    priority_update: PriorityUpdate,
    db: Session = Depends(get_db)
):

    ticket = (
        db.query(Ticket)
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        return {
            "error": "Ticket not found"
        }

    allowed_priorities = [
        "critical",
        "high",
        "medium",
        "low"
    ]

    if priority_update.priority not in allowed_priorities:
        return {
            "error": "Invalid priority",
            "allowed_priorities": allowed_priorities
        }

    # Remember the previous priority
    old_priority = ticket.priority

    # Do nothing if priority hasn't actually changed
    if old_priority == priority_update.priority:
        sla_info = compute_ticket_sla_details(ticket)
        return {
            "id": ticket.id,
            "priority": ticket.priority,
            "response_due_at": ticket.response_due_at,
            "resolution_due_at": ticket.resolution_due_at,
            "sla_status": ticket.sla_status,
            "sla": sla_info,
            "message": "Priority unchanged"
        }

    # Update ticket priority
    ticket.priority = priority_update.priority

    # Recalculate SLA deadlines based on new priority and original creation time
    deadlines = calculate_sla_deadlines(ticket.created_at, priority_update.priority)
    ticket.response_due_at = deadlines["response_due_at"]
    ticket.resolution_due_at = deadlines["resolution_due_at"]

    # Create audit record
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Priority Change",
        matched_keywords=[],
        match_location="none",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="priority_update",
        reason=(
            f"Ticket priority changed from "
            f"{old_priority} to {priority_update.priority}. SLA deadlines updated."
        )
    )

    db.add(audit)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit)

    sla_info = compute_ticket_sla_details(ticket)
    ticket.sla_status = sla_info["overall_status"]
    db.commit()
    db.refresh(ticket)

    # Generate priority change notification and check SLA
    try:
        notify_priority_changed(db, ticket, old_priority, priority_update.priority)
        check_and_generate_sla_notifications(db, target_ticket_id=ticket.id)
    except Exception as e:
        print(f"Notification error on priority change: {e}")

    return {
        "id": ticket.id,
        "priority": ticket.priority,
        "response_due_at": ticket.response_due_at,
        "resolution_due_at": ticket.resolution_due_at,
        "sla_status": ticket.sla_status,
        "sla": sla_info,
        "routing_method": ticket.routing_method,
        "message": "Ticket priority updated successfully"
    }


# --------------------------------
# PATCH /tickets/{ticket_id}/technician
# --------------------------------

class TechnicianAssignRequest(BaseModel):
    technician_id: Optional[int] = None
    assigned_by: Optional[str] = "Dispatcher"


@router.patch("/{ticket_id}/technician")
def assign_ticket_technician(
    ticket_id: int,
    payload: TechnicianAssignRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"error": "Ticket not found"}

    assigned_by = payload.assigned_by
    if isinstance(current_user, User) and current_user.name:
        assigned_by = current_user.name
    elif not assigned_by:
        assigned_by = "Dispatcher"

    if payload.technician_id is not None:
        tech = db.query(Technician).filter(Technician.id == payload.technician_id).first()
        if not tech:
            return {"error": "Technician not found"}
        if not tech.is_active:
            return {"error": f"Technician {tech.name} is inactive and cannot be assigned to tickets."}
        
        # Validate that technician belongs to the ticket's assigned team
        if (tech.team or "").strip().lower() != (ticket.assigned_team or "").strip().lower():
            return {
                "error": f"Technician {tech.name} belongs to '{tech.team}', but ticket is assigned to '{ticket.assigned_team}'."
            }

        ticket.assigned_technician_id = tech.id
        ticket.assigned_technician = tech.name
        audit_rule = "Technician Assigned"
        audit_reason = f"Ticket assigned to {tech.name} ({tech.team}) by {assigned_by}."
        tech_name = tech.name
    else:
        old_tech = ticket.assigned_technician or "technician"
        ticket.assigned_technician_id = None
        ticket.assigned_technician = None
        audit_rule = "Technician Unassigned"
        audit_reason = f"Ticket unassigned from {old_tech} by {assigned_by}."
        tech_name = None

    # Log to Activity Timeline
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule=audit_rule,
        matched_keywords=[],
        match_location="technician_assignment",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="technician_assignment",
        reason=audit_reason
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit)

    if tech_name:
        try:
            notify_technician_assigned(db, ticket, tech_name, assigned_by)
        except Exception as e:
            print(f"Error notifying technician assignment: {e}")

    sla_info = compute_ticket_sla_details(ticket)

    return {
        "id": ticket.id,
        "assigned_team": ticket.assigned_team,
        "assigned_technician_id": ticket.assigned_technician_id,
        "assigned_technician": ticket.assigned_technician,
        "escalation_level": ticket.escalation_level or 1,
        "sla": sla_info,
        "message": f"Technician {tech_name or 'unassigned'} updated successfully"
    }


# --------------------------------
# POST /tickets/{ticket_id}/escalate
# --------------------------------

class EscalateTicketRequest(BaseModel):
    escalation_level: int
    escalation_reason: str
    escalated_by: Optional[str] = "Technician"


@router.post("/{ticket_id}/escalate")
def escalate_ticket_endpoint(
    ticket_id: int,
    payload: EscalateTicketRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_internal_ticket_access(current_user)
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return {"error": "Ticket not found"}

    if payload.escalation_level not in [2, 3]:
        return {"error": "Invalid escalation level. Must be Level 2 (Team Escalation) or Level 3 (Specialist Escalation)."}

    current_level = ticket.escalation_level or 1
    if payload.escalation_level <= current_level:
        return {
            "error": f"Ticket is already at escalation Level {current_level}. Escalation must move upward to a higher level."
        }

    if not payload.escalation_reason or not payload.escalation_reason.strip():
        return {"error": "Escalation reason is required and cannot be blank."}

    clean_reason = payload.escalation_reason.strip()
    escalator = payload.escalated_by
    if isinstance(current_user, User) and current_user.name:
        escalator = current_user.name
    elif not escalator:
        escalator = "Technician"

    ticket.escalation_level = payload.escalation_level
    ticket.escalation_reason = clean_reason
    ticket.escalated_at = func.now()
    ticket.escalated_by = escalator

    level_label = "Level 2 (Team Escalation)" if payload.escalation_level == 2 else "Level 3 (Specialist Escalation)"
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Ticket Escalated",
        matched_keywords=[],
        match_location="escalation",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="manual_escalation",
        reason=f"[{level_label}] {clean_reason} (Escalated by {escalator})"
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)
    db.refresh(audit)

    try:
        notify_ticket_escalated(db, ticket, payload.escalation_level, clean_reason, escalator)
    except Exception as e:
        print(f"Error notifying ticket escalation: {e}")

    sla_info = compute_ticket_sla_details(ticket)

    return {
        "id": ticket.id,
        "escalation_level": ticket.escalation_level,
        "escalation_reason": ticket.escalation_reason,
        "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
        "escalated_by": ticket.escalated_by,
        "sla": sla_info,
        "message": f"Ticket successfully escalated to {level_label}"
    }


# --------------------------------
# DELETE /tickets/
# Delete all tickets and their audit history
# --------------------------------

@router.delete("/")
def delete_all_tickets(
    db: Session = Depends(get_db)
):
    # Delete notes first
    db.query(TicketNote).delete(
        synchronize_session=False
    )

    # Delete notifications
    db.query(Notification).delete(
        synchronize_session=False
    )

    # Delete audit records
    db.query(RoutingAudit).delete(
        synchronize_session=False
    )

    # Delete all tickets
    deleted_count = db.query(Ticket).delete(
        synchronize_session=False
    )

    db.commit()

    return {
        "message": "All tickets deleted successfully",
        "deleted_count": deleted_count
    }