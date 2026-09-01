# JACE HAUS — MSP Ticket Intelligence Platform

An enterprise-grade, multi-tenant Managed Service Provider (MSP) Ticket Intelligence and Service Desk Operations platform built with **FastAPI**, **PostgreSQL**, and **React (Vite)**.

---

## 🚀 Key Capabilities (Phases 1–9 Complete)

1. **Multi-Tenant Customer Portal & Isolation**
   - Secure customer authentication with strict tenant-level data isolation.
   - Self-service ticket submission, real-time conversation timeline, and technician update tracking.

2. **Role-Based Access Control (RBAC)**
   - Strict hierarchical role authorization across **Admin**, **Manager**, **Technician**, and **Customer**.
   - Endpoint-level route security decorators and JWT session management.

3. **Intelligent Ticket Routing & Dispatch**
   - Keyword and category-based dynamic routing engine with priority weighting.
   - Automatic technician workload balancing and audit trail logging for all routing decisions.

4. **Autonomous SLA & Notification Background Worker**
   - Non-blocking background worker executing periodic scans for SLA response and resolution targets.
   - Proactive warnings for tickets approaching breach thresholds and automated notification generation.

5. **Scoped Notification Center & Real-Time Toast Alerts**
   - Role- and team-scoped notification filtering (all, unread, high-priority).
   - In-app toast alerts for immediate ticket assignments and critical SLA escalations.

6. **Executive & Client SLA Reporting Engine**
   - Interactive analytics dashboard with dynamic date range filtering (7d, 30d, 90d, 1y).
   - Automated PDF report generation (ReportLab) and CSV data exports.

7. **Dynamic Team Management**
   - Team lifecycle management, team lead assignments, and customizable business hours/timezone configs.

8. **Customer Satisfaction (CSAT) Rating System**
   - 1–5 star rating surveys and feedback capture triggered automatically on ticket resolution.
   - Aggregate CSAT metrics and technician leaderboard scoring.

9. **Knowledge Base & Self-Service Deflection Engine**
   - Versioned knowledge base articles with categorization, tag search, and helpfulness tracking.
   - Live ticket deflection recommendations during ticket creation to reduce inbound ticket volume.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy ORM, Uvicorn, ReportLab, Pydantic
- **Database**: PostgreSQL (compatible with AWS RDS / Cloud SQL)
- **Frontend**: React 18, Vite, Modern CSS (Glassmorphism & responsive design)
- **Authentication**: Signed JWT tokens, PBKDF2-HMAC-SHA256 password hashing

---

## 📦 Project Structure

```
jace-haus-ticket-intelligence/
├── backend/
│   ├── app/
│   │   ├── api/          # REST API endpoints (auth, tickets, teams, csat, kb, reports)
│   │   ├── core/         # Security, auth middlewares, password hashing
│   │   ├── models/       # SQLAlchemy database entities
│   │   ├── routes/       # Analytic routers
│   │   ├── rules/        # Rule-based routing engine
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # SLA worker, PDF/CSV exporters, notifications
│   │   ├── database.py   # Database session setup and connection pooling
│   │   └── main.py       # FastAPI application entrypoint & startup migrations
│   ├── tests/            # Automated test suite (163 unit and regression tests)
│   ├── requirements.txt  # Python package dependencies
│   ├── .env.example      # Sample environment configuration template
│   └── verify_*.py       # Independent operational verification scripts
├── frontend/
│   ├── src/
│   │   ├── App.jsx       # Single-page application logic and component views
│   │   ├── App.css       # Production styles and responsive layouts
│   │   └── main.jsx      # React entrypoint
│   ├── index.html        # HTML template
│   ├── package.json      # Node dependencies and scripts
│   └── vite.config.js    # Vite configuration
├── .gitignore            # Git exclusion rules
└── README.md             # Project documentation
```

---

## ⚙️ Getting Started

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm
- PostgreSQL running locally or accessible via network

---

### 1. Backend Setup

1. Open a terminal and navigate to `backend/`:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Create a `.env` file in the `backend/` folder based on `.env.example`:
   ```env
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/jace_haus
   JWT_SECRET_KEY=your-secure-random-jwt-secret-key-here
   JWT_ALGORITHM=HS256
   JWT_EXPIRATION_MINUTES=1440
   ```

5. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *The database tables and seed data will automatically be verified and initialized on startup.*
   - API Docs: `http://localhost:8000/docs`

---

### 2. Frontend Setup

1. Open a new terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   - Application URL: `http://localhost:5173`

---

## 🧪 Running Tests

The backend includes a comprehensive test suite covering RBAC, SLA workers, ticket routing, team management, CSAT, and Knowledge Base functionality.

From the `backend/` directory with the virtual environment active:

```bash
# Run all 160+ unit and regression tests
python -m unittest discover -s tests -p "test_*.py"

# Run specific test suites
python -m unittest tests/test_auth_rbac_suite.py
python -m unittest tests/test_sla_worker.py
python -m unittest tests/test_reporting.py
python -m unittest tests/test_teams.py
python -m unittest tests/test_csat.py
python -m unittest tests/test_kb.py
```

---

## 🏗️ Production Frontend Build

To build the frontend for production deployment:

```bash
cd frontend
npm run build
```

Production assets will be output to `frontend/dist/`.

---

## 👥 Default Demo Credentials (Development & Testing)

| Role | Email | Password | Scope / Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@jacehaus.com` | `Admin@123` | Full system access, routing rules, KB authoring, team management |
| **Manager** | `manager@jacehaus.com` | `Manager@123` | SLA reports, team analytics, ticket escalations |
| **Technician** | `rahul.sharma@jacehaus.com` | `Tech@123` | Technician workbench, ticket resolution, work notes |
| **Customer** | `john.doe@acme.com` | `Client@123` | Customer portal, ticket submission, KB self-service, CSAT reviews |

---

## 📄 License

Proprietary — JACE HAUS MSP Operations. All rights reserved.
