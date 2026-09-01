import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.technician import Technician
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_note import TicketNote
from app.core.security import hash_password, create_access_token
from app.services.sla_service import compute_ticket_sla_details

client = TestClient(app)


class TestReportingSuite(unittest.TestCase):
    """
    Automated test suite for Phase 6: Executive & Client SLA Reporting.
    Tests summary metrics, SLA calculations, multi-tenant isolation,
    query param tampering resistance, CSV exports, and PDF generation.
    """

    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # 1. Technicians
        cls.tech_m365 = cls.db.query(Technician).filter(Technician.email == "rahul.rep@jacehaus.com").first()
        if not cls.tech_m365:
            cls.tech_m365 = Technician(name="Rahul Reporter", email="rahul.rep@jacehaus.com", team="M365 Support", is_active=True)
            cls.db.add(cls.tech_m365)
            cls.db.commit()
            cls.db.refresh(cls.tech_m365)

        cls.tech_net = cls.db.query(Technician).filter(Technician.email == "arjun.rep@jacehaus.com").first()
        if not cls.tech_net:
            cls.tech_net = Technician(name="Arjun Reporter", email="arjun.rep@jacehaus.com", team="Network Team", is_active=True)
            cls.db.add(cls.tech_net)
            cls.db.commit()
            cls.db.refresh(cls.tech_net)

        # 2. Customers
        cls.cust_acme = cls.db.query(Customer).filter(Customer.email == "john.rep@acme.com").first()
        if not cls.cust_acme:
            cls.cust_acme = Customer(name="John Acme", email="john.rep@acme.com", company="Acme Corp")
            cls.db.add(cls.cust_acme)
            cls.db.commit()
            cls.db.refresh(cls.cust_acme)

        cls.cust_globex = cls.db.query(Customer).filter(Customer.email == "sarah.rep@globex.com").first()
        if not cls.cust_globex:
            cls.cust_globex = Customer(name="Sarah Globex", email="sarah.rep@globex.com", company="Globex Financial")
            cls.db.add(cls.cust_globex)
            cls.db.commit()
            cls.db.refresh(cls.cust_globex)

        # 3. Users
        def get_or_create_user(email, name, role, technician_id=None, customer_id=None, company=None):
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    password_hash=hash_password("RepPass123!"),
                    role=role,
                    technician_id=technician_id,
                    customer_id=customer_id,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
            return u

        cls.admin_user = get_or_create_user("admin.rep@jacehaus.com", "Admin Rep", "admin")
        cls.manager_user = get_or_create_user("mgr.rep@jacehaus.com", "Manager Rep", "manager")
        cls.tech_user = get_or_create_user("tech.rep@jacehaus.com", "Tech Rep", "technician", technician_id=cls.tech_m365.id)
        cls.acme_user = get_or_create_user("acme.user.rep@acme.com", "John Acme User", "customer", customer_id=cls.cust_acme.id, company="Acme Corp")
        cls.globex_user = get_or_create_user("globex.user.rep@globex.com", "Sarah Globex User", "customer", customer_id=cls.cust_globex.id, company="Globex Financial")

        # Tokens
        cls.admin_token = create_access_token({"sub": cls.admin_user.id, "email": cls.admin_user.email, "role": "admin"})
        cls.manager_token = create_access_token({"sub": cls.manager_user.id, "email": cls.manager_user.email, "role": "manager"})
        cls.tech_token = create_access_token({"sub": cls.tech_user.id, "email": cls.tech_user.email, "role": "technician"})
        cls.acme_token = create_access_token({"sub": cls.acme_user.id, "email": cls.acme_user.email, "role": "customer"})
        cls.globex_token = create_access_token({"sub": cls.globex_user.id, "email": cls.globex_user.email, "role": "customer"})

        # 4. Seed test tickets for reporting
        now = datetime.now(timezone.utc)
        cls.t_acme1 = Ticket(
            title="Acme OneDrive Sync Fail",
            description="Sync issue on Windows 11",
            category="Microsoft 365",
            assigned_team="M365 Support",
            customer_id=cls.cust_acme.id,
            customer_name=cls.cust_acme.name,
            customer_company=cls.cust_acme.company,
            priority="high",
            status="resolved",
            created_at=now - timedelta(days=2),
            responded_at=now - timedelta(days=2, hours=-1),
            resolved_at=now - timedelta(days=1),
            routing_method="rule_engine"
        )
        cls.t_acme2 = Ticket(
            title="Acme Teams Calling Broken",
            description="Audio fails on incoming calls",
            category="Microsoft 365",
            assigned_team="M365 Support",
            customer_id=cls.cust_acme.id,
            customer_name=cls.cust_acme.name,
            customer_company=cls.cust_acme.company,
            priority="critical",
            status="in_progress",
            created_at=now - timedelta(hours=3),
            response_due_at=now - timedelta(hours=2),
            routing_method="rule_engine"
        )
        cls.t_globex1 = Ticket(
            title="Globex Core Firewall Latency",
            description="Packet drop on interface ge-0/0/1",
            category="Network",
            assigned_team="Network Team",
            customer_id=cls.cust_globex.id,
            customer_name=cls.cust_globex.name,
            customer_company=cls.cust_globex.company,
            priority="critical",
            status="new",
            created_at=now - timedelta(hours=1),
            routing_method="rule_engine"
        )
        cls.db.add_all([cls.t_acme1, cls.t_acme2, cls.t_globex1])
        cls.db.commit()
        cls.db.refresh(cls.t_acme1)
        cls.db.refresh(cls.t_acme2)
        cls.db.refresh(cls.t_globex1)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # TEST 1: Unauthenticated Reporting Requests Return 401
    # =========================================================================
    def test_01_unauthenticated_reporting_returns_401(self):
        """Unauthenticated requests to all /reports endpoints return HTTP 401."""
        endpoints = [
            "/reports/summary",
            "/reports/sla",
            "/reports/tickets",
            "/reports/export/csv",
            "/reports/export/pdf",
        ]
        for ep in endpoints:
            r = client.get(ep)
            self.assertEqual(r.status_code, 401, f"Endpoint {ep} did not enforce 401 unauthenticated.")

    # =========================================================================
    # TEST 2: Customer Blocked from Internal-Only Endpoints
    # =========================================================================
    def test_02_customer_cannot_access_internal_endpoints(self):
        """Customer users receive HTTP 403 when requesting internal rules/analytics/users."""
        headers = {"Authorization": f"Bearer {self.acme_token}"}
        self.assertEqual(client.get("/rules/", headers=headers).status_code, 403)
        self.assertEqual(client.get("/analytics/", headers=headers).status_code, 403)
        self.assertEqual(client.get("/technicians/", headers=headers).status_code, 403)

    # =========================================================================
    # TEST 3: Customer Report Only Contains Their Own Organization Data
    # =========================================================================
    def test_03_customer_report_scoped_to_own_organization(self):
        """Customer A (Acme) only receives Acme Corp tickets and metrics in /reports/summary."""
        r = client.get("/reports/summary", headers={"Authorization": f"Bearer {self.acme_token}"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["organization_name"], "Acme Corp")
        self.assertTrue(data["is_customer_view"])

        # Fetch tickets list
        r_t = client.get("/reports/tickets", headers={"Authorization": f"Bearer {self.acme_token}"})
        self.assertEqual(r_t.status_code, 200)
        companies = {t["customer_company"] for t in r_t.json()["tickets"]}
        self.assertTrue(all(c == "Acme Corp" for c in companies if c))
        # Globex ticket must never be present
        ticket_ids = [t["id"] for t in r_t.json()["tickets"]]
        self.assertNotIn(self.t_globex1.id, ticket_ids)

    # =========================================================================
    # TEST 4: Customer Query Param Tampering Override
    # =========================================================================
    def test_04_customer_query_param_tampering_prevented(self):
        """If Customer A passes ?customer_id=<Globex_ID>, backend overrides to Acme Corp."""
        r = client.get(
            f"/reports/summary?customer_id={self.cust_globex.id}",
            headers={"Authorization": f"Bearer {self.acme_token}"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["organization_name"], "Acme Corp")

        # Verify ticket list
        r_t = client.get(
            f"/reports/tickets?customer_id={self.cust_globex.id}",
            headers={"Authorization": f"Bearer {self.acme_token}"}
        )
        ticket_ids = [t["id"] for t in r_t.json()["tickets"]]
        self.assertNotIn(self.t_globex1.id, ticket_ids)

    # =========================================================================
    # TEST 5: Admin Can Generate Organization-Wide Reports
    # =========================================================================
    def test_05_admin_organization_wide_report(self):
        """Admin can access organization-wide report covering all customers and teams."""
        r = client.get("/reports/summary", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["is_customer_view"])
        self.assertGreaterEqual(data["summary"]["total_tickets"], 3)
        self.assertIn("Acme Corp", data["summary"]["tickets_by_customer"])
        self.assertIn("Globex Financial", data["summary"]["tickets_by_customer"])

    # =========================================================================
    # TEST 6: Manager Can Generate Organization-Wide Reports
    # =========================================================================
    def test_06_manager_organization_wide_report(self):
        """Manager can generate executive summaries and filter by customer."""
        r = client.get(
            f"/reports/summary?customer_id={self.cust_globex.id}",
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["organization_name"], "Globex Financial")

    # =========================================================================
    # TEST 7: CSV Export Works with Valid Content & Headers
    # =========================================================================
    def test_07_csv_export_format_and_headers(self):
        """GET /reports/export/csv returns valid CSV stream with required columns."""
        r = client.get("/reports/export/csv", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", r.headers["Content-Disposition"])
        content = r.text
        self.assertIn("Ticket ID,Created Date (UTC),Customer Name,Company / Organization", content)
        self.assertIn("Acme OneDrive Sync Fail", content)
        self.assertIn("Globex Core Firewall Latency", content)

    # =========================================================================
    # TEST 8: PDF Executive Report Generation
    # =========================================================================
    def test_08_pdf_export_generation(self):
        """GET /reports/export/pdf returns valid binary PDF document."""
        r = client.get("/reports/export/pdf", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", r.headers["Content-Disposition"])
        # PDF magic header
        self.assertTrue(r.content.startswith(b"%PDF-"))
        self.assertGreater(len(r.content), 1000)

    # =========================================================================
    # TEST 9: Date Filtering (Start Date & End Date)
    # =========================================================================
    def test_09_date_filtering(self):
        """Date filters constrain report tickets to the specified window."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        r = client.get(
            f"/reports/summary?start_date={yesterday}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("start_date", data["filters"])

    # =========================================================================
    # TEST 10: SLA Performance Report Calculations
    # =========================================================================
    def test_10_sla_performance_calculations(self):
        """GET /reports/sla computes compliance rates, breaches, and priority breakdowns."""
        r = client.get("/reports/sla", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)
        sla = r.json()["sla"]
        self.assertIn("total_evaluated", sla)
        self.assertIn("overall_sla_compliance_rate", sla)
        self.assertIn("sla_by_priority", sla)
        self.assertIn("critical", sla["sla_by_priority"])
        self.assertIn("high", sla["sla_by_priority"])

    # =========================================================================
    # TEST 11: Team and Priority Filtering
    # =========================================================================
    def test_11_team_and_priority_filtering(self):
        """Filtering by team='Network Team' and priority='critical' returns exact subset."""
        r = client.get(
            "/reports/tickets?team=Network Team&priority=critical",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r.status_code, 200)
        tickets = r.json()["tickets"]
        for t in tickets:
            self.assertEqual(t["assigned_team"], "Network Team")
            self.assertEqual(t["priority"].lower(), "critical")

    # =========================================================================
    # TEST 12: Customer PDF Export Isolation
    # =========================================================================
    def test_12_customer_pdf_export_isolation(self):
        """Customer downloading PDF report receives an Acme Corp scoped document."""
        r = client.get("/reports/export/pdf", headers={"Authorization": f"Bearer {self.acme_token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF-"))
        self.assertIn("executive_sla_report_acme_corp", r.headers["Content-Disposition"])

    # =========================================================================
    # TEST 13: Internal Notes Never Included in Customer Reports
    # =========================================================================
    def test_13_internal_notes_never_in_customer_reports(self):
        """Internal work notes are never surfaced in customer-facing report exports."""
        # Add internal work note
        note = TicketNote(
            ticket_id=self.t_acme1.id,
            note_type="internal",
            content="Internal proprietary diagnosis: check registry subkey 0x44.",
            author="Rahul Sharma"
        )
        self.db.add(note)
        self.db.commit()

        # Customer requests CSV export
        r_csv = client.get("/reports/export/csv", headers={"Authorization": f"Bearer {self.acme_token}"})
        self.assertEqual(r_csv.status_code, 200)
        self.assertNotIn("Internal proprietary diagnosis", r_csv.text)

    # =========================================================================
    # TEST 14: Cross-Tenant Customer Export Attempt Blocked
    # =========================================================================
    def test_14_cross_tenant_customer_export_blocked(self):
        """Customer A cannot download Customer B's CSV by tampering with URL parameters."""
        r_csv = client.get(
            f"/reports/export/csv?customer_id={self.cust_globex.id}",
            headers={"Authorization": f"Bearer {self.acme_token}"}
        )
        self.assertEqual(r_csv.status_code, 200)
        self.assertNotIn("Globex Financial", r_csv.text)
        self.assertNotIn("Globex Core Firewall Latency", r_csv.text)

    # =========================================================================
    # TEST 15: Existing Core Ticket Operations Remain Intact
    # =========================================================================
    def test_15_existing_core_ticket_operations_intact(self):
        """Verify ticket routing and assignment continues functioning normally."""
        r = client.post(
            "/tickets/route",
            json={"title": "M365 OneDrive Reporting Check", "description": "Verification of routing."},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("ticket_id", r.json())


if __name__ == "__main__":
    unittest.main()
