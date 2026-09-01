import sys
import os
from datetime import datetime, timezone

# Ensure stdout handles utf-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_note import TicketNote
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.main import run_db_migrations
from app.api.portal import (
    list_portal_customers,
    get_customer_profile,
    update_customer_profile,
    get_customer_dashboard,
    list_customer_tickets,
    get_customer_ticket_detail,
    create_customer_ticket,
    add_customer_ticket_update,
    reopen_customer_ticket,
    confirm_ticket_resolution,
    get_customer_notifications,
    mark_customer_notification_read,
    mark_all_customer_notifications_read,
    PortalTicketCreateRequest,
    CustomerUpdateCreate,
    CustomerProfileUpdate
)
from app.api.tickets import add_ticket_note, update_ticket_status, NoteCreate, StatusUpdate

def run_tests():
    print("=" * 65)
    print("VERIFYING CLIENT / CUSTOMER PORTAL")
    print("=" * 65)

    # 1. Run migrations & seeding
    run_db_migrations()
    db = SessionLocal()

    try:
        # -------------------------------------------------------------
        # [TEST 1] Schema & Seeding
        # -------------------------------------------------------------
        print("\n[TEST 1] Verifying Customer Database Schema & Seeding...")
        customers = db.query(Customer).filter(Customer.is_active == True).all()
        assert len(customers) >= 4, f"Expected >= 4 seeded customers, got {len(customers)}"
        print(f"  Found {len(customers)} active customers in database.")
        
        cust_a = db.query(Customer).filter(Customer.email == "john.doe@acme.com").first()
        cust_b = db.query(Customer).filter(Customer.email == "sarah.j@globex.com").first()
        assert cust_a is not None, "Customer A (John Doe) not found"
        assert cust_b is not None, "Customer B (Sarah Jenkins) not found"
        print(f"  Customer A: {cust_a.name} ({cust_a.company}) - ID: {cust_a.id}")
        print(f"  Customer B: {cust_b.name} ({cust_b.company}) - ID: {cust_b.id}")
        print("  [PASS] Customer schema and seeding verified.")

        # -------------------------------------------------------------
        # [TEST 2] Profile Retrieval & Update
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing Customer Profile GET & PATCH...")
        profile_data = get_customer_profile(customer=cust_a)
        assert profile_data["email"] == "john.doe@acme.com"
        assert profile_data["company"] == "Acme Corp"

        # Patch profile phone
        patch_res = update_customer_profile(
            payload=CustomerProfileUpdate(phone="+1 555-9999"),
            customer=cust_a,
            db=db
        )
        assert patch_res["profile"]["phone"] == "+1 555-9999"
        print("  [PASS] Customer profile endpoints working.")

        # -------------------------------------------------------------
        # [TEST 3] Customer Ticket Creation & Auto-Routing
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing Customer Ticket Creation via /portal/tickets...")
        create_payload = PortalTicketCreateRequest(
            title="Portal Test - Critical Firewall Outage at Branch",
            description="Our primary firewall has failed and the branch office has no VPN or internet connectivity.",
            category="Network",
            priority="critical"
        )
        res = create_customer_ticket(payload=create_payload, customer=cust_a, db=db)
        ticket_data = res["ticket"]
        ticket_id_a = ticket_data["id"]
        assert ticket_data["customer_id"] == cust_a.id
        assert ticket_data["customer_company"] == "Acme Corp"
        assert ticket_data["assigned_team"] == "Network Team"
        assert ticket_data["priority"] == "critical"
        assert ticket_data["sla"]["response_sla"] == "15m"
        print(f"  [PASS] Created Ticket #{ticket_id_a} assigned to {ticket_data['assigned_team']} with SLA {ticket_data['sla']['response_sla']}.")

        # Create ticket for Customer B
        create_payload_b = PortalTicketCreateRequest(
            title="Portal Test - Outlook 365 licensing problem",
            description="Outlook keeps asking to re-activate license key for finance team.",
            category="M365",
            priority="medium"
        )
        res_b = create_customer_ticket(payload=create_payload_b, customer=cust_b, db=db)
        ticket_id_b = res_b["ticket"]["id"]
        print(f"  [PASS] Created Ticket #{ticket_id_b} for Customer B ({cust_b.company}).")

        # -------------------------------------------------------------
        # [TEST 4] Customer Isolation & Security
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing Customer Isolation & Ownership Checks...")
        # Customer A lists tickets
        list_a = list_customer_tickets(customer=cust_a, db=db)
        ticket_ids_for_a = [t["id"] for t in list_a["tickets"]]
        assert ticket_id_a in ticket_ids_for_a, "Ticket A should be visible to Customer A"
        assert ticket_id_b not in ticket_ids_for_a, "Ticket B MUST NOT be visible to Customer A"
        print(f"  Customer A sees {len(ticket_ids_for_a)} ticket(s), Ticket #{ticket_id_b} is strictly hidden.")

        # Customer B attempts to access Customer A's ticket directly
        hacked = False
        try:
            get_customer_ticket_detail(ticket_id=ticket_id_a, customer=cust_b, db=db)
        except Exception as e:
            hacked = True
            print(f"  [PASS] Direct unauthorized access correctly blocked with exception: '{e}'.")
        assert hacked, "Customer B was able to access Customer A's ticket!"

        # -------------------------------------------------------------
        # [TEST 5] Customer Ticket Detail (Safe Sanitization)
        # -------------------------------------------------------------
        print("\n[TEST 5] Testing Customer Ticket Detail Sanitization...")
        detail = get_customer_ticket_detail(ticket_id=ticket_id_a, customer=cust_a, db=db)
        assert "ticket" in detail
        assert "updates" in detail
        assert "activity" in detail
        # Check that internal fields are NOT present
        assert "score" not in detail["ticket"]
        assert "matched_keywords" not in detail["ticket"]
        assert "escalation_reason" not in detail["ticket"]
        print("  [PASS] Ticket detail returned safely without internal routing scores or escalation diagnostics.")

        # -------------------------------------------------------------
        # [TEST 6] Internal Work Note Hiding vs Customer Update
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing Internal Work Notes Invisibility to Customers...")
        # Technician adds internal note via internal API
        add_ticket_note(
            ticket_id=ticket_id_a,
            note_data=NoteCreate(
                note_type="internal",
                content="INTERNAL: Investigating Core Switch IPsec config. Secret diagnostic info.",
                author="Arjun Patel"
            ),
            db=db
        )
        # Technician adds customer update via internal API
        add_ticket_note(
            ticket_id=ticket_id_a,
            note_data=NoteCreate(
                note_type="customer",
                content="PUBLIC: Engineer is currently investigating the firewall failover link.",
                author="Network Support Team"
            ),
            db=db
        )

        # Customer fetches ticket details
        detail = get_customer_ticket_detail(ticket_id=ticket_id_a, customer=cust_a, db=db)
        updates = detail["updates"]
        update_contents = [u["content"] for u in updates]
        assert any("PUBLIC: Engineer is currently investigating" in c for c in update_contents), "Customer update should be visible"
        assert not any("INTERNAL: Investigating Core Switch" in c for c in update_contents), "Internal work note MUST NOT be visible"
        print("  [PASS] Internal work notes are 100% hidden from Customer Portal; Customer Updates are visible.")

        # -------------------------------------------------------------
        # [TEST 7] Customer Reply / Update Workflow
        # -------------------------------------------------------------
        print("\n[TEST 7] Testing Customer Reply / Update Workflow...")
        reply_res = add_customer_ticket_update(
            ticket_id=ticket_id_a,
            payload=CustomerUpdateCreate(content="Thank you. We have also rebooted the backup ISP modem on our side."),
            customer=cust_a,
            db=db
        )
        assert reply_res["update"]["content"] == "Thank you. We have also rebooted the backup ISP modem on our side."
        print("  [PASS] Customer reply successfully posted and logged to timeline.")

        # -------------------------------------------------------------
        # [TEST 8] Ticket Resolution & Reopen Workflow
        # -------------------------------------------------------------
        print("\n[TEST 8] Testing Ticket Resolution Confirmation & Reopening...")
        # Technician marks ticket resolved via internal API
        update_ticket_status(
            ticket_id=ticket_id_a,
            status_update=StatusUpdate(
                status="resolved",
                resolution_summary="Replaced faulty SFP transceiver on edge firewall",
                resolution_details="Re-routed traffic to secondary fiber link."
            ),
            db=db
        )

        # Customer confirms resolution
        confirm_res = confirm_ticket_resolution(ticket_id=ticket_id_a, customer=cust_a, db=db)
        assert "confirmed" in confirm_res["message"].lower()

        # Customer reopens ticket
        reopen_res = reopen_customer_ticket(ticket_id=ticket_id_a, customer=cust_a, db=db)
        assert reopen_res["ticket"]["status"] == "in_progress"
        print("  [PASS] Customer confirmation and reopen workflow verified.")

        # -------------------------------------------------------------
        # [TEST 9] Customer Notifications
        # -------------------------------------------------------------
        print("\n[TEST 9] Testing Customer Notifications Isolation...")
        notif_res = get_customer_notifications(customer=cust_a, db=db)
        notifs = notif_res["notifications"]
        print(f"  Customer A received {len(notifs)} scoped notification(s).")
        # Ensure all notifications belong to Customer A's tickets
        for n in notifs:
            assert n["ticket_id"] in ticket_ids_for_a or n["ticket_id"] == ticket_id_a, f"Notification ticket {n['ticket_id']} does not belong to Customer A"
        print("  [PASS] Customer notifications are strictly scoped.")

        # -------------------------------------------------------------
        # [TEST 10] Customer Dashboard Metrics
        # -------------------------------------------------------------
        print("\n[TEST 10] Testing Customer Dashboard Metrics...")
        dash = get_customer_dashboard(customer=cust_a, db=db)
        assert "metrics" in dash
        assert dash["metrics"]["total_tickets"] >= 1
        assert "recent_tickets" in dash
        assert "recent_activity" in dash
        print(f"  Dashboard Metrics for {dash['customer']['name']}: {dash['metrics']}")
        print("  [PASS] Customer dashboard metrics verified.")

        print("\n" + "=" * 65)
        print("ALL 10 CLIENT / CUSTOMER PORTAL TESTS PASSED (100% SUCCESS)!")
        print("=" * 65)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
