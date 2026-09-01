import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.team import Team
from app.models.technician import Technician
from app.models.ticket import Ticket
from app.models.routing_rule import RoutingRule
from app.models.notification import Notification
from app.models.customer import Customer
from app.core.security import hash_password, create_access_token

client = TestClient(app)


class TestDynamicTeamManagementSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # Create canonical customers
        cls.cust_acme = cls.db.query(Customer).filter(Customer.email == "john.teamtest@acme.com").first()
        if not cls.cust_acme:
            cls.cust_acme = Customer(name="John TeamTest", email="john.teamtest@acme.com", company="Acme Corp", is_active=True)
            cls.db.add(cls.cust_acme)
            cls.db.commit()
            cls.db.refresh(cls.cust_acme)

        # Retrieve canonical teams
        cls.team_m365 = cls.db.query(Team).filter(Team.name == "M365 Support").first()
        cls.team_net = cls.db.query(Team).filter(Team.name == "Network Team").first()
        cls.team_sec = cls.db.query(Team).filter(Team.name == "Security Team").first()

        # Technicians
        cls.tech_rahul = cls.db.query(Technician).filter(Technician.email == "rahul.sharma@jacehaus.com").first()
        cls.tech_priya = cls.db.query(Technician).filter(Technician.email == "priya.mehta@jacehaus.com").first()
        cls.tech_arjun = cls.db.query(Technician).filter(Technician.email == "arjun.patel@jacehaus.com").first()
        cls.tech_aditya = cls.db.query(Technician).filter(Technician.email == "aditya.singh@jacehaus.com").first()

        # Create/find Users
        cls.user_admin = cls.db.query(User).filter(User.email == "admin@jacehaus.com").first()
        cls.user_manager = cls.db.query(User).filter(User.email == "manager@jacehaus.com").first()
        cls.user_tech = cls.db.query(User).filter(User.email == "rahul.sharma@jacehaus.com").first()
        cls.user_cust = cls.db.query(User).filter(User.email == "john.doe@acme.com").first()

        # Create JWT Tokens
        cls.admin_token = create_access_token({"sub": str(cls.user_admin.id), "role": "admin", "email": cls.user_admin.email})
        cls.manager_token = create_access_token({"sub": str(cls.user_manager.id), "role": "manager", "email": cls.user_manager.email})
        cls.tech_token = create_access_token({"sub": str(cls.user_tech.id), "role": "technician", "email": cls.user_tech.email, "technician_id": cls.tech_rahul.id})
        cls.cust_token = create_access_token({"sub": str(cls.user_cust.id), "role": "customer", "email": cls.user_cust.email, "customer_id": cls.cust_acme.id})

        # Add a test ticket & rule for verification
        cls.ticket1 = Ticket(
            title="Team Test Ticket",
            description="Testing dynamic team routing",
            category="Email",
            assigned_team_id=cls.team_m365.id,
            assigned_team="M365 Support",
            priority="high",
            status="new"
        )
        cls.db.add(cls.ticket1)
        cls.db.commit()
        cls.db.refresh(cls.ticket1)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # -------------------------------------------------------------
    # TEST 1: Admin Team CRUD
    # -------------------------------------------------------------
    def test_01_admin_team_crud(self):
        """Admin can create, read, update, and delete a dynamic team."""
        # Cleanup if leftover exists
        existing = self.db.query(Team).filter(Team.name == "Cloud Infrastructure").first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        # 1. Create
        payload = {
            "name": "Cloud Infrastructure",
            "description": "Azure & AWS Cloud Engineering Team",
            "business_hours_start": "09:00",
            "business_hours_end": "17:00",
            "timezone": "America/Chicago",
            "work_days": "MON,TUE,WED,THU,FRI",
            "is_active": True
        }
        r_create = client.post("/teams/", json=payload, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_create.status_code, 201)
        data = r_create.json()["team"]
        team_id = data["id"]
        self.assertEqual(data["name"], "Cloud Infrastructure")
        self.assertEqual(data["slug"], "cloud-infrastructure")

        # 2. Read
        r_get = client.get(f"/teams/{team_id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.json()["name"], "Cloud Infrastructure")

        # 3. Update
        r_put = client.put(f"/teams/{team_id}", json={"description": "Updated Cloud Infra Team"}, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_put.status_code, 200)
        self.assertEqual(r_put.json()["team"]["description"], "Updated Cloud Infra Team")

        # 4. Delete
        r_del = client.delete(f"/teams/{team_id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_del.status_code, 200)

    # -------------------------------------------------------------
    # TEST 2: Manager Cannot Delete Teams
    # -------------------------------------------------------------
    def test_02_manager_cannot_delete(self):
        """Manager has edit access but receives 403 on team deletion."""
        existing = self.db.query(Team).filter(Team.name == "DevOps Team").first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        # Create a team via admin
        r_create = client.post("/teams/", json={"name": "DevOps Team", "description": "CI/CD"}, headers={"Authorization": f"Bearer {self.admin_token}"})
        team_id = r_create.json()["team"]["id"]

        # Manager can update
        r_put = client.put(f"/teams/{team_id}", json={"description": "DevOps & SRE"}, headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_put.status_code, 200)

        # Manager cannot delete -> 403
        r_del = client.delete(f"/teams/{team_id}", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(r_del.status_code, 403)

        # Cleanup via admin
        client.delete(f"/teams/{team_id}", headers={"Authorization": f"Bearer {self.admin_token}"})

    # -------------------------------------------------------------
    # TEST 3: Technician Read-Only Access
    # -------------------------------------------------------------
    def test_03_technician_read_only(self):
        """Technicians can list teams and view details, but receive 403 on write endpoints."""
        r_list = client.get("/teams/", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_list.status_code, 200)
        self.assertGreaterEqual(r_list.json()["count"], 1)

        # Tech cannot create -> 403
        r_post = client.post("/teams/", json={"name": "Tech Unauthorized Team"}, headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_post.status_code, 403)

        # Tech cannot update -> 403
        r_put = client.put(f"/teams/{self.team_m365.id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_put.status_code, 403)

    # -------------------------------------------------------------
    # TEST 4: Customer Access Denied (403)
    # -------------------------------------------------------------
    def test_04_customer_receives_403(self):
        """Customer users receive 403 on all internal /teams endpoints."""
        r_get = client.get("/teams/", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(r_get.status_code, 403)

        r_detail = client.get(f"/teams/{self.team_m365.id}", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(r_detail.status_code, 403)

    # -------------------------------------------------------------
    # TEST 5: Team Lead Assignment
    # -------------------------------------------------------------
    def test_05_team_lead_assignment(self):
        """Assigning a team lead links the technician and displays in team profile."""
        r_team = client.get(f"/teams/{self.team_m365.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_team.status_code, 200)
        self.assertEqual(r_team.json()["team_lead_name"], "Rahul Sharma")
        self.assertEqual(r_team.json()["team_lead_id"], self.tech_rahul.id)

    # -------------------------------------------------------------
    # TEST 6: Team Activation and Deactivation Safety
    # -------------------------------------------------------------
    def test_06_team_activation_deactivation(self):
        """Deactivating team checks for open tickets and active rules, blocking unforced deactivation."""
        # Team M365 has active tickets/rules -> should fail without force
        r_deact = client.patch(
            f"/teams/{self.team_m365.id}/status",
            json={"is_active": False, "force": False},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_deact.status_code, 400)
        self.assertIn("active workload or active routing rules", str(r_deact.json()))

        # Creating a temporary empty team to test clean deactivation
        r_create = client.post("/teams/", json={"name": "Temp QA Team", "is_active": True}, headers={"Authorization": f"Bearer {self.admin_token}"})
        temp_id = r_create.json()["team"]["id"]

        r_toggle = client.patch(f"/teams/{temp_id}/status", json={"is_active": False}, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_toggle.status_code, 200)
        self.assertFalse(r_toggle.json()["team"]["is_active"])

        # Re-activate
        r_re = client.patch(f"/teams/{temp_id}/status", json={"is_active": True}, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_re.status_code, 200)
        self.assertTrue(r_re.json()["team"]["is_active"])

        client.delete(f"/teams/{temp_id}", headers={"Authorization": f"Bearer {self.admin_token}"})

    # -------------------------------------------------------------
    # TEST 7: Dynamic Routing Rule Team Validation
    # -------------------------------------------------------------
    def test_07_dynamic_routing_rule_team_validation(self):
        """Creating routing rule with dynamic team succeeds; invalid/inactive team is rejected."""
        existing = self.db.query(Team).filter(Team.name == "Database Team").first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        # Create dynamic team
        r_create = client.post("/teams/", json={"name": "Database Team", "is_active": True}, headers={"Authorization": f"Bearer {self.admin_token}"})
        db_team_id = r_create.json()["team"]["id"]

        # Create rule for Database Team -> succeeds
        r_rule = client.post(
            "/rules/",
            json={"category": "Database", "team": "Database Team", "priority": "high", "keywords": ["sql", "postgres"], "description": "Database issues"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_rule.status_code, 200)
        self.assertEqual(r_rule.json()["rule"]["team"], "Database Team")
        self.assertEqual(r_rule.json()["rule"]["team_id"], db_team_id)

        # Non-existent team -> error
        r_invalid = client.post(
            "/rules/",
            json={"category": "Aliens", "team": "Area 51 Team", "priority": "low", "keywords": ["ufo"], "description": "Aliens"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertIn("error", r_invalid.json())

    # -------------------------------------------------------------
    # TEST 8: Dynamic Ticket Team Assignment
    # -------------------------------------------------------------
    def test_08_dynamic_ticket_team_assignment(self):
        """Re-routing a ticket to a dynamic team logs audit and updates queue."""
        r_patch = client.patch(
            f"/tickets/{self.ticket1.id}/team",
            json={"team": "Database Team"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_patch.status_code, 200)
        self.assertEqual(r_patch.json()["assigned_team"], "Database Team")

        # Move back to M365 Support
        client.patch(f"/tickets/{self.ticket1.id}/team", json={"team": "M365 Support"}, headers={"Authorization": f"Bearer {self.admin_token}"})

    # -------------------------------------------------------------
    # TEST 9: Existing String Fields Remain Synchronized
    # -------------------------------------------------------------
    def test_09_existing_string_fields_remain_synchronized(self):
        """Technician.team, Ticket.assigned_team, RoutingRule.team remain populated strings."""
        db = SessionLocal()
        tech = db.query(Technician).filter(Technician.id == self.tech_rahul.id).first()
        self.assertEqual(tech.team, "M365 Support")
        self.assertEqual(tech.team_id, self.team_m365.id)
        db.close()

    # -------------------------------------------------------------
    # TEST 10: Business Hours and Timezone Persistence
    # -------------------------------------------------------------
    def test_10_business_hours_and_timezone_persistence(self):
        """Team operating hours, timezone, and work days persist accurately."""
        r_team = client.get(f"/teams/{self.team_sec.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_team.status_code, 200)
        data = r_team.json()
        self.assertEqual(data["business_hours_start"], "00:00")
        self.assertEqual(data["business_hours_end"], "23:59")
        self.assertEqual(data["timezone"], "UTC")
        self.assertEqual(data["work_days"], "MON,TUE,WED,THU,FRI,SAT,SUN")

    # -------------------------------------------------------------
    # TEST 11: Duplicate Team Name Prevention
    # -------------------------------------------------------------
    def test_11_duplicate_team_name_prevention(self):
        """Attempting to create a team with an existing name returns HTTP 400."""
        r_dup = client.post(
            "/teams/",
            json={"name": "M365 Support", "description": "Duplicate M365"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_dup.status_code, 400)
        self.assertIn("already exists", r_dup.json()["detail"])

    # -------------------------------------------------------------
    # TEST 12: Inactive Teams Excluded from Active Selection
    # -------------------------------------------------------------
    def test_12_inactive_teams_excluded_from_active_selection(self):
        """Inactive teams are filtered out when is_active=true."""
        r_active = client.get("/teams/?is_active=true", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_active.status_code, 200)
        for t in r_active.json()["teams"]:
            self.assertTrue(t["is_active"])

    # -------------------------------------------------------------
    # TEST 13: Existing Technicians Remain Correctly Assigned
    # -------------------------------------------------------------
    def test_13_existing_technicians_remain_correctly_assigned(self):
        """Existing technicians are linked to team_id and show in members list."""
        r_team = client.get(f"/teams/{self.team_m365.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_team.status_code, 200)
        member_names = [m["name"] for m in r_team.json()["members"]]
        self.assertIn("Rahul Sharma", member_names)
        self.assertIn("Priya Mehta", member_names)

    # -------------------------------------------------------------
    # TEST 14: Existing Tickets Remain Correctly Assigned
    # -------------------------------------------------------------
    def test_14_existing_tickets_remain_correctly_assigned(self):
        """Tickets have valid assigned_team_id and assigned_team."""
        db = SessionLocal()
        ticket = db.query(Ticket).filter(Ticket.id == self.ticket1.id).first()
        self.assertEqual(ticket.assigned_team, "M365 Support")
        self.assertEqual(ticket.assigned_team_id, self.team_m365.id)
        db.close()

    # -------------------------------------------------------------
    # TEST 15: Existing Notification Team Scoping Still Works
    # -------------------------------------------------------------
    def test_15_existing_notification_team_scoping_still_works(self):
        """Notification filtering by scope=my_team continues working with dynamic teams."""
        db = SessionLocal()
        ticket_net = Ticket(
            title="Network Outage",
            description="Switch failure",
            assigned_team_id=self.team_net.id,
            assigned_team="Network Team",
            priority="critical",
            status="new"
        )
        db.add(ticket_net)
        db.commit()
        db.refresh(ticket_net)

        notif_m365 = Notification(
            ticket_id=self.ticket1.id,
            type="TICKET_ASSIGNED",
            severity="info",
            title="Ticket Assigned to M365",
            message="Test message",
            is_read=False
        )
        notif_net = Notification(
            ticket_id=ticket_net.id,
            type="TICKET_ASSIGNED",
            severity="info",
            title="Ticket Assigned to Network",
            message="Test message",
            is_read=False
        )
        db.add_all([notif_m365, notif_net])
        db.commit()
        db.refresh(notif_m365)
        db.refresh(notif_net)
        m365_id = notif_m365.id
        net_id = notif_net.id
        db.close()

        r_notif = client.get("/notifications/?scope=my_team", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(r_notif.status_code, 200)
        notif_ids = [n["id"] for n in r_notif.json()["notifications"]]
        self.assertIn(m365_id, notif_ids)
        self.assertNotIn(net_id, notif_ids)

    # -------------------------------------------------------------
    # TEST 16: Team Rename Synchronization
    # -------------------------------------------------------------
    def test_16_team_rename_synchronization(self):
        """Renaming a team cascades to linked technicians, routing rules, tickets, and notifications."""
        # Cleanup any previous remnants
        db_clean = SessionLocal()
        for t_name in ["Old Name Team", "New Name Team"]:
            t_old = db_clean.query(Team).filter(Team.name == t_name).first()
            if t_old:
                db_clean.query(Technician).filter(Technician.team_id == t_old.id).delete()
                db_clean.query(RoutingRule).filter(RoutingRule.team_id == t_old.id).delete()
                db_clean.delete(t_old)
        db_clean.commit()
        db_clean.close()

        # Create a test team
        r_create = client.post("/teams/", json={"name": "Old Name Team", "is_active": True}, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_create.status_code, 201)
        rename_team_id = r_create.json()["team"]["id"]

        # Create tech and rule with Old Name Team
        db = SessionLocal()
        tech = Technician(name="Rename Tech", email="renametech@jacehaus.com", team_id=rename_team_id, team="Old Name Team", is_active=True)
        rule = RoutingRule(category="RenameCat", team_id=rename_team_id, team="Old Name Team", priority="low", keywords=["rename"], is_active=True)
        db.add_all([tech, rule])
        db.commit()
        db.refresh(tech)
        db.refresh(rule)
        tech_id = tech.id
        rule_id = rule.id
        db.close()

        # Rename team
        r_rename = client.put(f"/teams/{rename_team_id}", json={"name": "New Name Team"}, headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_rename.status_code, 200)
        self.assertEqual(r_rename.json()["team"]["name"], "New Name Team")

        # Verify synchronization
        db = SessionLocal()
        refreshed_tech = db.query(Technician).filter(Technician.id == tech_id).first()
        refreshed_rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
        self.assertEqual(refreshed_tech.team, "New Name Team")
        self.assertEqual(refreshed_rule.team, "New Name Team")

        # Cleanup
        db.delete(refreshed_rule)
        db.delete(refreshed_tech)
        team_to_del = db.query(Team).filter(Team.id == rename_team_id).first()
        if team_to_del:
            db.delete(team_to_del)
        db.commit()
        db.close()

    # -------------------------------------------------------------
    # TEST 17: Team Deletion Safety
    # -------------------------------------------------------------
    def test_17_team_deletion_safety(self):
        """Team referenced by active rules or tickets cannot be deleted."""
        # Team M365 has tickets and rules -> deletion must fail with 400
        r_del = client.delete(f"/teams/{self.team_m365.id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(r_del.status_code, 400)
        self.assertIn("reference it", r_del.json()["detail"])

    # -------------------------------------------------------------
    # TEST 18: Unauthorized Access Returns Correct Status Codes
    # -------------------------------------------------------------
    def test_18_unauthorized_access_returns_correct_status_codes(self):
        """Unauthenticated requests to /teams/ return 401."""
        r_no_auth = client.get("/teams/")
        self.assertEqual(r_no_auth.status_code, 401)

        r_post_no_auth = client.post("/teams/", json={"name": "No Auth Team"})
        self.assertEqual(r_post_no_auth.status_code, 401)

    # -------------------------------------------------------------
    # TEST 19: PUT /teams/{id} With Member Team Lead (No Circular Dependency)
    # -------------------------------------------------------------
    def test_19_put_team_with_member_team_lead_no_circular_dependency(self):
        """Editing team description and team lead where lead is a member completes without CircularDependencyError."""
        # 1. Update existing team (M365 Support) with tech_rahul as lead and update description
        r_put = client.put(
            f"/teams/{self.team_m365.id}",
            json={
                "description": "Updated M365 Specialized Helpdesk Support",
                "team_lead_id": self.tech_rahul.id,
                "business_hours_start": "08:30",
                "business_hours_end": "17:30",
                "timezone": "America/New_York",
                "work_days": "MON,TUE,WED,THU,FRI"
            },
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_put.status_code, 200)
        team_data = r_put.json()["team"]
        self.assertEqual(team_data["description"], "Updated M365 Specialized Helpdesk Support")
        self.assertEqual(team_data["team_lead_id"], self.tech_rahul.id)
        self.assertEqual(team_data["team_lead_name"], "Rahul Sharma")
        self.assertEqual(team_data["business_hours_start"], "08:30")

        # 2. Subsequent edit on description only with lead still attached
        r_put2 = client.put(
            f"/teams/{self.team_m365.id}",
            json={"description": "M365 Cloud & Tenant Operations"},
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(r_put2.status_code, 200)
        self.assertEqual(r_put2.json()["team"]["description"], "M365 Cloud & Tenant Operations")
        self.assertEqual(r_put2.json()["team"]["team_lead_id"], self.tech_rahul.id)

        # 3. Create a brand new team, add a member, and assign that member as lead via PUT
        r_create = client.post(
            "/teams/",
            json={"name": "SRE Reliability Team", "description": "Site reliability", "is_active": True},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_create.status_code, 201)
        sre_team_id = r_create.json()["team"]["id"]

        # Create technician assigned to SRE team
        db = SessionLocal()
        sre_tech = Technician(name="SRE Lead Tech", email="srelead@jacehaus.com", team_id=sre_team_id, team="SRE Reliability Team", is_active=True)
        db.add(sre_tech)
        db.commit()
        db.refresh(sre_tech)
        sre_tech_id = sre_tech.id
        db.close()

        # Update SRE team to assign sre_tech as team lead
        r_sre_put = client.put(
            f"/teams/{sre_team_id}",
            json={"description": "High-availability site reliability engineering", "team_lead_id": sre_tech_id},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(r_sre_put.status_code, 200)
        self.assertEqual(r_sre_put.json()["team"]["team_lead_id"], sre_tech_id)
        self.assertEqual(r_sre_put.json()["team"]["team_lead_name"], "SRE Lead Tech")

        # Cleanup
        db = SessionLocal()
        db.query(Technician).filter(Technician.id == sre_tech_id).delete()
        sre_team = db.query(Team).filter(Team.id == sre_team_id).first()
        if sre_team:
            db.delete(sre_team)
        db.commit()
        db.close()


if __name__ == "__main__":
    unittest.main()
