"""
================================================================================
MSP TICKET INTELLIGENCE — AUTOMATED AUTHENTICATION & RBAC TEST SUITE
================================================================================
Comprehensive automated test suite covering:
1. Login & Token Authentication
2. Password Cryptography & Security
3. Authentication Protection & Token Validation
4. Role-Based Access Control (Admin, Manager, Technician, Customer)
5. Ticket Access Security & Multi-Tenant Scoping
6. Regression & Core Operational Functionality
7. Negative & Security Test Cases
================================================================================
"""

import sys
import os
import unittest
import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.database import SessionLocal, engine
from app.models.user import User
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.technician import Technician
from app.models.routing_rule import RoutingRule
from app.models.routing_audit import RoutingAudit
from app.models.ticket_note import TicketNote
from app.models.notification import Notification

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    SECRET_KEY,
    ALGORITHM,
    PBKDF2_ITERATIONS
)
from app.core.auth import (
    get_current_user,
    get_optional_current_user,
    require_roles,
    require_admin,
    require_manager_or_admin,
    require_internal,
    require_customer
)
from app.api.auth import (
    login,
    logout,
    get_current_user_profile,
    list_users,
    create_user,
    update_user,
    LoginRequest,
    UserCreateRequest,
    UserUpdateRequest
)
from app.api.rules import (
    get_rules,
    create_rule,
    update_rule,
    update_rule_status,
    re_evaluate_rule,
    RuleCreate,
    RuleUpdate,
    RuleStatusUpdate
)
from app.routes.analytics import get_analytics
from app.api.technicians import (
    get_technicians,
    create_technician,
    update_technician,
    get_technician_workload,
    TechnicianCreateRequest,
    TechnicianUpdateRequest
)
from app.api.tickets import (
    get_tickets,
    get_ticket,
    route_ticket_endpoint,
    update_ticket_status,
    update_ticket_team,
    update_ticket_priority,
    add_ticket_note,
    get_ticket_notes,
    assign_ticket_technician,
    escalate_ticket_endpoint,
    TicketRequest,
    StatusUpdate,
    TeamUpdate,
    PriorityUpdate,
    NoteCreate,
    TechnicianAssignRequest,
    EscalateTicketRequest
)
from app.api.portal import (
    get_customer_dashboard,
    list_customer_tickets,
    get_customer_ticket_detail,
    create_customer_ticket,
    add_customer_ticket_update,
    confirm_ticket_resolution,
    reopen_customer_ticket,
    get_customer_profile,
    update_customer_profile,
    get_customer_notifications,
    mark_customer_notification_read,
    mark_all_customer_notifications_read,
    get_current_customer,
    PortalTicketCreateRequest,
    CustomerUpdateCreate,
    CustomerProfileUpdate
)


