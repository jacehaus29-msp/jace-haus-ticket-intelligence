from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.core.auth import get_current_user, require_internal
from app.models.user import User
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.csat import CSATRating
from app.models.routing_audit import RoutingAudit
from app.services.notification_service import notify_low_csat_rating


router = APIRouter(
    tags=["Customer CSAT & Resolution Rating"]
)


RATING_LABELS = {
    1: "Very Dissatisfied",
    2: "Dissatisfied",
    3: "Neutral",
    4: "Satisfied",
    5: "Very Satisfied",
}


class CSATSubmitRequest(BaseModel):
    rating: int = Field(..., description="Rating score from 1 to 5")
    feedback: Optional[str] = Field(None, description="Optional customer written feedback")


def get_authenticated_customer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Customer:
    """
    Strictly authenticate customer from signed JWT bearer token.
    Rejects unauthenticated (401) or non-customer (403) access.
    """
    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only customer user accounts can perform this action."
        )
    if current_user.customer_id:
        cust = db.query(Customer).filter(Customer.id == current_user.customer_id, Customer.is_active == True).first()
        if cust:
            return cust
    if current_user.email:
        cust = db.query(Customer).filter(Customer.email == current_user.email, Customer.is_active == True).first()
        if cust:
            current_user.customer_id = cust.id
            db.commit()
            return cust
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No customer organization associated with this user account."
    )


def serialize_csat(csat: CSATRating, ticket: Optional[Ticket] = None) -> Dict[str, Any]:
    return {
        "id": csat.id,
        "ticket_id": csat.ticket_id,
        "ticket_title": ticket.title if ticket else None,
        "customer_id": csat.customer_id,
        "rating": csat.rating,
        "rating_label": RATING_LABELS.get(csat.rating, f"{csat.rating} Stars"),
        "feedback": csat.feedback,
        "submitted_at": csat.submitted_at.isoformat() if csat.submitted_at else None,
        "created_at": csat.created_at.isoformat() if csat.created_at else None,
    }


def resolve_csat_org_name(current_user: User, db: Session, customer_id: Optional[int] = None) -> str:
    if current_user.role == "customer":
        if current_user.customer_id:
            cust = db.query(Customer).filter(Customer.id == current_user.customer_id).first()
            if cust:
                return cust.company or cust.name
        cust = db.query(Customer).filter(Customer.email == current_user.email).first()
        if cust:
            return cust.company or cust.name
        return current_user.name
    elif customer_id:
        cust = db.query(Customer).filter(Customer.id == customer_id).first()
        if cust:
            return cust.company or cust.name
    return "All MSP Organizations"


# =============================================================================
# 1. CUSTOMER PORTAL CSAT ENDPOINTS
# =============================================================================

