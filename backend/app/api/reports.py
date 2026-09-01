from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.services.sla_service import compute_ticket_sla_details, format_duration
from app.services.csv_report_service import generate_tickets_csv
from app.services.pdf_report_service import generate_executive_pdf_report

router = APIRouter(
    prefix="/reports",
    tags=["Executive & Client SLA Reporting"]
)


def apply_report_filters(
    query,
    current_user: User,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    customer_id: Optional[int] = None,
    team: Optional[str] = None,
    technician_id: Optional[int] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = None
):
    """
    Apply multi-dimensional filters with strict server-side tenant and role scoping.
    """
    # 1. Server-Side Customer Tenant Isolation
    if current_user.role == "customer":
        # Force customer boundary regardless of any frontend parameter
        if current_user.customer_id:
            query = query.filter(Ticket.customer_id == current_user.customer_id)
        else:
            cust = db.query(Customer).filter(Customer.email == current_user.email).first()
            if cust:
                query = query.filter(Ticket.customer_id == cust.id)
            else:
                query = query.filter(Ticket.customer_company == current_user.company)
    elif current_user.role == "technician":
        # Technicians bounded to their team
        if current_user.technician_id:
            tech = db.query(Technician).filter(Technician.id == current_user.technician_id).first()
            if tech and tech.team:
                query = query.filter(Ticket.assigned_team == tech.team)
    else:
        # Admin / Manager can filter by customer
        if customer_id:
            query = query.filter(Ticket.customer_id == customer_id)

    # 2. Date Range Filtering (created_at)
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            query = query.filter(Ticket.created_at >= start_dt)
        except Exception:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            # If end_date is date only, cover end of day
            if end_dt.hour == 0 and end_dt.minute == 0:
                end_dt = end_dt + timedelta(days=1)
            query = query.filter(Ticket.created_at <= end_dt)
        except Exception:
            pass

    # 3. Dimensional Filters
    if team and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_team == team)

    if technician_id and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_technician_id == technician_id)

    if priority:
        query = query.filter(func.lower(Ticket.priority) == priority.lower().strip())

    if category:
        query = query.filter(func.lower(Ticket.category) == category.lower().strip())

    if status_filter:
        query = query.filter(func.lower(Ticket.status) == status_filter.lower().strip())

    return query


def compute_metrics_for_tickets(tickets: List[Ticket]) -> Dict[str, Any]:
    """Calculate executive KPIs and SLA aggregations across a ticket collection."""
    total_tickets = len(tickets)

    status_counts = {"new": 0, "in_progress": 0, "resolved": 0}
    priority_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    category_counts = {}
    team_counts = {}
    customer_counts = {}

    sla_counts = {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0}
    resp_breaches = 0
    res_breaches = 0
    escalations_count = 0
    automated_count = 0

    response_times = []
    resolution_times = []

    sla_by_priority = {
        "critical": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "high": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "medium": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
        "low": {"on_track": 0, "at_risk": 0, "breached": 0, "met": 0},
    }
    sla_by_team = {}
    sla_by_customer = {}

    for t in tickets:
        st = (t.status or "new").lower()
        if st in status_counts:
            status_counts[st] += 1

        pr = (t.priority or "medium").lower()
        if pr in priority_counts:
            priority_counts[pr] += 1

        cat = t.category or "General"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        tm = t.assigned_team or "Support Desk"
        team_counts[tm] = team_counts.get(tm, 0) + 1

        c_name = t.customer_company or t.customer_name or "Unassigned Client"
        customer_counts[c_name] = customer_counts.get(c_name, 0) + 1

        if (t.escalation_level or 1) > 1:
            escalations_count += 1

        if t.routing_method == "rule_engine":
            automated_count += 1

        sla = compute_ticket_sla_details(t)
        overall = sla.get("overall_status", "on_track")
        if overall in sla_counts:
            sla_counts[overall] += 1

        if sla.get("response_status") == "breached":
            resp_breaches += 1
        if sla.get("resolution_status") == "breached":
            res_breaches += 1

        if pr in sla_by_priority and overall in sla_by_priority[pr]:
            sla_by_priority[pr][overall] += 1

        if tm not in sla_by_team:
            sla_by_team[tm] = {"total": 0, "breached": 0, "met": 0, "on_track": 0, "at_risk": 0}
        sla_by_team[tm]["total"] += 1
        if overall in sla_by_team[tm]:
            sla_by_team[tm][overall] += 1

        if c_name not in sla_by_customer:
            sla_by_customer[c_name] = {"total": 0, "breached": 0, "met": 0, "on_track": 0, "at_risk": 0}
        sla_by_customer[c_name]["total"] += 1
        if overall in sla_by_customer[c_name]:
            sla_by_customer[c_name][overall] += 1

        if sla.get("response_time_seconds") is not None:
            response_times.append(sla["response_time_seconds"])

        if sla.get("resolution_time_seconds") is not None and st == "resolved":
            resolution_times.append(sla["resolution_time_seconds"])

    sla_breaches_total = sla_counts["breached"]
    sla_compliance_rate = (
        round(((total_tickets - sla_breaches_total) / total_tickets) * 100)
        if total_tickets > 0
        else 100
    )
    automation_rate = (
        round((automated_count / total_tickets) * 100)
        if total_tickets > 0
        else 0
    )

    avg_resp_sec = (sum(response_times) / len(response_times)) if response_times else None
    avg_res_sec = (sum(resolution_times) / len(resolution_times)) if resolution_times else None

    return {
        "total_tickets": total_tickets,
        "new_tickets": status_counts["new"],
        "in_progress_tickets": status_counts["in_progress"],
        "resolved_tickets": status_counts["resolved"],
        "open_tickets": status_counts["new"] + status_counts["in_progress"],
        "status_counts": status_counts,
        "sla_compliance_rate": sla_compliance_rate,
        "sla_breaches": sla_breaches_total,
        "response_sla_breaches": resp_breaches,
        "resolution_sla_breaches": res_breaches,
        "sla_at_risk": sla_counts["at_risk"],
        "sla_met": sla_counts["met"],
        "sla_on_track": sla_counts["on_track"],
        "avg_response_time_seconds": avg_resp_sec,
        "avg_response_time_label": format_duration(avg_resp_sec) if avg_resp_sec is not None else "N/A",
        "avg_resolution_time_seconds": avg_res_sec,
        "avg_resolution_time_label": format_duration(avg_res_sec) if avg_res_sec is not None else "N/A",
        "escalation_count": escalations_count,
        "automated_count": automated_count,
        "automation_rate": automation_rate,
        "tickets_by_priority": priority_counts,
        "tickets_by_category": category_counts,
        "tickets_by_team": team_counts,
        "tickets_by_customer": customer_counts,
        "sla_by_priority": sla_by_priority,
        "sla_by_team": sla_by_team,
        "sla_by_customer": sla_by_customer,
    }


