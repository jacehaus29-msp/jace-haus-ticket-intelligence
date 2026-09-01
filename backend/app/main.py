from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.api.rules import router as rules_router
from app.api.tickets import router as tickets_router
from app.api.notifications import router as notifications_router
from app.api.technicians import router as technicians_router
from app.api.portal import router as portal_router
from app.api.auth import router as auth_router
from app.api.reports import router as reports_router
from app.api.teams import router as teams_router
from app.api.csat import router as csat_router
from app.api.kb import router as kb_router
from app.database import Base, engine
from app.routes import analytics
from app.models.user import User
from app.models.customer import Customer
from app.models.team import Team
from app.models.ticket import Ticket
from app.models.technician import Technician
from app.models.routing_rule import RoutingRule
from app.models.routing_audit import RoutingAudit
from app.models.notification import Notification
from app.models.ticket_note import TicketNote
from app.core.security import hash_password

# Create database tables and ensure SLA columns, notifications & ticket notes exist
Base.metadata.create_all(bind=engine)

SEED_CUSTOMERS = [
    {"name": "John Doe", "email": "john.doe@acme.com", "company": "Acme Corp", "phone": "+1 555-0192"},
    {"name": "Sarah Jenkins", "email": "sarah.j@globex.com", "company": "Globex Financial", "phone": "+1 555-0144"},
    {"name": "Tony Stark", "email": "tony@starkindustries.com", "company": "Stark Industries", "phone": "+1 555-3000"},
    {"name": "Bruce Wayne", "email": "bruce@wayneenterprises.com", "company": "Wayne Enterprises", "phone": "+1 555-1939"},
]