@router.get("/portal/csat/ticket/{ticket_id}")
def get_ticket_csat_status(
    ticket_id: int,
    customer: Customer = Depends(get_authenticated_customer),
    db: Session = Depends(get_db)
):
    """
    Check eligibility and retrieve existing CSAT rating for a specific ticket.
    Strict tenant security: customers can only query their own tickets.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only view satisfaction details for your organization's tickets."
        )

    csat = db.query(CSATRating).filter(CSATRating.ticket_id == ticket_id).first()
    is_eligible = (ticket.status == "resolved")

    return {
        "ticket_id": ticket.id,
        "ticket_status": ticket.status,
        "is_eligible": is_eligible,
        "has_rated": csat is not None,
        "csat": serialize_csat(csat, ticket) if csat else None
    }


@router.post("/portal/csat/ticket/{ticket_id}")
def submit_ticket_csat(
    ticket_id: int,
    payload: CSATSubmitRequest,
    customer: Customer = Depends(get_authenticated_customer),
    db: Session = Depends(get_db)
):
    """
    Customer submits a 1-5 star satisfaction rating and optional written feedback for a resolved ticket.
    Enforces customer tenant isolation, resolved status eligibility, bounds checking, duplicate prevention,
    timeline audit logging, and low-CSAT alert generation.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    # 1. Security / Tenant Isolation Check
    if ticket.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only rate tickets submitted by your organization."
        )

    # 2. Ticket Status Eligibility Check
    if ticket.status != "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only resolved tickets can receive satisfaction ratings. Current status is '{ticket.status}'."
        )

    # 3. Rating Value Validation (1 to 5 only)
    if not isinstance(payload.rating, int) or payload.rating < 1 or payload.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be an integer between 1 and 5 (1=Very Dissatisfied, 5=Very Satisfied)."
        )

    # 4. Duplicate Rating Prevention (1 immutable rating per ticket)
    existing_csat = db.query(CSATRating).filter(CSATRating.ticket_id == ticket.id).first()
    if existing_csat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A satisfaction rating has already been submitted for this ticket."
        )

    clean_feedback = payload.feedback.strip() if payload.feedback and payload.feedback.strip() else None

    # 5. Persist CSAT Rating
    csat = CSATRating(
        ticket_id=ticket.id,
        customer_id=customer.id,
        rating=payload.rating,
        feedback=clean_feedback
    )
    db.add(csat)
    db.commit()
    db.refresh(csat)

    # 6. Log to Activity Timeline (RoutingAudit)
    rating_label = RATING_LABELS.get(payload.rating, f"{payload.rating} Stars")
    fb_snippet = f' Feedback: "{clean_feedback[:100]}..."' if clean_feedback else ""
    audit = RoutingAudit(
        ticket_id=ticket.id,
        rule="CSAT Rating Submitted",
        matched_keywords=[],
        match_location="customer_portal",
        score=0,
        confidence=100,
        team=ticket.assigned_team or "Support Desk",
        priority=ticket.priority or "medium",
        category=ticket.category or "General",
        routing_method="csat_survey",
        reason=f"Customer {customer.name} ({customer.company}) submitted a {payload.rating}★ rating ({rating_label}).{fb_snippet}"
    )
    db.add(audit)
    db.commit()

    # 7. Low-Rating Alert (1 or 2 stars) for Internal Admins/Managers
    if payload.rating <= 2:
        try:
            notify_low_csat_rating(
                db=db,
                ticket=ticket,
                rating=payload.rating,
                customer_name=customer.name,
                customer_company=customer.company,
                feedback=clean_feedback
            )
        except Exception as e:
            print(f"Error creating low CSAT notification: {e}")

    return {
        "message": "Thank you for your feedback! Your rating has been recorded.",
        "csat": serialize_csat(csat, ticket)
    }


# =============================================================================
# 2. EXECUTIVE & CSAT REPORTING ENDPOINTS
# =============================================================================