class BaseAuthRBACTestCase(unittest.TestCase):
    """Base test case providing clean DB sessions and fixture helpers."""

    def setUp(self):
        self.db: Session = SessionLocal()
        self._created_user_ids = []
        self._created_ticket_ids = []
        self._created_rule_ids = []
        self._created_customer_ids = []
        self._created_technician_ids = []

    def tearDown(self):
        try:
            # Clean up test-created tickets & notes & audits
            for tid in self._created_ticket_ids:
                self.db.query(TicketNote).filter(TicketNote.ticket_id == tid).delete(synchronize_session=False)
                self.db.query(RoutingAudit).filter(RoutingAudit.ticket_id == tid).delete(synchronize_session=False)
                self.db.query(Notification).filter(Notification.ticket_id == tid).delete(synchronize_session=False)
                self.db.query(Ticket).filter(Ticket.id == tid).delete(synchronize_session=False)

            # Clean up test-created users
            for uid in self._created_user_ids:
                self.db.query(User).filter(User.id == uid).delete(synchronize_session=False)

            # Clean up test-created rules
            for rid in self._created_rule_ids:
                self.db.query(RoutingRule).filter(RoutingRule.id == rid).delete(synchronize_session=False)

            # Clean up test-created customers
            for cid in self._created_customer_ids:
                self.db.query(Customer).filter(Customer.id == cid).delete(synchronize_session=False)

            # Clean up test-created technicians
            for tech_id in self._created_technician_ids:
                self.db.query(Technician).filter(Technician.id == tech_id).delete(synchronize_session=False)

            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def create_test_user(
        self,
        name: str = "Test User",
        email: str = None,
        password: str = "TestPass@123",
        role: str = "technician",
        is_active: bool = True,
        technician_id: Optional[int] = None,
        customer_id: Optional[int] = None
    ) -> User:
        if not email:
            email = f"test_{int(time.time() * 1000)}@jacehaus.test"
        user = User(
            name=name,
            email=email.lower().strip(),
            password_hash=hash_password(password),
            role=role.lower().strip(),
            is_active=is_active,
            technician_id=technician_id,
            customer_id=customer_id
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self._created_user_ids.append(user.id)
        return user

    def create_test_customer(
        self,
        name: str = "Test Customer",
        email: str = None,
        company: str = "Test Org",
        phone: str = "+1 555-0199"
    ) -> Customer:
        if not email:
            email = f"cust_{int(time.time() * 1000)}@testorg.test"
        cust = Customer(
            name=name,
            email=email.lower().strip(),
            company=company,
            phone=phone,
            is_active=True
        )
        self.db.add(cust)
        self.db.commit()
        self.db.refresh(cust)
        self._created_customer_ids.append(cust.id)
        return cust

    def create_test_technician(
        self,
        name: str = "Test Technician",
        email: str = None,
        team: str = "Network Team"
    ) -> Technician:
        if not email:
            email = f"tech_{int(time.time() * 1000)}@jacehaus.test"
        tech = Technician(
            name=name,
            email=email.lower().strip(),
            team=team,
            is_active=True
        )
        self.db.add(tech)
        self.db.commit()
        self.db.refresh(tech)
        self._created_technician_ids.append(tech.id)
        return tech


# =============================================================================
# 1. LOGIN & TOKEN AUTHENTICATION TESTS
# =============================================================================

class Test1_LoginAuthentication(BaseAuthRBACTestCase):
    """Test suite for user login, credentials validation, and token payload."""

    def test_01_admin_login_success(self):
        user = self.create_test_user(name="Admin Tester", role="admin", password="AdminSecret@123")
        res = login(LoginRequest(email=user.email, password="AdminSecret@123"), db=self.db)
        self.assertIn("access_token", res)
        self.assertEqual(res["token_type"], "bearer")
        self.assertEqual(res["user"]["role"], "admin")
        self.assertEqual(res["user"]["email"], user.email)
        self.assertEqual(res["message"], "Login successful")

    def test_02_manager_login_success(self):
        user = self.create_test_user(name="Manager Tester", role="manager", password="ManagerSecret@123")
        res = login(LoginRequest(email=user.email, password="ManagerSecret@123"), db=self.db)
        self.assertIn("access_token", res)
        self.assertEqual(res["user"]["role"], "manager")

    def test_03_technician_login_success(self):
        tech_prof = self.create_test_technician(team="M365 Support")
        user = self.create_test_user(name="Tech Tester", role="technician", password="TechSecret@123", technician_id=tech_prof.id)
        res = login(LoginRequest(email=user.email, password="TechSecret@123"), db=self.db)
        self.assertIn("access_token", res)
        self.assertEqual(res["user"]["role"], "technician")
        self.assertEqual(res["user"]["team"], "M365 Support")

    def test_04_customer_login_success(self):
        cust_prof = self.create_test_customer(company="Initech LLC")
        user = self.create_test_user(name="Client Tester", role="customer", password="ClientSecret@123", customer_id=cust_prof.id)
        res = login(LoginRequest(email=user.email, password="ClientSecret@123"), db=self.db)
        self.assertIn("access_token", res)
        self.assertEqual(res["user"]["role"], "customer")
        self.assertEqual(res["user"]["company"], "Initech LLC")

    def test_05_invalid_password_rejected(self):
        user = self.create_test_user(password="CorrectPassword@123")
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(email=user.email, password="WrongPassword!"), db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid email or password", ctx.exception.detail)

    def test_06_unknown_email_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(email="nonexistent.user.xyz@jacehaus.com", password="Password@123"), db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_07_deactivated_account_rejected(self):
        user = self.create_test_user(password="Secret@123", is_active=False)
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(email=user.email, password="Secret@123"), db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("deactivated", ctx.exception.detail.lower())

    def test_08_token_claims_and_structure(self):
        user = self.create_test_user(name="Token Tester", role="admin")
        res = login(LoginRequest(email=user.email, password="TestPass@123"), db=self.db)
        token = res["access_token"]
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], user.id)
        self.assertEqual(payload["email"], user.email)
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["name"], "Token Tester")
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)
        self.assertGreater(payload["exp"], payload["iat"])

    def test_09_logout_endpoint(self):
        res = logout()
        self.assertEqual(res["message"], "Logged out successfully")


# =============================================================================
# 2. PASSWORD SECURITY & CRYPTOGRAPHY TESTS
# =============================================================================

class Test2_PasswordSecurity(BaseAuthRBACTestCase):
    """Test suite for PBKDF2 hashing security, salt uniqueness, and timing safety."""

    def test_01_passwords_not_stored_as_plaintext(self):
        raw_password = "SuperSecretPlainTextPassword@2026"
        user = self.create_test_user(password=raw_password)
        db_user = self.db.query(User).filter(User.id == user.id).first()
        self.assertNotEqual(db_user.password_hash, raw_password)
        self.assertNotIn(raw_password, db_user.password_hash)
        self.assertTrue(db_user.password_hash.startswith("pbkdf2:sha256:100000$"))

    def test_02_password_hash_salt_uniqueness(self):
        raw_password = "IdenticalPassword@123"
        hash_1 = hash_password(raw_password)
        hash_2 = hash_password(raw_password)
        self.assertNotEqual(hash_1, hash_2, "Two hashes of same password must differ due to random salt")

    def test_03_password_verification_accurate(self):
        raw_pw = "VerificationTest@987"
        hashed = hash_password(raw_pw)
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password(raw_pw + "extra", hashed))
        self.assertFalse(verify_password("", hashed))
        self.assertFalse(verify_password(raw_pw, ""))

    def test_04_corrupted_hash_verification_fails_safely(self):
        self.assertFalse(verify_password("Password@123", "corrupted:hash:string"))
        self.assertFalse(verify_password("Password@123", "pbkdf2:sha256:invalid$salt$hash"))
        self.assertFalse(verify_password("Password@123", None))

    def test_05_empty_password_hashing_fails(self):
        with self.assertRaises(ValueError):
            hash_password("")


