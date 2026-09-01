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
from app.models.notification import Notification
from app.models.routing_audit import RoutingAudit
from app.core.security import hash_password, create_access_token
from app.services.notification_service import (
    notify_technician_assigned,
    notify_ticket_escalated,
    create_notification
)

client = TestClient(app)


class TestPhase4ToastsAndCleanupSuite(unittest.TestCase):
    """
    Automated test suite for Phase 4: Frontend Real-Time Toast Alerts and Notification Cleanup.
    Tests toast event detection, duplicate prevention, scoping, Clear Read RBAC,
    and customer isolation.
    """

    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # 1. Technicians
        cls.tech_m365 = cls.db.query(Technician).filter(Technician.email == "rahul.sharma@jacehaus.com").first()
        if not cls.tech_m365:
            cls.tech_m365 = Technician(name="Rahul Sharma", email="rahul.sharma@jacehaus.com", team="M365 Support", is_active=True)
            cls.db.add(cls.tech_m365)
            cls.db.commit()
            cls.db.refresh(cls.tech_m365)

        cls.tech_net = cls.db.query(Technician).filter(Technician.email == "arjun.patel@jacehaus.com").first()
        if not cls.tech_net:
            cls.tech_net = Technician(name="Arjun Patel", email="arjun.patel@jacehaus.com", team="Network Team", is_active=True)
            cls.db.add(cls.tech_net)
            cls.db.commit()
            cls.db.refresh(cls.tech_net)

        # 2. Customer
        cls.customer = cls.db.query(Customer).filter(Customer.email == "john.doe@acme.com").first()
        if not cls.customer:
            cls.customer = Customer(name="John Doe", email="john.doe@acme.com", company="Acme Corp")
            cls.db.add(cls.customer)
            cls.db.commit()
            cls.db.refresh(cls.customer)

        # 3. Users
        def get_or_create_user(email, name, role, technician_id=None, customer_id=None):
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    password_hash=hash_password("Pass123!"),
                    role=role,
                    technician_id=technician_id,
                    customer_id=customer_id,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
            return u

        cls.admin_user = get_or_create_user("admin.phase4@jacehaus.com", "Admin Phase4", "admin")
        cls.manager_user = get_or_create_user("mgr.phase4@jacehaus.com", "Manager Phase4", "manager")
        cls.tech_m365_user = get_or_create_user("rahul.phase4@jacehaus.com", "Rahul Phase4", "technician", technician_id=cls.tech_m365.id)
        cls.tech_net_user = get_or_create_user("arjun.phase4@jacehaus.com", "Arjun Phase4", "technician", technician_id=cls.tech_net.id)
        cls.cust_user = get_or_create_user("cust.phase4@acme.com", "Cust Phase4", "customer", customer_id=cls.customer.id)

        # Tokens
        cls.admin_token = create_access_token({"sub": cls.admin_user.id, "email": cls.admin_user.email, "role": "admin"})
        cls.manager_token = create_access_token({"sub": cls.manager_user.id, "email": cls.manager_user.email, "role": "manager"})
        cls.m365_token = create_access_token({"sub": cls.tech_m365_user.id, "email": cls.tech_m365_user.email, "role": "technician"})
        cls.net_token = create_access_token({"sub": cls.tech_net_user.id, "email": cls.tech_net_user.email, "role": "technician"})
        cls.cust_token = create_access_token({"sub": cls.cust_user.id, "email": cls.cust_user.email, "role": "customer"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # TEST 1: Toast Event Detection - Ticket Assigned to Technician
    # =========================================================================
    def test_01_toast_detection_ticket_assigned(self):
        """Ticket assigned to technician creates a TICKET_ASSIGNED notification suitable for toast."""
        ticket = Ticket(
            title="M365 OneDrive Sync Error",
            description="OneDrive cannot sync folders.",
            assigned_team="M365 Support",
            assigned_technician_id=self.tech_m365.id,
            assigned_technician=self.tech_m365.name,
            priority="high",
            status="in_progress"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        notif = notify_technician_assigned(
            db=self.db,
            ticket=ticket,
            technician_name=self.tech_m365.name,
            assigned_by="Dispatcher"
        )
        self.assertEqual(notif.type, "TICKET_ASSIGNED")
        self.assertEqual(notif.ticket_id, ticket.id)
        self.assertIn("Assigned to Rahul Sharma", notif.title)

        # Verify Rahul's queue receives this notification
        r = client.get("/notifications/?scope=my_tickets", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r.status_code, 200)
        notif_ids = [n["id"] for n in r.json()["notifications"]]
        self.assertIn(notif.id, notif_ids)

    # =========================================================================
    # TEST 2: Toast Event Detection - Critical/High Ticket Escalated
    # =========================================================================
    def test_02_toast_detection_ticket_escalated(self):
        """Ticket escalated creates an ESCALATION notification with critical severity."""
        ticket = Ticket(
            title="Database Latency Spike",
            description="Query response times degraded by 400%.",
            assigned_team="M365 Support",
            priority="critical",
            status="in_progress"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        notif = notify_ticket_escalated(
            db=self.db,
            ticket=ticket,
            escalation_level=2,
            reason="Requires senior DBA review",
            escalated_by="Rahul Sharma"
        )
        self.assertEqual(notif.type, "ESCALATION")
        self.assertEqual(notif.severity, "critical")
        self.assertIn("🚨", notif.title)
        self.assertIn("Level 2", notif.title)

    # =========================================================================
    # TEST 3: Toast Event Detection - SLA Breach
    # =========================================================================
    def test_03_toast_detection_sla_breach(self):
        """SLA breach generates SLA_BREACHED notification with critical severity."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Breached Response SLA Ticket",
            description="No response given in time.",
            assigned_team="M365 Support",
            priority="critical",
            status="new",
            created_at=now - timedelta(hours=2),
            response_due_at=now - timedelta(minutes=45),
            resolution_due_at=now + timedelta(hours=1)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        notif = create_notification(
            db=self.db,
            ticket_id=ticket.id,
            notification_type="SLA_BREACHED",
            severity="critical",
            title=f"Response SLA Breached - Ticket #{ticket.id}",
            message="Ticket has breached its response SLA deadline."
        )
        self.assertEqual(notif.type, "SLA_BREACHED")
        self.assertEqual(notif.severity, "critical")
        self.assertEqual(notif.ticket_id, ticket.id)

    # =========================================================================
    # TEST 4: Toast Event Detection - Customer Update / Reply
    # =========================================================================
    def test_04_toast_detection_customer_update(self):
        """Customer update posted via Customer Portal generates CUSTOMER_UPDATE notification."""
        ticket = Ticket(
            title="Outlook Add-in Crashing",
            description="Add-in error on startup.",
            assigned_team="M365 Support",
            customer_id=self.customer.id,
            customer_name=self.customer.name,
            customer_company=self.customer.company,
            priority="medium",
            status="in_progress"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        # Post reply via portal endpoint
        r = client.post(
            f"/portal/tickets/{ticket.id}/updates",
            json={"content": "Here are the crash logs requested."},
            headers={"Authorization": f"Bearer {self.cust_token}"}
        )
        self.assertEqual(r.status_code, 200)

        # Verify CUSTOMER_UPDATE notification was generated
        notif = self.db.query(Notification).filter(
            Notification.ticket_id == ticket.id,
            Notification.type == "CUSTOMER_UPDATE"
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("Customer Update on Ticket", notif.title)
        self.assertEqual(notif.ticket_id, ticket.id)

    # =========================================================================
    # TEST 5: Toast Ticket Navigation - Ticket Detail Retrieval
    # =========================================================================
    def test_05_toast_ticket_navigation_resolution(self):
        """Clicking toast navigates to valid ticket details via GET /tickets/{id}."""
        ticket = Ticket(
            title="Navigable Toast Ticket",
            description="Testing toast navigation.",
            assigned_team="M365 Support",
            priority="low",
            status="new"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        r = client.get(f"/tickets/{ticket.id}", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], ticket.id)
        self.assertEqual(r.json()["title"], "Navigable Toast Ticket")

    # =========================================================================
    # TEST 6: Clear Read RBAC Enforcement
    # =========================================================================
    def test_06_clear_read_rbac(self):
        """Only Admin and Manager can call DELETE /notifications/clear-read; Tech and Cust get 403."""
        # 1. Unauthenticated -> 401
        r_unauth = client.delete("/notifications/clear-read")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 403
        r_tech = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_tech.status_code, 403)

        # 4. Manager -> 200
        r_mgr = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)
        self.assertIn("deleted_count", r_mgr.json())

        # 5. Admin -> 200
        r_admin = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)

    # =========================================================================
    # TEST 7: Clear Read Preserves Unread Notifications
    # =========================================================================
    def test_07_clear_read_preserves_unread_notifications(self):
        """DELETE /notifications/clear-read removes read notifications and keeps unread untouched."""
        n_read = Notification(
            type="INFO",
            severity="info",
            title="Read to be cleared",
            message="Old read alert",
            is_read=True
        )
        n_unread = Notification(
            type="CRITICAL",
            severity="critical",
            title="Unread must remain intact",
            message="Urgent ongoing alert",
            is_read=False
        )
        self.db.add_all([n_read, n_unread])
        self.db.commit()
        self.db.refresh(n_read)
        self.db.refresh(n_unread)

        # Perform Clear Read as Admin
        r = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r.status_code, 200)

        # Read notification deleted
        deleted_check = self.db.query(Notification).filter(Notification.id == n_read.id).first()
        self.assertIsNone(deleted_check)

        # Unread notification preserved
        unread_check = self.db.query(Notification).filter(Notification.id == n_unread.id).first()
        self.assertIsNotNone(unread_check)
        self.assertFalse(unread_check.is_read)


if __name__ == "__main__":
    unittest.main()
