import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.technician import Technician
from app.models.team import Team
from app.models.csat import CSATRating
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.models.ticket_note import TicketNote
from app.core.security import create_access_token

client = TestClient(app)


class TestCSATResolutionRatingSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # Canonical Customers
        cls.cust_acme = cls.db.query(Customer).filter(Customer.email == "john.doe@acme.com").first()
        cls.cust_globex = cls.db.query(Customer).filter(Customer.email == "sarah.j@globex.com").first()

        # Canonical Users
        cls.user_admin = cls.db.query(User).filter(User.email == "admin@jacehaus.com").first()
        cls.user_manager = cls.db.query(User).filter(User.email == "manager@jacehaus.com").first()
        cls.user_tech = cls.db.query(User).filter(User.email == "rahul.sharma@jacehaus.com").first()
        cls.user_cust_acme = cls.db.query(User).filter(User.email == "john.doe@acme.com").first()
        cls.user_cust_globex = cls.db.query(User).filter(User.email == "sarah.j@globex.com").first()

        # JWT Tokens
        cls.admin_token = create_access_token({"sub": str(cls.user_admin.id), "role": "admin", "email": cls.user_admin.email})
        cls.manager_token = create_access_token({"sub": str(cls.user_manager.id), "role": "manager", "email": cls.user_manager.email})
        cls.tech_token = create_access_token({"sub": str(cls.user_tech.id), "role": "technician", "email": cls.user_tech.email})
        cls.cust_acme_token = create_access_token({"sub": str(cls.user_cust_acme.id), "role": "customer", "email": cls.user_cust_acme.email, "customer_id": cls.cust_acme.id})
        cls.cust_globex_token = create_access_token({"sub": str(cls.user_cust_globex.id), "role": "customer", "email": cls.user_cust_globex.email, "customer_id": cls.cust_globex.id})

        # Create Resolved Ticket for Acme
        cls.ticket_acme_resolved = Ticket(
            title="Acme Resolved Printer Issue",
            description="Office printer network configuration resolved",
            customer_id=cls.cust_acme.id,
            customer_name=cls.cust_acme.name,
            customer_company=cls.cust_acme.company,
            customer_email=cls.cust_acme.email,
            assigned_team="Network Team",
            priority="medium",
            status="resolved",
            resolved_at=datetime.now(timezone.utc)
        )
        # Create Open Ticket for Acme
        cls.ticket_acme_open = Ticket(
            title="Acme Open Server Issue",
            description="Server RAM upgrade required",
            customer_id=cls.cust_acme.id,
            customer_name=cls.cust_acme.name,
            customer_company=cls.cust_acme.company,
            customer_email=cls.cust_acme.email,
            assigned_team="Endpoint Team",
            priority="high",
            status="in_progress"
        )
        # Create Resolved Ticket for Globex
        cls.ticket_globex_resolved = Ticket(
            title="Globex Resolved VPN Issue",
            description="SSL VPN tunnel credentials refreshed",
            customer_id=cls.cust_globex.id,
            customer_name=cls.cust_globex.name,
            customer_company=cls.cust_globex.company,
            customer_email=cls.cust_globex.email,
            assigned_team="Security Team",
            priority="critical",
            status="resolved",
            resolved_at=datetime.now(timezone.utc)
        )

        cls.db.add_all([cls.ticket_acme_resolved, cls.ticket_acme_open, cls.ticket_globex_resolved])
        cls.db.commit()
        cls.db.refresh(cls.ticket_acme_resolved)
        cls.db.refresh(cls.ticket_acme_open)
        cls.db.refresh(cls.ticket_globex_resolved)

    @classmethod
    def tearDownClass(cls):
        # Clean up test tickets and any linked CSATs
        cls.db.query(CSATRating).filter(CSATRating.ticket_id.in_([
            cls.ticket_acme_resolved.id,
            cls.ticket_acme_open.id,
            cls.ticket_globex_resolved.id
        ])).delete(synchronize_session=False)
        cls.db.query(Ticket).filter(Ticket.id.in_([
            cls.ticket_acme_resolved.id,
            cls.ticket_acme_open.id,
            cls.ticket_globex_resolved.id
        ])).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    # -------------------------------------------------------------
    # 1. Customer submits 5★ rating for own resolved ticket
    # -------------------------------------------------------------
    def test_01_customer_submit_rating_success(self):
        """Customer can submit 5-star rating for own resolved ticket."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_acme_resolved.id}",
            json={"rating": 5, "feedback": "Outstanding resolution speed and polite technician."},
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["csat"]["rating"], 5)
        self.assertEqual(data["csat"]["rating_label"], "Very Satisfied")
        self.assertEqual(data["csat"]["feedback"], "Outstanding resolution speed and polite technician.")

    # -------------------------------------------------------------
    # 2. Customer cannot rate another customer's ticket (403)
    # -------------------------------------------------------------
    def test_02_customer_cannot_rate_another_customer_ticket(self):
        """Customer A cannot rate Customer B's ticket."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_globex_resolved.id}",
            json={"rating": 5, "feedback": "Hacking attempt rating"},
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access denied", res.json()["detail"])

    # -------------------------------------------------------------
    # 3. Unauthenticated request returns 401
    # -------------------------------------------------------------
    def test_03_unauthenticated_request_rejected(self):
        """Unauthenticated CSAT submission or status check returns 401 or 403."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_acme_resolved.id}",
            json={"rating": 5}
        )
        # Without auth header, portal auth dependency enforces 401/403
        self.assertIn(res.status_code, [401, 403, 404])

    # -------------------------------------------------------------
    # 4. Customer cannot rate unresolved ticket (400)
    # -------------------------------------------------------------
    def test_04_cannot_rate_unresolved_ticket(self):
        """Submitting rating for new or in_progress ticket returns 400."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_acme_open.id}",
            json={"rating": 4, "feedback": "Still open but rating anyway"},
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Only resolved tickets can receive satisfaction ratings", res.json()["detail"])

    # -------------------------------------------------------------
    # 5. Invalid rating below 1 rejected (400)
    # -------------------------------------------------------------
    def test_05_invalid_rating_below_1_rejected(self):
        """Rating of 0 or negative is rejected."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_globex_resolved.id}",
            json={"rating": 0, "feedback": "Zero stars"},
            headers={"Authorization": f"Bearer {self.cust_globex_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("between 1 and 5", res.json()["detail"])

    # -------------------------------------------------------------
    # 6. Invalid rating above 5 rejected (400)
    # -------------------------------------------------------------
    def test_06_invalid_rating_above_5_rejected(self):
        """Rating above 5 is rejected."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_globex_resolved.id}",
            json={"rating": 6, "feedback": "6 stars!"},
            headers={"Authorization": f"Bearer {self.cust_globex_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("between 1 and 5", res.json()["detail"])

    # -------------------------------------------------------------
    # 7. Duplicate rating is rejected/prevented (400)
    # -------------------------------------------------------------
    def test_07_duplicate_rating_rejected(self):
        """Attempting to rate a ticket that already has a rating returns 400."""
        # ticket_acme_resolved was already rated in test_01
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_acme_resolved.id}",
            json={"rating": 4, "feedback": "Second rating attempt"},
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("already been submitted", res.json()["detail"])

    # -------------------------------------------------------------
    # 8. Feedback is optional
    # -------------------------------------------------------------
    def test_08_feedback_is_optional(self):
        """Rating submitted with None/empty feedback succeeds."""
        # Create another resolved ticket for Globex
        db = SessionLocal()
        t = Ticket(
            title="Globex Optional Feedback Ticket",
            description="Testing optional feedback",
            customer_id=self.cust_globex.id,
            customer_name=self.cust_globex.name,
            customer_company=self.cust_globex.company,
            assigned_team="Network Team",
            priority="low",
            status="resolved",
            resolved_at=datetime.now(timezone.utc)
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        tid = t.id
        db.close()

        res = client.post(
            f"/portal/csat/ticket/{tid}",
            json={"rating": 4},
            headers={"Authorization": f"Bearer {self.cust_globex_token}"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["csat"]["rating"], 4)
        self.assertIsNone(res.json()["csat"]["feedback"])

    # -------------------------------------------------------------
    # 9. Rating is persisted correctly in database
    # -------------------------------------------------------------
    def test_09_rating_persisted_in_db(self):
        """CSAT record exists in database with matching ticket_id and customer_id."""
        db = SessionLocal()
        record = db.query(CSATRating).filter(CSATRating.ticket_id == self.ticket_acme_resolved.id).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.rating, 5)
        self.assertEqual(record.customer_id, self.cust_acme.id)
        db.close()

    # -------------------------------------------------------------
    # 10. Admin can access CSAT analytics
    # -------------------------------------------------------------
    def test_10_admin_can_access_csat_analytics(self):
        """Admin user can query GET /reports/csat/summary."""
        res = client.get(
            "/reports/csat/summary",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("overall_csat_percentage", data)
        self.assertIn("average_rating", data)
        self.assertIn("star_breakdown", data)
        self.assertIn("csat_by_customer", data)
        self.assertIn("csat_by_team", data)

    # -------------------------------------------------------------
    # 11. Manager can access CSAT analytics
    # -------------------------------------------------------------
    def test_11_manager_can_access_csat_analytics(self):
        """Manager user can query GET /reports/csat/summary."""
        res = client.get(
            "/reports/csat/summary",
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("overall_csat_percentage", res.json())

    # -------------------------------------------------------------
    # 12. Customer gets scoped organization CSAT data in reports
    # -------------------------------------------------------------
    def test_12_customer_scoped_csat_reports(self):
        """Customer accessing /reports/csat/summary sees only their organization's metrics and no internal team breakdowns."""
        res = client.get(
            "/reports/csat/summary",
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_customer_view"])
        self.assertEqual(data["csat_by_team"], {})
        self.assertEqual(data["csat_by_technician"], {})

    # -------------------------------------------------------------
    # 13. Customer sees only own organization's CSAT data
    # -------------------------------------------------------------
    def test_13_customer_portal_csat_status_check(self):
        """Customer A can check own ticket CSAT status, blocked from Customer B's ticket."""
        # Own ticket -> 200
        res_own = client.get(
            f"/portal/csat/ticket/{self.ticket_acme_resolved.id}",
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res_own.status_code, 200)
        self.assertTrue(res_own.json()["has_rated"])

        # Other's ticket -> 403
        res_other = client.get(
            f"/portal/csat/ticket/{self.ticket_globex_resolved.id}",
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res_other.status_code, 403)

    # -------------------------------------------------------------
    # 14. Low rating generates internal notification (1-2 stars)
    # -------------------------------------------------------------
    def test_14_low_rating_generates_internal_notification(self):
        """Submitting a 1 or 2-star rating emits an internal CSAT_ALERT notification."""
        # Create another resolved ticket for Globex to rate 1-star
        db = SessionLocal()
        t_low = Ticket(
            title="Globex Low Rating Ticket",
            description="Outage resolved poorly",
            customer_id=self.cust_globex.id,
            customer_name=self.cust_globex.name,
            customer_company=self.cust_globex.company,
            assigned_team="Security Team",
            priority="critical",
            status="resolved",
            resolved_at=datetime.now(timezone.utc)
        )
        db.add(t_low)
        db.commit()
        db.refresh(t_low)
        t_low_id = t_low.id
        db.close()

        res = client.post(
            f"/portal/csat/ticket/{t_low_id}",
            json={"rating": 1, "feedback": "Took 4 hours to get someone on the phone!"},
            headers={"Authorization": f"Bearer {self.cust_globex_token}"}
        )
        self.assertEqual(res.status_code, 200)

        # Check notifications for CSAT_ALERT
        db = SessionLocal()
        notif = db.query(Notification).filter(
            Notification.ticket_id == t_low_id,
            Notification.type == "CSAT_ALERT"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.severity, "critical")
        self.assertIn("Low CSAT Alert (1★)", notif.title)
        self.assertIn("Took 4 hours", notif.message)
        db.close()

    # -------------------------------------------------------------
    # 15. Low-rating notification is deduplicated
    # -------------------------------------------------------------
    def test_15_low_rating_notification_deduplicated(self):
        """Notification helper does not create duplicates for the same ticket."""
        db = SessionLocal()
        ticket = db.query(Ticket).filter(Ticket.id == self.ticket_acme_resolved.id).first()
        from app.services.notification_service import notify_low_csat_rating
        n1 = notify_low_csat_rating(db, ticket, 2, "John Doe", "Acme Corp", "Bad experience")
        n2 = notify_low_csat_rating(db, ticket, 2, "John Doe", "Acme Corp", "Bad experience")
        self.assertEqual(n1.id, n2.id)
        db.close()

    # -------------------------------------------------------------
    # 16. CSAT appears in reporting summary correctly
    # -------------------------------------------------------------
    def test_16_csat_reporting_summary_calculations(self):
        """Verify CSAT metrics calculation (total_responses, average_rating, response_rate)."""
        res = client.get(
            "/reports/csat/summary",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["total_responses"], 2)
        self.assertGreater(data["average_rating"], 0)
        self.assertGreaterEqual(data["low_rating_count"], 1)

    # -------------------------------------------------------------
    # 17. CSAT does not expose internal work notes
    # -------------------------------------------------------------
    def test_17_csat_does_not_expose_internal_work_notes(self):
        """Customer accessing portal CSAT or ticket detail never sees internal work notes."""
        db = SessionLocal()
        note = TicketNote(
            ticket_id=self.ticket_acme_resolved.id,
            note_type="internal",
            content="TOP SECRET internal technician diagnosis",
            author="Rahul Sharma"
        )
        db.add(note)
        db.commit()
        db.close()

        res = client.get(
            f"/portal/tickets/{self.ticket_acme_resolved.id}",
            headers={"Authorization": f"Bearer {self.cust_acme_token}"}
        )
        self.assertEqual(res.status_code, 200)
        updates_text = " ".join([u["content"] for u in res.json().get("updates", [])])
        self.assertNotIn("TOP SECRET", updates_text)

    # -------------------------------------------------------------
    # 18. Technician cannot manipulate customer ratings
    # -------------------------------------------------------------
    def test_18_technician_cannot_manipulate_customer_ratings(self):
        """Technician role cannot POST to customer rating endpoints."""
        res = client.post(
            f"/portal/csat/ticket/{self.ticket_globex_resolved.id}",
            json={"rating": 5, "feedback": "Technician self-rating"},
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        # Technician has no customer account -> 403 Forbidden
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # 19. CSAT audit event is created in routing_audits
    # -------------------------------------------------------------
    def test_19_csat_audit_event_created(self):
        """Submitting CSAT logs an audit event with rule 'CSAT Rating Submitted'."""
        db = SessionLocal()
        audit = db.query(RoutingAudit).filter(
            RoutingAudit.ticket_id == self.ticket_acme_resolved.id,
            RoutingAudit.rule == "CSAT Rating Submitted"
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("5★ rating", audit.reason)
        db.close()

    # -------------------------------------------------------------
    # 20. Division-by-zero handled safely
    # -------------------------------------------------------------
    def test_20_division_by_zero_handled_safely(self):
        """Querying CSAT summary with date range containing 0 responses returns 0.0 without errors."""
        res = client.get(
            "/reports/csat/summary?start_date=1999-01-01&end_date=1999-01-02",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_responses"], 0)
        self.assertEqual(data["overall_csat_percentage"], 0.0)
        self.assertEqual(data["average_rating"], 0.0)
        self.assertEqual(data["response_rate"], 0.0)

    # -------------------------------------------------------------
    # 21. Rating remains associated with correct ticket and customer
    # -------------------------------------------------------------
    def test_21_rating_association_integrity(self):
        """CSAT record correctly maps to ticket and customer foreign keys."""
        db = SessionLocal()
        csat = db.query(CSATRating).filter(CSATRating.ticket_id == self.ticket_acme_resolved.id).first()
        self.assertIsNotNone(csat)
        self.assertEqual(csat.customer_id, self.cust_acme.id)
        self.assertEqual(csat.ticket_id, self.ticket_acme_resolved.id)
        db.close()

    # -------------------------------------------------------------
    # 22. Existing customer portal functionality remains intact
    # -------------------------------------------------------------
    def test_22_existing_customer_portal_intact(self):
        """Customer dashboard, ticket listing, and profile continue working normally."""
        res_dash = client.get("/portal/dashboard", headers={"Authorization": f"Bearer {self.cust_acme_token}"})
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn("metrics", res_dash.json())

        res_list = client.get("/portal/tickets", headers={"Authorization": f"Bearer {self.cust_acme_token}"})
        self.assertEqual(res_list.status_code, 200)
        self.assertIn("tickets", res_list.json())


if __name__ == "__main__":
    unittest.main()