# =============================================================================
# 3. AUTHENTICATION PROTECTION & TOKEN VALIDATION TESTS
# =============================================================================

class Test3_AuthenticationProtection(BaseAuthRBACTestCase):
    """Test suite for FastAPI dependency guards, token decoding, and header handling."""

    def test_01_missing_auth_header_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization=None, x_auth_token=None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Authentication required", ctx.exception.detail)

    def test_02_malformed_auth_header_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization="InvalidFormatTokenHere")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_03_invalid_signature_token_raises_401(self):
        user = self.create_test_user()
        valid_token = create_access_token({"sub": user.id})
        # Tamper signature part
        parts = valid_token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}.badsignature123456"
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization=f"Bearer {tampered_token}")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_04_expired_token_raises_401(self):
        user = self.create_test_user()
        # Create token that expired 10 minutes ago
        expired_token = create_access_token(
            {"sub": user.id},
            expires_delta=timedelta(minutes=-10)
        )
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization=f"Bearer {expired_token}")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_05_nonexistent_user_token_raises_401(self):
        fake_token = create_access_token({"sub": 999999999})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization=f"Bearer {fake_token}")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("no longer exists", ctx.exception.detail.lower())

    def test_06_deactivated_user_token_raises_403(self):
        user = self.create_test_user(is_active=False)
        token = create_access_token({"sub": user.id})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(db=self.db, authorization=f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("inactive", ctx.exception.detail.lower())

    def test_07_x_auth_token_header_accepted(self):
        user = self.create_test_user()
        token = create_access_token({"sub": user.id})
        authenticated_user = get_current_user(db=self.db, authorization=None, x_auth_token=token)
        self.assertEqual(authenticated_user.id, user.id)

    def test_08_optional_user_dependency_behavior(self):
        # Anonymous call -> None
        anon = get_optional_current_user(db=self.db, authorization=None)
        self.assertIsNone(anon)

        # Authenticated call -> User
        user = self.create_test_user()
        token = create_access_token({"sub": user.id})
        auth_u = get_optional_current_user(db=self.db, authorization=f"Bearer {token}")
        self.assertIsNotNone(auth_u)
        self.assertEqual(auth_u.id, user.id)


# =============================================================================
# 4. ROLE-BASED ACCESS CONTROL (RBAC) TESTS
# =============================================================================

class Test4_RoleBasedAccessControl(BaseAuthRBACTestCase):
    """Test suite verifying endpoint permissions across ADMIN, MANAGER, TECHNICIAN, and CUSTOMER."""

    def test_01_admin_can_access_all_endpoints(self):
        admin = self.create_test_user(role="admin")

        # 1. Routing Rules Read & Write
        rules_res = get_rules(db=self.db, current_user=admin)
        self.assertIn("rules", rules_res)

        new_rule_res = create_rule(
            RuleCreate(
                category="RBAC Test Rule",
                team="Network Team",
                priority="high",
                keywords=["testkeywordrbac"],
                description="Test rule description"
            ),
            db=self.db,
            current_user=admin
        )
        self.assertIn("rule", new_rule_res)
        rule_id = new_rule_res["rule"]["id"]
        self._created_rule_ids.append(rule_id)

        # 2. Analytics Access
        analytics_res = get_analytics(db=self.db, current_user=admin)
        self.assertIn("total_tickets", analytics_res)

        # 3. User Management Access
        users_res = list_users(admin_user=admin, db=self.db)
        self.assertIn("users", users_res)

        # 4. Technicians List Access
        techs_res = get_technicians(db=self.db, current_user=admin)
        self.assertIn("technicians", techs_res)

    def test_02_manager_can_read_rules_and_analytics(self):
        manager = self.create_test_user(role="manager")

        # Manager can view rules
        rules_res = get_rules(db=self.db, current_user=manager)
        self.assertIn("rules", rules_res)

        # Manager can view analytics
        analytics_res = get_analytics(db=self.db, current_user=manager)
        self.assertIn("total_tickets", analytics_res)

    def test_03_manager_cannot_modify_rules_or_users(self):
        manager = self.create_test_user(role="manager")
        admin = self.create_test_user(role="admin")

        # Create a rule using admin first
        rule_res = create_rule(
            RuleCreate(
                category=f"Rule_{int(time.time()*1000)}",
                team="Network Team",
                priority="medium",
                keywords=["switch", "router"],
                description="Network hardware rule"
            ),
            db=self.db,
            current_user=admin
        )
        r_id = rule_res["rule"]["id"]
        self._created_rule_ids.append(r_id)

        # 1. Manager CANNOT create rules (403)
        with self.assertRaises(HTTPException) as ctx:
            create_rule(
                RuleCreate(category="Blocked Rule", team="Network Team", priority="low", keywords=["k"], description="d"),
                db=self.db,
                current_user=manager
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # 2. Manager CANNOT edit rules (403)
        with self.assertRaises(HTTPException) as ctx:
            update_rule(
                rule_id=r_id,
                rule_update=RuleUpdate(team="M365 Support", priority="high", keywords=["office"], description="new desc"),
                db=self.db,
                current_user=manager
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # 3. Manager CANNOT toggle rule status (403)
        with self.assertRaises(HTTPException) as ctx:
            update_rule_status(
                rule_id=r_id,
                status_update=RuleStatusUpdate(is_active=False),
                db=self.db,
                current_user=manager
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # 4. Manager CANNOT re-evaluate rules (403)
        with self.assertRaises(HTTPException) as ctx:
            re_evaluate_rule(
                rule_id=r_id,
                db=self.db,
                current_user=manager
            )
        self.assertEqual(ctx.exception.status_code, 403)

        # 5. Manager CANNOT manage users (403)
        checker = require_admin
        with self.assertRaises(HTTPException) as ctx:
            checker(current_user=manager)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_04_technician_cannot_access_rules(self):
        tech = self.create_test_user(role="technician")
        with self.assertRaises(HTTPException) as ctx:
            get_rules(db=self.db, current_user=tech)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            create_rule(
                RuleCreate(category="Blocked", team="Network Team", priority="low", keywords=["k"], description="d"),
                db=self.db,
                current_user=tech
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_05_technician_cannot_access_analytics(self):
        tech = self.create_test_user(role="technician")
        with self.assertRaises(HTTPException) as ctx:
            get_analytics(db=self.db, current_user=tech)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_06_technician_cannot_manage_users(self):
        tech = self.create_test_user(role="technician")
        checker = require_admin
        with self.assertRaises(HTTPException) as ctx:
            checker(current_user=tech)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_07_customer_cannot_access_internal_tickets(self):
        cust_user = self.create_test_user(role="customer")
        with self.assertRaises(HTTPException) as ctx:
            get_tickets(db=self.db, current_user=cust_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_08_customer_cannot_access_rules_analytics_technicians_users(self):
        cust_user = self.create_test_user(role="customer")

        # Blocked from Rules
        with self.assertRaises(HTTPException) as ctx:
            get_rules(db=self.db, current_user=cust_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Blocked from Analytics
        with self.assertRaises(HTTPException) as ctx:
            get_analytics(db=self.db, current_user=cust_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # Blocked from Technicians
        with self.assertRaises(HTTPException) as ctx:
            get_technicians(db=self.db, current_user=cust_user)
        self.assertEqual(ctx.exception.status_code, 403)


# =============================================================================
# 5. TICKET ACCESS SECURITY & MULTI-TENANT ISOLATION TESTS
# =============================================================================

class Test5_TicketAccessSecurity(BaseAuthRBACTestCase):
    """Test suite verifying tenant isolation, cross-tenant protection, and identity stamping."""

    def test_01_customer_portal_ticket_isolation(self):
        cust_a = self.create_test_customer(name="Customer Alpha", company="Alpha Corp")
        cust_b = self.create_test_customer(name="Customer Beta", company="Beta Corp")

        user_a = self.create_test_user(role="customer", customer_id=cust_a.id)
        user_b = self.create_test_user(role="customer", customer_id=cust_b.id)

        # Create ticket for Customer Alpha
        alpha_ticket_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(
                title="Alpha VPN Outage",
                description="Alpha corporate network connection failed.",
                category="Network"
            ),
            customer=cust_a,
            db=self.db
        )
        t_id = alpha_ticket_res["ticket"]["id"]
        self._created_ticket_ids.append(t_id)

        # Customer Alpha CAN view ticket detail
        detail_a = get_customer_ticket_detail(ticket_id=t_id, customer=cust_a, db=self.db)
        self.assertEqual(detail_a["ticket"]["id"], t_id)

        # Customer Beta CANNOT view Customer Alpha's ticket
        with self.assertRaises(HTTPException) as ctx:
            get_customer_ticket_detail(ticket_id=t_id, customer=cust_b, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("another customer account", ctx.exception.detail.lower())

    def test_02_customer_header_spoofing_prevented(self):
        """When authenticated as Customer A, providing header X-Customer-Id of Customer B is safely ignored/bound to A."""
        cust_a = self.create_test_customer(name="Legitimate User", company="Legit Corp")
        cust_b = self.create_test_customer(name="Victim Org", company="Target Corp")

        user_a = self.create_test_user(role="customer", customer_id=cust_a.id)

        resolved_customer = get_current_customer(
            db=self.db,
            x_customer_id=str(cust_b.id),  # Malicious attempt to spoof customer B
            current_user=user_a
        )
        self.assertEqual(resolved_customer.id, cust_a.id, "Customer identity must bind strictly to current_user.customer_id")

    def test_03_internal_work_notes_hidden_from_customer(self):
        cust = self.create_test_customer(company="Gamma Org")
        ticket_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Work Note Invisibility Test", description="Testing note visibility.", category="Endpoint"),
            customer=cust,
            db=self.db
        )
        tid = ticket_res["ticket"]["id"]
        self._created_ticket_ids.append(tid)

        # Add internal work note (technician only)
        tech_user = self.create_test_user(name="Lead Tech", role="technician")
        add_ticket_note(
            ticket_id=tid,
            note_data=NoteCreate(content="PRIVATE INTERNAL WORK NOTE: Secret root password logged.", note_type="internal"),
            db=self.db,
            current_user=tech_user
        )

        # Add customer update (public)
        add_ticket_note(
            ticket_id=tid,
            note_data=NoteCreate(content="PUBLIC CUSTOMER UPDATE: We are checking your device.", note_type="customer"),
            db=self.db,
            current_user=tech_user
        )

        # Fetch through Customer Portal
        portal_detail = get_customer_ticket_detail(ticket_id=tid, customer=cust, db=self.db)
        updates = portal_detail["updates"]

        # Verify internal note is NOT in updates
        self.assertEqual(len(updates), 1)
        self.assertIn("PUBLIC CUSTOMER UPDATE", updates[0]["content"])
        self.assertNotIn("PRIVATE INTERNAL WORK NOTE", json.dumps(portal_detail))

    def test_04_technician_note_author_auto_stamped(self):
        cust = self.create_test_customer()
        t_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Author Stamping Test", description="Desc", category="Network"),
            customer=cust,
            db=self.db
        )
        tid = t_res["ticket"]["id"]
        self._created_ticket_ids.append(tid)

        # 1. Rahul Sharma adds internal note with default payload author="MSP Technician"
        rahul = self.create_test_user(name="Rahul Sharma", role="technician")
        note1 = add_ticket_note(
            ticket_id=tid,
            note_data=NoteCreate(content="Checked Microsoft 365 licensing and Exchange mailbox.", note_type="internal", author="MSP Technician"),
            db=self.db,
            current_user=rahul
        )
        self.assertEqual(note1["author"], "Rahul Sharma")

        # 2. Arjun Patel adds customer update note with payload author="Fake User"
        arjun = self.create_test_user(name="Arjun Patel", role="technician")
        note2 = add_ticket_note(
            ticket_id=tid,
            note_data=NoteCreate(content="Switch firmware updated successfully.", note_type="customer", author="Fake User"),
            db=self.db,
            current_user=arjun
        )
        self.assertEqual(note2["author"], "Arjun Patel")

        # 3. Aditya Singh adds note with empty payload author
        aditya = self.create_test_user(name="Aditya Singh", role="technician")
        note3 = add_ticket_note(
            ticket_id=tid,
            note_data=NoteCreate(content="Firewall logs analyzed for malicious IP.", note_type="internal", author=""),
            db=self.db,
            current_user=aditya
        )
        self.assertEqual(note3["author"], "Aditya Singh")

        # 4. Verify in database notes table
        db_notes = self.db.query(TicketNote).filter(TicketNote.ticket_id == tid).order_by(TicketNote.id.asc()).all()
        self.assertEqual(len(db_notes), 3)
        self.assertEqual(db_notes[0].author, "Rahul Sharma")
        self.assertEqual(db_notes[1].author, "Arjun Patel")
        self.assertEqual(db_notes[2].author, "Aditya Singh")

        # 5. Verify in Activity Timeline audits
        audits = self.db.query(RoutingAudit).filter(RoutingAudit.ticket_id == tid, RoutingAudit.routing_method == "technician_note").all()
        self.assertEqual(len(audits), 3)
        self.assertIn("Rahul Sharma", audits[0].reason)
        self.assertIn("Arjun Patel", audits[1].reason)
        self.assertIn("Aditya Singh", audits[2].reason)

    def test_05_technician_escalation_identity_auto_stamped(self):
        cust = self.create_test_customer()
        t_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Escalation Stamping Test", description="Desc", category="Network"),
            customer=cust,
            db=self.db
        )
        tid = t_res["ticket"]["id"]
        self._created_ticket_ids.append(tid)

        # Arjun Patel escalates ticket
        arjun = self.create_test_user(name="Arjun Patel", role="technician")
        esc = escalate_ticket_endpoint(
            ticket_id=tid,
            payload=EscalateTicketRequest(escalation_level=2, escalation_reason="Escalation to senior infrastructure lead.", escalated_by="MSP Technician"),
            db=self.db,
            current_user=arjun
        )
        self.assertEqual(esc["escalation_level"], 2)
        self.assertEqual(esc["escalated_by"], "Arjun Patel")

        t_check = self.db.query(Ticket).filter(Ticket.id == tid).first()
        self.assertEqual(t_check.escalated_by, "Arjun Patel")

    def test_06_multi_tenant_named_customer_isolation(self):
        """Test multi-tenant isolation across John Doe (Acme Corp), Sarah Jenkins (Globex Financial), Tony Stark (Stark Industries), and Bruce Wayne (Wayne Enterprises)."""
        # Create or fetch customer accounts
        acme = self.create_test_customer(name="John Doe", email="test.john.doe@acme.com", company="Acme Corp")
        globex = self.create_test_customer(name="Sarah Jenkins", email="test.sarah.j@globex.com", company="Globex Financial")
        stark = self.create_test_customer(name="Tony Stark", email="test.tony@starkindustries.com", company="Stark Industries")
        wayne = self.create_test_customer(name="Bruce Wayne", email="test.bruce@wayneenterprises.com", company="Wayne Enterprises")

        user_john = self.create_test_user(name="John Doe", email="test.john.doe@acme.com", role="customer", customer_id=acme.id)
        user_sarah = self.create_test_user(name="Sarah Jenkins", email="test.sarah.j@globex.com", role="customer", customer_id=globex.id)
        user_tony = self.create_test_user(name="Tony Stark", email="test.tony@starkindustries.com", role="customer", customer_id=stark.id)
        user_bruce = self.create_test_user(name="Bruce Wayne", email="test.bruce@wayneenterprises.com", role="customer", customer_id=wayne.id)

        # Create tickets for each tenant
        t_acme = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Acme Router Offline", description="Core router not responding.", category="Network"),
            customer=acme,
            db=self.db
        )["ticket"]
        self._created_ticket_ids.append(t_acme["id"])

        t_globex = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Globex Trading Latency", description="High latency on trading terminal.", category="Application"),
            customer=globex,
            db=self.db
        )["ticket"]
        self._created_ticket_ids.append(t_globex["id"])

        t_stark = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Stark Arc Reactor Telemetry", description="Telemetry drops on sensor grid.", category="Endpoint"),
            customer=stark,
            db=self.db
        )["ticket"]
        self._created_ticket_ids.append(t_stark["id"])

        t_wayne = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Wayne Satellite Uplink", description="Encrypted uplink synchronization timeout.", category="Security"),
            customer=wayne,
            db=self.db
        )["ticket"]
        self._created_ticket_ids.append(t_wayne["id"])

        # 1. John Doe views ticket list -> ONLY Acme tickets returned
        john_tickets = list_customer_tickets(customer=acme, db=self.db)["tickets"]
        john_ticket_ids = [t["id"] for t in john_tickets]
        self.assertIn(t_acme["id"], john_ticket_ids)
        self.assertNotIn(t_globex["id"], john_ticket_ids)
        self.assertNotIn(t_stark["id"], john_ticket_ids)
        self.assertNotIn(t_wayne["id"], john_ticket_ids)

        # 2. Sarah Jenkins views ticket list -> ONLY Globex tickets returned
        sarah_tickets = list_customer_tickets(customer=globex, db=self.db)["tickets"]
        sarah_ticket_ids = [t["id"] for t in sarah_tickets]
        self.assertIn(t_globex["id"], sarah_ticket_ids)
        self.assertNotIn(t_acme["id"], sarah_ticket_ids)
        self.assertNotIn(t_stark["id"], sarah_ticket_ids)
        self.assertNotIn(t_wayne["id"], sarah_ticket_ids)

        # 3. Tony Stark views ticket list -> ONLY Stark tickets returned
        tony_tickets = list_customer_tickets(customer=stark, db=self.db)["tickets"]
        tony_ticket_ids = [t["id"] for t in tony_tickets]
        self.assertIn(t_stark["id"], tony_ticket_ids)
        self.assertNotIn(t_acme["id"], tony_ticket_ids)
        self.assertNotIn(t_globex["id"], tony_ticket_ids)
        self.assertNotIn(t_wayne["id"], tony_ticket_ids)

        # 4. Bruce Wayne views ticket list -> ONLY Wayne tickets returned
        wayne_tickets = list_customer_tickets(customer=wayne, db=self.db)["tickets"]
        wayne_ticket_ids = [t["id"] for t in wayne_tickets]
        self.assertIn(t_wayne["id"], wayne_ticket_ids)
        self.assertNotIn(t_acme["id"], wayne_ticket_ids)
        self.assertNotIn(t_globex["id"], wayne_ticket_ids)
        self.assertNotIn(t_stark["id"], wayne_ticket_ids)

        # 5. Cross-Tenant Direct URL ID Access is Blocked (HTTP 403)
        # John Doe (Acme Corp) attempts to access Wayne Enterprises ticket
        with self.assertRaises(HTTPException) as ctx:
            get_customer_ticket_detail(ticket_id=t_wayne["id"], customer=acme, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("another customer account", ctx.exception.detail.lower())

        # John Doe (Acme Corp) attempts to access Globex Financial ticket
        with self.assertRaises(HTTPException) as ctx:
            get_customer_ticket_detail(ticket_id=t_globex["id"], customer=acme, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("another customer account", ctx.exception.detail.lower())

        # John Doe (Acme Corp) attempts to access Stark Industries ticket
        with self.assertRaises(HTTPException) as ctx:
            get_customer_ticket_detail(ticket_id=t_stark["id"], customer=acme, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("another customer account", ctx.exception.detail.lower())

        # Non-existent ticket ID returns 404
        with self.assertRaises(HTTPException) as ctx:
            get_customer_ticket_detail(ticket_id=999999, customer=acme, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

        # Cross-tenant updates and resolution confirmations are blocked (403)
        with self.assertRaises(HTTPException) as ctx:
            add_customer_ticket_update(ticket_id=t_stark["id"], payload=CustomerUpdateCreate(content="Unauthorized update"), customer=acme, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            confirm_ticket_resolution(ticket_id=t_acme["id"], customer=stark, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            reopen_customer_ticket(ticket_id=t_wayne["id"], customer=globex, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

        # 6. Dashboard metrics strictly scoped to Acme Corp
        dash_john = get_customer_dashboard(customer=acme, db=self.db)
        for t in dash_john["recent_tickets"]:
            t_obj = self.db.query(Ticket).filter(Ticket.id == t["id"]).first()
            self.assertEqual(t_obj.customer_id, acme.id)
            self.assertEqual(t_obj.customer_company, "Acme Corp")

        # 7. Internal API rejection for customer users
        with self.assertRaises(HTTPException) as ctx:
            get_tickets(db=self.db, current_user=user_john)
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            get_ticket(ticket_id=t_acme["id"], db=self.db, current_user=user_john)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_07_customer_ticket_creation_identity_locking(self):
        """When creating a ticket as John Doe, the company and identity are locked to Acme Corp even if headers attempt to spoof."""
        acme = self.create_test_customer(name="John Doe", email="auth.john.doe@acme.com", company="Acme Corp")
        wayne = self.create_test_customer(name="Bruce Wayne", email="auth.bruce@wayneenterprises.com", company="Wayne Enterprises")

        user_john = self.create_test_user(name="John Doe", email="auth.john.doe@acme.com", role="customer", customer_id=acme.id)

        # Resolve customer via get_current_customer with spoofed X-Customer-Id
        resolved = get_current_customer(
            db=self.db,
            x_customer_id=str(wayne.id),  # Spoofing attempt
            current_user=user_john
        )
        self.assertEqual(resolved.id, acme.id)
        self.assertEqual(resolved.company, "Acme Corp")
        self.assertEqual(resolved.name, "John Doe")

        # Ticket created strictly uses resolved customer
        t_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Acme Printer Config", description="Printer configuration needed.", category="Endpoint"),
            customer=resolved,
            db=self.db
        )
        t_id = t_res["ticket"]["id"]
        self._created_ticket_ids.append(t_id)

        t_db = self.db.query(Ticket).filter(Ticket.id == t_id).first()
        self.assertEqual(t_db.customer_id, acme.id)
        self.assertEqual(t_db.customer_name, "John Doe")
        self.assertEqual(t_db.customer_company, "Acme Corp")
        self.assertEqual(t_db.customer_email, "auth.john.doe@acme.com")


# =============================================================================
# 6. REGRESSION & CORE FUNCTIONALITY TESTS
# =============================================================================

class Test6_RegressionCoreFunctionality(BaseAuthRBACTestCase):
    """Test suite ensuring that core routing, SLA calculation, and lifecycle operations remain fully intact."""

    def test_01_ticket_creation_and_routing_engine(self):
        admin = self.create_test_user(role="admin")
        res = route_ticket_endpoint(
            ticket=TicketRequest(
                title="Critical BGP routing failure on core switch",
                description="Packet loss exceeding 80% across primary gateway router."
            ),
            db=self.db,
            current_user=admin
        )
        tid = res["ticket_id"]
        self._created_ticket_ids.append(tid)

        self.assertEqual(res["decision"]["team"], "Network Team")
        self.assertIn("response_due_at", res["sla"])
        self.assertIn("resolution_due_at", res["sla"])

    def test_02_ticket_audit_timeline_recording(self):
        admin = self.create_test_user(role="admin")
        res = route_ticket_endpoint(
            ticket=TicketRequest(title="Outlook calendar sync failure", description="Office 365 calendar sync issue."),
            db=self.db,
            current_user=admin
        )
        tid = res["ticket_id"]
        self._created_ticket_ids.append(tid)

        audits = self.db.query(RoutingAudit).filter(RoutingAudit.ticket_id == tid).all()
        self.assertGreaterEqual(len(audits), 1)
        self.assertEqual(audits[0].team, res["decision"]["team"])

    def test_03_routing_rule_reevaluation(self):
        admin = self.create_test_user(role="admin")
        # Create unique rule
        rule_res = create_rule(
            RuleCreate(
                category="Reeval Category",
                team="Endpoint Team",
                priority="low",
                keywords=["reevalkeywordxyz"],
                description="Reevaluation test"
            ),
            db=self.db,
            current_user=admin
        )
        rid = rule_res["rule"]["id"]
        self._created_rule_ids.append(rid)

        # Create ticket matching rule
        ticket_res = route_ticket_endpoint(
            ticket=TicketRequest(title="Issue with reevalkeywordxyz", description="Hardware fault"),
            db=self.db,
            current_user=admin
        )
        tid = ticket_res["ticket_id"]
        self._created_ticket_ids.append(tid)

        # Re-evaluate rule
        reeval_res = re_evaluate_rule(rule_id=rid, db=self.db, current_user=admin)
        self.assertIn("tickets_checked", reeval_res)

    def test_04_sla_deadlines_and_status_calculation(self):
        admin = self.create_test_user(role="admin")
        t_res = route_ticket_endpoint(
            ticket=TicketRequest(title="VIP executive outage", description="Critical system down for CEO."),
            db=self.db,
            current_user=admin
        )
        tid = t_res["ticket_id"]
        self._created_ticket_ids.append(tid)

        ticket = self.db.query(Ticket).filter(Ticket.id == tid).first()
        self.assertIsNotNone(ticket.response_due_at)
        self.assertIsNotNone(ticket.resolution_due_at)
        self.assertIn(ticket.sla_status, ["on_track", "at_risk", "breached", "met"])

    def test_05_technician_workload_dynamic_calculation(self):
        admin = self.create_test_user(role="admin")

        # Create ticket
        t_res = route_ticket_endpoint(
            ticket=TicketRequest(title="Outlook email delivery delay", description="Microsoft 365 exchange mailbox sync issue"),
            db=self.db,
            current_user=admin
        )
        tid = t_res["ticket_id"]
        self._created_ticket_ids.append(tid)
        assigned_team = t_res["decision"]["team"]

        # Create technician matching assigned team
        tech = self.create_test_technician(team=assigned_team)

        # Initial workload 0
        w0 = get_technician_workload(self.db, tech.id)
        self.assertEqual(w0["active_workload"], 0)

        assign_res = assign_ticket_technician(
            ticket_id=tid,
            payload=TechnicianAssignRequest(technician_id=tech.id),
            db=self.db,
            current_user=admin
        )
        self.assertNotIn("error", assign_res)

        w1 = get_technician_workload(self.db, tech.id)
        self.assertEqual(w1["active_workload"], 1)

        # Resolve ticket -> workload drops to 0
        update_ticket_status(
            ticket_id=tid,
            status_update=StatusUpdate(status="resolved", resolution_summary="Fixed"),
            db=self.db
        )

        w2 = get_technician_workload(self.db, tech.id)
        self.assertEqual(w2["active_workload"], 0)


# =============================================================================
# 7. NEGATIVE & SECURITY SCENARIOS TESTS
# =============================================================================

class Test7_NegativeSecurityTests(BaseAuthRBACTestCase):
    """Test suite verifying defensive input handling and security boundaries."""

    def test_01_sql_injection_safety(self):
        sql_injection_email = "' OR '1'='1' --"
        with self.assertRaises(HTTPException) as ctx:
            login(LoginRequest(email=sql_injection_email, password="' OR '1'='1'"), db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_02_cross_team_technician_assignment_rejected(self):
        admin = self.create_test_user(role="admin")
        tech_m365 = self.create_test_technician(team="M365 Support")

        # Create ticket explicitly routed to Network Team via router keyword
        t_res = route_ticket_endpoint(
            ticket=TicketRequest(title="Primary router offline", description="Core network switch and VPN unreachable"),
            db=self.db,
            current_user=admin
        )
        tid = t_res["ticket_id"]
        self._created_ticket_ids.append(tid)

        # Attempt to assign M365 tech to Network ticket -> MUST RETURN ERROR
        assign_res = assign_ticket_technician(
            ticket_id=tid,
            payload=TechnicianAssignRequest(technician_id=tech_m365.id),
            db=self.db,
            current_user=admin
        )
        self.assertIn("error", assign_res)
        self.assertIn("belongs to", assign_res["error"].lower())

    def test_03_invalid_downward_escalation_rejected(self):
        admin = self.create_test_user(role="admin")
        t_res = route_ticket_endpoint(
            ticket=TicketRequest(title="Escalation level validation", description="Desc"),
            db=self.db,
            current_user=admin
        )
        tid = t_res["ticket_id"]
        self._created_ticket_ids.append(tid)

        # Escalate to level 2
        escalate_ticket_endpoint(
            ticket_id=tid,
            payload=EscalateTicketRequest(escalation_level=2, escalation_reason="Initial tier 2 escalation"),
            db=self.db,
            current_user=admin
        )

        # Attempting to escalate to level 2 again or level 1 must return error
        esc_dup_res = escalate_ticket_endpoint(
            ticket_id=tid,
            payload=EscalateTicketRequest(escalation_level=2, escalation_reason="Duplicate level 2"),
            db=self.db,
            current_user=admin
        )
        self.assertIn("error", esc_dup_res)
        self.assertIn("already at escalation level 2", esc_dup_res["error"].lower())

    def test_04_reopen_non_resolved_ticket_rejected(self):
        cust = self.create_test_customer()
        t_res = create_customer_ticket(
            payload=PortalTicketCreateRequest(title="Reopen check", description="Desc", category="Service Desk"),
            customer=cust,
            db=self.db
        )
        tid = t_res["ticket_id"] if "ticket_id" in t_res else t_res["ticket"]["id"]
        self._created_ticket_ids.append(tid)

        # Ticket is currently 'new', reopening must fail
        with self.assertRaises(HTTPException) as ctx:
            reopen_customer_ticket(ticket_id=tid, customer=cust, db=self.db)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("only resolved tickets can be reopened", ctx.exception.detail.lower())


# =============================================================================
# SUITE RUNNER
# =============================================================================

def run_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(Test1_LoginAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(Test2_PasswordSecurity))
    suite.addTests(loader.loadTestsFromTestCase(Test3_AuthenticationProtection))
    suite.addTests(loader.loadTestsFromTestCase(Test4_RoleBasedAccessControl))
    suite.addTests(loader.loadTestsFromTestCase(Test5_TicketAccessSecurity))
    suite.addTests(loader.loadTestsFromTestCase(Test6_RegressionCoreFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(Test7_NegativeSecurityTests))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    result = run_suite()
    if not result.wasSuccessful():
        sys.exit(1)
