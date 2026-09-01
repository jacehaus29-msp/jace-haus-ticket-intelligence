from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.notification import Notification
from app.models.ticket import Ticket
from app.models.routing_audit import RoutingAudit
from app.services.sla_service import compute_ticket_sla_details


def create_notification(
    db: Session,
    ticket_id: Optional[int],
    notification_type: str,
    severity: str,
    title: str,
    message: str,
    check_duplicate: bool = True
) -> Notification:
    """
    Create a persistent notification with optional deduplication.
    Returns the created (or existing) Notification instance.
    """
    if check_duplicate and ticket_id is not None:
        # Check if an identical notification already exists for this ticket
        existing = (
            db.query(Notification)
            .filter(
                Notification.ticket_id == ticket_id,
                Notification.type == notification_type,
                Notification.title == title
            )
            .first()
        )
        if existing:
            return existing

    notification = Notification(
        ticket_id=ticket_id,
        type=notification_type,
        severity=severity,
        title=title,
        message=message,
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def check_and_generate_sla_notifications(
    db: Session,
    target_ticket_id: Optional[int] = None
) -> List[Notification]:
    """
    Scan tickets to detect SLA at-risk conditions, SLA breaches, and automatic escalations.
    Generates persistent notifications and audit timeline events when new thresholds are met.
    """
    now = datetime.now(timezone.utc)
    generated_notifications = []

    if target_ticket_id is not None:
        tickets = db.query(Ticket).filter(Ticket.id == target_ticket_id).all()
    else:
        tickets = db.query(Ticket).all()

    for ticket in tickets:
        sla_info = compute_ticket_sla_details(ticket, now)
        ticket_priority = (ticket.priority or "medium").lower().strip()
        ticket_status = (ticket.status or "new").lower().strip()

        # -------------------------------------------------------------
        # 1. RESPONSE SLA - AT RISK
        # -------------------------------------------------------------
        if sla_info.get("response_status") == "at_risk" and ticket_status == "new":
            title = f"Response SLA At Risk - Ticket #{ticket.id}"
            message = (
                f"Ticket #{ticket.id} (\"{ticket.title}\") is approaching its response SLA deadline. "
                f"{sla_info.get('response_remaining_label', 'Deadline approaching')}. "
                f"Assigned Team: {ticket.assigned_team}, Priority: {ticket_priority.upper()}."
            )
            existing = (
                db.query(Notification)
                .filter(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "SLA_AT_RISK",
                    Notification.title == title
                )
                .first()
            )
            if not existing:
                notif = create_notification(
                    db=db,
                    ticket_id=ticket.id,
                    notification_type="SLA_AT_RISK",
                    severity="warning",
                    title=title,
                    message=message
                )
                generated_notifications.append(notif)

        # -------------------------------------------------------------
        # 2. RESOLUTION SLA - AT RISK
        # -------------------------------------------------------------
        if sla_info.get("resolution_status") == "at_risk" and ticket_status in ["new", "in_progress"]:
            title = f"Resolution SLA At Risk - Ticket #{ticket.id}"
            message = (
                f"Ticket #{ticket.id} (\"{ticket.title}\") is approaching its resolution SLA deadline. "
                f"{sla_info.get('resolution_remaining_label', 'Deadline approaching')}. "
                f"Assigned Team: {ticket.assigned_team}, Priority: {ticket_priority.upper()}."
            )
            existing = (
                db.query(Notification)
                .filter(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "SLA_AT_RISK",
                    Notification.title == title
                )
                .first()
            )
            if not existing:
                notif = create_notification(
                    db=db,
                    ticket_id=ticket.id,
                    notification_type="SLA_AT_RISK",
                    severity="warning",
                    title=title,
                    message=message
                )
                generated_notifications.append(notif)

        # -------------------------------------------------------------
        # 3. RESPONSE SLA - BREACHED
        # -------------------------------------------------------------
        if sla_info.get("response_status") == "breached":
            title = f"Response SLA Breached - Ticket #{ticket.id}"
            message = (
                f"Ticket #{ticket.id} (\"{ticket.title}\") has breached its guaranteed response SLA "
                f"({sla_info.get('response_sla', 'target')}). Assigned Team: {ticket.assigned_team}, "
                f"Priority: {ticket_priority.upper()}."
            )
            existing = (
                db.query(Notification)
                .filter(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "SLA_BREACHED",
                    Notification.title == title
                )
                .first()
            )
            if not existing:
                notif = create_notification(
                    db=db,
                    ticket_id=ticket.id,
                    notification_type="SLA_BREACHED",
                    severity="critical",
                    title=title,
                    message=message
                )
                generated_notifications.append(notif)

                # Add to ticket activity timeline if not already recorded
                audit_exists = (
                    db.query(RoutingAudit)
                    .filter(
                        RoutingAudit.ticket_id == ticket.id,
                        RoutingAudit.rule == "Response SLA Breached"
                    )
                    .first()
                )
                if not audit_exists:
                    audit = RoutingAudit(
                        ticket_id=ticket.id,
                        rule="Response SLA Breached",
                        matched_keywords=[],
                        match_location="sla",
                        score=0,
                        confidence=100,
                        team=ticket.assigned_team,
                        priority=ticket.priority,
                        category=ticket.category or "General",
                        routing_method="sla_monitor",
                        reason=f"Response SLA deadline ({sla_info.get('response_sla')}) exceeded for ticket #{ticket.id}."
                    )
                    db.add(audit)
                    db.commit()

        # -------------------------------------------------------------
        # 4. RESOLUTION SLA - BREACHED & ESCALATION
        # -------------------------------------------------------------
        if sla_info.get("resolution_status") == "breached":
            title = f"Resolution SLA Breached - Ticket #{ticket.id}"
            message = (
                f"Ticket #{ticket.id} (\"{ticket.title}\") has breached its guaranteed resolution SLA "
                f"({sla_info.get('resolution_sla', 'target')}). Assigned Team: {ticket.assigned_team}, "
                f"Priority: {ticket_priority.upper()}."
            )
            existing = (
                db.query(Notification)
                .filter(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "SLA_BREACHED",
                    Notification.title == title
                )
                .first()
            )
            if not existing:
                notif = create_notification(
                    db=db,
                    ticket_id=ticket.id,
                    notification_type="SLA_BREACHED",
                    severity="critical",
                    title=title,
                    message=message
                )
                generated_notifications.append(notif)

                # Add to ticket activity timeline if not already recorded
                audit_exists = (
                    db.query(RoutingAudit)
                    .filter(
                        RoutingAudit.ticket_id == ticket.id,
                        RoutingAudit.rule == "Resolution SLA Breached"
                    )
                    .first()
                )
                if not audit_exists:
                    audit = RoutingAudit(
                        ticket_id=ticket.id,
                        rule="Resolution SLA Breached",
                        matched_keywords=[],
                        match_location="sla",
                        score=0,
                        confidence=100,
                        team=ticket.assigned_team,
                        priority=ticket.priority,
                        category=ticket.category or "General",
                        routing_method="sla_monitor",
                        reason=f"Resolution SLA deadline ({sla_info.get('resolution_sla')}) exceeded for ticket #{ticket.id}."
                    )
                    db.add(audit)
                    db.commit()

            # ---------------------------------------------------------
            # 5. AUTOMATIC ESCALATION FOR CRITICAL & HIGH TICKETS
            # ---------------------------------------------------------
            if ticket_priority in ["critical", "high"]:
                esc_title = f"🚨 Escalation Required - Ticket #{ticket.id}"
                esc_message = (
                    f"Critical SLA breach: Ticket #{ticket.id} (\"{ticket.title}\") "
                    f"({ticket_priority.upper()} priority, assigned to {ticket.assigned_team}) "
                    f"has breached its resolution deadline and requires immediate escalation."
                )
                esc_existing = (
                    db.query(Notification)
                    .filter(
                        Notification.ticket_id == ticket.id,
                        Notification.type == "ESCALATION",
                        Notification.title == esc_title
                    )
                    .first()
                )
                if not esc_existing:
                    esc_notif = create_notification(
                        db=db,
                        ticket_id=ticket.id,
                        notification_type="ESCALATION",
                        severity="critical",
                        title=esc_title,
                        message=esc_message
                    )
                    generated_notifications.append(esc_notif)

                    # Log escalation event in activity timeline
                    esc_audit_exists = (
                        db.query(RoutingAudit)
                        .filter(
                            RoutingAudit.ticket_id == ticket.id,
                            RoutingAudit.rule == "Escalation Triggered"
                        )
                        .first()
                    )
                    if not esc_audit_exists:
                        audit_esc = RoutingAudit(
                            ticket_id=ticket.id,
                            rule="Escalation Triggered",
                            matched_keywords=[],
                            match_location="escalation",
                            score=0,
                            confidence=100,
                            team=ticket.assigned_team,
                            priority=ticket.priority,
                            category=ticket.category or "General",
                            routing_method="escalation_engine",
                            reason=f"Automatic escalation triggered: {ticket_priority.upper()} priority ticket #{ticket.id} breached resolution SLA."
                        )
                        db.add(audit_esc)
                        db.commit()

    return generated_notifications


def notify_ticket_created(db: Session, ticket: Ticket, decision: Dict[str, Any]) -> Notification:
    """Create notification when a ticket is created and routed."""
    prio = (ticket.priority or "medium").lower()
    severity = "critical" if prio == "critical" else "warning" if prio == "high" else "info"

    title = f"Ticket #{ticket.id} Assigned to {ticket.assigned_team}"
    message = (
        f"Ticket #{ticket.id} (\"{ticket.title}\") routed to {ticket.assigned_team} "
        f"with {prio.upper()} priority ({ticket.routing_method})."
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="TICKET_ASSIGNED",
        severity=severity,
        title=title,
        message=message,
        check_duplicate=False
    )


def notify_priority_changed(
    db: Session,
    ticket: Ticket,
    old_priority: str,
    new_priority: str
) -> Notification:
    """Create notification when ticket priority is modified."""
    p_new = (new_priority or "medium").lower()
    severity = "critical" if p_new == "critical" else "warning" if p_new == "high" else "info"

    title = f"Priority Changed: Ticket #{ticket.id}"
    message = (
        f"Ticket #{ticket.id} priority changed from {old_priority.upper()} to {new_priority.upper()}. "
        f"SLA response and resolution deadlines updated."
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="PRIORITY_CHANGED",
        severity=severity,
        title=title,
        message=message,
        check_duplicate=False
    )


def notify_status_changed(
    db: Session,
    ticket: Ticket,
    old_status: str,
    new_status: str
) -> Notification:
    """Create notification when ticket status is changed."""
    title = f"Status Changed: Ticket #{ticket.id}"
    message = f"Ticket #{ticket.id} status changed from {old_status} to {new_status}."
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="STATUS_CHANGED",
        severity="info",
        title=title,
        message=message,
        check_duplicate=False
    )


