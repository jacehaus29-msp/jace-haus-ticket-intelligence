from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_note import TicketNote
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.services.routing_service import route_ticket
from app.services.sla_service import calculate_sla_deadlines, compute_ticket_sla_details
from app.services.notification_service import (
    notify_ticket_created,
    notify_status_changed,
    create_notification,
    check_and_generate_sla_notifications
)

router = APIRouter(
    prefix="/portal",
    tags=["Client Portal"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from app.models.user import User
from app.core.auth import get_optional_current_user

def get_current_customer(
    db: Session = Depends(get_db),
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id: Optional[int] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user)
) -> Customer:
    """
    Extract and authenticate current customer identity.
    If authenticated as a CUSTOMER user, strictly binds to the customer account associated with that user.
    If authenticated as ADMIN / MANAGER or using API headers, allows specified customer account.
    """
    if isinstance(current_user, User) and current_user.role == "customer":
        if current_user.customer_id:
            cust = db.query(Customer).filter(Customer.id == current_user.customer_id, Customer.is_active == True).first()
            if cust:
                return cust
        # Fallback by email match
        cust = db.query(Customer).filter(Customer.email == current_user.email, Customer.is_active == True).first()
        if cust:
            # Auto-link customer_id on user record for fast indexing
            current_user.customer_id = cust.id
            db.commit()
            return cust
        # Fallback by name match
        cust = db.query(Customer).filter(Customer.name == current_user.name, Customer.is_active == True).first()
        if cust:
            current_user.customer_id = cust.id
            db.commit()
            return cust
        raise HTTPException(status_code=403, detail="No customer account associated with this user.")

    target_id = None
    if isinstance(x_customer_id, str) and x_customer_id.strip().isdigit():
        target_id = int(x_customer_id.strip())
    elif isinstance(customer_id, int):
        target_id = customer_id

    if target_id is not None:
        cust = db.query(Customer).filter(Customer.id == target_id, Customer.is_active == True).first()
        if not cust:
            raise HTTPException(status_code=404, detail=f"Customer with ID {target_id} not found or inactive.")
        return cust

    # Fallback to default active customer
    cust = db.query(Customer).filter(Customer.is_active == True).order_by(Customer.id.asc()).first()
    if not cust:
        raise HTTPException(status_code=404, detail="No active customers found in system.")
    return cust


# -----------------------------------------------------------------------------
# SERIALIZERS (STRICT CUSTOMER-SAFE DATA ONLY)
# -----------------------------------------------------------------------------

def serialize_portal_ticket(ticket: Ticket) -> Dict[str, Any]:
    """Serialize ticket safely for customer view, completely hiding internal scores, rules, and technicians."""
    sla_info = compute_ticket_sla_details(ticket)
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category or "General",
        "priority": ticket.priority or "medium",
        "status": ticket.status or "new",
        "assigned_team": ticket.assigned_team or "Support Desk",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "responded_at": ticket.responded_at.isoformat() if ticket.responded_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "response_due_at": ticket.response_due_at.isoformat() if ticket.response_due_at else None,
        "resolution_due_at": ticket.resolution_due_at.isoformat() if ticket.resolution_due_at else None,
        "sla_status": ticket.sla_status or sla_info.get("overall_status", "on_track"),
        "sla": {
            "overall_status": sla_info.get("overall_status", "on_track"),
            "response_status": sla_info.get("response_status", "on_track"),
            "resolution_status": sla_info.get("resolution_status", "on_track"),
            "response_sla": sla_info.get("response_sla"),
            "resolution_sla": sla_info.get("resolution_sla"),
            "response_remaining_label": sla_info.get("response_remaining_label"),
            "resolution_remaining_label": sla_info.get("resolution_remaining_label")
        },
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_company": ticket.customer_company,
        "source": ticket.source or "portal"
    }


