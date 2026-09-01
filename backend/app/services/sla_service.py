from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# SLA duration configuration based on priority
SLA_CONFIG: Dict[str, Dict[str, Any]] = {
    "critical": {
        "response_time": timedelta(minutes=15),
        "resolution_time": timedelta(hours=2),
        "response_label": "15m",
        "resolution_label": "2h",
        "at_risk_threshold_percent": 0.25,
    },
    "high": {
        "response_time": timedelta(minutes=30),
        "resolution_time": timedelta(hours=4),
        "response_label": "30m",
        "resolution_label": "4h",
        "at_risk_threshold_percent": 0.25,
    },
    "medium": {
        "response_time": timedelta(hours=1),
        "resolution_time": timedelta(hours=8),
        "response_label": "1h",
        "resolution_label": "8h",
        "at_risk_threshold_percent": 0.25,
    },
    "low": {
        "response_time": timedelta(hours=4),
        "resolution_time": timedelta(hours=24),
        "response_label": "4h",
        "resolution_label": "24h",
        "at_risk_threshold_percent": 0.25,
    },
}


def get_sla_config(priority: Optional[str]) -> Dict[str, Any]:
    """Retrieve SLA configuration for a given priority."""
    p = (priority or "medium").lower().strip()
    return SLA_CONFIG.get(p, SLA_CONFIG["medium"])


def calculate_sla_deadlines(created_at: Optional[datetime], priority: Optional[str]) -> Dict[str, datetime]:
    """Calculate response and resolution deadlines from creation timestamp and priority."""
    config = get_sla_config(priority)
    base_time = created_at if created_at else datetime.now(timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    return {
        "response_due_at": base_time + config["response_time"],
        "resolution_due_at": base_time + config["resolution_time"],
    }


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string (e.g., '14m', '1h 30m')."""
    if seconds is None:
        return "N/A"
    
    total_seconds = int(abs(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return "< 1m"


def compute_ticket_sla_details(ticket: Any, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Compute full SLA evaluation details for a ticket.
    Determines status: 'on_track', 'at_risk', 'breached', 'met', or 'not_started'.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Resolve created_at
    created_at = ticket.created_at or now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    priority = (ticket.priority or "medium").lower().strip()
    config = get_sla_config(priority)

    # Deadlines (backfill from created_at if not stored)
    response_due_at = ticket.response_due_at or (created_at + config["response_time"])
    if response_due_at.tzinfo is None:
        response_due_at = response_due_at.replace(tzinfo=timezone.utc)

    resolution_due_at = ticket.resolution_due_at or (created_at + config["resolution_time"])
    if resolution_due_at.tzinfo is None:
        resolution_due_at = resolution_due_at.replace(tzinfo=timezone.utc)

    responded_at = ticket.responded_at
    if responded_at and responded_at.tzinfo is None:
        responded_at = responded_at.replace(tzinfo=timezone.utc)

    resolved_at = ticket.resolved_at
    if resolved_at and resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)

    status = (ticket.status or "new").lower().strip()

    # -----------------------------------------------------------------
    # 1. Response SLA Evaluation
    # -----------------------------------------------------------------
    if responded_at:
        response_breached = responded_at > response_due_at
        response_status = "breached" if response_breached else "met"
        response_time_seconds = max(0, (responded_at - created_at).total_seconds())
        response_remaining_seconds = 0
        response_time_label = format_duration(response_time_seconds)
        response_remaining_label = "Responded"
    elif status in ["in_progress", "resolved"]:
        # If in_progress or resolved but responded_at wasn't saved, consider responded at current time
        response_breached = now > response_due_at
        response_status = "breached" if response_breached else "met"
        response_time_seconds = max(0, (now - created_at).total_seconds())
        response_remaining_seconds = 0
        response_time_label = format_duration(response_time_seconds)
        response_remaining_label = "Responded"
    else:
        # Not responded yet
        response_time_seconds = None
        response_time_label = None
        
        diff = (response_due_at - now).total_seconds()
        if diff < 0:
            response_breached = True
            response_status = "breached"
            response_remaining_seconds = 0
            response_remaining_label = f"Overdue by {format_duration(abs(diff))}"
        else:
            response_breached = False
            response_remaining_seconds = diff
            # Check at_risk threshold (within 25% of total response duration)
            at_risk_seconds = config["response_time"].total_seconds() * config["at_risk_threshold_percent"]
            if diff <= at_risk_seconds:
                response_status = "at_risk"
            else:
                response_status = "on_track"
            response_remaining_label = f"{format_duration(diff)} left"

    # -----------------------------------------------------------------
    # 2. Resolution SLA Evaluation
    # -----------------------------------------------------------------
    if resolved_at or status == "resolved":
        effective_resolved_at = resolved_at or now
        resolution_breached = effective_resolved_at > resolution_due_at
        resolution_status = "breached" if resolution_breached else "met"
        resolution_time_seconds = max(0, (effective_resolved_at - created_at).total_seconds())
        resolution_remaining_seconds = 0
        resolution_time_label = format_duration(resolution_time_seconds)
        resolution_remaining_label = "Resolved"
    else:
        # Not resolved yet
        resolution_time_seconds = None
        resolution_time_label = None
        
        diff = (resolution_due_at - now).total_seconds()
        if diff < 0:
            resolution_breached = True
            resolution_status = "breached"
            resolution_remaining_seconds = 0
            resolution_remaining_label = f"Overdue by {format_duration(abs(diff))}"
        else:
            resolution_breached = False
            resolution_remaining_seconds = diff
            # Check at_risk threshold (within 25% of total resolution duration)
            at_risk_seconds = config["resolution_time"].total_seconds() * config["at_risk_threshold_percent"]
            if diff <= at_risk_seconds:
                resolution_status = "at_risk"
            else:
                resolution_status = "on_track"
            resolution_remaining_label = f"{format_duration(diff)} left"

    # -----------------------------------------------------------------
    # 3. Overall SLA Status Determination
    # -----------------------------------------------------------------
    if status == "resolved":
        if response_status == "breached" or resolution_status == "breached":
            overall_status = "breached"
        else:
            overall_status = "met"
    else:
        if response_status == "breached" or resolution_status == "breached":
            overall_status = "breached"
        elif response_status == "at_risk" or resolution_status == "at_risk":
            overall_status = "at_risk"
        else:
            overall_status = "on_track"

    return {
        "priority": priority,
        "response_sla": config["response_label"],
        "resolution_sla": config["resolution_label"],
        "response_due_at": response_due_at.isoformat(),
        "resolution_due_at": resolution_due_at.isoformat(),
        "responded_at": responded_at.isoformat() if responded_at else None,
        "resolved_at": resolved_at.isoformat() if resolved_at else None,
        "response_status": response_status,
        "resolution_status": resolution_status,
        "overall_status": overall_status,
        "response_time_label": response_time_label,
        "resolution_time_label": resolution_time_label,
        "response_remaining_label": response_remaining_label,
        "resolution_remaining_label": resolution_remaining_label,
        "response_remaining_seconds": response_remaining_seconds,
        "resolution_remaining_seconds": resolution_remaining_seconds,
        "response_time_seconds": response_time_seconds,
        "resolution_time_seconds": resolution_time_seconds,
    }
