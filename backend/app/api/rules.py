from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.team import Team
from app.models.routing_rule import RoutingRule
from app.models.ticket import Ticket
from app.models.routing_audit import RoutingAudit
from app.models.user import User
from app.core.auth import get_optional_current_user
from app.services.routing_service import route_ticket
from app.services.sla_service import calculate_sla_deadlines, compute_ticket_sla_details
from app.services.notification_service import check_and_generate_sla_notifications
router = APIRouter(
    prefix="/rules",
    tags=["Routing Rules"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_rules_read_permission(user: Optional[User]):
    if isinstance(user, User) and user.role in ["customer", "technician"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Admins and Managers have permission to view routing rules."
        )


def check_rules_write_permission(user: Optional[User]):
    if isinstance(user, User) and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only Admins have permission to create, edit, delete, or re-evaluate routing rules."
        )


# --------------------------------
# GET /rules/
# --------------------------------

@router.get("/")
def get_rules(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_rules_read_permission(current_user)

    rules = (
        db.query(RoutingRule)
        .order_by(RoutingRule.id.asc())
        .all()
    )

    return {
        "count": len(rules),
        "rules": [
            {
                "id": rule.id,
                "name": rule.category,
                "category": rule.category,
                "team": rule.team,
                "priority": rule.priority,
                "keywords": rule.keywords or [],
                "description": rule.description,
                "status": "active" if rule.is_active else "inactive",
            }
            for rule in rules
        ]
    }

# --------------------------------
# POST /rules/
# --------------------------------

class RuleCreate(BaseModel):
    category: str
    team: str
    priority: str
    keywords: list[str]
    description: str


@router.post("/")
def create_rule(
    rule_create: RuleCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_rules_write_permission(current_user)

    # Dynamic active teams query
    active_team_records = db.query(Team).filter(Team.is_active == True).all()
    active_teams_map = {t.name.lower(): t for t in active_team_records}
    
    if not active_teams_map:
        fallback_list = ["M365 Support", "Network Team", "Security Team", "Endpoint Team", "Backup Team", "Application Support", "Service Desk"]
        active_teams_map = {name.lower(): None for name in fallback_list}

    allowed_priorities = [
        "critical",
        "high",
        "medium",
        "low"
    ]

    matched_team = active_teams_map.get(rule_create.team.strip().lower())
    if matched_team is None and rule_create.team.strip().lower() not in active_teams_map:
        return {
            "error": "Invalid team"
        }

    if rule_create.priority not in allowed_priorities:
        return {
            "error": "Invalid priority"
        }

    team_name = matched_team.name if matched_team else rule_create.team.strip()
    team_id = matched_team.id if matched_team else None

    rule = RoutingRule(
        category=rule_create.category,
        team_id=team_id,
        team=team_name,
        priority=rule_create.priority,
        keywords=rule_create.keywords,
        description=rule_create.description,
        is_active=True
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return {
        "message": "Routing rule created successfully",
        "rule": {
            "id": rule.id,
            "name": rule.category,
            "category": rule.category,
            "team_id": rule.team_id,
            "team": rule.team,
            "priority": rule.priority,
            "keywords": rule.keywords or [],
            "description": rule.description,
            "status": "active" if rule.is_active else "inactive"
        }
    }
# --------------------------------
# PUT /rules/{rule_id}
# --------------------------------

class RuleUpdate(BaseModel):
    team: str
    priority: str
    keywords: list[str]
    description: str


@router.put("/{rule_id}")
def update_rule(
    rule_id: int,
    rule_update: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_rules_write_permission(current_user)

    rule = (
        db.query(RoutingRule)
        .filter(RoutingRule.id == rule_id)
        .first()
    )

    if not rule:
        return {
            "error": "Routing rule not found"
        }

    active_team_records = db.query(Team).filter(Team.is_active == True).all()
    active_teams_map = {t.name.lower(): t for t in active_team_records}
    
    if not active_teams_map:
        fallback_list = ["M365 Support", "Network Team", "Security Team", "Endpoint Team", "Backup Team", "Application Support", "Service Desk"]
        active_teams_map = {name.lower(): None for name in fallback_list}

    allowed_priorities = [
        "critical",
        "high",
        "medium",
        "low"
    ]

    matched_team = active_teams_map.get(rule_update.team.strip().lower())
    if matched_team is None and rule_update.team.strip().lower() not in active_teams_map:
        return {
            "error": "Invalid team"
        }

    if rule_update.priority not in allowed_priorities:
        return {
            "error": "Invalid priority"
        }

    team_name = matched_team.name if matched_team else rule_update.team.strip()
    team_id = matched_team.id if matched_team else None

    rule.team_id = team_id
    rule.team = team_name
    rule.priority = rule_update.priority
    rule.keywords = rule_update.keywords
    rule.description = rule_update.description

    db.commit()
    db.refresh(rule)

    return {
        "message": "Routing rule updated successfully",
        "rule": {
            "id": rule.id,
            "name": rule.category,
            "category": rule.category,
            "team": rule.team,
            "priority": rule.priority,
            "keywords": rule.keywords or [],
            "description": rule.description,
            "status": "active" if rule.is_active else "inactive",
        }
    }

# --------------------------------
# PATCH /rules/{rule_id}/status
# --------------------------------

class RuleStatusUpdate(BaseModel):
    is_active: bool


@router.patch("/{rule_id}/status")
def update_rule_status(
    rule_id: int,
    status_update: RuleStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_rules_write_permission(current_user)
    rule = (
        db.query(RoutingRule)
        .filter(RoutingRule.id == rule_id)
        .first()
    )

    if not rule:
        return {
            "error": "Routing rule not found"
        }

    rule.is_active = status_update.is_active

    db.commit()
    db.refresh(rule)

    return {
        "message": "Routing rule status updated successfully",
        "rule": {
            "id": rule.id,
            "name": rule.category,
            "category": rule.category,
            "team": rule.team,
            "priority": rule.priority,
            "keywords": rule.keywords or [],
            "description": rule.description,
            "status": "active" if rule.is_active else "inactive",
            "is_active": rule.is_active
        }
    }
# --------------------------------
# POST /rules/{rule_id}/re-evaluate
# --------------------------------

@router.post("/{rule_id}/re-evaluate")
def re_evaluate_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    check_rules_write_permission(current_user)

    rule = (
        db.query(RoutingRule)
        .filter(RoutingRule.id == rule_id)
        .first()
    )

    if not rule:
        return {
            "error": "Routing rule not found"
        }

    # Only re-evaluate tickets that were originally
    # routed automatically. Manual assignments are protected.
    tickets = (
        db.query(Ticket)
        .filter(
            Ticket.category == rule.category,
            Ticket.routing_method == "rule_engine"
        )
        .all()
    )

    updated_tickets = []

    for ticket in tickets:

        old_team = ticket.assigned_team
        old_priority = ticket.priority
        old_category = ticket.category

        # General is the fallback rule, so apply the
# edited General rule directly to existing General tickets.
        if rule.category == "General":

           result = {
        "team": rule.team,
        "priority": rule.priority,
        "category": rule.category,
        "rule": rule.category,
        "matched_keywords": [],
        "match_location": "fallback",
        "score": 0,
        "confidence": 100,
        "reason": (
            "Ticket re-evaluated using the updated "
            "General fallback rule."
        )
    }

        else:

         result = route_ticket(
        {
            "title": ticket.title,
            "description": ticket.description
        },
        db
    )

        new_team = result.get("team")
        new_priority = result.get("priority")
        new_category = result.get("category")

        # Only create an audit/update if something actually changed
        if (
            old_team != new_team
            or old_priority != new_priority
            or old_category != new_category
        ):

            ticket.assigned_team = new_team
            ticket.priority = new_priority
            ticket.category = new_category
            ticket.routing_method = "rule_engine"

            # If priority changed, recalculate SLA deadlines
            if old_priority != new_priority:
                deadlines = calculate_sla_deadlines(ticket.created_at, new_priority)
                ticket.response_due_at = deadlines["response_due_at"]
                ticket.resolution_due_at = deadlines["resolution_due_at"]
                sla_info = compute_ticket_sla_details(ticket)
                ticket.sla_status = sla_info["overall_status"]
                try:
                    check_and_generate_sla_notifications(db, target_ticket_id=ticket.id)
                except Exception as e:
                    print(f"Error checking SLA notifications on rule re-evaluate: {e}")

            audit = RoutingAudit(
                ticket_id=ticket.id,
                rule=result.get("rule"),
                matched_keywords=result.get(
                    "matched_keywords",
                    []
                ),
                match_location=result.get(
                    "match_location"
                ),
                score=result.get("score", 0),
                confidence=result.get(
                    "confidence",
                    0
                ),
                team=new_team,
                priority=new_priority,
                category=new_category,
                routing_method="rule_engine",
                reason=(
                    f"Ticket re-evaluated after "
                    f"routing rule update. "
                    f"Team: {old_team} → {new_team}, "
                    f"Priority: {old_priority} → "
                    f"{new_priority}."
                )
            )

            db.add(audit)

            updated_tickets.append({
                "ticket_id": ticket.id,
                "old_team": old_team,
                "new_team": new_team,
                "old_priority": old_priority,
                "new_priority": new_priority
            })

    db.commit()

    return {
        "message": "Rule re-evaluation completed",
        "rule": rule.category,
        "tickets_checked": len(tickets),
        "tickets_updated": len(updated_tickets),
        "updated_tickets": updated_tickets
    }