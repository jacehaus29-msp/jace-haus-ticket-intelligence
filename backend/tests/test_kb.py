import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app, run_db_migrations
from app.database import SessionLocal
from app.models.user import User
from app.models.customer import Customer
from app.models.kb import KBCategory, KBArticle, KBArticleVersion, KBArticleFeedback
from app.core.security import create_access_token

client = TestClient(app)


class TestKnowledgeBaseSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_db_migrations()
        cls.db: Session = SessionLocal()

        # Canonical Users
        cls.user_admin = cls.db.query(User).filter(User.email == "admin@jacehaus.com").first()
        cls.user_manager = cls.db.query(User).filter(User.email == "manager@jacehaus.com").first()
        cls.user_tech = cls.db.query(User).filter(User.email == "rahul.sharma@jacehaus.com").first()
        cls.user_cust = cls.db.query(User).filter(User.email == "john.doe@acme.com").first()

        # JWT Tokens
        cls.admin_token = create_access_token({"sub": str(cls.user_admin.id), "role": "admin", "email": cls.user_admin.email})
        cls.manager_token = create_access_token({"sub": str(cls.user_manager.id), "role": "manager", "email": cls.user_manager.email})
        cls.tech_token = create_access_token({"sub": str(cls.user_tech.id), "role": "technician", "email": cls.user_tech.email})
        cls.cust_token = create_access_token({"sub": str(cls.user_cust.id), "role": "customer", "email": cls.user_cust.email})

        # Clean up test rows from prior test runs
        test_slugs = [
            "hardware-provisioning-asset-care",
            "configuring-dual-4k-monitors-with-thunderbolt-4-docks",
            "internal-sop-vmware-esxi-host-patching-cluster-evacuation",
            "unfinished-draft-article",
            "article-to-be-deleted"
        ]
        cls.db.query(KBArticle).filter(KBArticle.slug.in_(test_slugs)).delete(synchronize_session=False)
        cls.db.query(KBCategory).filter(KBCategory.slug.in_(test_slugs)).delete(synchronize_session=False)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # -------------------------------------------------------------
    # 1. Admin creates KB category
    # -------------------------------------------------------------
    def test_01_admin_create_category(self):
        """Admin can create a new knowledge category."""
        existing = self.db.query(KBCategory).filter(KBCategory.slug == "hardware-provisioning-asset-care").first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        res = client.post(
            "/kb/categories",
            json={
                "name": "Hardware Provisioning & Asset Care",
                "description": "Standard procedures for laptop imaging and asset lifecycle",
                "icon": "laptop",
                "display_order": 10
            },
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["category"]["name"], "Hardware Provisioning & Asset Care")
        self.assertEqual(data["category"]["slug"], "hardware-provisioning-asset-care")

    # -------------------------------------------------------------
    # 2. Admin creates public article (Version 1)
    # -------------------------------------------------------------
    def test_02_admin_create_public_article(self):
        """Admin can create a public published article; auto-creates version 1."""
        res = client.post(
            "/kb/articles",
            json={
                "title": "Configuring Dual 4K Monitors with Thunderbolt 4 Docks",
                "summary": "Step-by-step display settings and firmware updates for external monitors",
                "content": "# Dual Monitor Setup\n\n1. Plug in dock power.\n2. Connect DisplayPort cables.\n3. Update Intel Graphics drivers.",
                "visibility": "public",
                "status": "published",
                "tags": "monitor, display, dock, thunderbolt, hardware",
                "change_summary": "Initial monitor guide"
            },
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["article"]["title"], "Configuring Dual 4K Monitors with Thunderbolt 4 Docks")
        self.assertEqual(data["article"]["visibility"], "public")
        self.assertEqual(data["article"]["current_version"], 1)

    # -------------------------------------------------------------
    # 3. Admin creates internal article
    # -------------------------------------------------------------
    def test_03_admin_create_internal_article(self):
        """Admin can create an internal engineering runbook."""
        res = client.post(
            "/kb/articles",
            json={
                "title": "Internal SOP: VMware ESXi Host Patching & Cluster Evacuation",
                "summary": "Procedure for putting hypervisors into maintenance mode and running VUM updates",
                "content": "# ESXi Patching Runbook\n\n**INTERNAL USE ONLY**\n\n1. Migrate VMs via vMotion.\n2. Enter maintenance mode.\n3. Run esxcli software profile update.",
                "visibility": "internal",
                "status": "published",
                "tags": "esxi, vmware, hypervisor, patching, internal",
                "change_summary": "Initial hypervisor SOP"
            },
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["article"]["visibility"], "internal")
        self.__class__.internal_article_id = data["article"]["id"]

    # -------------------------------------------------------------
    # 4. Manager updates article with automatic versioning
    # -------------------------------------------------------------
    def test_04_manager_edit_article_versioning(self):
        """Manager updates article; version number increments to 2 and version history is stored."""
        # Find the monitor article
        art = self.db.query(KBArticle).filter(KBArticle.slug.like("configuring-dual-4k-monitors%")).first()
        self.assertIsNotNone(art)

        res = client.put(
            f"/kb/articles/{art.id}",
            json={
                "title": "Configuring Dual 4K Monitors with Thunderbolt 4 Docks (Updated)",
                "content": "# Dual Monitor Setup (Updated)\n\n1. Plug in dock.\n2. Use certified HDMI 2.1 cables.\n3. Configure Windows Display Settings.",
                "change_summary": "Added HDMI 2.1 cable requirement"
            },
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["article"]["current_version"], 2)

        # Check version audit history
        res_ver = client.get(
            f"/kb/articles/{art.id}/versions",
            headers={"Authorization": f"Bearer {self.manager_token}"}
        )
        self.assertEqual(res_ver.status_code, 200)
        v_data = res_ver.json()
        self.assertEqual(v_data["count"], 2)
        self.assertEqual(v_data["versions"][0]["version_number"], 2)
        self.assertEqual(v_data["versions"][1]["version_number"], 1)

    # -------------------------------------------------------------
    # 5. Technician can read internal and public articles
    # -------------------------------------------------------------
    def test_05_technician_can_read_internal_and_public(self):
        """Technician can read internal runbooks and public articles."""
        res_list = client.get(
            "/kb/articles",
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        self.assertEqual(res_list.status_code, 200)
        visibilities = [a["visibility"] for a in res_list.json()["articles"]]
        self.assertIn("internal", visibilities)
        self.assertIn("public", visibilities)

        # Direct detail lookup of internal article
        res_detail = client.get(
            f"/kb/articles/{self.internal_article_id}",
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn("ESXi Patching Runbook", res_detail.json()["article"]["content"])

    # -------------------------------------------------------------
    # 6. Technician cannot create or edit articles (403)
    # -------------------------------------------------------------
    def test_06_technician_cannot_create_or_edit(self):
        """Technician receives 403 on POST /kb/articles and PUT /kb/articles/{id}."""
        res_post = client.post(
            "/kb/articles",
            json={"title": "Tech Article", "content": "Sample content"},
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        self.assertEqual(res_post.status_code, 403)

        res_put = client.put(
            f"/kb/articles/{self.internal_article_id}",
            json={"title": "Unauthorized Edit"},
            headers={"Authorization": f"Bearer {self.tech_token}"}
        )
        self.assertEqual(res_put.status_code, 403)

    # -------------------------------------------------------------
    # 7. Customer can read public article & view count increments
    # -------------------------------------------------------------
    def test_07_customer_can_read_public_article(self):
        """Customer can read public article and view count increments."""
        art = self.db.query(KBArticle).filter(KBArticle.visibility == "public", KBArticle.status == "published").first()
        init_views = art.view_count

        res = client.get(f"/portal/kb/articles/{art.slug}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["article"]["id"], art.id)
        self.assertEqual(data["article"]["view_count"], init_views + 1)

    # -------------------------------------------------------------
    # 8. Customer cannot read internal article (403/404)
    # -------------------------------------------------------------
    def test_08_customer_cannot_read_internal_article(self):
        """Customer requesting internal article receives 403 Forbidden."""
        res = client.get(f"/portal/kb/articles/{self.internal_article_id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn("restricted to internal MSP engineering", res.json()["detail"])

    # -------------------------------------------------------------
    # 9. Customer cannot read draft article (403/404)
    # -------------------------------------------------------------
    def test_09_customer_cannot_read_draft_article(self):
        """Customer cannot access draft articles."""
        # Create draft article via admin
        res_draft = client.post(
            "/kb/articles",
            json={"title": "Unfinished Draft Article", "content": "Draft content...", "status": "draft", "visibility": "public"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        draft_id = res_draft.json()["article"]["id"]

        res = client.get(f"/portal/kb/articles/{draft_id}")
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # 10. Customer cannot access internal KB write endpoints (403)
    # -------------------------------------------------------------
    def test_10_customer_cannot_modify_articles(self):
        """Customer role receives 403 on /kb endpoints."""
        res = client.get("/kb/articles", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # 11. Portal KB search strictly excludes internal articles
    # -------------------------------------------------------------
    def test_11_portal_kb_search_isolation(self):
        """Searching portal KB never returns internal runbooks."""
        res = client.get("/portal/kb/articles?query=esxi")
        self.assertEqual(res.status_code, 200)
        # ESXi is internal only, should return 0 results in portal
        self.assertEqual(res.json()["count"], 0)

        # Searching for MFA returns public MFA guide
        res_mfa = client.get("/portal/kb/articles?query=authenticator")
        self.assertEqual(res_mfa.status_code, 200)
        self.assertGreaterEqual(res_mfa.json()["count"], 1)

    # -------------------------------------------------------------
    # 12. Portal KB category filter
    # -------------------------------------------------------------
    def test_12_portal_kb_category_filter(self):
        """Category filtering returns only articles matching selected category."""
        res = client.get("/portal/kb/articles?category_slug=security-mfa")
        self.assertEqual(res.status_code, 200)
        for a in res.json()["articles"]:
            self.assertEqual(a["category_name"], "Security & Multi-Factor Auth")

    # -------------------------------------------------------------
    # 13. Article helpfulness upvote
    # -------------------------------------------------------------
    def test_13_article_helpfulness_upvote(self):
        """Submitting positive feedback increments helpful_count."""
        art = self.db.query(KBArticle).filter(KBArticle.visibility == "public", KBArticle.status == "published").first()
        init_helpful = art.helpful_count

        res = client.post(
            f"/portal/kb/articles/{art.id}/feedback",
            json={"is_helpful": True, "comment": "Saved me 30 minutes!"},
            headers={"Authorization": f"Bearer {self.cust_token}"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["helpful_count"], init_helpful + 1)

    # -------------------------------------------------------------
    # 14. Article helpfulness downvote
    # -------------------------------------------------------------
    def test_14_article_helpfulness_downvote(self):
        """Submitting negative feedback increments not_helpful_count."""
        art = self.db.query(KBArticle).filter(KBArticle.visibility == "public", KBArticle.status == "published").first()
        init_not_helpful = art.not_helpful_count

        res = client.post(
            f"/portal/kb/articles/{art.id}/feedback",
            json={"is_helpful": False, "comment": "Steps were confusing on Mac"},
            headers={"Authorization": f"Bearer {self.cust_token}"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["not_helpful_count"], init_not_helpful + 1)

    # -------------------------------------------------------------
    # 15. Smart ticket deflection suggestions
    # -------------------------------------------------------------
    def test_15_smart_ticket_deflection_suggestions(self):
        """Suggest endpoint returns matching public articles for ticket title terms."""
        res = client.get("/portal/kb/suggest?q=vpn+tunnel+disconnected")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data["count"], 1)
        self.assertIn("VPN", data["suggestions"][0]["title"])

    # -------------------------------------------------------------
    # 16. Unauthenticated requests to internal endpoints return 401
    # -------------------------------------------------------------
    def test_16_unauthenticated_requests_rejected(self):
        """Unauthenticated request to /kb/articles returns 401."""
        res = client.get("/kb/articles")
        self.assertEqual(res.status_code, 401)

    # -------------------------------------------------------------
    # 17. KB Analytics calculations
    # -------------------------------------------------------------
    def test_17_kb_analytics_calculation(self):
        """KB Analytics returns article counts, view metrics, and helpfulness %."""
        res = client.get("/kb/analytics", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_articles", data)
        self.assertIn("overall_helpfulness_percentage", data)
        self.assertIn("top_viewed_articles", data)
        self.assertGreater(data["total_views"], 0)

    # -------------------------------------------------------------
    # 18. Manager cannot delete category or article (Admin only)
    # -------------------------------------------------------------
    def test_18_manager_cannot_delete(self):
        """Manager receives 403 on DELETE endpoints."""
        art = self.db.query(KBArticle).first()
        res_del_art = client.delete(f"/kb/articles/{art.id}", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(res_del_art.status_code, 403)

        cat = self.db.query(KBCategory).first()
        res_del_cat = client.delete(f"/kb/categories/{cat.id}", headers={"Authorization": f"Bearer {self.manager_token}"})
        self.assertEqual(res_del_cat.status_code, 403)

    # -------------------------------------------------------------
    # 19. Admin delete article cascades cleanly
    # -------------------------------------------------------------
    def test_19_admin_delete_article_cascades(self):
        """Admin deleting an article cascades version history and feedback records."""
        # Create dedicated article to delete
        res_create = client.post(
            "/kb/articles",
            json={"title": "Article To Be Deleted", "content": "Temporary content to test cascade deletion"},
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        art_id = res_create.json()["article"]["id"]

        # Add feedback
        client.post(f"/portal/kb/articles/{art_id}/feedback", json={"is_helpful": True})

        # Delete article
        res_del = client.delete(f"/kb/articles/{art_id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        self.assertEqual(res_del.status_code, 200)

        # Verify DB cascade
        db = SessionLocal()
        self.assertIsNone(db.query(KBArticle).filter(KBArticle.id == art_id).first())
        self.assertEqual(db.query(KBArticleVersion).filter(KBArticleVersion.article_id == art_id).count(), 0)
        self.assertEqual(db.query(KBArticleFeedback).filter(KBArticleFeedback.article_id == art_id).count(), 0)
        db.close()

    # -------------------------------------------------------------
    # 20. Existing functionality regression check
    # -------------------------------------------------------------
    def test_20_existing_functionality_regression_check(self):
        """Verify Customer portal tickets, dashboard, and teams remain fully functional."""
        res_dash = client.get("/portal/dashboard", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(res_dash.status_code, 200)

        res_teams = client.get("/teams", headers={"Authorization": f"Bearer {self.tech_token}"})
        self.assertEqual(res_teams.status_code, 200)

    # -------------------------------------------------------------
    # 21. Deflection suggestion to full article reading flow
    # -------------------------------------------------------------
    def test_21_deflection_suggestion_to_article_detail_flow(self):
        """Verify complete interaction: suggest keywords -> returns suggestion -> fetch full article -> submit solved deflection feedback."""
        # 1. Customer types subject matching VPN
        res_sug = client.get("/portal/kb/suggest?q=Office+VPN+gateway+disconnects", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(res_sug.status_code, 200)
        sugs = res_sug.json().get("suggestions", [])
        self.assertGreaterEqual(len(sugs), 1)

        first_sug = sugs[0]
        self.assertIn("id", first_sug)
        self.assertIn("title", first_sug)

        # 2. Customer clicks "Read Solution ->" triggering detail fetch
        art_id = first_sug["id"]
        res_detail = client.get(f"/portal/kb/articles/{art_id}", headers={"Authorization": f"Bearer {self.cust_token}"})
        self.assertEqual(res_detail.status_code, 200)
        art_data = res_detail.json().get("article", {})
        self.assertEqual(art_data["id"], art_id)
        self.assertIn("content", art_data)
        self.assertGreater(len(art_data["content"]), 0)

        # 3. Customer clicks "This Solved My Issue - Cancel Ticket"
        res_fb = client.post(
            f"/portal/kb/articles/{art_id}/feedback",
            json={"is_helpful": True, "comment": "Deflected ticket submission"},
            headers={"Authorization": f"Bearer {self.cust_token}"}
        )
        self.assertEqual(res_fb.status_code, 200)
        self.assertIn("helpful_count", res_fb.json())


if __name__ == "__main__":
    unittest.main()