@router.get("/reports/csat/summary")
def get_csat_summary_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive CSAT analytics, star distribution, response rate,
    and multi-dimensional breakdowns with tenant isolation.
    """
    # 1. Fetch CSAT Ratings with filters
    query = db.query(CSATRating, Ticket).join(Ticket, CSATRating.ticket_id == Ticket.id)
    if current_user.role == "customer":
        if current_user.customer_id:
            query = query.filter(CSATRating.customer_id == current_user.customer_id)
        else:
            cust = db.query(Customer).filter(Customer.email == current_user.email).first()
            if cust:
                query = query.filter(CSATRating.customer_id == cust.id)
            else:
                query = query.filter(CSATRating.id == -1)
    elif customer_id and current_user.role in ["admin", "manager"]:
        query = query.filter(CSATRating.customer_id == customer_id)

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            query = query.filter(CSATRating.submitted_at >= start_dt)
        except Exception:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt.hour == 0 and end_dt.minute == 0:
                end_dt = end_dt + timedelta(days=1)
            query = query.filter(CSATRating.submitted_at <= end_dt)
        except Exception:
            pass

    if team and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_team == team)
    if technician_id and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_technician_id == technician_id)
    if priority:
        query = query.filter(func.lower(Ticket.priority) == priority.lower().strip())
    if category:
        query = query.filter(func.lower(Ticket.category) == category.lower().strip())

    results = query.order_by(CSATRating.submitted_at.desc()).all()

    # 2. Fetch Eligible (Resolved) Tickets Count for Response Rate
    ticket_query = db.query(Ticket).filter(Ticket.status == "resolved")
    if current_user.role == "customer":
        if current_user.customer_id:
            ticket_query = ticket_query.filter(Ticket.customer_id == current_user.customer_id)
        else:
            cust = db.query(Customer).filter(Customer.email == current_user.email).first()
            if cust:
                ticket_query = ticket_query.filter(Ticket.customer_id == cust.id)
            else:
                ticket_query = ticket_query.filter(Ticket.id == -1)
    elif customer_id and current_user.role in ["admin", "manager"]:
        ticket_query = ticket_query.filter(Ticket.customer_id == customer_id)
    if team and current_user.role in ["admin", "manager"]:
        ticket_query = ticket_query.filter(Ticket.assigned_team == team)
    if priority:
        ticket_query = ticket_query.filter(func.lower(Ticket.priority) == priority.lower().strip())
    if category:
        ticket_query = ticket_query.filter(func.lower(Ticket.category) == category.lower().strip())

    eligible_count = ticket_query.count()

    # 3. Compute CSAT Aggregations
    total_responses = len(results)
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    ratings_sum = 0
    positive_count = 0  # 4 and 5 stars

    by_customer = {}
    by_team = {}
    by_technician = {}
    by_priority = {}
    by_category = {}

    recent_ratings = []

    for csat, t in results:
        r = csat.rating
        star_counts[r] = star_counts.get(r, 0) + 1
        ratings_sum += r
        if r >= 4:
            positive_count += 1

        # Breakdowns
        c_name = t.customer_company or t.customer_name or "Client"
        if c_name not in by_customer:
            by_customer[c_name] = {"total": 0, "sum": 0, "positive": 0}
        by_customer[c_name]["total"] += 1
        by_customer[c_name]["sum"] += r
        if r >= 4:
            by_customer[c_name]["positive"] += 1

        tm = t.assigned_team or "Support Desk"
        if tm not in by_team:
            by_team[tm] = {"total": 0, "sum": 0, "positive": 0}
        by_team[tm]["total"] += 1
        by_team[tm]["sum"] += r
        if r >= 4:
            by_team[tm]["positive"] += 1

        tech = t.assigned_technician or "Unassigned"
        if tech not in by_technician:
            by_technician[tech] = {"total": 0, "sum": 0, "positive": 0}
        by_technician[tech]["total"] += 1
        by_technician[tech]["sum"] += r
        if r >= 4:
            by_technician[tech]["positive"] += 1

        prio = (t.priority or "medium").lower()
        if prio not in by_priority:
            by_priority[prio] = {"total": 0, "sum": 0, "positive": 0}
        by_priority[prio]["total"] += 1
        by_priority[prio]["sum"] += r
        if r >= 4:
            by_priority[prio]["positive"] += 1

        cat = t.category or "General"
        if cat not in by_category:
            by_category[cat] = {"total": 0, "sum": 0, "positive": 0}
        by_category[cat]["total"] += 1
        by_category[cat]["sum"] += r
        if r >= 4:
            by_category[cat]["positive"] += 1

        if len(recent_ratings) < 20:
            recent_ratings.append({
                "id": csat.id,
                "ticket_id": t.id,
                "ticket_title": t.title,
                "customer_name": t.customer_name,
                "customer_company": t.customer_company,
                "assigned_team": t.assigned_team if current_user.role != "customer" else "Support Desk",
                "assigned_technician": t.assigned_technician if current_user.role != "customer" else "MSP Engineer",
                "priority": t.priority,
                "category": t.category,
                "rating": csat.rating,
                "rating_label": RATING_LABELS.get(csat.rating, f"{csat.rating} Stars"),
                "feedback": csat.feedback,
                "submitted_at": csat.submitted_at.isoformat() if csat.submitted_at else None
            })

    # Calculations with Division-by-Zero Protection
    overall_csat_percentage = (
        round((positive_count / total_responses) * 100, 1)
        if total_responses > 0
        else 0.0
    )
    average_rating = (
        round(ratings_sum / total_responses, 1)
        if total_responses > 0
        else 0.0
    )
    response_rate = (
        round((total_responses / eligible_count) * 100, 1)
        if eligible_count > 0
        else 0.0
    )

    star_breakdown = {
        "5_star": star_counts[5],
        "4_star": star_counts[4],
        "3_star": star_counts[3],
        "2_star": star_counts[2],
        "1_star": star_counts[1],
    }

    star_percentages = {
        "5_star": round((star_counts[5] / total_responses) * 100, 1) if total_responses > 0 else 0.0,
        "4_star": round((star_counts[4] / total_responses) * 100, 1) if total_responses > 0 else 0.0,
        "3_star": round((star_counts[3] / total_responses) * 100, 1) if total_responses > 0 else 0.0,
        "2_star": round((star_counts[2] / total_responses) * 100, 1) if total_responses > 0 else 0.0,
        "1_star": round((star_counts[1] / total_responses) * 100, 1) if total_responses > 0 else 0.0,
    }

    low_rating_count = star_counts[1] + star_counts[2]

    # Format dimension dictionaries
    def format_dim(d):
        return {
            k: {
                "total_responses": v["total"],
                "avg_rating": round(v["sum"] / v["total"], 1) if v["total"] > 0 else 0.0,
                "csat_percentage": round((v["positive"] / v["total"]) * 100, 1) if v["total"] > 0 else 0.0,
            }
            for k, v in d.items()
        }

    return {
        "organization_name": resolve_csat_org_name(current_user, db, customer_id),
        "is_customer_view": current_user.role == "customer",
        "total_responses": total_responses,
        "eligible_tickets_count": eligible_count,
        "response_rate": response_rate,
        "overall_csat_percentage": overall_csat_percentage,
        "average_rating": average_rating,
        "low_rating_count": low_rating_count,
        "star_breakdown": star_breakdown,
        "star_percentages": star_percentages,
        "csat_by_customer": format_dim(by_customer) if current_user.role != "customer" else {},
        "csat_by_team": format_dim(by_team) if current_user.role != "customer" else {},
        "csat_by_technician": format_dim(by_technician) if current_user.role != "customer" else {},
        "csat_by_priority": format_dim(by_priority),
        "csat_by_category": format_dim(by_category),
        "recent_ratings": recent_ratings
    }


@router.get("/reports/csat")
def list_csat_ratings(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    team: Optional[str] = Query(None),
    technician_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    rating: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List individual CSAT ratings with filters and tenant scoping."""
    query = db.query(CSATRating, Ticket).join(Ticket, CSATRating.ticket_id == Ticket.id)

    if current_user.role == "customer":
        if current_user.customer_id:
            query = query.filter(CSATRating.customer_id == current_user.customer_id)
        else:
            cust = db.query(Customer).filter(Customer.email == current_user.email).first()
            if cust:
                query = query.filter(CSATRating.customer_id == cust.id)
            else:
                query = query.filter(CSATRating.id == -1)
    elif customer_id and current_user.role in ["admin", "manager"]:
        query = query.filter(CSATRating.customer_id == customer_id)

    if rating:
        query = query.filter(CSATRating.rating == rating)
    if team and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_team == team)
    if technician_id and current_user.role in ["admin", "manager"]:
        query = query.filter(Ticket.assigned_technician_id == technician_id)
    if priority:
        query = query.filter(func.lower(Ticket.priority) == priority.lower().strip())
    if category:
        query = query.filter(func.lower(Ticket.category) == category.lower().strip())

    items = query.order_by(CSATRating.submitted_at.desc()).limit(limit).all()

    return {
        "count": len(items),
        "ratings": [
            {
                "id": csat.id,
                "ticket_id": t.id,
                "ticket_title": t.title,
                "customer_name": t.customer_name,
                "customer_company": t.customer_company,
                "assigned_team": t.assigned_team if current_user.role != "customer" else "Support Desk",
                "assigned_technician": t.assigned_technician if current_user.role != "customer" else "MSP Engineer",
                "priority": t.priority,
                "category": t.category,
                "rating": csat.rating,
                "rating_label": RATING_LABELS.get(csat.rating, f"{csat.rating} Stars"),
                "feedback": csat.feedback,
                "submitted_at": csat.submitted_at.isoformat() if csat.submitted_at else None
            }
            for csat, t in items
        ]
    }
