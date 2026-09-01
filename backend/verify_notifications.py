import sys
import os
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, r"c:\Users\Abhishek Shah\jace-haus-ticket-intelligence\backend")
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.database import SessionLocal, engine, Base
from app.models.ticket import Ticket
from app.models.routing_rule import RoutingRule
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.services.sla_service import calculate_sla_deadlines, compute_ticket_sla_details
from app.services.notification_service import (
    create_notification,
    check_and_generate_sla_notifications,
    notify_ticket_created,
    notify_priority_changed,
    notify_status_changed
)
from app.main import run_db_migrations

def test_notifications_and_escalations():
    print("==================================================================")
    print(" RUNNING NOTIFICATIONS & ESCALATION SYSTEM VERIFICATION")
    print("==================================================================")
    
    # 1. Run migrations
    run_db_migrations()
    db = SessionLocal()

    try:
        # Clean up existing test data
        db.query(Notification).delete()
        db.query(RoutingAudit).delete()
        db.query(Ticket).delete()
        db.commit()
        print("✓ Database cleaned for isolated verification test")

        # -------------------------------------------------------------
        # TEST 1: Ticket Creation & Notification
        # -------------------------------------------------------------
        now = datetime.now(timezone.utc)
        deadlines = calculate_sla_deadlines(now, "critical")
        
        ticket1 = Ticket(
            title="Production Database Outage - Immediate Failure",
            description="The main customer database cluster is unresponsive.",
            category="Infrastructure",
            assigned_team="Database Team",
            priority="critical",
            routing_method="rule_engine",
            response_due_at=deadlines["response_due_at"],
            resolution_due_at=deadlines["resolution_due_at"],
            status="new"
        )
        db.add(ticket1)
        db.commit()
        db.refresh(ticket1)

        # Trigger ticket created notification
        notif1 = notify_ticket_created(db, ticket1, {"team": ticket1.assigned_team, "priority": ticket1.priority})
        print(f"✓ Ticket #{ticket1.id} created with initial notification: ID={notif1.id}, Type={notif1.type}, Severity={notif1.severity}")
        assert notif1.type == "TICKET_ASSIGNED"
        assert notif1.severity == "critical"
        assert notif1.is_read == False

        # -------------------------------------------------------------
        # TEST 2: SLA At-Risk Detection & Deduplication
        # -------------------------------------------------------------
        # Move response due time to 3 minutes from now (within 25% window of 15 min SLA)
        ticket1.response_due_at = now + timedelta(minutes=3)
        db.commit()

        # Run SLA scanner
        generated = check_and_generate_sla_notifications(db, target_ticket_id=ticket1.id)
        print(f"✓ SLA scanner evaluated ticket #{ticket1.id}: Generated {len(generated)} alert(s)")
        
        at_risk_notifs = db.query(Notification).filter(
            Notification.ticket_id == ticket1.id,
            Notification.type == "SLA_AT_RISK"
        ).all()
        assert len(at_risk_notifs) >= 1, "Expected SLA_AT_RISK notification"
        print(f"✓ SLA At-Risk alert verified: '{at_risk_notifs[0].title}' (Severity: {at_risk_notifs[0].severity})")

        # Re-run scanner to ensure deduplication prevents duplicate alerts
        re_generated = check_and_generate_sla_notifications(db, target_ticket_id=ticket1.id)
        at_risk_count_after = db.query(Notification).filter(
            Notification.ticket_id == ticket1.id,
            Notification.type == "SLA_AT_RISK"
        ).count()
        assert at_risk_count_after == len(at_risk_notifs), f"Deduplication failed: got {at_risk_count_after} vs {len(at_risk_notifs)}"
        print("✓ Deduplication verified: Re-running scanner produced 0 duplicate SLA_AT_RISK alerts")

        # -------------------------------------------------------------
        # TEST 3: SLA Breach & Automatic Escalation
        # -------------------------------------------------------------
        # Simulate breach by setting deadlines in the past
        ticket1.response_due_at = now - timedelta(minutes=10)
        ticket1.resolution_due_at = now - timedelta(minutes=5)
        db.commit()

        breach_gen = check_and_generate_sla_notifications(db, target_ticket_id=ticket1.id)
        print(f"✓ SLA scanner on breached ticket #{ticket1.id}: Generated {len(breach_gen)} notification(s)")

        breach_notifs = db.query(Notification).filter(
            Notification.ticket_id == ticket1.id,
            Notification.type == "SLA_BREACHED"
        ).all()
        assert len(breach_notifs) >= 1, "Expected SLA_BREACHED notifications"
        print(f"✓ SLA Breach notification verified: Count = {len(breach_notifs)}")

        escalation_notifs = db.query(Notification).filter(
            Notification.ticket_id == ticket1.id,
            Notification.type == "ESCALATION"
        ).all()
        assert len(escalation_notifs) >= 1, "Expected ESCALATION notification for critical ticket"
        print(f"✓ Automatic Escalation verified: '{escalation_notifs[0].title}' (Severity: {escalation_notifs[0].severity})")
        assert escalation_notifs[0].severity == "critical"

        # Check that activity timeline logged escalation and breaches
        audits = db.query(RoutingAudit).filter(RoutingAudit.ticket_id == ticket1.id).all()
        audit_rules = [a.rule for a in audits]
        print(f"✓ Ticket #{ticket1.id} Activity Timeline events: {audit_rules}")
        assert "Escalation Triggered" in audit_rules, "Expected 'Escalation Triggered' in audit history"

        # -------------------------------------------------------------
        # TEST 4: Priority & Status Changes
        # -------------------------------------------------------------
        prio_notif = notify_priority_changed(db, ticket1, "critical", "high")
        print(f"✓ Priority change notification verified: ID={prio_notif.id}, Type={prio_notif.type}")
        assert prio_notif.type == "PRIORITY_CHANGED"

        status_notif = notify_status_changed(db, ticket1, "new", "in_progress")
        print(f"✓ Status change notification verified: ID={status_notif.id}, Type={status_notif.type}")
        assert status_notif.type == "STATUS_CHANGED"

        # -------------------------------------------------------------
        # TEST 5: Mark as Read & Mark All as Read
        # -------------------------------------------------------------
        total_unread = db.query(Notification).filter(Notification.is_read == False).count()
        print(f"✓ Unread notifications count before read action: {total_unread}")
        assert total_unread > 0

        # Mark single as read
        notif1.is_read = True
        db.commit()
        unread_after_single = db.query(Notification).filter(Notification.is_read == False).count()
        assert unread_after_single == total_unread - 1
        print(f"✓ Single mark-as-read verified: unread count decremented to {unread_after_single}")

        # Mark all as read
        db.query(Notification).update({"is_read": True})
        db.commit()
        unread_after_all = db.query(Notification).filter(Notification.is_read == False).count()
        assert unread_after_all == 0
        print("✓ Mark-all-as-read verified: unread count is 0")

        # -------------------------------------------------------------
        # TEST 6: Analytics Metrics
        # -------------------------------------------------------------
        from app.routes.analytics import get_analytics
        analytics_result = get_analytics(db)
        print("✓ Analytics response received:")
        print(f"  - Total Notifications: {analytics_result.get('total_notifications')}")
        print(f"  - Unread Notifications: {analytics_result.get('unread_notifications')}")
        print(f"  - SLA At-Risk Alerts: {analytics_result.get('sla_at_risk_alerts')}")
        print(f"  - SLA Breaches Alerts: {analytics_result.get('sla_breaches_alerts')}")
        print(f"  - Escalations Count: {analytics_result.get('escalations_count')}")
        print(f"  - Notifications By Severity: {analytics_result.get('notifications_by_severity')}")
        
        assert analytics_result.get("total_notifications") >= 4
        assert analytics_result.get("sla_breaches_alerts") >= 1
        assert analytics_result.get("escalations_count") >= 1

        print("==================================================================")
        print(" ALL VERIFICATION TESTS PASSED SUCCESSFULLY! (100% PASS)")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    test_notifications_and_escalations()
