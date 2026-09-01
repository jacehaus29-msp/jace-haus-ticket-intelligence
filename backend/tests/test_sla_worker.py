import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.models.routing_audit import RoutingAudit
from app.services.sla_worker import SLAWorker, sla_worker
from app.core.security import hash_password, create_access_token

client = TestClient(app)


class TestSLAWorkerSuite(unittest.TestCase):
    """
    Automated test suite for the autonomous SLA & Notification Background Worker.
    Tests detection of at-risk, breaches, automatic escalations, deduplication,
    error resilience, and lifecycle management.
    """

    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # Create tech user
        cls.tech_user = cls.db.query(User).filter(User.email == "tech.worker.test@jacehaus.com").first()
        if not cls.tech_user:
            cls.tech_user = User(
                name="Tech Worker Tester",
                email="tech.worker.test@jacehaus.com",
                password_hash=hash_password("TechPass123!"),
                role="technician",
                is_active=True
            )
            cls.db.add(cls.tech_user)
            cls.db.commit()
            cls.db.refresh(cls.tech_user)

        cls.tech_token = create_access_token({"sub": cls.tech_user.id, "email": cls.tech_user.email, "role": "technician"})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # =========================================================================
    # TEST 1: Worker Single Cycle & Response SLA At-Risk Detection
    # =========================================================================
    def test_01_worker_detects_response_sla_at_risk(self):
        """Worker scan cycle detects Response SLA approaching deadline."""
        now = datetime.now(timezone.utc)
        # Create ticket with response due in 3 minutes (within 25% warning window of 15m SLA)
        ticket = Ticket(
            title="Urgent Network Switch Failure",
            description="Switch 3 on Floor 2 is power cycling.",
            category="Network",
            assigned_team="Network Team",
            priority="critical",
            status="new",
            created_at=now - timedelta(minutes=12),
            response_due_at=now + timedelta(minutes=3),
            resolution_due_at=now + timedelta(hours=2)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        worker = SLAWorker(interval_seconds=10)
        res = worker.run_once()

        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["alerts_generated"], 1)

        # Verify notification created
        notif = self.db.query(Notification).filter(
            Notification.ticket_id == ticket.id,
            Notification.type == "SLA_AT_RISK"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.severity, "warning")
        self.assertIn("Response SLA At Risk", notif.title)

    # =========================================================================
    # TEST 2: Resolution SLA At-Risk Detection
    # =========================================================================
    def test_02_worker_detects_resolution_sla_at_risk(self):
        """Worker scan cycle detects Resolution SLA approaching deadline for in_progress ticket."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="M365 License Allocation Blocked",
            description="User onboarding blocked by license pool sync.",
            category="M365",
            assigned_team="M365 Support",
            priority="high",
            status="in_progress",
            created_at=now - timedelta(hours=3, minutes=30),
            response_due_at=now - timedelta(hours=3),
            responded_at=now - timedelta(hours=3),
            resolution_due_at=now + timedelta(minutes=30)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        worker = SLAWorker(interval_seconds=10)
        res = worker.run_once()
        self.assertTrue(res["success"])

        notif = self.db.query(Notification).filter(
            Notification.ticket_id == ticket.id,
            Notification.type == "SLA_AT_RISK"
        ).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.severity, "warning")
        self.assertIn("Resolution SLA At Risk", notif.title)

    # =========================================================================
    # TEST 3: SLA Breach & Automatic Escalation
    # =========================================================================
    def test_03_worker_detects_breach_and_triggers_escalation(self):
        """Worker detects SLA breach and triggers automatic escalation for Critical ticket."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Core Firewall Offline - Security Risk",
            description="Main gateway firewall went offline.",
            category="Security",
            assigned_team="Security Team",
            priority="critical",
            status="new",
            created_at=now - timedelta(hours=3),
            response_due_at=now - timedelta(hours=2, minutes=45),
            resolution_due_at=now - timedelta(hours=1)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        worker = SLAWorker(interval_seconds=10)
        res = worker.run_once()
        self.assertTrue(res["success"])

        # 1. Breach Notification
        breach_notif = self.db.query(Notification).filter(
            Notification.ticket_id == ticket.id,
            Notification.type == "SLA_BREACHED"
        ).first()
        self.assertIsNotNone(breach_notif)
        self.assertEqual(breach_notif.severity, "critical")

        # 2. Escalation Notification
        esc_notif = self.db.query(Notification).filter(
            Notification.ticket_id == ticket.id,
            Notification.type == "ESCALATION"
        ).first()
        self.assertIsNotNone(esc_notif)
        self.assertEqual(esc_notif.severity, "critical")
        self.assertIn("Escalation Required", esc_notif.title)

        # 3. Timeline Audit Recorded
        audit = self.db.query(RoutingAudit).filter(
            RoutingAudit.ticket_id == ticket.id,
            RoutingAudit.rule == "Escalation Triggered"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.routing_method, "escalation_engine")

    # =========================================================================
    # TEST 4: Deduplication Protection
    # =========================================================================
    def test_04_deduplication_prevents_duplicate_notifications(self):
        """Consecutive worker runs do not create duplicate notifications for unchanged states."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            title="Deduplication Test Ticket",
            description="Testing alert deduplication.",
            category="Endpoint",
            assigned_team="Endpoint Team",
            priority="critical",
            status="new",
            created_at=now - timedelta(hours=4),
            response_due_at=now - timedelta(hours=3),
            resolution_due_at=now - timedelta(hours=2)
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)

        worker = SLAWorker(interval_seconds=10)

        # First run -> generates alerts
        res1 = worker.run_once()
        self.assertTrue(res1["success"])
        initial_count = self.db.query(Notification).filter(Notification.ticket_id == ticket.id).count()
        self.assertGreaterEqual(initial_count, 1)

        # Second run -> 0 new alerts for this ticket
        res2 = worker.run_once()
        self.assertTrue(res2["success"])
        second_count = self.db.query(Notification).filter(Notification.ticket_id == ticket.id).count()
        self.assertEqual(initial_count, second_count)

    # =========================================================================
    # TEST 5: Worker Error Resilience (Session Safety & No Crash)
    # =========================================================================
    def test_05_worker_error_resilience(self):
        """Worker catches exceptions without crashing and tracks diagnostic error."""
        worker = SLAWorker(interval_seconds=10)
        with patch("app.services.sla_worker.check_and_generate_sla_notifications", side_effect=RuntimeError("Simulated DB connection glitch")):
            res = worker.run_once()
            self.assertFalse(res["success"])
            self.assertIn("Simulated DB connection glitch", res["error"])
            self.assertEqual(worker._last_error, "Simulated DB connection glitch")

        # Subsequent run succeeds normally
        res_ok = worker.run_once()
        self.assertTrue(res_ok["success"])
        self.assertIsNone(worker._last_error)

    # =========================================================================
    # TEST 6: Worker Start & Stop Lifecycle
    # =========================================================================
    def test_06_worker_start_and_stop_lifecycle(self):
        """Test async start and stop methods of SLAWorker."""
        async def run_async_test():
            worker = SLAWorker(interval_seconds=1)
            self.assertFalse(worker.is_running)

            # Start worker
            worker.start()
            self.assertTrue(worker.is_running)

            # Allow loop to tick
            await asyncio.sleep(0.05)
            self.assertTrue(worker.is_running)

            # Stop worker
            await worker.stop()
            self.assertFalse(worker.is_running)

        asyncio.run(run_async_test())

    # =========================================================================
    # TEST 7: Diagnostic Worker Status API Endpoint
    # =========================================================================
    def test_07_worker_status_endpoint(self):
        """GET /notifications/worker-status returns worker telemetry."""
        # 1. Unauthenticated -> 401
        r_unauth = client.get("/notifications/worker-status")
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Authenticated -> 200
        r_ok = client.get(
            "/notifications/worker-status",
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        self.assertEqual(r_ok.status_code, 200)
        data = r_ok.json()
        self.assertIn("is_running", data)
        self.assertIn("interval_seconds", data)
        self.assertIn("total_runs", data)
        self.assertIn("total_alerts_generated", data)


if __name__ == "__main__":
    unittest.main()
