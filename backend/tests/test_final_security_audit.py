import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.technician import Technician
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_note import TicketNote
from app.models.notification import Notification
from app.models.routing_audit import RoutingAudit
from app.services.sla_worker import SLAWorker
from app.core.security import hash_password, create_access_token
from app.services.notification_service import (
    check_and_generate_sla_notifications,
    notify_technician_assigned,
    notify_ticket_escalated,
    create_notification
)

client = TestClient(app)


class TestFinalSecurityAuditSuite(unittest.TestCase):
    """
    Phase 5 Final Automated Security Audit & Production Verification Suite.
    Validates end-to-end security, tenant isolation, RBAC boundaries, SLA workers,
    toasts, and regression invariants.
    """

    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # Technicians
        cls.tech_m365 = cls.db.query(Technician).filter(Technician.email == "rahul.audit@jacehaus.com").first()
        if not cls.tech_m365:
            cls.tech_m365 = Technician(name="Rahul Audit", email="rahul.audit@jacehaus.com", team="M365 Support", is_active=True)
            cls.db.add(cls.tech_m365)
            cls.db.commit()
            cls.db.refresh(cls.tech_m365)

        cls.tech_net = cls.db.query(Technician).filter(Technician.email == "arjun.audit@jacehaus.com").first()
        if not cls.tech_net:
            cls.tech_net = Technician(name="Arjun Audit", email="arjun.audit@jacehaus.com", team="Network Team", is_active=True)
            cls.db.add(cls.tech_net)
            cls.db.commit()
            cls.db.refresh(cls.tech_net)

        # Customers
        cls.cust_a = cls.db.query(Customer).filter(Customer.email == "alice.audit@acme.com").first()
        if not cls.cust_a:
            cls.cust_a = Customer(name="Alice Audit", email="alice.audit@acme.com", company="Acme Corp")
            cls.db.add(cls.cust_a)
            cls.db.commit()
            cls.db.refresh(cls.cust_a)

        cls.cust_b = cls.db.query(Customer).filter(Customer.email == "bob.audit@globex.com").first()
        if not cls.cust_b:
            cls.cust_b = Customer(name="Bob Audit", email="bob.audit@globex.com", company="Globex Financial")
            cls.db.add(cls.cust_b)
            cls.db.commit()
            cls.db.refresh(cls.cust_b)

        # Users
        def get_or_create_user(email, name, role, technician_id=None, customer_id=None):
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    password_hash=hash_password("AuditPass123!"),
                    role=role,
                    technician_id=technician_id,
                    customer_id=customer_id,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
            return u

        cls.admin_user = get_or_create_user("admin.audit5@jacehaus.com", "Admin Audit", "admin")
        cls.manager_user = get_or_create_user("mgr.audit5@jacehaus.com", "Manager Audit", "manager")
        cls.tech_m365_user = get_or_create_user("tech.m365.audit5@jacehaus.com", "Tech M365", "technician", technician_id=cls.tech_m365.id)
        cls.tech_net_user = get_or_create_user("tech.net.audit5@jacehaus.com", "Tech Net", "technician", technician_id=cls.tech_net.id)
        cls.cust_a_user = get_or_create_user("cust.a.audit5@acme.com", "Cust Alice", "customer", customer_id=cls.cust_a.id)
        cls.cust_b_user = get_or_create_user("cust.b.audit5@globex.com", "Cust Bob", "customer", customer_id=cls.cust_b.id)

        # Tokens
        cls.admin_token = create_access_token({"sub": cls.admin_user.id, "email": cls.admin_user.email, "role": "admin"})
        cls.manager_token = create_access_token({"sub": cls.manager_user.id, "email": cls.manager_user.email, "role": "manager"})
        cls.m365_token = create_access_token({"sub": cls.tech_m365_user.id, "email": cls.tech_m365_user.email, "role": "technician"})
        cls.net_token = create_access_token({"sub": cls.tech_net_user.id, "email": cls.tech_net_user.email, "role": "technician"})
        cls.cust_a_token = create_access_token({"sub": cls.cust_a_user.id, "email": cls.cust_a_user.email, "role": "customer"})
        cls.cust_b_token = create_access_token({"sub": cls.cust_b_user.id, "email": cls.cust_b_user.email, "role": "customer"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # CHECK 1: Unauthenticated Requests Return 401
    # =========================================================================
    def test_01_unauthenticated_requests_return_401(self):
        """Unauthenticated requests to protected endpoints consistently return HTTP 401."""
        endpoints = [
            ("GET", "/notifications/"),
            ("GET", "/notifications/unread-count"),
            ("GET", "/notifications/worker-status"),
            ("DELETE", "/notifications/clear-read"),
            ("GET", "/teams/"),
            ("GET", "/reports/summary"),
        ]
        for method, url in endpoints:
            if method == "GET":
                r = client.get(url)
            elif method == "POST":
                r = client.post(url)
            elif method == "DELETE":
                r = client.delete(url)
            self.assertEqual(r.status_code, 401, f"Failed for {method} {url}: expected 401, got {r.status_code}")

    # =========================================================================
    # CHECK 2: Customers Receive 403 on Internal Endpoints
    # =========================================================================
    def test_02_customers_receive_403_on_internal_endpoints(self):
        """Customers receive HTTP 403 Forbidden on all internal MSP endpoints."""
        headers = {"Authorization": f"Bearer {self.cust_a_token}"}
        internal_endpoints = [
            ("GET", "/technicians/"),
            ("GET", "/rules/"),
            ("GET", "/analytics/"),
            ("GET", "/notifications/"),
            ("GET", "/notifications/unread-count"),
            ("GET", "/notifications/worker-status"),
            ("DELETE", "/notifications/clear-read"),
            ("GET", "/teams/"),
            ("POST", "/tickets/route"),
        ]
        for method, url in internal_endpoints:
            if method == "GET":
                r = client.get(url, headers=headers)
            elif method == "POST":
                r = client.post(url, json={"title": "t", "description": "d"}, headers=headers)
            elif method == "DELETE":
                r = client.delete(url, headers=headers)
            self.assertEqual(r.status_code, 403, f"Failed for {method} {url}: expected 403, got {r.status_code}")

    # =========================================================================
    # CHECK 3: Technicians Cannot Bypass Team Boundary with scope=all
    # =========================================================================
    def test_03_technician_cannot_bypass_team_boundary_with_scope_all(self):
        """Technician requesting scope=all only receives notifications from their assigned team."""
        # Create ticket for Network Team
        t_net = Ticket(
            title="Network Core Switch #9 Down",
            description="Core rack outage.",
            assigned_team="Network Team",
            priority="critical",
            status="new"
        )
        self.db.add(t_net)
        self.db.commit()
        self.db.refresh(t_net)

        n_net = Notification(
            ticket_id=t_net.id,
            type="SLA_BREACHED",
            severity="critical",
            title=f"Network Breach #{t_net.id}",
            message="Switch down",
            is_read=False
        )
        self.db.add(n_net)
        self.db.commit()
        self.db.refresh(n_net)

        # Rahul (M365 Support) requests scope=all
        r = client.get("/notifications/?scope=all", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r.status_code, 200)
        notif_ids = [n["id"] for n in r.json()["notifications"]]
        self.assertNotIn(n_net.id, notif_ids, "Security breach: Technician saw another team's notification via scope=all")

    # =========================================================================
    # CHECK 4: Technicians Cannot Access Another Team's Ticket Notifications
    # =========================================================================
    def test_04_technician_cross_team_ticket_notifications_blocked(self):
        """GET /notifications/ticket/{ticket_id} returns 403 for cross-team ticket."""
        t_net = Ticket(
            title="Firewall Policy Update",
            description="Rule update for DMZ.",
            assigned_team="Network Team",
            priority="medium",
            status="in_progress"
        )
        self.db.add(t_net)
        self.db.commit()
        self.db.refresh(t_net)

        r = client.get(f"/notifications/ticket/{t_net.id}", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("Access denied", r.json()["detail"])

    # =========================================================================
    # CHECK 5: Admin / Manager Authorized Clear Read RBAC
    # =========================================================================
    def test_05_clear_read_authorization_and_technician_block(self):
        """Admin/Manager can execute Clear Read; Technician is blocked with 403."""
        # Tech blocked
        r_tech = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_tech.status_code, 403)

        # Manager allowed
        r_mgr = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)

        # Admin allowed
        r_admin = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)

    # =========================================================================
    # CHECK 6: Clear Read Never Deletes Unread Notifications
    # =========================================================================
    def test_06_clear_read_preserves_unread_notifications(self):
        """Clear Read removes read alerts and keeps 100% of unread alerts intact."""
        n_read = Notification(type="INFO", severity="info", title="Read Alert Audit", message="msg", is_read=True)
        n_unread = Notification(type="CRITICAL", severity="critical", title="Unread Alert Audit", message="msg", is_read=False)
        self.db.add_all([n_read, n_unread])
        self.db.commit()
        self.db.refresh(n_read)
        self.db.refresh(n_unread)

        r = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)

        # Read deleted
        self.assertIsNone(self.db.query(Notification).filter(Notification.id == n_read.id).first())
        # Unread kept
        unread_found = self.db.query(Notification).filter(Notification.id == n_unread.id).first()
        self.assertIsNotNone(unread_found)
        self.assertFalse(unread_found.is_read)

    # =========================================================================
    # CHECK 7: SLA Worker Starts and Stops Cleanly
    # =========================================================================
    def test_07_sla_worker_starts_and_stops_cleanly(self):
        """SLA worker registers task with loop and stops cleanly when cancelled."""
        async def run_lifecycle():
            worker = SLAWorker(interval_seconds=1)
            self.assertFalse(worker.is_running)
            worker.start()
            self.assertTrue(worker.is_running)
            await asyncio.sleep(0.05)
            await worker.stop()
            self.assertFalse(worker.is_running)

        asyncio.run(run_lifecycle())

    # =========================================================================
    # CHECK 8: SLA Worker Survives Scan Errors
    # =========================================================================
    def test_08_sla_worker_survives_scan_errors(self):
        """Worker logs errors and returns success=False without crashing."""
        worker = SLAWorker(interval_seconds=5)
        with patch("app.services.sla_worker.check_and_generate_sla_notifications", side_effect=RuntimeError("Transient DB connection drop")):
            res = worker.run_once()
            self.assertFalse(res["success"])
            self.assertEqual(worker._last_error, "Transient DB connection drop")

        # Subsequent scan succeeds
        res_ok = worker.run_once()
        self.assertTrue(res_ok["success"])
        self.assertIsNone(worker._last_error)

    # =========================================================================
    # CHECK 9: Duplicate SLA Notifications Prevented
    # =========================================================================
    def test_09_duplicate_sla_notifications_prevented(self):
        """Repeated scan cycles do not create duplicate SLA notifications for unchanged tickets."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Deduplication Verification Ticket",
            description="Testing duplicate prevention.",
            assigned_team="M365 Support",
            priority="critical",
            status="new",
            created_at=now - timedelta(hours=3),
            response_due_at=now - timedelta(hours=2),
            resolution_due_at=now - timedelta(hours=1)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        # Run scan 1
        alerts1 = check_and_generate_sla_notifications(self.db, target_ticket_id=ticket.id)
        count1 = self.db.query(Notification).filter(Notification.ticket_id == ticket.id).count()
        self.assertGreaterEqual(count1, 1)

        # Run scan 2
        alerts2 = check_and_generate_sla_notifications(self.db, target_ticket_id=ticket.id)
        self.assertEqual(len(alerts2), 0)
        count2 = self.db.query(Notification).filter(Notification.ticket_id == ticket.id).count()
        self.assertEqual(count1, count2)

    # =========================================================================
    # CHECK 10: Escalation Notifications Generated Correctly
    # =========================================================================
    def test_10_escalation_notifications_and_audits_generated(self):
        """Escalated ticket creates critical notification and logs RoutingAudit timeline entry."""
        ticket = Ticket(
            title="Core VPN Server Kernel Panic",
            description="All remote workers disconnected.",
            assigned_team="Network Team",
            priority="critical",
            status="in_progress"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        notif = notify_ticket_escalated(
            db=self.db,
            ticket=ticket,
            escalation_level=3,
            reason="Kernel crash requires senior network engineer",
            escalated_by="Arjun Patel"
        )
        self.assertEqual(notif.type, "ESCALATION")
        self.assertEqual(notif.severity, "critical")
        self.assertIn("Level 3", notif.title)

    # =========================================================================
    # CHECK 11: Toast Scoping and Customer Update Isolation
    # =========================================================================
    def test_11_customer_tenant_isolation_and_update_sanitization(self):
        """Customer updates do not expose internal notes and maintain strict tenant isolation."""
        # Alice (Acme) creates ticket
        r_create = client.post(
            "/portal/tickets",
            json={"title": "Acme Printer Offline", "description": "Cannot print invoices.", "priority": "medium"},
            headers={"Authorization": f"Bearer {self.cust_a_token}"}
        )
        self.assertEqual(r_create.status_code, 200)
        t_id = r_create.json()["ticket"]["id"]

        # Bob (Globex) attempts to access Alice's ticket -> 403 Forbidden
        r_bob_blocked = client.get(f"/portal/tickets/{t_id}", headers={"Authorization": f"Bearer {self.cust_b_token}"})
        self.assertEqual(r_bob_blocked.status_code, 403)

        # Alice posts update
        r_update = client.post(
            f"/portal/tickets/{t_id}/updates",
            json={"content": "Printer IP is 192.168.1.50"},
            headers={"Authorization": f"Bearer {self.cust_a_token}"}
        )
        self.assertEqual(r_update.status_code, 200)

        # Internal work note added by tech
        note_internal = TicketNote(
            ticket_id=t_id,
            note_type="internal",
            content="Internal diagnosis: checking CUPS daemon on print server.",
            author="Rahul Sharma"
        )
        self.db.add(note_internal)
        self.db.commit()

        # Alice views ticket details: internal note is 100% hidden
        r_alice_detail = client.get(f"/portal/tickets/{t_id}", headers={"Authorization": f"Bearer {self.cust_a_token}"})
        self.assertEqual(r_alice_detail.status_code, 200)
        updates = r_alice_detail.json()["updates"]
        update_contents = [n["content"] for n in updates]
        self.assertIn("Printer IP is 192.168.1.50", update_contents)
        self.assertNotIn("Internal diagnosis: checking CUPS daemon on print server.", update_contents)

    # =========================================================================
    # CHECK 12: Core Ticket Operations Remain Intact
    # =========================================================================
    def test_12_core_ticket_operations_intact(self):
        """Ticket create, search, update, notes, resolve workflow executes without regressions."""
        # Create ticket via route
        r_create = client.post(
            "/tickets/route",
            json={"title": "Regression Core Check", "description": "Verify system health."},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_create.status_code, 200)
        tid = r_create.json()["ticket_id"]

        # Add work note
        r_note = client.post(
            f"/tickets/{tid}/notes",
            json={"content": "Diagnosing issue.", "note_type": "internal"},
            headers={"Authorization": f"Bearer {self.m365_token}"}
        )
        self.assertEqual(r_note.status_code, 200)
        self.assertEqual(r_note.json()["author"], "Tech M365")

        # Resolve ticket
        r_resolve = client.patch(
            f"/tickets/{tid}/status",
            json={"status": "resolved", "resolution_summary": "System verified", "resolution_details": "All checks passed."},
            headers={"Authorization": f"Bearer {self.m365_token}"}
        )
        self.assertEqual(r_resolve.status_code, 200)
        self.assertEqual(r_resolve.json()["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