def resolve_organization_name(current_user: User, db: Session, customer_id: Optional[int] = None) -> str:
    if current_user.role == "customer":
        if current_user.customer_id:
            cust = db.query(Customer).filter(Customer.id == current_user.customer_id).first()
            if cust:
                return cust.company or cust.name
        return current_user.company or current_user.name
    elif customer_id:
        cust = db.query(Customer).filter(Customer.id == customer_id).first()
        if cust:
            return cust.company or cust.name
    return "All MSP Organizations"


# -----------------------------------------------------------------------------
# 1. EXECUTIVE SUMMARY REPORT ENDPOINT
# -----------------------------------------------------------------------------

@router.get("/summary")
def get_reports_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate executive KPI summary metrics with filter parameters and tenant isolation.
    """
    query = db.query(Ticket)
    query = apply_report_filters(
        query=query,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        team=team,
        technician_id=technician_id,
        priority=priority,
        category=category,
        status_filter=status,
        db=db
    )

    tickets = query.order_by(Ticket.created_at.desc()).all()
    metrics = compute_metrics_for_tickets(tickets)
    org_name = resolve_organization_name(current_user, db, customer_id)

    # Sanitize team breakdown for customer users
    if current_user.role == "customer":
        metrics["tickets_by_team"] = {"MSP Support Desk": metrics["total_tickets"]}
        metrics["sla_by_team"] = {}

    return {
        "organization_name": org_name,
        "is_customer_view": current_user.role == "customer",
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "team": team if current_user.role != "customer" else None,
            "priority": priority,
            "category": category,
            "status": status,
        },
        "summary": metrics
    }


# -----------------------------------------------------------------------------
# 2. SLA DETAILED PERFORMANCE REPORT ENDPOINT
# -----------------------------------------------------------------------------

@router.get("/sla")
def get_reports_sla(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate detailed SLA performance report containing compliance rates and breakdowns.
    """
    query = db.query(Ticket)
    query = apply_report_filters(
        query=query,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        team=team,
        priority=priority,
        db=db
    )

    tickets = query.all()
    metrics = compute_metrics_for_tickets(tickets)

    sla_report = {
        "total_evaluated": metrics["total_tickets"],
        "overall_sla_compliance_rate": metrics["sla_compliance_rate"],
        "response_sla_breaches": metrics["response_sla_breaches"],
        "resolution_sla_breaches": metrics["resolution_sla_breaches"],
        "total_sla_breaches": metrics["sla_breaches"],
        "at_risk_tickets": metrics["sla_at_risk"],
        "avg_response_time_label": metrics["avg_response_time_label"],
        "avg_resolution_time_label": metrics["avg_resolution_time_label"],
        "sla_by_priority": metrics["sla_by_priority"],
        "sla_by_team": metrics["sla_by_team"] if current_user.role != "customer" else {},
        "sla_by_customer": metrics["sla_by_customer"] if current_user.role in ["admin", "manager"] else {},
    }

    return {
        "organization_name": resolve_organization_name(current_user, db, customer_id),
        "sla": sla_report
    }