SEED_TEAMS = [
    {"name": "M365 Support", "slug": "m365-support", "description": "Microsoft 365, Exchange, Teams & Entra ID support", "lead_email": "rahul.sharma@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
    {"name": "Network Team", "slug": "network-team", "description": "Firewalls, switches, SD-WAN & ISP routing", "lead_email": "arjun.patel@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
    {"name": "Security Team", "slug": "security-team", "description": "SOC monitoring, EDR/MDR alert response & vulnerability remediation", "lead_email": "aditya.singh@jacehaus.com", "business_hours_start": "00:00", "business_hours_end": "23:59", "timezone": "UTC", "work_days": "MON,TUE,WED,THU,FRI,SAT,SUN", "is_active": True},
    {"name": "Endpoint Team", "slug": "endpoint-team", "description": "Workstation provisioning, patch management & hardware dispatch", "lead_email": "karan.shah@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
    {"name": "Backup Team", "slug": "backup-team", "description": "BDR appliances, immutable cloud backups & restore testing", "lead_email": "amit.verma@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
    {"name": "Application Support", "slug": "application-support", "description": "Line-of-business software, SQL databases & ERP/CRM support", "lead_email": "vikram.rao@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
    {"name": "Service Desk", "slug": "service-desk", "description": "Tier 1 triage, user access onboarding & dispatch", "lead_email": "raj.malhotra@jacehaus.com", "business_hours_start": "08:00", "business_hours_end": "18:00", "timezone": "America/New_York", "work_days": "MON,TUE,WED,THU,FRI", "is_active": True},
]

SEED_TECHNICIANS = [
    # M365 Support
    {"name": "Rahul Sharma", "email": "rahul.sharma@jacehaus.com", "team": "M365 Support", "is_active": True},
    {"name": "Priya Mehta", "email": "priya.mehta@jacehaus.com", "team": "M365 Support", "is_active": True},
    # Network Team
    {"name": "Arjun Patel", "email": "arjun.patel@jacehaus.com", "team": "Network Team", "is_active": True},
    {"name": "Rohan Desai", "email": "rohan.desai@jacehaus.com", "team": "Network Team", "is_active": True},
    # Security Team
    {"name": "Aditya Singh", "email": "aditya.singh@jacehaus.com", "team": "Security Team", "is_active": True},
    {"name": "Neha Kapoor", "email": "neha.kapoor@jacehaus.com", "team": "Security Team", "is_active": True},
    # Endpoint Team
    {"name": "Karan Shah", "email": "karan.shah@jacehaus.com", "team": "Endpoint Team", "is_active": True},
    {"name": "Sneha Joshi", "email": "sneha.joshi@jacehaus.com", "team": "Endpoint Team", "is_active": True},
    # Backup Team
    {"name": "Amit Verma", "email": "amit.verma@jacehaus.com", "team": "Backup Team", "is_active": True},
    {"name": "Pooja Nair", "email": "pooja.nair@jacehaus.com", "team": "Backup Team", "is_active": True},
    # Application Support
    {"name": "Vikram Rao", "email": "vikram.rao@jacehaus.com", "team": "Application Support", "is_active": True},
    {"name": "Ananya Iyer", "email": "ananya.iyer@jacehaus.com", "team": "Application Support", "is_active": True},
    # Service Desk
    {"name": "Raj Malhotra", "email": "raj.malhotra@jacehaus.com", "team": "Service Desk", "is_active": True},
    {"name": "Simran Kaur", "email": "simran.kaur@jacehaus.com", "team": "Service Desk", "is_active": True},
]

# Development seed users (Development & Testing only)
SEED_USERS = [
    {
        "name": "Jace Admin",
        "email": "admin@jacehaus.com",
        "password": "Admin@123",
        "role": "admin",
        "tech_email": None,
        "cust_email": None
    },
    {
        "name": "Sarah Manager",
        "email": "manager@jacehaus.com",
        "password": "Manager@123",
        "role": "manager",
        "tech_email": None,
        "cust_email": None
    },
    # Technicians
    {
        "name": "Rahul Sharma",
        "email": "rahul.sharma@jacehaus.com",
        "password": "Tech@123",
        "role": "technician",
        "tech_email": "rahul.sharma@jacehaus.com",
        "cust_email": None
    },
    {
        "name": "Arjun Patel",
        "email": "arjun.patel@jacehaus.com",
        "password": "Tech@123",
        "role": "technician",
        "tech_email": "arjun.patel@jacehaus.com",
        "cust_email": None
    },
    {
        "name": "Aditya Singh",
        "email": "aditya.singh@jacehaus.com",
        "password": "Tech@123",
        "role": "technician",
        "tech_email": "aditya.singh@jacehaus.com",
        "cust_email": None
    },
    # Customers
    {
        "name": "John Doe",
        "email": "john.doe@acme.com",
        "password": "Client@123",
        "role": "customer",
        "tech_email": None,
        "cust_email": "john.doe@acme.com"
    },
    {
        "name": "Sarah Jenkins",
        "email": "sarah.j@globex.com",
        "password": "Client@123",
        "role": "customer",
        "tech_email": None,
        "cust_email": "sarah.j@globex.com"
    },
    {
        "name": "Tony Stark",
        "email": "tony@starkindustries.com",
        "password": "Client@123",
        "role": "customer",
        "tech_email": None,
        "cust_email": "tony@starkindustries.com"
    },
    {
        "name": "Bruce Wayne",
        "email": "bruce@wayneenterprises.com",
        "password": "Client@123",
        "role": "customer",
        "tech_email": None,
        "cust_email": "bruce@wayneenterprises.com"
    }
]

def run_db_migrations():
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS customers (id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) UNIQUE NOT NULL, company VARCHAR(150) NOT NULL, phone VARCHAR(50), is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS technicians (id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) UNIQUE NOT NULL, team VARCHAR(100) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS teams (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, slug VARCHAR(100) UNIQUE NOT NULL, description TEXT, team_lead_id INTEGER REFERENCES technicians(id) ON DELETE SET NULL, business_hours_start VARCHAR(10) DEFAULT '08:00', business_hours_end VARCHAR(10) DEFAULT '18:00', timezone VARCHAR(50) DEFAULT 'America/New_York', work_days VARCHAR(50) DEFAULT 'MON,TUE,WED,THU,FRI', is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(50) NOT NULL, technician_id INTEGER REFERENCES technicians(id) ON DELETE SET NULL, customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("ALTER TABLE technicians ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE routing_rules ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assigned_team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS response_due_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_due_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS responded_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS sla_status VARCHAR(50);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_summary VARCHAR(255);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_details TEXT;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assigned_technician_id INTEGER REFERENCES technicians(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assigned_technician VARCHAR(100);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalation_level INTEGER DEFAULT 1;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalation_reason TEXT;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS escalated_by VARCHAR(100);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL;"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_email VARCHAR(150);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_company VARCHAR(150);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'portal';"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS email_message_id VARCHAR(255);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS email_conversation_id VARCHAR(255);"))
            conn.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS email_sender VARCHAR(150);"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, ticket_id INTEGER, type VARCHAR(50) NOT NULL, severity VARCHAR(20) NOT NULL, title VARCHAR(255) NOT NULL, message TEXT NOT NULL, is_read BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS ticket_notes (id SERIAL PRIMARY KEY, ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE, note_type VARCHAR(50) NOT NULL DEFAULT 'internal', content TEXT NOT NULL, author VARCHAR(100) NOT NULL DEFAULT 'Technician', created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS csat_ratings (id SERIAL PRIMARY KEY, ticket_id INTEGER NOT NULL UNIQUE REFERENCES tickets(id) ON DELETE CASCADE, customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE, rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5), feedback TEXT, submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_csat_ratings_ticket_id ON csat_ratings (ticket_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_csat_ratings_customer_id ON csat_ratings (customer_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_csat_ratings_rating ON csat_ratings (rating);"))

            # Phase 9: Knowledge Base Tables & Indexes
            conn.execute(text("CREATE TABLE IF NOT EXISTS kb_categories (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE NOT NULL, slug VARCHAR(100) UNIQUE NOT NULL, description TEXT, icon VARCHAR(50) DEFAULT 'book', display_order INTEGER NOT NULL DEFAULT 0, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS kb_articles (id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, slug VARCHAR(255) UNIQUE NOT NULL, summary TEXT, content TEXT NOT NULL, category_id INTEGER REFERENCES kb_categories(id) ON DELETE SET NULL, category_name VARCHAR(100), visibility VARCHAR(20) NOT NULL DEFAULT 'public', status VARCHAR(20) NOT NULL DEFAULT 'published', author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, author_name VARCHAR(100), team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL, team_name VARCHAR(100), tags TEXT, view_count INTEGER NOT NULL DEFAULT 0, helpful_count INTEGER NOT NULL DEFAULT 0, not_helpful_count INTEGER NOT NULL DEFAULT 0, current_version INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(), updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS kb_article_versions (id SERIAL PRIMARY KEY, article_id INTEGER NOT NULL REFERENCES kb_articles(id) ON DELETE CASCADE, version_number INTEGER NOT NULL, title VARCHAR(255) NOT NULL, content TEXT NOT NULL, summary TEXT, change_summary VARCHAR(255), edited_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL, edited_by_name VARCHAR(100), created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS kb_article_feedback (id SERIAL PRIMARY KEY, article_id INTEGER NOT NULL REFERENCES kb_articles(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL, customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL, is_helpful BOOLEAN NOT NULL, comment TEXT, session_id VARCHAR(100), created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW());"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_categories_slug ON kb_categories (slug);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_articles_slug ON kb_articles (slug);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_articles_category_id ON kb_articles (category_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_articles_visibility ON kb_articles (visibility);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_articles_status ON kb_articles (status);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_article_versions_article_id ON kb_article_versions (article_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_kb_article_feedback_article_id ON kb_article_feedback (article_id);"))
            conn.commit()

            # Seed customers
            for cust in SEED_CUSTOMERS:
                conn.execute(
                    text(
                        "INSERT INTO customers (name, email, company, phone, is_active) "
                        "VALUES (:name, :email, :company, :phone, TRUE) "
                        "ON CONFLICT (email) DO NOTHING;"
                    ),
                    cust
                )

            # Seed technicians
            for tech in SEED_TECHNICIANS:
                conn.execute(
                    text(
                        "INSERT INTO technicians (name, email, team, is_active) "
                        "VALUES (:name, :email, :team, :is_active) "
                        "ON CONFLICT (email) DO UPDATE SET team = EXCLUDED.team, is_active = EXCLUDED.is_active;"
                    ),
                    tech
                )

            # Seed teams
            for t in SEED_TEAMS:
                lead_id = None
                if t["lead_email"]:
                    row = conn.execute(text("SELECT id FROM technicians WHERE email = :email"), {"email": t["lead_email"]}).fetchone()
                    if row:
                        lead_id = row[0]
                conn.execute(
                    text(
                        "INSERT INTO teams (name, slug, description, team_lead_id, business_hours_start, business_hours_end, timezone, work_days, is_active) "
                        "VALUES (:name, :slug, :description, :team_lead_id, :business_hours_start, :business_hours_end, :timezone, :work_days, :is_active) "
                        "ON CONFLICT (name) DO NOTHING;"
                    ),
                    {
                        "name": t["name"],
                        "slug": t["slug"],
                        "description": t["description"],
                        "team_lead_id": lead_id,
                        "business_hours_start": t["business_hours_start"],
                        "business_hours_end": t["business_hours_end"],
                        "timezone": t["timezone"],
                        "work_days": t["work_days"],
                        "is_active": t["is_active"]
                    }
                )

            # Link existing technicians, routing rules, and tickets to their corresponding team_id
            conn.execute(text("UPDATE technicians SET team_id = (SELECT id FROM teams WHERE teams.name = technicians.team) WHERE team_id IS NULL;"))
            conn.execute(text("UPDATE routing_rules SET team_id = (SELECT id FROM teams WHERE teams.name = routing_rules.team) WHERE team_id IS NULL;"))
            conn.execute(text("UPDATE tickets SET assigned_team_id = (SELECT id FROM teams WHERE teams.name = tickets.assigned_team) WHERE assigned_team_id IS NULL AND assigned_team IS NOT NULL;"))

            # Seed users
            for u in SEED_USERS:
                tech_id = None
                if u["tech_email"]:
                    row = conn.execute(text("SELECT id FROM technicians WHERE email = :email"), {"email": u["tech_email"]}).fetchone()
                    if row:
                        tech_id = row[0]

                cust_id = None
                if u["cust_email"]:
                    row = conn.execute(text("SELECT id FROM customers WHERE email = :email"), {"email": u["cust_email"]}).fetchone()
                    if row:
                        cust_id = row[0]

                p_hash = hash_password(u["password"])
                conn.execute(
                    text(
                        "INSERT INTO users (name, email, password_hash, role, technician_id, customer_id, is_active) "
                        "VALUES (:name, :email, :password_hash, :role, :technician_id, :customer_id, TRUE) "
                        "ON CONFLICT (email) DO NOTHING;"
                    ),
                    {
                        "name": u["name"],
                        "email": u["email"],
                        "password_hash": p_hash,
                        "role": u["role"],
                        "technician_id": tech_id,
                        "customer_id": cust_id
                    }
                )

            # Seed Knowledge Base Categories
            seed_kb_cats = [
                {"name": "Microsoft 365 & Cloud Services", "slug": "m365-cloud", "description": "Guides for Outlook, Teams, OneDrive, SharePoint, and Exchange Online.", "icon": "cloud", "display_order": 1},
                {"name": "Network & Secure VPN", "slug": "network-vpn", "description": "Connecting to office Wi-Fi, GlobalProtect, IPsec VPN tunnels, and home router checks.", "icon": "network", "display_order": 2},
                {"name": "Security & Multi-Factor Auth", "slug": "security-mfa", "description": "Microsoft Authenticator, password resets, phishing safety, and device compliance.", "icon": "shield", "display_order": 3},
                {"name": "Workstations & Hardware", "slug": "workstations-hardware", "description": "Windows 11/MacOS setup, dual monitors, printing, docking stations, and peripherals.", "icon": "laptop", "display_order": 4},
                {"name": "Backup & Disaster Recovery", "slug": "backup-recovery", "description": "File retention policies, cloud backups, and requesting historical document restores.", "icon": "database", "display_order": 5},
                {"name": "Internal SOPs & Runbooks", "slug": "internal-sops", "description": "Tier 2/3 engineering troubleshooting procedures, firewall failover, and incident containment.", "icon": "lock", "display_order": 6},
            ]
            for cat in seed_kb_cats:
                conn.execute(
                    text(
                        "INSERT INTO kb_categories (name, slug, description, icon, display_order, is_active) "
                        "VALUES (:name, :slug, :description, :icon, :display_order, TRUE) "
                        "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, icon = EXCLUDED.icon, display_order = EXCLUDED.display_order;"
                    ),
                    cat
                )

            # Seed Knowledge Base Articles
            seed_kb_arts = [
                {
                    "title": "How to Set Up Multi-Factor Authentication (MFA) via Microsoft Authenticator",
                    "slug": "setup-mfa-microsoft-authenticator",
                    "cat_slug": "security-mfa",
                    "visibility": "public",
                    "status": "published",
                    "summary": "Step-by-step instructions for registering your smartphone with Microsoft Authenticator for secure sign-in.",
                    "content": "# Setting Up Microsoft Authenticator (MFA)\n\nMulti-Factor Authentication (MFA) adds an essential layer of security to your organization's Microsoft 365 account.\n\n### Step 1: Install the App\n1. On your mobile phone, open the Apple App Store or Google Play Store.\n2. Search for and install **Microsoft Authenticator**.\n3. Open the app and tap **I Agree** to permissions.\n\n### Step 2: Initiate Setup from Your Computer\n1. On your computer browser, navigate to: https://aka.ms/mfasetup\n2. Sign in with your work email address and password.\n3. When prompted that *More information is required*, click **Next**.\n\n### Step 3: Scan the QR Code\n1. In the mobile app, tap the **+** (Add Account) icon and select **Work or school account**.\n2. Choose **Scan a QR code**.\n3. Point your phone camera at the QR code displayed on your monitor.\n\n### Step 4: Verify the Number Match\n1. Enter the 2-digit number shown on your computer screen into the prompt on your phone and tap **Approve**.",
                    "tags": "mfa, authenticator, security, password, 2fa, login, microsoft 365",
                    "team_name": "Security Team",
                    "helpful_count": 24,
                    "not_helpful_count": 1,
                    "view_count": 182
                },
                {
                    "title": "Troubleshooting GlobalProtect & Office IPsec VPN Connection Failures",
                    "slug": "troubleshooting-vpn-connection-failures",
                    "cat_slug": "network-vpn",
                    "visibility": "public",
                    "status": "published",
                    "summary": "Quick fixes for common VPN connection errors, portal gateway timeouts, and certificate renewal issues.",
                    "content": "# Troubleshooting Corporate VPN Connections\n\nIf you are experiencing issues connecting to the corporate network via GlobalProtect or IPsec VPN, follow these diagnostic steps.\n\n### Step 1: Verify Internet Connectivity\n1. Disconnect from the VPN client.\n2. Open a browser and verify you can load public websites (e.g. google.com).\n\n### Step 2: Refresh VPN Gateway Portal\n1. Open **GlobalProtect** in your system tray.\n2. Click the gear icon (**Settings**) -> **General** tab.\n3. Click **Refresh Connection**.\n4. Re-authenticate using your M365 credentials and MFA prompt.\n\n### Step 3: Clear DNS Cache\nOpen Command Prompt as Administrator and run:\n`ipconfig /flushdns`\n`ipconfig /renew`",
                    "tags": "vpn, globalprotect, network, connection, remote work, ipsec",
                    "team_name": "Network Team",
                    "helpful_count": 19,
                    "not_helpful_count": 2,
                    "view_count": 145
                },
                {
                    "title": "Outlook Desktop Email Synchronization and Profile Reset Steps",
                    "slug": "outlook-desktop-sync-and-profile-reset",
                    "cat_slug": "m365-cloud",
                    "visibility": "public",
                    "status": "published",
                    "summary": "How to resolve stuck outbox emails, missing calendar items, or corrupted Outlook OST data files.",
                    "content": "# Fixing Outlook Synchronization & Profile Issues\n\nWhen Microsoft Outlook displays *Disconnected* or fails to sync new emails:\n\n### Method 1: Check Online Mode via Webmail\nVerify webmail is working at https://outlook.office.com.\n\n### Method 2: Restart in Safe Mode\nPress `Win + R`, type `outlook.exe /safe` and press Enter.\n\n### Method 3: Rebuild Corrupted Outlook Data File (.OST)\n1. Close Outlook.\n2. Press `Win + R` and enter: `%localappdata%\\Microsoft\\Outlook`\n3. Rename `yourname@company.com.ost` to `...ost.old`.\n4. Restart Outlook to re-download a fresh copy from Exchange Online.",
                    "tags": "outlook, email, m365, exchange, sync, ost, calendar",
                    "team_name": "M365 Support",
                    "helpful_count": 31,
                    "not_helpful_count": 0,
                    "view_count": 210
                },
                {
                    "title": "Internal SOP: Cisco Firepower & Gateway Failover Diagnostic Procedure",
                    "slug": "internal-sop-cisco-firepower-failover",
                    "cat_slug": "internal-sops",
                    "visibility": "internal",
                    "status": "published",
                    "summary": "MSP Engineer Runbook for investigating high-availability (HA) firewall state desync and manual failover commands.",
                    "content": "# Internal Engineering Runbook: Firepower HA Failover\n\n**RESTRICTED — MSP INTERNAL ENGINEERING ACCESS ONLY**\n\n### Diagnostic CLI Commands\nConnect via Bastion Host SSH:\n`ssh admin@10.240.1.1`\n`show failover state`\n`show failover history`\n`show monitor-interface`\n\n### Manual Failover Procedure\nIf primary unit is degraded:\n`failover active`\n`show logging | grep -i failover`",
                    "tags": "sop, internal, cisco, firewall, firepower, failover, network team",
                    "team_name": "Network Team",
                    "helpful_count": 8,
                    "not_helpful_count": 0,
                    "view_count": 45
                }
            ]

            admin_user_row = conn.execute(text("SELECT id, name FROM users WHERE email = 'admin@jacehaus.com'")).fetchone()
            admin_uid = admin_user_row[0] if admin_user_row else None
            admin_uname = admin_user_row[1] if admin_user_row else "System Admin"

            for art in seed_kb_arts:
                cat_row = conn.execute(text("SELECT id, name FROM kb_categories WHERE slug = :slug"), {"slug": art["cat_slug"]}).fetchone()
                cat_id = cat_row[0] if cat_row else None
                cat_name = cat_row[1] if cat_row else "General"

                team_row = conn.execute(text("SELECT id FROM teams WHERE name = :tname"), {"tname": art["team_name"]}).fetchone()
                team_id = team_row[0] if team_row else None

                art_row = conn.execute(text("SELECT id FROM kb_articles WHERE slug = :slug"), {"slug": art["slug"]}).fetchone()
                if not art_row:
                    res = conn.execute(
                        text(
                            "INSERT INTO kb_articles (title, slug, summary, content, category_id, category_name, visibility, status, author_id, author_name, team_id, team_name, tags, view_count, helpful_count, not_helpful_count, current_version) "
                            "VALUES (:title, :slug, :summary, :content, :category_id, :category_name, :visibility, :status, :author_id, :author_name, :team_id, :team_name, :tags, :view_count, :helpful_count, :not_helpful_count, 1) "
                            "RETURNING id;"
                        ),
                        {
                            "title": art["title"],
                            "slug": art["slug"],
                            "summary": art["summary"],
                            "content": art["content"],
                            "category_id": cat_id,
                            "category_name": cat_name,
                            "visibility": art["visibility"],
                            "status": art["status"],
                            "author_id": admin_uid,
                            "author_name": admin_uname,
                            "team_id": team_id,
                            "team_name": art["team_name"],
                            "tags": art["tags"],
                            "view_count": art["view_count"],
                            "helpful_count": art["helpful_count"],
                            "not_helpful_count": art["not_helpful_count"]
                        }
                    )
                    new_art_id = res.fetchone()[0]
                    conn.execute(
                        text(
                            "INSERT INTO kb_article_versions (article_id, version_number, title, content, summary, change_summary, edited_by_id, edited_by_name) "
                            "VALUES (:aid, 1, :title, :content, :summary, 'Initial publication', :uid, :uname);"
                        ),
                        {
                            "aid": new_art_id,
                            "title": art["title"],
                            "content": art["content"],
                            "summary": art["summary"],
                            "uid": admin_uid,
                            "uname": admin_uname
                        }
                    )

            conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}")

run_db_migrations()


from contextlib import asynccontextmanager
from app.services.sla_worker import sla_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start autonomous background SLA worker
    try:
        sla_worker.start()
    except Exception as e:
        print(f"[Main] Warning: Failed to start SLA worker on startup: {e}")
    yield
    # Shutdown: Stop autonomous background SLA worker cleanly
    try:
        await sla_worker.stop()
    except Exception as e:
        print(f"[Main] Warning: Failed to stop SLA worker on shutdown: {e}")


app = FastAPI(
    title="Jace Haus Ticket Intelligence",
    version="1.0.0",
    lifespan=lifespan
)


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API routers
app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(technicians_router)
app.include_router(teams_router)
app.include_router(rules_router)
app.include_router(analytics.router)
app.include_router(notifications_router)
app.include_router(portal_router)
app.include_router(reports_router)
app.include_router(csat_router)
app.include_router(kb_router)

@app.get("/")
def root():
    return {
        "name": "Jace Haus Ticket Intelligence",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }