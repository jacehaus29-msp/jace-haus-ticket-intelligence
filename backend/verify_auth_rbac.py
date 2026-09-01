import sys
import os
from datetime import datetime

# Set path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.database import SessionLocal, engine
from app.models.user import User
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.technician import Technician
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.api.auth import login, get_current_user_profile, list_users, create_user, update_user, LoginRequest, UserCreateRequest, UserUpdateRequest
from app.api.rules import get_rules, create_rule, RuleCreate
from app.routes.analytics import get_analytics
from app.api.technicians import get_technicians
from app.api.tickets import get_tickets, add_ticket_note, escalate_ticket_endpoint, NoteCreate, EscalateTicketRequest
from app.api.portal import (
    get_customer_dashboard,
    list_customer_tickets,
    get_customer_ticket_detail,
    create_customer_ticket,
    PortalTicketCreateRequest,
    get_current_customer
)
from fastapi import HTTPException


def run_tests():
    print("=" * 65)
    print("VERIFYING AUTHENTICATION & ROLE-BASED ACCESS CONTROL (RBAC)")
    print("=" * 65)

    db = SessionLocal()
    try:
        # -------------------------------------------------------------
        # TEST 1: Password Hashing & Verification
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing PBKDF2 Password Hashing & Verification...")
        pw = "Secret@Pass123"
        hashed = hash_password(pw)
        assert hashed.startswith("pbkdf2:sha256:100000$"), "Hash format invalid"
        assert verify_password(pw, hashed) is True, "Valid password verification failed"
        assert verify_password("WrongPassword", hashed) is False, "Invalid password incorrectly accepted"
        print("  [PASS] Password hashing & constant-time verification working properly.")

        # -------------------------------------------------------------
        # TEST 2: Seed Users Verification & DB Presence
        # -------------------------------------------------------------
        print("\n[TEST 2] Verifying Seed Users in Database...")
        admin = db.query(User).filter(User.email == "admin@jacehaus.com").first()
        manager = db.query(User).filter(User.email == "manager@jacehaus.com").first()
        tech = db.query(User).filter(User.email == "rahul.sharma@jacehaus.com").first()
        cust_a = db.query(User).filter(User.email == "john.doe@acme.com").first()
        cust_b = db.query(User).filter(User.email == "sarah.j@globex.com").first()

        assert admin is not None and admin.role == "admin", "Admin seed user missing"
        assert manager is not None and manager.role == "manager", "Manager seed user missing"
        assert tech is not None and tech.role == "technician", "Technician seed user missing"
        assert cust_a is not None and cust_a.role == "customer", "Customer A seed user missing"
        assert cust_b is not None and cust_b.role == "customer", "Customer B seed user missing"
        print(f"  Found users: Admin ({admin.name}), Manager ({manager.name}), Tech ({tech.name}), Customer A ({cust_a.name})")
        print("  [PASS] Seed users verified.")

        # -------------------------------------------------------------
        # TEST 3: Login Endpoints & Token Generation
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing Login & Token Generation for Roles...")
        # Valid Admin login
        admin_login = login(LoginRequest(email="admin@jacehaus.com", password="Admin@123"), db=db)
        assert "access_token" in admin_login, "Token missing in login response"
        assert admin_login["user"]["role"] == "admin"
        admin_token = admin_login["access_token"]

        # Valid Tech login
        tech_login = login(LoginRequest(email="rahul.sharma@jacehaus.com", password="Tech@123"), db=db)
        tech_token = tech_login["access_token"]
        assert tech_login["user"]["team"] == "M365 Support"

        # Valid Customer login
        cust_login = login(LoginRequest(email="john.doe@acme.com", password="Client@123"), db=db)
        cust_token = cust_login["access_token"]
        assert cust_login["user"]["company"] == "Acme Corp"
        print("  [PASS] Login succeeded for Admin, Technician, and Customer accounts.")

        # -------------------------------------------------------------
        # TEST 4: Invalid Password & Deactivated User Handling
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing Invalid Credentials & Deactivated Accounts...")
        try:
            login(LoginRequest(email="admin@jacehaus.com", password="WrongPassword!"), db=db)
            assert False, "Login should have raised 401 for wrong password"
        except HTTPException as e:
            assert e.status_code == 401
            print("  [PASS] Invalid password correctly rejected (401).")

        # Test inactive user
        test_inactive = db.query(User).filter(User.email == "test.inactive@jacehaus.com").first()
        if not test_inactive:
            test_inactive = User(
                name="Inactive User",
                email="test.inactive@jacehaus.com",
                password_hash=hash_password("Pass@123"),
                role="technician",
                is_active=False
            )
            db.add(test_inactive)
            db.commit()
            db.refresh(test_inactive)

        try:
            login(LoginRequest(email="test.inactive@jacehaus.com", password="Pass@123"), db=db)
            assert False, "Login should have rejected inactive user"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Deactivated user correctly rejected (403).")

        # -------------------------------------------------------------
        # TEST 5: GET /auth/me Endpoint
        # -------------------------------------------------------------
        print("\n[TEST 5] Testing /auth/me Endpoint...")
        profile_admin = get_current_user_profile(current_user=admin, db=db)
        assert profile_admin["user"]["email"] == "admin@jacehaus.com"
        assert profile_admin["permissions"]["is_admin"] is True
        assert "password_hash" not in profile_admin["user"]

        profile_tech = get_current_user_profile(current_user=tech, db=db)
        assert profile_tech["permissions"]["is_admin"] is False
        assert profile_tech["permissions"]["is_technician"] is True
        print("  [PASS] /auth/me returns sanitized profile and permission flags.")

        # -------------------------------------------------------------
        # TEST 6: User Management (Admin Only)
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing Admin User Management Endpoints...")
        user_list = list_users(admin_user=admin, db=db)
        assert user_list["count"] >= 5

        # Create new user via admin
        test_new_email = "new.technician.test@jacehaus.com"
        existing_test = db.query(User).filter(User.email == test_new_email).first()
        if existing_test:
            db.delete(existing_test)
            db.commit()

        new_user_res = create_user(
            UserCreateRequest(
                name="Test New Tech",
                email=test_new_email,
                password="TechPassword@123",
                role="technician"
            ),
            admin_user=admin,
            db=db
        )
        assert new_user_res["user"]["email"] == test_new_email
        created_id = new_user_res["user"]["id"]

        # Update user active status
        updated_res = update_user(
            user_id=created_id,
            payload=UserUpdateRequest(is_active=False),
            admin_user=admin,
            db=db
        )
        assert updated_res["user"]["is_active"] is False
        print(f"  [PASS] User created (ID: {created_id}) and deactivated successfully.")

        # Cleanup
        to_del = db.query(User).filter(User.id == created_id).first()
        if to_del:
            db.delete(to_del)
            db.commit()

        # -------------------------------------------------------------
        # TEST 7: Role-Based Routing Rules Access
        # -------------------------------------------------------------
        print("\n[TEST 7] Testing Routing Rules RBAC...")
        # Admin can view & edit
        admin_rules = get_rules(db=db, current_user=admin)
        assert "rules" in admin_rules

        # Manager can view
        mgr_rules = get_rules(db=db, current_user=manager)
        assert "rules" in mgr_rules

        # Technician blocked from viewing/editing rules
        try:
            get_rules(db=db, current_user=tech)
            assert False, "Technician should not view rules"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Technician blocked from viewing routing rules (403).")

        # Manager blocked from creating rules
        try:
            create_rule(
                RuleCreate(category="Test", team="Network Team", priority="low", keywords=["test"], description="test"),
                db=db,
                current_user=manager
            )
            assert False, "Manager should not create rules"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Manager blocked from modifying routing rules (403).")

        # Customer blocked from viewing rules
        try:
            get_rules(db=db, current_user=cust_a)
            assert False, "Customer should not view rules"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Customer blocked from viewing routing rules (403).")

        # -------------------------------------------------------------
        # TEST 8: Role-Based Analytics Access
        # -------------------------------------------------------------
        print("\n[TEST 8] Testing Analytics RBAC...")
        # Admin and Manager can access
        admin_analytics = get_analytics(db=db, current_user=admin)
        assert "total_tickets" in admin_analytics
        mgr_analytics = get_analytics(db=db, current_user=manager)
        assert "total_tickets" in mgr_analytics

        # Technician blocked
        try:
            get_analytics(db=db, current_user=tech)
            assert False, "Technician should not access analytics"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Technician blocked from Analytics (403).")

        # Customer blocked
        try:
            get_analytics(db=db, current_user=cust_a)
            assert False, "Customer should not access analytics"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Customer blocked from Analytics (403).")

        # -------------------------------------------------------------
        # TEST 9: Internal Tickets & Technicians Isolation from Customer
        # -------------------------------------------------------------
        print("\n[TEST 9] Testing Customer Block on Internal APIs...")
        try:
            get_tickets(db=db, current_user=cust_a)
            assert False, "Customer should not call internal /tickets"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Customer blocked from internal /tickets endpoint (403).")

        try:
            get_technicians(db=db, current_user=cust_a)
            assert False, "Customer should not call /technicians"
        except HTTPException as e:
            assert e.status_code == 403
            print("  [PASS] Customer blocked from /technicians endpoint (403).")

        # -------------------------------------------------------------
        # TEST 10: Authenticated Customer Portal Ownership & Ticket Creation
        # -------------------------------------------------------------
        print("\n[TEST 10] Testing Authenticated Customer Portal Ticket Creation...")
        cust_a_profile = get_current_customer(db=db, current_user=cust_a)
        cust_b_profile = get_current_customer(db=db, current_user=cust_b)

        # Create ticket as Customer A (John Doe / Acme Corp)
        new_portal_t = create_customer_ticket(
            payload=PortalTicketCreateRequest(
                title="Auth Verification - Acme VPN Connectivity",
                description="Unable to authenticate to Acme corporate gateway via Cisco AnyConnect.",
                category="Network"
            ),
            customer=cust_a_profile,
            db=db
        )
        created_t_id = new_portal_t["ticket"]["id"]
        assert new_portal_t["ticket"]["customer_company"] == "Acme Corp"
        print(f"  [PASS] Created Ticket #{created_t_id} for Acme Corp via authenticated customer token.")

        # Customer A can view
        cust_a_t = get_customer_ticket_detail(ticket_id=created_t_id, customer=cust_a_profile, db=db)
        assert cust_a_t["ticket"]["id"] == created_t_id

        # Customer B is FORBIDDEN from viewing Customer A's ticket
        try:
            get_customer_ticket_detail(ticket_id=created_t_id, customer=cust_b_profile, db=db)
            assert False, "Customer B should NOT access Customer A's ticket"
        except HTTPException as e:
            assert e.status_code == 403
            print(f"  [PASS] Cross-tenant access blocked with 403: {e.detail}")

        # -------------------------------------------------------------
        # TEST 11: Technician Identity Stamping on Work Notes & Escalation
        # -------------------------------------------------------------
        print("\n[TEST 11] Testing Technician Identity Stamping...")
        # Add internal work note with authenticated technician
        note_res = add_ticket_note(
            ticket_id=created_t_id,
            note_data=NoteCreate(
                content="Investigating VPN authentication logs in RADIUS server.",
                note_type="internal"
            ),
            db=db,
            current_user=tech
        )
        assert note_res["author"] == "Rahul Sharma", f"Expected 'Rahul Sharma', got {note_res['author']}"
        print(f"  [PASS] Work note author automatically stamped as '{note_res['author']}'.")

        # Escalate ticket with authenticated technician
        esc_res = escalate_ticket_endpoint(
            ticket_id=created_t_id,
            payload=EscalateTicketRequest(
                escalation_level=2,
                escalation_reason="RADIUS server certificate renewal issue requires tier-2 infrastructure support."
            ),
            db=db,
            current_user=tech
        )
        assert esc_res["escalation_level"] == 2
        
        # Verify in DB
        t_check = db.query(Ticket).filter(Ticket.id == created_t_id).first()
        assert t_check.escalated_by == "Rahul Sharma"
        print(f"  [PASS] Ticket escalated to Level 2 with escalated_by='{t_check.escalated_by}'.")

        print("\n" + "=" * 65)
        print("ALL 11 AUTHENTICATION & RBAC TESTS PASSED (100% SUCCESS)!")
        print("=" * 65)

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