# -----------------------------------------------------------------------------
# 3. FILTERED TICKET LIST REPORT ENDPOINT
# -----------------------------------------------------------------------------

@router.get("/tickets")
def get_reports_tickets(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve sanitized list of tickets matching filters for report preview tables.
    """
    query = db.query(Ticket)
    query = apply_report_filters(
        query=query,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        team=team,
        technician_id=technician_id,
        priority=priority,
        category=category,
        status_filter=status,
        db=db
    )

    tickets = query.order_by(Ticket.created_at.desc()).limit(limit).all()

    results = []
    is_cust = current_user.role == "customer"
    for t in tickets:
        sla = compute_ticket_sla_details(t)
        results.append({
            "id": t.id,
            "title": t.title,
            "category": t.category or "General",
            "priority": t.priority or "medium",
            "status": t.status or "new",
            "assigned_team": t.assigned_team if not is_cust else "Support Desk",
            "assigned_technician": t.assigned_technician if not is_cust else "MSP Engineer",
            "customer_name": t.customer_name,
            "customer_company": t.customer_company,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "responded_at": t.responded_at.isoformat() if t.responded_at else None,
            "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            "response_due_at": t.response_due_at.isoformat() if t.response_due_at else None,
            "resolution_due_at": t.resolution_due_at.isoformat() if t.resolution_due_at else None,
            "sla_status": sla.get("overall_status", "on_track"),
            "response_time_label": sla.get("response_time_label", "N/A"),
            "resolution_time_label": sla.get("resolution_time_label", "N/A"),
            "escalation_level": t.escalation_level or 1,
            "source": t.source or "manual"
        })

    return {
        "count": len(results),
        "tickets": results
    }


# -----------------------------------------------------------------------------
# 4. CSV EXPORT ENDPOINT
# -----------------------------------------------------------------------------

@router.get("/export/csv")
def export_reports_csv(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream sanitized CSV export containing ticket records and SLA performance.
    """
    query = db.query(Ticket)
    query = apply_report_filters(
        query=query,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        team=team,
        technician_id=technician_id,
        priority=priority,
        category=category,
        status_filter=status,
        db=db
    )

    tickets = query.order_by(Ticket.created_at.desc()).all()
    is_cust = current_user.role == "customer"
    csv_content = generate_tickets_csv(tickets, is_customer_view=is_cust)

    filename = f"msp_ticket_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


# -----------------------------------------------------------------------------
# 5. PDF EXECUTIVE REPORT ENDPOINT
# -----------------------------------------------------------------------------

@router.get("/export/pdf")
def export_reports_pdf(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream high-resolution executive PDF report suitable for client QBRs and SLA audits.
    """
    query = db.query(Ticket)
    query = apply_report_filters(
        query=query,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
        customer_id=customer_id,
        team=team,
        technician_id=technician_id,
        priority=priority,
        category=category,
        status_filter=status,
        db=db
    )

    tickets = query.order_by(Ticket.created_at.desc()).all()
    summary_metrics = compute_metrics_for_tickets(tickets)
    sla_metrics = {
        "sla_by_priority": summary_metrics["sla_by_priority"],
        "sla_by_team": summary_metrics["sla_by_team"],
        "sla_by_customer": summary_metrics["sla_by_customer"],
    }

    serialized_tickets = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "status": t.status,
            "sla_status": compute_ticket_sla_details(t).get("overall_status", "on_track")
        }
        for t in tickets
    ]

    is_cust = current_user.role == "customer"
    org_name = resolve_organization_name(current_user, db, customer_id)

    filter_dict = {
        "start_date": start_date,
        "end_date": end_date,
        "team": team if not is_cust else None,
        "priority": priority,
        "category": category,
        "status": status,
    }

    pdf_bytes = generate_executive_pdf_report(
        summary_data=summary_metrics,
        sla_data=sla_metrics,
        tickets_data=serialized_tickets,
        filters=filter_dict,
        organization_name=org_name,
        is_customer_view=is_cust
    )

    clean_org_slug = org_name.lower().replace(" ", "_")[:20]
    filename = f"executive_sla_report_{clean_org_slug}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )
