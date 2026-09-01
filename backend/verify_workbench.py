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
from app.models.ticket_note import TicketNote
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.api.tickets import (
    add_ticket_note,
    get_ticket_notes,
    update_ticket_note,
    delete_ticket_note,
    update_ticket_status,
    StatusUpdate,
    NoteCreate,
    NoteUpdate,
)
from app.routes.analytics import get_analytics


def run_tests():
    print("==================================================")
    print("MSP TECHNICIAN WORKBENCH VERIFICATION SUITE")
    print("==================================================")

    db = SessionLocal()
    try:
        # 1. Verify Database Models & Columns
        print("\n[TEST 1] Verifying Database Schema & Models...")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        ticket_cols = [c["name"] for c in inspector.get_columns("tickets")]
        assert "resolution_summary" in ticket_cols, "Missing resolution_summary on tickets"
        assert "resolution_details" in ticket_cols, "Missing resolution_details on tickets"
        assert "ticket_notes" in inspector.get_table_names(), "Missing ticket_notes table"
        note_cols = [c["name"] for c in inspector.get_columns("ticket_notes")]
        assert "note_type" in note_cols, "Missing note_type column"
        assert "content" in note_cols, "Missing content column"
        assert "author" in note_cols, "Missing author column"
        print("  [PASS] Database schema contains all required tables and columns.")

        # 2. Create a Test Ticket
        print("\n[TEST 2] Creating Test Ticket...")
        ticket = Ticket(
            title="Workbench Test - VPN Gateway Outage",
            description="Remote employees unable to establish IPsec tunnel to headquarters gateway",
            category="Network",
            assigned_team="Network Team",
            priority="critical",
            status="new",
            routing_method="rule_engine"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        print(f"  [PASS] Created Ticket #{ticket.id}: '{ticket.title}' ({ticket.priority.upper()})")

        # 3. Add Internal Work Note
        print("\n[TEST 3] Adding Internal Work Note...")
        note_res = add_ticket_note(
            ticket_id=ticket.id,
            note_data=NoteCreate(
                note_type="internal",
                content="Investigated gateway logs: found tunnel keepalive timeout on interface ge-0/0/1.",
                author="Senior Network Tech"
            ),
            db=db
        )
        assert note_res.get("id"), "Note was not created"
        assert note_res.get("note_type") == "internal", f"Expected internal, got {note_res.get('note_type')}"
        note_id = note_res["id"]
        print(f"  [PASS] Internal note #{note_id} created: author='{note_res['author']}'")

        # Verify audit log for internal note
        audit = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket.id, RoutingAudit.rule == "Work Note Added")
            .first()
        )
        assert audit is not None, "Missing RoutingAudit record for 'Work Note Added'"
        assert "[Internal Work Note]" in audit.reason, f"Unexpected audit reason: {audit.reason}"
        print(f"  [PASS] Audit timeline event logged: rule='{audit.rule}', reason='{audit.reason[:60]}...'")

        # 4. Add Customer Update
        print("\n[TEST 4] Adding Customer Update...")
        cust_res = add_ticket_note(
            ticket_id=ticket.id,
            note_data=NoteCreate(
                note_type="customer",
                content="We are currently re-establishing the backup VPN tunnel. Expected ETA is 15 minutes.",
                author="MSP Support Desk"
            ),
            db=db
        )
        assert cust_res.get("id"), "Customer note was not created"
        assert cust_res.get("note_type") == "customer", f"Expected customer, got {cust_res.get('note_type')}"
        cust_id = cust_res["id"]
        print(f"  [PASS] Customer update #{cust_id} created: author='{cust_res['author']}'")

        # Verify audit log for customer update
        cust_audit = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket.id, RoutingAudit.rule == "Customer Update Added")
            .first()
        )
        assert cust_audit is not None, "Missing RoutingAudit record for 'Customer Update Added'"
        assert "[Customer Update]" in cust_audit.reason, f"Unexpected audit reason: {cust_audit.reason}"
        print(f"  [PASS] Audit timeline event logged: rule='{cust_audit.rule}', reason='{cust_audit.reason[:60]}...'")

        # 5. Fetch & List Notes
        print("\n[TEST 5] Fetching Ticket Notes...")
        all_notes = get_ticket_notes(ticket_id=ticket.id, db=db)
        assert all_notes["count"] >= 2, f"Expected at least 2 notes, got {all_notes['count']}"
        print(f"  [PASS] Retrieved {all_notes['count']} notes for Ticket #{ticket.id}")

        # 6. Edit Note
        print("\n[TEST 6] Editing Note...")
        edit_res = update_ticket_note(
            ticket_id=ticket.id,
            note_id=note_id,
            note_data=NoteUpdate(content="Updated: Root cause identified as upstream ISP routing flap."),
            db=db
        )
        assert "Root cause identified" in edit_res["content"], "Content did not update"
        print(f"  [PASS] Note #{note_id} updated successfully")

        # 7. Start Working (Status -> in_progress)
        print("\n[TEST 7] Starting Work (Status -> in_progress)...")
        in_prog_res = update_ticket_status(
            ticket_id=ticket.id,
            status_update=StatusUpdate(status="in_progress"),
            db=db
        )
        assert in_prog_res["status"] == "in_progress", "Status was not updated"
        assert in_prog_res["responded_at"] is not None, "responded_at was not recorded"
        print(f"  [PASS] Ticket marked In Progress, responded_at={in_prog_res['responded_at']}")

        # 8. Resolve Ticket with Summary & Details
        print("\n[TEST 8] Resolving Ticket Workflow...")
        resolve_res = update_ticket_status(
            ticket_id=ticket.id,
            status_update=StatusUpdate(
                status="resolved",
                resolution_summary="Failed over to secondary ISP line and restarted IPsec daemon",
                resolution_details="Rerouted BGP peering via secondary carrier, re-negotiated Phase 1 & 2 SA, validated 50 concurrent tunnels."
            ),
            db=db
        )
        assert resolve_res["status"] == "resolved", "Status was not resolved"
        assert resolve_res["resolved_at"] is not None, "resolved_at was not set"
        assert resolve_res["resolution_summary"] == "Failed over to secondary ISP line and restarted IPsec daemon"
        assert resolve_res["resolution_details"] is not None
        assert resolve_res["sla_status"] in ["met", "breached"], f"Unexpected SLA: {resolve_res['sla_status']}"
        print(f"  [PASS] Ticket #{ticket.id} resolved with SLA state='{resolve_res['sla_status']}', resolved_at={resolve_res['resolved_at']}")

        # Verify Resolution Audit Record
        res_audit = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket.id, RoutingAudit.rule == "Ticket Resolved")
            .first()
        )
        assert res_audit is not None, "Missing 'Ticket Resolved' audit record"
        print(f"  [PASS] Audit timeline event logged: rule='{res_audit.rule}', reason='{res_audit.reason}'")

        # 9. Reopen Ticket
        print("\n[TEST 9] Reopening Ticket Workflow...")
        reopen_res = update_ticket_status(
            ticket_id=ticket.id,
            status_update=StatusUpdate(status="in_progress"),
            db=db
        )
        assert reopen_res["status"] == "in_progress", "Status did not reopen to in_progress"
        assert reopen_res["resolved_at"] is None, "resolved_at should be cleared when reopened"
        reopen_audit = (
            db.query(RoutingAudit)
            .filter(RoutingAudit.ticket_id == ticket.id, RoutingAudit.rule == "Ticket Reopened")
            .first()
        )
        assert reopen_audit is not None, "Missing 'Ticket Reopened' audit record"
        print(f"  [PASS] Ticket #{ticket.id} successfully reopened, resolved_at cleared, audit event logged.")

        # Re-resolve for analytics testing
        update_ticket_status(
            ticket_id=ticket.id,
            status_update=StatusUpdate(
                status="resolved",
                resolution_summary="Final resolution verified after customer check"
            ),
            db=db
        )

        # 10. Analytics Workbench Operational Metrics
        print("\n[TEST 10] Testing Analytics Operational Metrics...")
        analytics = get_analytics(db=db)
        assert "open_workload" in analytics, "Missing open_workload in analytics"
        assert "resolved_today" in analytics, "Missing resolved_today in analytics"
        assert "tickets_resolved_by_team" in analytics, "Missing tickets_resolved_by_team in analytics"
        assert analytics["resolved_today"] >= 1, f"Expected at least 1 resolved today, got {analytics['resolved_today']}"
        print(f"  [PASS] Operational Analytics: open_workload={analytics['open_workload']}, resolved_today={analytics['resolved_today']}, resolved_by_team={analytics['tickets_resolved_by_team']}")

        # 11. Delete Note
        print("\n[TEST 11] Deleting Note...")
        del_res = delete_ticket_note(ticket_id=ticket.id, note_id=cust_id, db=db)
        assert del_res.get("message") == "Note deleted successfully"
        notes_after_del = get_ticket_notes(ticket_id=ticket.id, db=db)
        assert not any(n["id"] == cust_id for n in notes_after_del["notes"])
        print(f"  [PASS] Note #{cust_id} successfully deleted.")

        # Cleanup test ticket
        db.query(TicketNote).filter(TicketNote.ticket_id == ticket.id).delete()
        db.query(RoutingAudit).filter(RoutingAudit.ticket_id == ticket.id).delete()
        db.query(Notification).filter(Notification.ticket_id == ticket.id).delete()
        db.query(Ticket).filter(Ticket.id == ticket.id).delete()
        db.commit()
        print("\n  [PASS] Test cleanup completed.")

        print("\n==================================================")
        print("ALL 11 WORKBENCH TESTS PASSED (100% SUCCESS)")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
