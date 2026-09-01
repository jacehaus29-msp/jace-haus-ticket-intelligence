import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.technician import Technician
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.core.security import hash_password, create_access_token

client = TestClient(app)


class TestNotificationsScopedFilteringSuite(unittest.TestCase):
    """
    Automated test suite for Phase 3: Role & Team Scoped Notification Filtering.
    Tests Admin, Manager, Technician, and Customer visibility boundaries,
    scoped unread counts, and ticket-level RBAC isolation.
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

        cls.tech_network = cls.db.query(Technician).filter(Technician.email == "arjun.patel@jacehaus.com").first()
        if not cls.tech_network:
            cls.tech_network = Technician(name="Arjun Patel", email="arjun.patel@jacehaus.com", team="Network Team", is_active=True)
            cls.db.add(cls.tech_network)
            cls.db.commit()
            cls.db.refresh(cls.tech_network)

        # 2. Users
        def get_or_create_user(email, name, role, technician_id=None):
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    password_hash=hash_password("Pass123!"),
                    role=role,
                    technician_id=technician_id,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
            return u

        cls.admin_user = get_or_create_user("admin.scoped@jacehaus.com", "Admin Scoped", "admin")
        cls.manager_user = get_or_create_user("mgr.scoped@jacehaus.com", "Manager Scoped", "manager")
        cls.tech_m365_user = get_or_create_user("rahul.scoped@jacehaus.com", "Rahul Scoped", "technician", technician_id=cls.tech_m365.id)
        cls.tech_net_user = get_or_create_user("arjun.scoped@jacehaus.com", "Arjun Scoped", "technician", technician_id=cls.tech_network.id)
        cls.cust_user = get_or_create_user("cust.scoped@acme.com", "Cust Scoped", "customer")

        # Tokens
        cls.admin_token = create_access_token({"sub": cls.admin_user.id, "email": cls.admin_user.email, "role": "admin"})
        cls.manager_token = create_access_token({"sub": cls.manager_user.id, "email": cls.manager_user.email, "role": "manager"})
        cls.m365_token = create_access_token({"sub": cls.tech_m365_user.id, "email": cls.tech_m365_user.email, "role": "technician"})
        cls.net_token = create_access_token({"sub": cls.tech_net_user.id, "email": cls.tech_net_user.email, "role": "technician"})
        cls.cust_token = create_access_token({"sub": cls.cust_user.id, "email": cls.cust_user.email, "role": "customer"})

        # 3. Create distinct test tickets & notifications
        # Ticket A: M365 Support assigned to Rahul Sharma
        cls.ticket_m365_rahul = Ticket(
            title="Rahul Assigned M365 Ticket",
            description="Outlook sync error for executive.",
            assigned_team="M365 Support",
            assigned_technician_id=cls.tech_m365.id,
            assigned_technician=cls.tech_m365.name,
            priority="high",
            status="in_progress"
        )
        # Ticket B: M365 Support unassigned to specific tech
        cls.ticket_m365_unassigned = Ticket(
            title="M365 Pool Unassigned Ticket",
            description="SharePoint storage quota alert.",
            assigned_team="M365 Support",
            assigned_technician_id=None,
            assigned_technician=None,
            priority="medium",
            status="new"
        )
        # Ticket C: Network Team ticket assigned to Arjun Patel
        cls.ticket_net_arjun = Ticket(
            title="Arjun Network Ticket",
            description="Core router packet drop issue.",
            assigned_team="Network Team",
            assigned_technician_id=cls.tech_network.id,
            assigned_technician=cls.tech_network.name,
            priority="critical",
            status="in_progress"
        )

        cls.db.add_all([cls.ticket_m365_rahul, cls.ticket_m365_unassigned, cls.ticket_net_arjun])
        cls.db.commit()
        cls.db.refresh(cls.ticket_m365_rahul)
        cls.db.refresh(cls.ticket_m365_unassigned)
        cls.db.refresh(cls.ticket_net_arjun)

        # Create notifications for each ticket
        cls.notif_m365_rahul = Notification(
            ticket_id=cls.ticket_m365_rahul.id,
            type="TICKET_ASSIGNED",
            severity="warning",
            title=f"M365 Rahul Notif #{cls.ticket_m365_rahul.id}",
            message="Rahul ticket assigned.",
            is_read=False
        )
        cls.notif_m365_pool = Notification(
            ticket_id=cls.ticket_m365_unassigned.id,
            type="TICKET_CREATED",
            severity="info",
            title=f"M365 Pool Notif #{cls.ticket_m365_unassigned.id}",
            message="M365 unassigned pool ticket.",
            is_read=False
        )
        cls.notif_net_arjun = Notification(
            ticket_id=cls.ticket_net_arjun.id,
            type="ESCALATION",
            severity="critical",
            title=f"Network Arjun Notif #{cls.ticket_net_arjun.id}",
            message="Network critical escalation.",
            is_read=False
        )

        cls.db.add_all([cls.notif_m365_rahul, cls.notif_m365_pool, cls.notif_net_arjun])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # TEST 1: Admin & Manager Global Scope
    # =========================================================================
    def test_01_admin_and_manager_global_visibility(self):
        """Admin and Manager can view notifications across all teams with scope=all."""
        # 1. Admin
        r_admin = client.get("/notifications/?scope=all", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)
        notif_ids = [n["id"] for n in r_admin.json()["notifications"]]
        self.assertIn(self.notif_m365_rahul.id, notif_ids)
        self.assertIn(self.notif_m365_pool.id, notif_ids)
        self.assertIn(self.notif_net_arjun.id, notif_ids)

        # 2. Manager
        r_mgr = client.get("/notifications/?scope=all", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)
        notif_ids_mgr = [n["id"] for n in r_mgr.json()["notifications"]]
        self.assertIn(self.notif_m365_rahul.id, notif_ids_mgr)
        self.assertIn(self.notif_net_arjun.id, notif_ids_mgr)

    # =========================================================================
    # TEST 2: Technician My-Team Filtering
    # =========================================================================
    def test_02_technician_my_team_scoping(self):
        """Technician (Rahul) sees all M365 Support tickets but zero Network Team tickets."""
        r_tech = client.get("/notifications/?scope=my_team", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_tech.status_code, 200)
        notif_ids = [n["id"] for n in r_tech.json()["notifications"]]

        # Rahul sees M365 tickets
        self.assertIn(self.notif_m365_rahul.id, notif_ids)
        self.assertIn(self.notif_m365_pool.id, notif_ids)

        # Rahul CANNOT see Network Team tickets
        self.assertNotIn(self.notif_net_arjun.id, notif_ids)

    # =========================================================================
    # TEST 3: Technician My-Tickets (Queue) Filtering
    # =========================================================================
    def test_03_technician_my_tickets_scoping(self):
        """Technician (Rahul) with scope=my_tickets sees only tickets assigned to Rahul."""
        r_queue = client.get("/notifications/?scope=my_tickets", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_queue.status_code, 200)
        notif_ids = [n["id"] for n in r_queue.json()["notifications"]]

        # Assigned to Rahul -> Present
        self.assertIn(self.notif_m365_rahul.id, notif_ids)

        # Unassigned M365 ticket -> Filtered out of personal queue
        self.assertNotIn(self.notif_m365_pool.id, notif_ids)

        # Network ticket -> Filtered out
        self.assertNotIn(self.notif_net_arjun.id, notif_ids)

    # =========================================================================
    # TEST 4: Technician Cannot See Other Team Notifications Via Scope=all
    # =========================================================================
    def test_04_technician_cannot_bypass_team_boundary(self):
        """When technician requests scope=all, backend bounds results to technician's team."""
        r_all = client.get("/notifications/?scope=all", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_all.status_code, 200)
        notif_ids = [n["id"] for n in r_all.json()["notifications"]]

        self.assertNotIn(self.notif_net_arjun.id, notif_ids)

    # =========================================================================
    # TEST 5: Ticket-Level Notification RBAC Protection
    # =========================================================================
    def test_05_ticket_notifications_endpoint_team_rbac(self):
        """GET /notifications/ticket/{id} returns 403 when technician accesses cross-team ticket."""
        # 1. Rahul accessing M365 ticket -> 200 OK
        r_m365 = client.get(f"/notifications/ticket/{self.ticket_m365_rahul.id}", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_m365.status_code, 200)

        # 2. Rahul accessing Network ticket -> 403 Forbidden
        r_net_blocked = client.get(f"/notifications/ticket/{self.ticket_net_arjun.id}", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_net_blocked.status_code, 403)
        self.assertIn("Access denied", r_net_blocked.json()["detail"])

        # 3. Admin accessing Network ticket -> 200 OK
        r_admin = client.get(f"/notifications/ticket/{self.ticket_net_arjun.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)

    # =========================================================================
    # TEST 6: Customer Isolation on Scoped Endpoints
    # =========================================================================
    def test_06_customer_blocked_on_scoped_endpoints(self):
        """Customer receives 403 on internal notification endpoints regardless of scope parameter."""
        for scope_param in ["all", "my_team", "my_tickets"]:
            r = client.get(f"/notifications/?scope={scope_param}", headers={"Authorization": f"Bearer {self.cust_token}"})
            self.assertEqual(r.status_code, 403)

        r_count = client.get("/notifications/unread-count?scope=my_team", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(r_count.status_code, 403)

    # =========================================================================
    # TEST 7: Scoped Unread Count & Scoped Mark-All-Read
    # =========================================================================
    def test_07_scoped_unread_count_and_mark_all_read(self):
        """Unread count and mark-all-read operate strictly within the requested scope."""
        # Check unread count for Rahul's queue
        r_queue_cnt = client.get("/notifications/unread-count?scope=my_tickets", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_queue_cnt.status_code, 200)
        self.assertGreaterEqual(r_queue_cnt.json()["unread_count"], 1)

        # Mark all read in Rahul's queue
        r_mark = client.patch("/notifications/read-all?scope=my_tickets", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_mark.status_code, 200)

        # Rahul's queue is now 0 unread
        r_queue_after = client.get("/notifications/unread-count?scope=my_tickets", headers={"Authorization": f"Bearer {self.m365_token}"})
        self.assertEqual(r_queue_after.json()["unread_count"], 0)

        # Network Team unread notification for Arjun remains UNREAD
        net_notif = self.db.query(Notification).filter(Notification.id == self.notif_net_arjun.id).first()
        self.assertIsNotNone(net_notif)
        self.assertFalse(net_notif.is_read)


if __name__ == "__main__":
    unittest.main()
