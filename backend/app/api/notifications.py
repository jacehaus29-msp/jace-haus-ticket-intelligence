from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.notification import Notification
from app.models.user import User
from app.models.technician import Technician
from app.models.ticket import Ticket
from app.core.auth import require_internal, require_manager_or_admin
from app.services.notification_service import (
    check_and_generate_sla_notifications,
    create_notification
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def apply_notification_scope(
    query,
    current_user: User,
    db: Session,
    scope: str = "all"
):
    """
    Apply role-aware team/queue scoping to the Notification query.
    - Admin & Manager:
        - scope='all': all notifications
        - scope='my_tickets': tickets assigned to their technician_id (if any)
        - scope='my_team': tickets assigned to their team (if linked to technician profile)
    - Technician:
        - scope='my_tickets': only tickets assigned to this technician
        - scope='my_team' or scope='all': only tickets in technician's assigned team (technician cannot see other teams' tickets)
    """
    user_role = (current_user.role or "").lower().strip()
    scope_clean = (scope or "all").lower().strip()

    if user_role in ["admin", "manager"]:
        if scope_clean == "my_tickets":
            if current_user.technician_id:
                query = query.join(Ticket, Notification.ticket_id == Ticket.id).filter(
                    Ticket.assigned_technician_id == current_user.technician_id
                )
            else:
                # No technician assigned to this admin/manager user
                query = query.filter(Notification.id == -1)
        elif scope_clean == "my_team":
            tech = None
            if current_user.technician_id:
                tech = db.query(Technician).filter(Technician.id == current_user.technician_id).first()
            if tech:
                query = query.join(Ticket, Notification.ticket_id == Ticket.id).filter(
                    Ticket.assigned_team == tech.team
                )
            else:
                # Admin/Manager with no team linked: global
                pass
        return query

    if user_role == "technician":
        tech = None
        if current_user.technician_id:
            tech = db.query(Technician).filter(Technician.id == current_user.technician_id).first()
        if not tech and current_user.email:
            tech = db.query(Technician).filter(Technician.email == current_user.email).first()

        if not tech:
            return query.filter(Notification.id == -1)

        if scope_clean == "my_tickets":
            query = query.join(Ticket, Notification.ticket_id == Ticket.id).filter(
                (Ticket.assigned_technician_id == tech.id) |
                (Ticket.assigned_technician == tech.name)
            )
        else:
            # scope='my_team' or default: strictly restricted to technician's team
            query = query.join(Ticket, Notification.ticket_id == Ticket.id).filter(
                Ticket.assigned_team == tech.team
            )
        return query

    # Fallback for unauthorized roles
    return query.filter(Notification.id == -1)


# --------------------------------
# GET /notifications
# --------------------------------

@router.get("/")
def get_notifications(
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = None,
    severity: Optional[str] = None,
    unread_only: bool = False,
    scope: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal)
):
    """
    Get system operational notifications with optional filters and role/team scoping.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    """
    # Proactively check SLA thresholds to generate alerts if needed
    try:
        check_and_generate_sla_notifications(db)
    except Exception as e:
        print(f"Error checking SLA notifications: {e}")

    query = db.query(Notification)
    query = apply_notification_scope(query, current_user, db, scope=scope or "all")

    if unread_only:
        query = query.filter(Notification.is_read == False)

    if type:
        query = query.filter(Notification.type == type.upper())

    if severity:
        query = query.filter(Notification.severity == severity.lower())

    # Get unread count matching the same role scope
    unread_query = db.query(Notification).filter(Notification.is_read == False)
    unread_query = apply_notification_scope(unread_query, current_user, db, scope=scope or "all")
    unread_count = unread_query.count()

    notifications = (
        query
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(notifications),
        "unread_count": unread_count,
        "scope": scope or "all",
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
# GET /notifications/unread-count
# --------------------------------

@router.get("/unread-count")
def get_unread_count(
    scope: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal)
):
    """
    Get unread notification count with optional role/team scoping.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    """
    try:
        check_and_generate_sla_notifications(db)
    except Exception as e:
        print(f"Error checking SLA notifications: {e}")

    query = db.query(Notification).filter(Notification.is_read == False)
    query = apply_notification_scope(query, current_user, db, scope=scope or "all")
    unread_count = query.count()

    return {
        "unread_count": unread_count,
        "scope": scope or "all"
    }


# --------------------------------
# PATCH /notifications/{notification_id}/read
# --------------------------------

@router.patch("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    scope: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal)
):
    """
    Mark a notification as read.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    """
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    notification.is_read = True
    db.commit()
    db.refresh(notification)

    unread_query = db.query(Notification).filter(Notification.is_read == False)
    unread_query = apply_notification_scope(unread_query, current_user, db, scope=scope or "all")
    unread_count = unread_query.count()

    return {
        "id": notification.id,
        "is_read": notification.is_read,
        "unread_count": unread_count,
        "message": "Notification marked as read"
    }


# --------------------------------
# PATCH /notifications/read-all
# --------------------------------

@router.patch("/read-all")
def mark_all_notifications_as_read(
    scope: Optional[str] = Query("all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal)
):
    """
    Mark all notifications matching the current scope as read.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    """
    query = db.query(Notification).filter(Notification.is_read == False)
    query = apply_notification_scope(query, current_user, db, scope=scope or "all")

    notif_ids = [n.id for n in query.all()]
    if notif_ids:
        updated_count = (
            db.query(Notification)
            .filter(Notification.id.in_(notif_ids))
            .update({"is_read": True}, synchronize_session=False)
        )
        db.commit()
    else:
        updated_count = 0

    return {
        "message": "Notifications marked as read",
        "updated_count": updated_count,
        "unread_count": 0
    }


# --------------------------------
# GET /notifications/ticket/{ticket_id}
# --------------------------------

@router.get("/ticket/{ticket_id}")
def get_ticket_notifications_alt(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_internal)
):
    """
    Get notifications associated with a specific ticket.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    Technicians can only access notifications for tickets in their team.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role == "technician":
        tech = None
        if current_user.technician_id:
            tech = db.query(Technician).filter(Technician.id == current_user.technician_id).first()
        if not tech and current_user.email:
            tech = db.query(Technician).filter(Technician.email == current_user.email).first()

        if tech and ticket.assigned_team and ticket.assigned_team != tech.team:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: You do not have permission to view notifications for tickets in '{ticket.assigned_team}'."
            )

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
# DELETE /notifications/clear-read
# --------------------------------

@router.delete("/clear-read")
def clear_read_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    """
    Delete all read notifications from the database.
    Restricted to ADMIN and MANAGER roles.
    """
    deleted_count = (
        db.query(Notification)
        .filter(Notification.is_read == True)
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "deleted_count": deleted_count,
        "message": f"Successfully deleted {deleted_count} read notification(s)."
    }


# --------------------------------
# DELETE /notifications/{notification_id}
# --------------------------------

@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin)
):
    """
    Delete a single notification by ID.
    Restricted to ADMIN and MANAGER roles.
    """
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    db.delete(notification)
    db.commit()

    return {
        "id": notification_id,
        "deleted": True,
        "message": f"Notification #{notification_id} deleted successfully."
    }


# --------------------------------
# GET /notifications/worker-status
# --------------------------------

@router.get("/worker-status")
def get_worker_status(
    current_user: User = Depends(require_internal)
):
    """
    Get diagnostic status of the background SLA & Notification worker.
    Restricted to internal staff (ADMIN, MANAGER, TECHNICIAN).
    """
    from app.services.sla_worker import sla_worker
    return sla_worker.get_status()
