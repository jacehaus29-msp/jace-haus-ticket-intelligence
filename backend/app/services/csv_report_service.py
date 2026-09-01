import csv
import io
from typing import List, Any
from app.services.sla_service import compute_ticket_sla_details, format_duration


def generate_tickets_csv(tickets: List[Any], is_customer_view: bool = False) -> str:
    """
    Generate CSV data string for a collection of tickets.
    Computes real-time SLA metrics for each ticket.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Ticket ID",
        "Created Date (UTC)",
        "Customer Name",
        "Company / Organization",
        "Title",
        "Category",
        "Priority",
        "Status",
        "Assigned Team",
        "Assigned Technician",
        "Response Due (UTC)",
        "Resolution Due (UTC)",
        "Responded At (UTC)",
        "Resolved At (UTC)",
        "Response Time",
        "Resolution Time",
        "Response SLA Status",
        "Resolution SLA Status",
        "Overall SLA Status",
        "Escalation Level",
        "Source",
    ]

    writer.writerow(headers)

    for t in tickets:
        sla = compute_ticket_sla_details(t)

        created_str = t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else ""
        resp_due_str = t.response_due_at.strftime("%Y-%m-%d %H:%M:%S") if t.response_due_at else ""
        res_due_str = t.resolution_due_at.strftime("%Y-%m-%d %H:%M:%S") if t.resolution_due_at else ""
        resp_at_str = t.responded_at.strftime("%Y-%m-%d %H:%M:%S") if t.responded_at else ""
        res_at_str = t.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if t.resolved_at else ""

        resp_time_str = sla.get("response_time_label") or "N/A"
        res_time_str = sla.get("resolution_time_label") or "N/A"

        tech_display = t.assigned_technician or "Unassigned"
        if is_customer_view:
            # Customer view uses generic team assignment
            tech_display = "MSP Support Team"

        row = [
            t.id,
            created_str,
            t.customer_name or "N/A",
            t.customer_company or "N/A",
            t.title or "",
            t.category or "General",
            (t.priority or "medium").upper(),
            (t.status or "new").replace("_", " ").upper(),
            t.assigned_team or "Support Desk",
            tech_display,
            resp_due_str,
            res_due_str,
            resp_at_str,
            res_at_str,
            resp_time_str,
            res_time_str,
            (sla.get("response_status") or "on_track").replace("_", " ").upper(),
            (sla.get("resolution_status") or "on_track").replace("_", " ").upper(),
            (sla.get("overall_status") or "on_track").replace("_", " ").upper(),
            t.escalation_level or 1,
            t.source or "manual",
        ]
        writer.writerow(row)

    return output.getvalue()
