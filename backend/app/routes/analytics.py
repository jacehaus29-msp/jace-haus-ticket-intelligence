from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models.ticket import Ticket
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.models.user import User
from app.core.auth import get_optional_current_user
from app.services.sla_service import compute_ticket_sla_details, format_duration
from app.services.notification_service import check_and_generate_sla_notifications


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    if isinstance(current_user, User) and current_user.role in ["customer", "technician"]:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Admins and Managers have permission to view operational analytics."
        )
    # Proactively check SLA thresholds to generate alerts if needed
    try:
        check_and_generate_sla_notifications(db)
    except Exception as e:
        print(f"Error checking SLA notifications in analytics: {e}")

    # -----------------------------------------
    # 1. TOTAL TICKETS
    # -----------------------------------------
    all_tickets = db.query(Ticket).all()
    total_tickets = len(all_tickets)

    # -----------------------------------------
    # 2. TICKETS BY PRIORITY
    # -----------------------------------------
    priority_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    priority_results = (
        db.query(
            Ticket.priority,
            func.count(Ticket.id)
        )
        .group_by(Ticket.priority)
        .all()
    )

    for priority, count in priority_results:
        if priority and priority.lower() in priority_counts:
            priority_counts[priority.lower()] = count
        elif priority:
            priority_counts[priority.lower()] = count

    # -----------------------------------------
    # 3. TICKETS BY ASSIGNED TEAM
    # -----------------------------------------
    team_results = (
        db.query(
            Ticket.assigned_team,
            func.count(Ticket.id)
        )
        .group_by(Ticket.assigned_team)
        .all()
    )

    tickets_by_team = {
        (team if team else "Unassigned"): count
        for team, count in team_results
    }

    # -----------------------------------------
    # 4. TICKETS BY CATEGORY
    # -----------------------------------------
    category_results = (
        db.query(
            Ticket.category,
            func.count(Ticket.id)
        )
        .group_by(Ticket.category)
        .all()
    )

    tickets_by_category = {
        (category if category else "General"): count
        for category, count in category_results
    }

    # -----------------------------------------
    # 5. TICKETS BY STATUS
    # -----------------------------------------
    status_counts = {
        "new": 0,
        "in_progress": 0,
        "resolved": 0,
    }

    status_results = (
        db.query(
            Ticket.status,
            func.count(Ticket.id)
        )
        .group_by(Ticket.status)
        .all()
    )

    for status, count in status_results:
        key = status.lower() if status else "new"
        status_counts[key] = count

    # -----------------------------------------
    # 6. ROUTING METHOD DISTRIBUTION & AUTOMATION
    # -----------------------------------------
    routing_results = (
        db.query(
            Ticket.routing_method,
            func.count(Ticket.id)
        )
        .group_by(Ticket.routing_method)
        .all()
    )

    tickets_by_routing = {
        (method if method else "unknown"): count
        for method, count in routing_results
    }

    automated_count = tickets_by_routing.get("rule_engine", 0)
    manual_count = tickets_by_routing.get("manual", 0)

    automation_rate = (
        round((automated_count / total_tickets) * 100)
        if total_tickets > 0
        else 0
    )

    # -----------------------------------------
    # 7. SLA MANAGEMENT & COMPLIANCE METRICS
    # -----------------------------------------
    sla_status_counts = {
        "on_track": 0,
        "at_risk": 0,
        "breached": 0,
        "met": 0,
    }

    sla_by_priority = {
        "critical": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "high": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "medium": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "low": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
    }

    response_times = []
    resolution_times = []

    for ticket in all_tickets:
        sla_info = compute_ticket_sla_details(ticket)
        overall = sla_info["overall_status"]
        if overall in sla_status_counts:
            sla_status_counts[overall] += 1

        p = (ticket.priority or "medium").lower().strip()
        if p in sla_by_priority and overall in sla_by_priority[p]:
            sla_by_priority[p][overall] += 1

        if sla_info.get("response_time_seconds") is not None:
            response_times.append(sla_info["response_time_seconds"])

        if sla_info.get("resolution_time_seconds") is not None and (ticket.status or "").lower() == "resolved":
            resolution_times.append(sla_info["resolution_time_seconds"])

    total_breached_tickets = sla_status_counts["breached"]
    total_at_risk_tickets = sla_status_counts["at_risk"]
    total_on_track_tickets = sla_status_counts["on_track"]
    total_met_tickets = sla_status_counts["met"]

    if total_tickets > 0:
        sla_compliance_rate = round(((total_tickets - total_breached_tickets) / total_tickets) * 100)
    else:
        sla_compliance_rate = 100

    avg_response_seconds = (sum(response_times) / len(response_times)) if response_times else None
    avg_resolution_seconds = (sum(resolution_times) / len(resolution_times)) if resolution_times else None

    avg_response_time_label = format_duration(avg_response_seconds) if avg_response_seconds is not None else "N/A"
    avg_resolution_time_label = format_duration(avg_resolution_seconds) if avg_resolution_seconds is not None else "N/A"

    # -----------------------------------------
    # 8. NOTIFICATIONS & ESCALATIONS METRICS
    # -----------------------------------------
    all_notifications = db.query(Notification).all()
    total_notifications = len(all_notifications)
    unread_notifications = sum(1 for n in all_notifications if not n.is_read)

    sla_at_risk_alerts = sum(1 for n in all_notifications if n.type == "SLA_AT_RISK")
    sla_breaches_alerts = sum(1 for n in all_notifications if n.type == "SLA_BREACHED")
    escalations_count = sum(1 for n in all_notifications if n.type == "ESCALATION")

    notifications_by_severity = {
        "critical": sum(1 for n in all_notifications if n.severity == "critical"),
        "warning": sum(1 for n in all_notifications if n.severity == "warning"),
        "info": sum(1 for n in all_notifications if n.severity == "info"),
    }

    notifications_by_type = {
        "SLA_AT_RISK": sla_at_risk_alerts,
        "SLA_BREACHED": sla_breaches_alerts,
        "ESCALATION": escalations_count,
        "TICKET_ASSIGNED": sum(1 for n in all_notifications if n.type == "TICKET_ASSIGNED"),
        "PRIORITY_CHANGED": sum(1 for n in all_notifications if n.type == "PRIORITY_CHANGED"),
        "STATUS_CHANGED": sum(1 for n in all_notifications if n.type == "STATUS_CHANGED"),
    }

    # -----------------------------------------
    # 9. TECHNICIAN WORKBENCH OPERATIONAL METRICS
    # -----------------------------------------
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    today_date = now_utc.date()

    open_workload = sum(1 for t in all_tickets if (t.status or "new").lower() != "resolved")
    resolved_today = 0
    tickets_resolved_by_team = {}
    escalated_tickets_count = sum(1 for t in all_tickets if (t.escalation_level or 1) > 1)
    escalations_by_level = {
        "level_1": sum(1 for t in all_tickets if (t.escalation_level or 1) == 1),
        "level_2": sum(1 for t in all_tickets if (t.escalation_level or 1) == 2),
        "level_3": sum(1 for t in all_tickets if (t.escalation_level or 1) == 3),
    }
    assigned_tickets_count = sum(1 for t in all_tickets if t.assigned_technician_id is not None)
    unassigned_tickets_count = sum(1 for t in all_tickets if t.assigned_technician_id is None and (t.status or "new") != "resolved")

    for t in all_tickets:
        if (t.status or "").lower() == "resolved":
            team_name = t.assigned_team or "Unassigned"
            tickets_resolved_by_team[team_name] = tickets_resolved_by_team.get(team_name, 0) + 1
            if t.resolved_at and t.resolved_at.date() == today_date:
                resolved_today += 1

    # -----------------------------------------
    # 10. TOP PERFORMERS / METRICS
    # -----------------------------------------
    top_team = None
    top_team_count = 0
    if tickets_by_team:
        top_team = max(tickets_by_team, key=tickets_by_team.get)
        top_team_count = tickets_by_team[top_team]

    top_priority = None
    top_priority_count = 0
    if priority_counts:
        top_priority = max(priority_counts, key=priority_counts.get)
        top_priority_count = priority_counts[top_priority]

    top_category = None
    top_category_count = 0
    if tickets_by_category:
        top_category = max(tickets_by_category, key=tickets_by_category.get)
        top_category_count = tickets_by_category[top_category]

    # -----------------------------------------
    # 11. RECENT TICKET ACTIVITY
    # -----------------------------------------
    recent_audits = (
        db.query(RoutingAudit)
        .order_by(RoutingAudit.id.desc())
        .limit(10)
        .all()
    )

    recent_activity = [
        {
            "id": audit.id,
            "ticket_id": audit.ticket_id,
            "rule": audit.rule,
            "team": audit.team,
            "priority": audit.priority,
            "category": audit.category,
            "routing_method": audit.routing_method,
            "reason": audit.reason,
            "created_at": audit.created_at.isoformat() if audit.created_at else None,
        }
        for audit in recent_audits
    ]

    # -----------------------------------------
    # 11. DYNAMIC SYSTEM & SLA INSIGHTS
    # -----------------------------------------
    insights = []

    if total_tickets > 0:
        insights.append(
            f"SLA Compliance is at {sla_compliance_rate}% ({total_tickets - total_breached_tickets}/{total_tickets} tickets compliant)."
        )

        if escalations_count > 0:
            insights.append(
                f"🚨 {escalations_count} high-priority ticket(s) triggered automatic escalation due to SLA breach."
            )

        if total_at_risk_tickets > 0:
            insights.append(
                f"⚠️ {total_at_risk_tickets} ticket(s) are currently At Risk of breaching their response or resolution SLA."
            )

        if total_breached_tickets > 0:
            insights.append(
                f"🚨 {total_breached_tickets} ticket(s) have breached SLA deadlines and require immediate escalation."
            )

        insights.append(
            f"{automation_rate}% of tickets ({automated_count}/{total_tickets}) are automatically routed by the rule engine."
        )

        if avg_response_time_label != "N/A":
            insights.append(
                f"Average response time is {avg_response_time_label}, and average resolution time is {avg_resolution_time_label}."
            )

        if unread_notifications > 0:
            insights.append(
                f"You have {unread_notifications} unread notification(s) in the notification center."
            )

        if top_team and top_team_count > 0:
            insights.append(
                f"{top_team} is handling the largest share of tickets with {top_team_count} ticket(s) ({round((top_team_count / total_tickets) * 100)}% of volume)."
            )
    else:
        insights.append("No tickets in the system yet. Create tickets to generate live operational and SLA insights.")

    # -----------------------------------------
    # RESPONSE
    # -----------------------------------------
    return {
        "total_tickets": total_tickets,
        "critical_tickets": priority_counts.get("critical", 0),
        "high_priority_tickets": priority_counts.get("high", 0),
        "medium_priority_tickets": priority_counts.get("medium", 0),
        "low_priority_tickets": priority_counts.get("low", 0),
        "tickets_by_priority": priority_counts,
        "tickets_by_team": tickets_by_team,
        "tickets_by_category": tickets_by_category,
        "tickets_by_status": status_counts,
        "tickets_by_routing": tickets_by_routing,
        "automated_count": automated_count,
        "manual_count": manual_count,
        "automation_rate": automation_rate,
        # SLA Metrics
        "sla_compliance_rate": sla_compliance_rate,
        "total_breached_tickets": total_breached_tickets,
        "total_at_risk_tickets": total_at_risk_tickets,
        "total_on_track_tickets": total_on_track_tickets,
        "total_met_tickets": total_met_tickets,
        "sla_status_counts": sla_status_counts,
        "sla_by_priority": sla_by_priority,
        "avg_response_time_seconds": avg_response_seconds,
        "avg_response_time_label": avg_response_time_label,
        "avg_resolution_time_seconds": avg_resolution_seconds,
        "avg_resolution_time_label": avg_resolution_time_label,
        # Notification & Escalation Metrics
        "total_notifications": total_notifications,
        "unread_notifications": unread_notifications,
        "sla_at_risk_alerts": sla_at_risk_alerts,
        "sla_breaches_alerts": sla_breaches_alerts,
        "escalations_count": escalations_count,
        "escalated_tickets_count": escalated_tickets_count,
        "escalations_by_level": escalations_by_level,
        "assigned_tickets_count": assigned_tickets_count,
        "unassigned_tickets_count": unassigned_tickets_count,
        "notifications_by_severity": notifications_by_severity,
        "notifications_by_type": notifications_by_type,
        # Top Performers
        "open_workload": open_workload,
        "resolved_today": resolved_today,
        "tickets_resolved_by_team": tickets_resolved_by_team,
        "top_team": {
            "name": top_team,
            "count": top_team_count
        },
        "top_priority": {
            "name": top_priority,
            "count": top_priority_count
        },
        "top_category": {
            "name": top_category,
            "count": top_category_count
        },
        "recent_activity": recent_activity,
        "insights": insights
    }