def serialize_portal_activity(audit: RoutingAudit) -> Dict[str, Any]:
    """Serialize audit event safely for customer timeline, sanitizing internal rule names."""
    title = "Ticket Update"
    icon = "📋"

    rule = (audit.rule or "").strip()
    if rule == "Customer Update Added":
        title = "Customer Update Added"
        icon = "📢"
    elif rule == "Work Note Added":
        # Internal work notes should not be passed to customer, but if passed fallback to update
        title = "Technician Note"
        icon = "🔒"
    elif rule == "Ticket Resolved":
        title = "Ticket Resolved"
        icon = "✅"
    elif rule == "Ticket Reopened":
        title = "Ticket Reopened"
        icon = "↻"
    elif rule == "Resolution Confirmed":
        title = "Resolution Confirmed"
        icon = "✓"
    elif rule in ["Response SLA Breached", "Resolution SLA Breached"]:
        title = "SLA Target Update"
        icon = "⏱"
    elif "Status Change" in rule or audit.routing_method == "status_update":
        title = "Status Changed"
        icon = "↻"
    elif audit.routing_method in ["rule_engine", "general_rule", "fallback_rule"] or "Routing" in rule:
        title = "Ticket Created & Assigned"
        icon = "🎫"
    elif audit.routing_method == "technician_assignment":
        title = "Support Specialist Assigned"
        icon = "👤"
    elif audit.routing_method in ["manual_escalation", "escalation_engine"]:
        title = "Priority Escalation"
        icon = "⚡"

    return {
        "id": audit.id,
        "title": title,
        "icon": icon,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
        "team": audit.team,
        "priority": audit.priority,
        "status": audit.routing_method,
        "description": audit.reason or "Ticket activity logged."
    }


# -----------------------------------------------------------------------------
# CUSTOMER IDENTITY & PROFILE ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/customers")
def list_portal_customers(db: Session = Depends(get_db)):
    """List available active customers for portal switcher."""
    customers = db.query(Customer).filter(Customer.is_active == True).order_by(Customer.name.asc()).all()
    return {
        "count": len(customers),
        "customers": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "company": c.company,
                "phone": c.phone
            }
            for c in customers
        ]
    }


@router.get("/profile")
def get_customer_profile(
    customer: Customer = Depends(get_current_customer)
):
    """Retrieve profile of authenticated customer."""
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "company": customer.company,
        "phone": customer.phone,
        "created_at": customer.created_at.isoformat() if customer.created_at else None
    }


class CustomerProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


@router.patch("/profile")
def update_customer_profile(
    payload: CustomerProfileUpdate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Update basic profile info for authenticated customer."""
    if payload.name and payload.name.strip():
        customer.name = payload.name.strip()
    if payload.phone is not None:
        customer.phone = payload.phone.strip()
    if payload.company and payload.company.strip():
        customer.company = payload.company.strip()

    db.commit()
    db.refresh(customer)

    return {
        "message": "Profile updated successfully",
        "profile": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "company": customer.company,
            "phone": customer.phone
        }
    }


# -----------------------------------------------------------------------------
# CUSTOMER DASHBOARD
# -----------------------------------------------------------------------------

@router.get("/dashboard")
def get_customer_dashboard(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Real-time database-driven metrics for the authenticated customer only."""
    customer_tickets = db.query(Ticket).filter(Ticket.customer_id == customer.id).all()
    total_tickets = len(customer_tickets)

    open_tickets = sum(1 for t in customer_tickets if (t.status or "new") in ["new", "in_progress", "awaiting_customer"])
    in_progress_tickets = sum(1 for t in customer_tickets if (t.status or "new") == "in_progress")
    resolved_tickets = sum(1 for t in customer_tickets if (t.status or "new") == "resolved")
    awaiting_customer_tickets = sum(1 for t in customer_tickets if (t.status or "new") == "awaiting_customer")

    recent_tickets = (
        db.query(Ticket)
        .filter(Ticket.customer_id == customer.id)
        .order_by(Ticket.id.desc())
        .limit(5)
        .all()
    )

    ticket_ids = [t.id for t in customer_tickets]
    recent_audits = []
    if ticket_ids:
        raw_audits = (
            db.query(RoutingAudit)
            .filter(
                RoutingAudit.ticket_id.in_(ticket_ids),
                RoutingAudit.rule != "Work Note Added"  # Hide internal work notes
            )
            .order_by(RoutingAudit.id.desc())
            .limit(8)
            .all()
        )
        recent_activity = [serialize_portal_activity(a) for a in raw_audits]
    else:
        recent_activity = []

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "company": customer.company
        },
        "metrics": {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "resolved_tickets": resolved_tickets,
            "awaiting_customer_tickets": awaiting_customer_tickets
        },
        "recent_tickets": [serialize_portal_ticket(t) for t in recent_tickets],
        "recent_activity": recent_activity
    }


