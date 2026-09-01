import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.core.security import hash_password, create_access_token

client = TestClient(app)


class TestNotificationsAuthRBACSuite(unittest.TestCase):
    """
    Comprehensive test suite for internal /notifications and /portal/notifications
    authentication, RBAC enforcement, and DELETE lifecycle.
    """

    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db = SessionLocal()

        # Ensure seed users exist for testing
        def get_or_create_user(email, name, role, customer_id=None, technician_id=None):
            u = cls.db.query(User).filter(User.email == email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    password_hash=hash_password("TestPassword123!"),
                    role=role,
                    customer_id=customer_id,
                    technician_id=technician_id,
                    is_active=True
                )
                cls.db.add(u)
                cls.db.commit()
                cls.db.refresh(u)
            return u

        # 1. Customers
        cls.cust_acme = cls.db.query(Customer).filter(Customer.email == "john.doe@acme.com").first()
        if not cls.cust_acme:
            cls.cust_acme = Customer(name="John Doe", email="john.doe@acme.com", company="Acme Corp")
            cls.db.add(cls.cust_acme)
            cls.db.commit()
            cls.db.refresh(cls.cust_acme)

        # 2. Technicians
        cls.tech_rahul = cls.db.query(Technician).filter(Technician.email == "rahul.sharma@jacehaus.com").first()
        if not cls.tech_rahul:
            cls.tech_rahul = Technician(name="Rahul Sharma", email="rahul.sharma@jacehaus.com", team="M365 Support", is_active=True)
            cls.db.add(cls.tech_rahul)
            cls.db.commit()
            cls.db.refresh(cls.tech_rahul)

        # 3. Users for each role
        cls.admin_user = get_or_create_user("admin.notif.test@jacehaus.com", "Admin Notif Tester", "admin")
        cls.manager_user = get_or_create_user("manager.notif.test@jacehaus.com", "Manager Notif Tester", "manager")
        cls.tech_user = get_or_create_user("tech.notif.test@jacehaus.com", "Tech Notif Tester", "technician", technician_id=cls.tech_rahul.id)
        cls.customer_user = get_or_create_user("cust.notif.test@acme.com", "Cust Notif Tester", "customer", customer_id=cls.cust_acme.id)

        # Generate tokens
        cls.admin_token = create_access_token({"sub": cls.admin_user.id, "email": cls.admin_user.email, "role": "admin"})
        cls.manager_token = create_access_token({"sub": cls.manager_user.id, "email": cls.manager_user.email, "role": "manager"})
        cls.tech_token = create_access_token({"sub": cls.tech_user.id, "email": cls.tech_user.email, "role": "technician"})
        cls.customer_token = create_access_token({"sub": cls.customer_user.id, "email": cls.customer_user.email, "role": "customer"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # TEST 1: GET /notifications/ Auth & RBAC
    # =========================================================================
    def test_01_get_notifications_rbac(self):
        """Unauthenticated -> 401; Customer -> 403; Tech/Mgr/Admin -> 200"""
        # 1. Unauthenticated -> 401
        r_unauth = client.get("/notifications/")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.get("/notifications/", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 200
        r_tech = client.get("/notifications/", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 200)
        self.assertIn("notifications", r_tech.json())
        self.assertIn("unread_count", r_tech.json())

        # 4. Manager -> 200
        r_mgr = client.get("/notifications/", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)

        # 5. Admin -> 200
        r_admin = client.get("/notifications/", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)

    # =========================================================================
    # TEST 2: GET /notifications/unread-count Auth & RBAC
    # =========================================================================
    def test_02_get_unread_count_rbac(self):
        """Unauthenticated -> 401; Customer -> 403; Tech/Mgr/Admin -> 200"""
        # 1. Unauthenticated -> 401
        r_unauth = client.get("/notifications/unread-count")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.get("/notifications/unread-count", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 200
        r_tech = client.get("/notifications/unread-count", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 200)
        self.assertIn("unread_count", r_tech.json())

    # =========================================================================
    # TEST 3: PATCH /notifications/{id}/read Auth & RBAC
    # =========================================================================
    def test_03_mark_read_rbac(self):
        """Mark single notification as read."""
        notif = Notification(
            type="TICKET_ASSIGNED",
            severity="info",
            title=f"Test Notification {datetime.now().timestamp()}",
            message="Testing mark read endpoint.",
            is_read=False
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)

        # 1. Unauthenticated -> 401
        r_unauth = client.patch(f"/notifications/{notif.id}/read")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.patch(f"/notifications/{notif.id}/read", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 200
        r_tech = client.patch(f"/notifications/{notif.id}/read", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 200)
        self.assertTrue(r_tech.json()["is_read"])

    # =========================================================================
    # TEST 4: PATCH /notifications/read-all Auth & RBAC
    # =========================================================================
    def test_04_mark_all_read_rbac(self):
        """Mark all notifications as read."""
        # 1. Unauthenticated -> 401
        r_unauth = client.patch("/notifications/read-all")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.patch("/notifications/read-all", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Manager -> 200
        r_mgr = client.patch("/notifications/read-all", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)
        self.assertEqual(r_mgr.json()["unread_count"], 0)

    # =========================================================================
    # TEST 5: GET /notifications/ticket/{ticket_id} Auth & RBAC
    # =========================================================================
    def test_05_get_ticket_notifications_rbac(self):
        """Get ticket notifications endpoint."""
        ticket = Ticket(
            title="Ticket for notification auth test",
            description="Testing ticket notifications endpoint.",
            priority="medium",
            assigned_team="M365 Support"
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        notif = Notification(
            ticket_id=ticket.id,
            type="SLA_AT_RISK",
            severity="warning",
            title=f"SLA warning for #{ticket.id}",
            message="Approaching response due.",
            is_read=False
        )
        self.db.add(notif)
        self.db.commit()

        # 1. Unauthenticated -> 401
        r_unauth = client.get(f"/notifications/ticket/{ticket.id}")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.get(f"/notifications/ticket/{ticket.id}", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 200
        r_tech = client.get(f"/notifications/ticket/{ticket.id}", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 200)
        self.assertEqual(r_tech.json()["ticket_id"], ticket.id)

    # =========================================================================
    # TEST 6: DELETE /notifications/{id} Restricted to ADMIN and MANAGER
    # =========================================================================
    def test_06_delete_single_notification_rbac(self):
        """Delete single notification endpoint."""
        notif = Notification(
            type="INFO",
            severity="info",
            title=f"Delete me test {datetime.now().timestamp()}",
            message="Testing delete endpoint.",
            is_read=True
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)

        # 1. Unauthenticated -> 401
        r_unauth = client.delete(f"/notifications/{notif.id}")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.delete(f"/notifications/{notif.id}", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 403 (Technicians CANNOT delete notifications)
        r_tech = client.delete(f"/notifications/{notif.id}", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 403)

        # 4. Manager -> 200 (Manager CAN delete)
        r_mgr = client.delete(f"/notifications/{notif.id}", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_mgr.status_code, 200)
        self.assertTrue(r_mgr.json()["deleted"])

        # 5. Deleted notification returns 404 on subsequent delete
        r_mgr_404 = client.delete(f"/notifications/{notif.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_mgr_404.status_code, 404)

    # =========================================================================
    # TEST 7: DELETE /notifications/clear-read Restricted to ADMIN and MANAGER
    # =========================================================================
    def test_07_clear_read_notifications_rbac(self):
        """Delete all read notifications endpoint."""
        # Add 2 read notifications and 1 unread notification
        n_read1 = Notification(type="INFO", severity="info", title="Read 1", message="m", is_read=True)
        n_read2 = Notification(type="INFO", severity="info", title="Read 2", message="m", is_read=True)
        n_unread = Notification(type="CRITICAL", severity="critical", title="Unread Keep Me", message="m", is_read=False)
        self.db.add_all([n_read1, n_read2, n_unread])
        self.db.commit()

        # 1. Unauthenticated -> 401
        r_unauth = client.delete("/notifications/clear-read")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Customer -> 403
        r_cust = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.customer_token}"})
        self.assertEqual(r_cust.status_code, 403)

        # 3. Technician -> 403
        r_tech = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_tech.status_code, 403)

        # 4. Admin -> 200
        r_admin = client.delete("/notifications/clear-read", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_admin.status_code, 200)
        self.assertGreaterEqual(r_admin.json()["deleted_count"], 2)

        # Confirm unread notification was NOT deleted
        self.db.refresh(n_unread)
        self.assertFalse(n_unread.is_read)


if __name__ == "__main__":
    unittest.main()
