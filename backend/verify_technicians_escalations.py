import sys
import os
from datetime import datetime, timezone

# Ensure stdout handles utf-8 if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models.ticket import Ticket
from app.models.technician import Technician
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.main import run_db_migrations
from app.api.technicians import (
    get_technicians,
    get_technician_by_id,
    get_technician_workload_endpoint,
    create_technician,
    TechnicianCreateRequest
)
from app.api.tickets import (
    assign_ticket_technician,
    escalate_ticket_endpoint,
    update_ticket_status,
    TechnicianAssignRequest,
    EscalateTicketRequest,
    StatusUpdate
)
from app.routes.analytics import get_analytics

def run_tests():
    print("=" * 65)
    print("VERIFYING TECHNICIAN ASSIGNMENT & ESCALATION SYSTEM")
    print("=" * 65)

    # 1. Run migrations and seeding
    run_db_migrations()

    db = SessionLocal()

    try:
        # TEST 1: Technician Database Schema & Seeding
        print("\n[TEST 1] Verifying Technician Database Schema & Seeding...")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        assert "technicians" in inspector.get_table_names(), "technicians table not found"
        tech_cols = [c["name"] for c in inspector.get_columns("technicians")]
        assert "name" in tech_cols and "email" in tech_cols and "team" in tech_cols and "is_active" in tech_cols
        
        ticket_cols = [c["name"] for c in inspector.get_columns("tickets")]
        assert "assigned_technician_id" in ticket_cols, "assigned_technician_id missing on tickets"
        assert "assigned_technician" in ticket_cols, "assigned_technician missing on tickets"
        assert "escalation_level" in ticket_cols, "escalation_level missing on tickets"
        assert "escalation_reason" in ticket_cols, "escalation_reason missing on tickets"
        assert "escalated_at" in ticket_cols, "escalated_at missing on tickets"
        assert "escalated_by" in ticket_cols, "escalated_by missing on tickets"

        techs = db.query(Technician).all()
        print(f"  Found {len(techs)} technicians in database.")
        assert len(techs) >= 14, f"Expected at least 14 technicians, found {len(techs)}"
        
        rahul = db.query(Technician).filter(Technician.email == "rahul.sharma@jacehaus.com").first()
        assert rahul is not None, "Rahul Sharma not found"
        assert rahul.team == "M365 Support"

        arjun = db.query(Technician).filter(Technician.email == "arjun.patel@jacehaus.com").first()
        assert arjun is not None, "Arjun Patel not found"
        assert arjun.team == "Network Team"

        aditya = db.query(Technician).filter(Technician.email == "aditya.singh@jacehaus.com").first()
        assert aditya is not None, "Aditya Singh not found"
        assert aditya.team == "Security Team"

        print("  [PASS] Technician schema and seeding verified across all teams.")

        # TEST 2: GET /technicians
        print("\n[TEST 2] Testing get_technicians endpoint...")
        techs_data = get_technicians(team=None, is_active=None, db=db)
        assert techs_data["count"] >= 14
        m365_techs = get_technicians(team="M365 Support", is_active=True, db=db)
        assert m365_techs["count"] >= 2
        print(f"  [PASS] Retrieved {techs_data['count']} technicians ({m365_techs['count']} for M365 Support).")

        # TEST 3: Create Test Ticket for M365 Support
        print("\n[TEST 3] Creating test ticket for M365 Support...")
        ticket = Ticket(
            title="Outlook VIP synchronization failure",
            description="Executive mailbox unable to sync exchange calendars in Microsoft 365.",
            category="Microsoft 365",
            assigned_team="M365 Support",
            priority="high",
            status="new",
            routing_method="rule_engine",
            sla_status="on_track",
            escalation_level=1
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        ticket_id = ticket.id
        print(f"  [PASS] Created Test Ticket #{ticket_id}: '{ticket.title}' (Team: {ticket.assigned_team})")

        # TEST 4: Assign Technician (Valid Team Match)
        print("\n[TEST 4] Testing Technician Assignment (Valid Team)...")
        assign_res = assign_ticket_technician(
            ticket_id=ticket_id,
            payload=TechnicianAssignRequest(technician_id=rahul.id, assigned_by="Helpdesk Lead"),
            db=db
        )
        assert "error" not in assign_res, f"Unexpected error: {assign_res}"
        assert assign_res["assigned_technician_id"] == rahul.id
        assert assign_res["assigned_technician"] == "Rahul Sharma"
        print(f"  [PASS] Ticket #{ticket_id} assigned to {assign_res['assigned_technician']}.")

        # Verify Activity Timeline
        audit_assign = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket_id, RoutingAudit.rule == "Technician Assigned")
            .first()
        )
        assert audit_assign is not None, "Technician Assigned timeline event not found"
        assert "Rahul Sharma" in audit_assign.reason
        print(f"  [PASS] Timeline event logged: rule='{audit_assign.rule}', reason='{audit_assign.reason}'")

        # Verify Notification
        notif_assign = (
            db.query(Notification)
            .filter(Notification.ticket_id == ticket_id, Notification.type == "TICKET_ASSIGNED")
            .order_by(Notification.id.desc())
            .first()
        )
        assert notif_assign is not None, "TICKET_ASSIGNED notification not found"
        print(f"  [PASS] Notification created: title='{notif_assign.title}', severity='{notif_assign.severity}'")

        # TEST 5: Workload Calculation for Rahul Sharma
        print("\n[TEST 5] Testing Workload Calculation...")
        tech_detail = get_technician_by_id(technician_id=rahul.id, db=db)
        assert tech_detail["active_workload"] >= 1, f"Expected active workload >= 1, got {tech_detail['active_workload']}"
        assert ticket_id in [t["id"] for t in tech_detail["active_tickets"]]
        print(f"  [PASS] Rahul Sharma active workload: {tech_detail['active_workload']} (includes Ticket #{ticket_id}).")

        # TEST 6: Invalid Assignment (Team Mismatch)
        print("\n[TEST 6] Testing Invalid Assignment (Team Mismatch)...")
        invalid_res = assign_ticket_technician(
            ticket_id=ticket_id,
            payload=TechnicianAssignRequest(technician_id=arjun.id, assigned_by="Dispatcher"),
            db=db
        )
        assert "error" in invalid_res, "Expected error on team mismatch"
        print(f"  [PASS] Team mismatch correctly blocked: '{invalid_res['error']}'")

        # TEST 7: Multi-Level Escalation - Level 2 (Team Escalation)
        print("\n[TEST 7] Testing Ticket Escalation to Level 2 (Team Escalation)...")
        esc2_res = escalate_ticket_endpoint(
            ticket_id=ticket_id,
            payload=EscalateTicketRequest(
                escalation_level=2,
                escalation_reason="High customer visibility and VIP SLA nearing risk threshold",
                escalated_by="Rahul Sharma"
            ),
            db=db
        )
        assert "error" not in esc2_res, f"Unexpected error: {esc2_res}"
        assert esc2_res["escalation_level"] == 2
        print(f"  [PASS] Ticket #{ticket_id} escalated to Level {esc2_res['escalation_level']}.")

        # Verify Activity Timeline for Level 2 Escalation
        audit_esc2 = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket_id, RoutingAudit.rule == "Ticket Escalated")
            .order_by(RoutingAudit.id.desc())
            .first()
        )
        assert audit_esc2 is not None, "Ticket Escalated audit event not found"
        assert "[Level 2 (Team Escalation)]" in audit_esc2.reason
        print(f"  [PASS] Timeline event logged: rule='{audit_esc2.rule}', reason='{audit_esc2.reason}'")

        # Verify Notification for Level 2 Escalation
        notif_esc2 = (
            db.query(Notification)
            .filter(Notification.ticket_id == ticket_id, Notification.type == "ESCALATION")
            .order_by(Notification.id.desc())
            .first()
        )
        assert notif_esc2 is not None, "ESCALATION notification not found"
        assert notif_esc2.severity == "critical"
        print(f"  [PASS] Critical Notification created: title='{notif_esc2.title}'")

        # TEST 8: Escalation Validation (Cannot move downward or stay same)
        print("\n[TEST 8] Testing Escalation Validation (Cannot move downward or stay same)...")
        same_esc = escalate_ticket_endpoint(
            ticket_id=ticket_id,
            payload=EscalateTicketRequest(escalation_level=2, escalation_reason="Trying same level", escalated_by="Tech"),
            db=db
        )
        assert "error" in same_esc
        print(f"  [PASS] Invalid escalation rejected: '{same_esc['error']}'")

        # TEST 9: Multi-Level Escalation - Level 3 (Specialist Escalation)
        print("\n[TEST 9] Testing Ticket Escalation to Level 3 (Specialist Escalation)...")
        esc3_res = escalate_ticket_endpoint(
            ticket_id=ticket_id,
            payload=EscalateTicketRequest(
                escalation_level=3,
                escalation_reason="Critical service outage requiring Microsoft Principal Support Engineer intervention",
                escalated_by="Engineering Manager"
            ),
            db=db
        )
        assert "error" not in esc3_res, f"Unexpected error: {esc3_res}"
        assert esc3_res["escalation_level"] == 3
        print(f"  [PASS] Ticket #{ticket_id} escalated to Level {esc3_res['escalation_level']}.")

        # TEST 10: Workload Exclusion upon Resolution
        print("\n[TEST 10] Testing Workload Exclusion upon Resolution...")
        res_res = update_ticket_status(
            ticket_id=ticket_id,
            status_update=StatusUpdate(
                status="resolved",
                resolution_summary="Recreated Exchange Hybrid OAuth certificates",
                resolution_details="Renewed expired federation certificates in Entra ID."
            ),
            db=db
        )
        assert "error" not in res_res

        tech_after = get_technician_by_id(technician_id=rahul.id, db=db)
        assert ticket_id not in [t["id"] for t in tech_after["active_tickets"]], "Resolved ticket still counted in active tickets"
        print(f"  [PASS] Resolved ticket successfully excluded from Rahul's active workload.")

        # TEST 11: Analytics Operational & Escalation Metrics
        print("\n[TEST 11] Testing Analytics Operational & Escalation Metrics...")
        analytics_data = get_analytics(db=db)
        assert "escalated_tickets_count" in analytics_data
        assert "escalations_by_level" in analytics_data
        assert "assigned_tickets_count" in analytics_data
        assert "unassigned_tickets_count" in analytics_data
        print(f"  [PASS] Analytics metrics: escalated_tickets={analytics_data['escalated_tickets_count']}, "
              f"escalations_by_level={analytics_data['escalations_by_level']}, "
              f"assigned_tickets={analytics_data['assigned_tickets_count']}")

        # Cleanup test ticket
        db.query(Notification).filter(Notification.ticket_id == ticket_id).delete(synchronize_session=False)
        db.query(RoutingAudit).filter(RoutingAudit.ticket_id == ticket_id).delete(synchronize_session=False)
        db.query(Ticket).filter(Ticket.id == ticket_id).delete(synchronize_session=False)
        db.commit()

        print("\n" + "=" * 65)
        print("ALL 11 TECHNICIAN & ESCALATION TESTS PASSED (100% SUCCESS)!")
        print("=" * 65)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