# -----------------------------------------------------------------------------
# MY TICKETS & CUSTOMER TICKET SEARCH
# -----------------------------------------------------------------------------

@router.get("/tickets")
def list_customer_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    sla_status: Optional[str] = None,
    search: Optional[str] = None,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    List tickets strictly belonging to the authenticated customer with filtering and search.
    """
    query = db.query(Ticket).filter(Ticket.customer_id == customer.id)

    if status and status != "all":
        if status == "open":
            query = query.filter(Ticket.status.in_(["new", "in_progress", "awaiting_customer"]))
        else:
            query = query.filter(Ticket.status == status)

    if priority and priority != "all":
        query = query.filter(Ticket.priority == priority)

    if category and category != "all":
        query = query.filter(Ticket.category == category)

    if sla_status and sla_status != "all":
        query = query.filter(Ticket.sla_status == sla_status)

    if search and search.strip():
        q = f"%{search.strip().lower()}%"
        query = query.filter(
            (func.lower(Ticket.title).like(q)) |
            (func.lower(Ticket.description).like(q)) |
            (func.cast(Ticket.id, func.TEXT).like(q))
        )

    tickets = query.order_by(Ticket.id.desc()).all()

    return {
        "count": len(tickets),
        "tickets": [serialize_portal_ticket(t) for t in tickets]
    }


# -----------------------------------------------------------------------------
# CUSTOMER TICKET DETAIL
# -----------------------------------------------------------------------------

@router.get("/tickets/{ticket_id}")
def get_customer_ticket_detail(
    ticket_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Retrieve single ticket detail strictly verified by customer ownership.
    Hides all internal technician notes, routing scores, and escalation details.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.customer_id != customer.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: This ticket belongs to another customer account."
        )

    # Fetch customer updates only (exclude internal work notes)
    notes = (
        db.query(TicketNote)
        .filter(
            TicketNote.ticket_id == ticket_id,
            TicketNote.note_type == "customer"
        )
        .order_by(TicketNote.created_at.asc())
        .all()
    )

    # Fetch customer-visible activity events (exclude internal notes)
    audits = (
        db.query(RoutingAudit)
        .filter(
            RoutingAudit.ticket_id == ticket_id,
            RoutingAudit.rule != "Work Note Added"
        )
        .order_by(RoutingAudit.id.asc())
        .all()
    )

    serialized_ticket = serialize_portal_ticket(ticket)
    serialized_notes = [
        {
            "id": n.id,
            "content": n.content,
            "author": n.author,
            "created_at": n.created_at.isoformat() if n.created_at else None
        }
        for n in notes
    ]
    serialized_activity = [serialize_portal_activity(a) for a in audits]

    return {
        "ticket": serialized_ticket,
        "updates": serialized_notes,
        "activity": serialized_activity
    }


# -----------------------------------------------------------------------------
# CUSTOMER TICKET SUBMISSION
# -----------------------------------------------------------------------------

class PortalTicketCreateRequest(BaseModel):
    title: str
    description: str
    category: Optional[str] = None
    priority: Optional[str] = None


@router.post("/tickets")
def create_customer_ticket(
    payload: PortalTicketCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Customer submits a new ticket.
    Executes the existing deterministic routing engine, calculates SLA targets,
    logs activity audit, and emits notifications.
    """
    if not payload.title.strip() or not payload.description.strip():
        raise HTTPException(status_code=400, detail="Subject and description are required.")

    # Run deterministic routing engine
    routing_result = route_ticket(
        {
            "title": payload.title.strip(),
            "description": payload.description.strip(),
            "category": payload.category
        },
        db
    )

    final_priority = payload.priority if payload.priority in ["low", "medium", "high", "critical"] else routing_result.get("priority", "medium")
    final_category = payload.category or routing_result.get("category", "General")
    final_team = routing_result.get("team", "Service Desk")

    # Calculate initial SLA deadlines based on priority
    deadlines = calculate_sla_deadlines(None, final_priority)

    new_ticket = Ticket(
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=final_category,
        assigned_team=final_team,
        priority=final_priority,
        status="new",
        routing_method=routing_result.get("routing_method", "rule_engine"),
        response_due_at=deadlines["response_due_at"],
        resolution_due_at=deadlines["resolution_due_at"],
        sla_status="on_track",
        customer_id=customer.id,
        customer_name=customer.name,
        customer_email=customer.email,
        customer_company=customer.company
    )

    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    # Log to Activity Timeline
    audit = RoutingAudit(
        ticket_id=new_ticket.id,
        rule=routing_result.get("rule", "Customer Ticket Submitted"),
        matched_keywords=routing_result.get("matched_keywords", []),
        match_location=routing_result.get("match_location"),
        score=routing_result.get("score", 0),
        confidence=routing_result.get("confidence", 0),
        team=final_team,
        priority=final_priority,
        category=final_category,
        routing_method=routing_result.get("routing_method", "customer_portal"),
        reason=f"Submitted via Customer Portal by {customer.name} ({customer.company}). Auto-routed to {final_team}."
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    # Emit notification
    try:
        notify_ticket_created(db, new_ticket, routing_result)
        check_and_generate_sla_notifications(db, target_ticket_id=new_ticket.id)
    except Exception as e:
        print(f"Error in portal ticket notifications: {e}")

    return {
        "message": "Ticket created and routed successfully",
        "ticket": serialize_portal_ticket(new_ticket)
    }


# -----------------------------------------------------------------------------
# CUSTOMER COMMUNICATION / REPLIES
# -----------------------------------------------------------------------------

class CustomerUpdateCreate(BaseModel):
    content: str


@router.post("/tickets/{ticket_id}/updates")
def add_customer_ticket_update(
    ticket_id: int,
    payload: CustomerUpdateCreate,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """
    Customer adds a public update/reply to their ticket.
    Visible to both customer and technicians, logged in timeline and notifications.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied to this ticket.")

    clean_content = payload.content.strip()
    if not clean_content:
        raise HTTPException(status_code=400, detail="Update content cannot be blank.")

    note = TicketNote(
        ticket_id=ticket.id,
        note_type="customer",
        content=clean_content,
        author=f"{customer.name} ({customer.company})"
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Log to Activity Timeline
    snippet = clean_content[:120] + ("..." if len(clean_content) > 120 else "")
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Customer Update Added",
        matched_keywords=[],
        match_location="customer_portal",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="customer_note",
        reason=f"[Customer Update] {customer.name}: {snippet}"
    )
    db.add(audit)
    db.commit()

    # Generate Notification for technicians
    try:
        create_notification(
            db=db,
            ticket_id=ticket.id,
            notification_type="CUSTOMER_UPDATE",
            severity="info",
            title=f"Customer Update on Ticket #{ticket.id}",
            message=f"{customer.name} ({customer.company}) added an update to Ticket #{ticket.id} (\"{ticket.title}\").",
            check_duplicate=False
        )
    except Exception as e:
        print(f"Error creating customer update notification: {e}")

    return {
        "message": "Update posted successfully",
        "update": {
            "id": note.id,
            "content": note.content,
            "author": note.author,
            "created_at": note.created_at.isoformat() if note.created_at else None
        }
    }


# -----------------------------------------------------------------------------
# CUSTOMER TICKET REOPENING & CONFIRMATION
# -----------------------------------------------------------------------------

@router.post("/tickets/{ticket_id}/reopen")
def reopen_customer_ticket(
    ticket_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Customer reopens a resolved ticket."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied to this ticket.")

    if ticket.status != "resolved":
        raise HTTPException(status_code=400, detail="Only resolved tickets can be reopened.")

    ticket.status = "in_progress"
    ticket.resolved_at = None

    sla_info = compute_ticket_sla_details(ticket)
    ticket.sla_status = sla_info.get("overall_status", "on_track")

    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Ticket Reopened",
        matched_keywords=[],
        match_location="customer_portal",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="customer_action",
        reason=f"Customer {customer.name} reopened the ticket for further assistance."
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    try:
        notify_status_changed(db, ticket, "resolved", "in_progress")
    except Exception as e:
        print(f"Error notifying ticket reopen: {e}")

    return {
        "message": "Ticket successfully reopened",
        "ticket": serialize_portal_ticket(ticket)
    }


@router.post("/tickets/{ticket_id}/confirm-resolution")
def confirm_ticket_resolution(
    ticket_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Customer confirms ticket resolution."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Access denied to this ticket.")

    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="Resolution Confirmed",
        matched_keywords=[],
        match_location="customer_portal",
        score=0,
        confidence=100,
        team=ticket.assigned_team,
        priority=ticket.priority,
        category=ticket.category or "General",
        routing_method="customer_action",
        reason=f"Customer {customer.name} confirmed the resolution of Ticket #{ticket.id}."
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Ticket resolution confirmed. Thank you!",
        "ticket_id": ticket.id
    }


# -----------------------------------------------------------------------------
# CUSTOMER NOTIFICATIONS
# -----------------------------------------------------------------------------

@router.get("/notifications")
def get_customer_notifications(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Fetch notifications relevant only to the customer's tickets."""
    customer_tickets = db.query(Ticket.id).filter(Ticket.customer_id == customer.id).all()
    ticket_ids = [t[0] for t in customer_tickets]

    if not ticket_ids:
        return {
            "unread_count": 0,
            "notifications": []
        }

    notifications = (
        db.query(Notification)
        .filter(
            Notification.ticket_id.in_(ticket_ids),
            Notification.type != "ESCALATION"  # Internal escalations hidden from client
        )
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )

    unread_count = sum(1 for n in notifications if not n.is_read)

    return {
        "unread_count": unread_count,
        "notifications": [
            {
                "id": n.id,
                "ticket_id": n.ticket_id,
                "type": n.type,
                "severity": n.severity,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None
            }
            for n in notifications
        ]
    }


@router.patch("/notifications/{notification_id}/read")
def mark_customer_notification_read(
    notification_id: int,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Mark a customer notification as read."""
    customer_tickets = db.query(Ticket.id).filter(Ticket.customer_id == customer.id).all()
    ticket_ids = [t[0] for t in customer_tickets]

    notif = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.ticket_id.in_(ticket_ids)
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found.")

    notif.is_read = True
    db.commit()

    return {"message": "Notification marked as read", "id": notif.id}


@router.post("/notifications/mark-all-read")
def mark_all_customer_notifications_read(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    """Mark all customer notifications as read."""
    customer_tickets = db.query(Ticket.id).filter(Ticket.customer_id == customer.id).all()
    ticket_ids = [t[0] for t in customer_tickets]

    if ticket_ids:
        db.query(Notification).filter(
            Notification.ticket_id.in_(ticket_ids),
            Notification.is_read == False
        ).update({"is_read": True}, synchronize_session=False)
        db.commit()

    return {"message": "All notifications marked as read"}