def notify_technician_assigned(
    db: Session,
    ticket: Ticket,
    technician_name: str,
    assigned_by: str = "Dispatcher"
) -> Notification:
    """Create notification when a ticket is assigned to a specific technician."""
    prio = (ticket.priority or "medium").lower()
    severity = "critical" if prio == "critical" else "warning" if prio == "high" else "info"

    title = f"Ticket #{ticket.id} Assigned to {technician_name}"
    message = (
        f"Ticket #{ticket.id} (\"{ticket.title}\") in {ticket.assigned_team} has been "
        f"assigned to {technician_name} by {assigned_by}."
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="TICKET_ASSIGNED",
        severity=severity,
        title=title,
        message=message,
        check_duplicate=False
    )


def notify_ticket_escalated(
    db: Session,
    ticket: Ticket,
    escalation_level: int,
    reason: str,
    escalated_by: str = "Technician"
) -> Notification:
    """Create notification when a ticket is escalated."""
    level_label = (
        "Level 2 — Team Escalation" if escalation_level == 2
        else "Level 3 — Specialist Escalation" if escalation_level == 3
        else f"Level {escalation_level}"
    )
    title = f"🚨 Ticket #{ticket.id} Escalated to Level {escalation_level}"
    message = (
        f"Ticket #{ticket.id} (\"{ticket.title}\") in {ticket.assigned_team} was escalated to "
        f"{level_label} by {escalated_by}. Reason: {reason}"
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="ESCALATION",
        severity="critical",
        title=title,
        message=message,
        check_duplicate=False
    )


def notify_ticket_resolved(
    db: Session,
    ticket: Ticket
) -> Notification:
    """Create customer-facing resolution and feedback invitation notification."""
    title = f"Ticket #{ticket.id} Resolved — Feedback Requested"
    message = (
        f"Ticket #{ticket.id} (\"{ticket.title}\") has been marked as resolved. "
        f"How did we do? Please share your resolution rating in the Customer Portal."
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="TICKET_RESOLVED",
        severity="info",
        title=title,
        message=message,
        check_duplicate=True
    )


def notify_low_csat_rating(
    db: Session,
    ticket: Ticket,
    rating: int,
    customer_name: str,
    customer_company: str,
    feedback: Optional[str] = None
) -> Notification:
    """Create internal alert notification for Admins/Managers when a customer submits a low CSAT rating (1-2 stars)."""
    title = f"Low CSAT Alert ({rating}★) — Ticket #{ticket.id}"
    fb_text = f' "{feedback.strip()}"' if feedback and feedback.strip() else " No written comments provided."
    message = (
        f"Customer {customer_name} ({customer_company}) rated Ticket #{ticket.id} (\"{ticket.title}\") "
        f"{rating}/5 stars.{fb_text} Assigned Team: {ticket.assigned_team}."
    )
    return create_notification(
        db=db,
        ticket_id=ticket.id,
        notification_type="CSAT_ALERT",
        severity="warning" if rating == 2 else "critical",
        title=title,
        message=message,
        check_duplicate=True
    )


