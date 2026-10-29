# MassCommAI — AI-Powered Multilingual Public Awareness and Mass Communication Platform

[![Infosys Springboard](https://img.shields.io/badge/Infosys_Springboard-Virtual_Internship-blue.svg)](https://springboard.infosys.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.142+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_18_|_Vite_6-61DAFB.svg?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_14+-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS_3.4-38B2AC.svg?logo=tailwind-css)](https://tailwindcss.com)

**MassCommAI** is an enterprise-grade public communication and awareness platform developed as part of the **Infosys Springboard Virtual Internship** (September–November 2026). The platform empowers government departments, educational institutions, healthcare agencies, and public organizations to design, translate, personalize, distribute, and analyze multilingual awareness campaigns across multiple Indian languages and communication channels (Email, SMS, WhatsApp, Web).

---

## 1. Milestone 1 Roadmap & Task Tracking

| Task | Module / Deliverable | Status | Description |
| :---: | :--- | :---: | :--- |
| **Task 1** | **Project Foundation, Database Design & Landing Page** | **COMPLETE** | Monorepo setup, PostgreSQL schema (9 entities + 1 associative), Alembic migrations, database-aware `/health` probe, modern SaaS landing page, Axios API client. |
| **Task 2** | **User Registration & Role Seeding** | **COMPLETE** | Default role seeding (`Admin`, `Campaign Manager`, `Communication Team`), `POST /auth/register` with bcrypt password hashing (72-byte safe), least-privilege enforcement, registration UI. |
| **Task 3** | **JWT Authentication & Role-Based Access Control** | **COMPLETE** | `POST /auth/login`, `GET /auth/me`, JWT bearer tokens, active status validation, admin user governance (`/admin/users`), self-protection & last-admin safeguards, role-gated React dashboard & admin panel. |
| **Task 4** | **Audience Database Management** | *Next* | Audience CRUD, deduplication, CSV bulk upload with row-by-row validation, language distribution stats. |
| **Task 5** | **Audience Segmentation Engine** | *Pending* | Dynamic JSON rule compiler (AND/OR), `POST /segments/preview`, visual segment builder UI. |
| **Task 6** | **Campaign Creation & Template Library** | *Pending* | 4-step campaign wizard, template content library with `{name}` placeholders, priority workflows. |

---

## 2. Architecture & Repository Structure

```text
MassCommAI/
├── .gitignore
├── .env.example              # Root environment template
├── README.md                 # Project documentation & execution guide
├── docs/
│   └── DATABASE_DESIGN.md    # Detailed ER diagram and schema specifications
├── backend/                  # FastAPI Application
│   ├── alembic/              # Database migration versioning
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0de49a2cf7ef_initial_schema_all_models.py
│   ├── alembic.ini
│   ├── requirements.txt      # Python dependencies (FastAPI, PyJWT, SQLAlchemy, etc.)
│   ├── .env.example          # Backend environment template
│   ├── .env                  # Local backend secrets (git-ignored)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI entrypoint, CORS, OpenAPI & Lifespan
│   │   ├── core/             # Pydantic Settings & security utilities
│   │   │   ├── __init__.py
│   │   │   ├── config.py     # Settings, JWT_ALGORITHM, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
│   │   │   ├── dependencies.py # get_current_user, get_current_active_user, require_role(...)
│   │   │   └── security.py   # bcrypt hashing & PyJWT token encoding/decoding
│   │   ├── db/               # Engine, Sessionmaker & Declarative Base
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── seed.py       # Idempotent role seeder & bootstrap admin helper
│   │   │   └── session.py
│   │   ├── models/           # SQLAlchemy 2.0 ORM Models
│   │   │   ├── __init__.py
│   │   │   ├── user.py       # Role & User
│   │   │   ├── audience.py   # AudienceMember
│   │   │   ├── segment.py    # Segment & campaign_segments
│   │   │   ├── campaign.py   # Campaign
│   │   │   ├── template.py   # Template
│   │   │   └── communication.py # Message, DeliveryLog, Feedback
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   │   ├── __init__.py
│   │   │   └── user.py       # Registration, Login, Token, RoleUpdate, StatusUpdate schemas
│   │   ├── routers/          # API Route handlers
│   │   │   ├── __init__.py
│   │   │   ├── health.py     # GET /health with live database probing
│   │   │   ├── auth.py       # POST /auth/register, POST /auth/login, GET /auth/me
│   │   │   └── admin_users.py # GET /admin/users, PUT /admin/users/{id}/role, PATCH /admin/users/{id}/status
│   │   └── services/         # Business logic layer
│   │       ├── __init__.py
│   │       └── auth_service.py # Authentication, hashing, user retrieval
│   └── tests/                # Automated regression test suite
│       ├── __init__.py
│       ├── test_auth_registration.py # Task 2 registration test suite (11 tests)
│       └── test_auth_jwt_rbac.py     # Task 3 JWT & RBAC test suite (12 tests)
└── frontend/                 # React SPA (Vite + Tailwind CSS)
    ├── package.json
    ├── vite.config.js
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── index.html
    ├── .env.example          # Frontend environment template
    ├── .env                  # Local frontend configuration (git-ignored)
    └── src/
        ├── main.jsx          # App bootstrap
        ├── App.jsx           # App router, AuthProvider & route guards
        ├── index.css         # Tailwind & theme tokens
        ├── context/
        │   └── AuthContext.jsx # Global JWT session state, login, logout, role helpers
        ├── components/
        │   ├── guards/
        │   │   ├── ProtectedRoute.jsx # Gated route for authenticated users
        │   │   └── AdminRoute.jsx     # Gated route strictly for Admins
        │   └── layout/
        │       ├── Navbar.jsx # Role-aware navigation with live backend connection badge
        │       └── Footer.jsx
        ├── pages/
        │   ├── LandingPage.jsx        # High-conversion SaaS landing page
        │   ├── RegisterPage.jsx       # Public user registration (Communication Team role)
        │   ├── auth/
        │   │   └── LoginPage.jsx      # SaaS login page with JWT handling
        │   ├── dashboard/
        │   │   └── DashboardPage.jsx  # Authenticated member dashboard shell
        │   └── admin/
        │       └── UserManagementPage.jsx # Admin user table, role assignment & account status
        └── services/
            ├── api.js          # Axios client with JWT request interceptor & 401 response handling
            ├── authService.js  # Auth API calls (register, login, me)
            └── adminService.js # Admin API calls (list users, update role, update status)
```

---

## 3. Technology Stack

- **Backend:** Python 3.12+ / 3.14, FastAPI, Uvicorn, PyJWT, Pydantic v2, `pydantic-settings`.
- **Database & ORM:** PostgreSQL 14+, SQLAlchemy 2.0+, Alembic, `psycopg` 3.x driver.
- **Frontend:** React 18, Vite 6, Tailwind CSS 3.4, React Router DOM 6, Axios, Lucide Icons.
- **Development Ports:**
  - Backend: `http://127.0.0.1:8000`
  - Frontend: `http://127.0.0.1:5173`

---

## 4. Security & Role-Based Access Control (RBAC)

### 4.1 Role Hierarchy & Permissions

| Role Name | Scope | Capabilities |
| :--- | :--- | :--- |
| **Admin** | Full system governance | Access user governance console, change user roles, activate/deactivate accounts, view all campaigns & audiences. |
| **Campaign Manager** | Campaign execution | Create & edit campaigns, design templates, define audience segments, schedule dispatches. |
| **Communication Team** | Content & distribution | Default role for public registration. Draft content, preview translations, monitor delivery statistics. |

### 4.2 Security Safeguards
- **Least-Privilege Registration:** All public registrations via `POST /auth/register` receive the `Communication Team` role. Client requests cannot override this role.
- **Bcrypt 72-Byte Boundary Safe:** Passwords are pre-validated to ensure `len(password.encode('utf-8')) <= 72`, preventing bcrypt's truncation vulnerability or unhandled exceptions.
- **Stateless Bearer JWT:** Signed using `HS256` with a configurable `SECRET_KEY` and expiration window (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Production Key Validation:** In `production` or `staging` environments, the backend startup validates that `SECRET_KEY` is not a default placeholder and has a cryptographic length of at least 32 characters, preventing insecure deployments.
- **Live Database Authorization:** Every authenticated API request (`get_current_user`) verifies current user status and role against the database, ensuring immediate revocation if an admin deactivates or demotes a user.
- **Self-Protection & Last-Admin Defense:** Admins cannot demote or deactivate their own account, and the system prevents deactivating or demoting the last remaining active Administrator.

### 4.3 Session Storage & Token Security Architecture
- **Bearer Token Storage:** The client application persists the JWT access token in browser `localStorage` under `masscomm_auth_token`. An Axios request interceptor attaches this token as `Authorization: Bearer <token>` on all outbound API requests.
- **Architectural Trade-offs & XSS Consideration:**
  - *Benefits:* Decoupled, stateless REST communication between the React Single Page Application (SPA) and FastAPI backend without cross-origin cookie domain issues or complex CORS credential synchronization.
  - *XSS Exposure:* Tokens stored in `localStorage` can be exposed if an application contains Cross-Site Scripting (XSS) vulnerabilities that execute arbitrary JavaScript in the user's browser context.
  - *Mitigations Implemented:*
    1. React's automatic context-aware JSX escaping protects against raw HTML markup injection.
    2. Strict Pydantic v2 input schemas on all backend endpoints sanitize and validate all payload inputs.
    3. Live database status validation (`get_current_user`) checks `is_active` on every request. Compromised tokens can be instantly invalidated by deactivating the account without waiting for token expiration.
    4. Configurable token expiration lifetimes (`ACCESS_TOKEN_EXPIRE_MINUTES`).
    5. Automatic session purging and `localStorage` clearance on any `401 Unauthorized` API response.

---

## 5. Quick Start Instructions

### Step 5.1: Database Preparation

Ensure PostgreSQL is running and create the development database:

```bash
# Connect to PostgreSQL and create the database
psql -U postgres -c "CREATE DATABASE masscommai_dev;"
```

### Step 5.2: Backend Setup

1. Open a terminal and navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a project-local Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install declared backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env to ensure your DATABASE_URL, SECRET_KEY, and CORS_ORIGINS match your environment
   ```

5. Run Alembic database migrations:
   ```bash
   alembic upgrade head
   ```

6. Seed default roles (idempotent, runs automatically on FastAPI startup as well):
   ```bash
   python -m app.db.seed
   ```

7. (Optional) Bootstrap an initial Administrator account securely:
   ```bash
   # Secure interactive bootstrap (prompts for email, full name, and password with hidden input):
   python -m app.db.seed --bootstrap-admin

   # Or in non-interactive CI/CD deployment via environment variables:
   ADMIN_BOOTSTRAP_EMAIL="admin@agency.gov.in" \
   ADMIN_BOOTSTRAP_PASSWORD="<choose-a-strong-secret-password>" \
   python -m app.db.seed --bootstrap-admin
   ```

8. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

### Step 5.3: Frontend Setup

1. Open a second terminal and navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

4. Start the Vite development server:
   ```bash
   npm run dev
   ```

5. Access the application in your browser at `http://127.0.0.1:5173`.

---

## 6. Endpoints & API Reference

| Method | Endpoint | Access Level | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Public | Live database probe (`SELECT 1`), returns 200 OK or 503 Service Unavailable |
| `POST` | `/auth/register` | Public | Register user account (defaults to `Communication Team` role) |
| `POST` | `/auth/login` | Public | Authenticate with email & password, returns JWT Bearer token |
| `GET` | `/auth/me` | Authenticated | Retrieve current user profile and role details |
| `GET` | `/admin/users` | Admin Only | Paginated list of users with search, role, and active-status filters |
| `PUT` | `/admin/users/{id}/role` | Admin Only | Assign new role (`Admin`, `Campaign Manager`, `Communication Team`) |
| `PATCH` | `/admin/users/{id}/status` | Admin Only | Activate or deactivate a user account |
| `GET` | `/docs` | Public | OpenAPI interactive Swagger documentation |
| `GET` | `/redoc` | Public | OpenAPI ReDoc specification |

---

## 7. Automated Testing

Run the full backend test suite covering Tasks 1, 2, and 3:

```bash
# From workspace root
PYTHONPATH=backend ./backend/.venv/bin/python -m unittest discover -s backend/tests
```

To run the frontend production build verification:

```bash
# From workspace root
cd frontend && npm run build
```

---

## 8. Troubleshooting Guide

- **Backend fails to connect to database:**
  Verify PostgreSQL is active using `pg_isready`. Ensure the `DATABASE_URL` in `backend/.env` uses the `postgresql+psycopg://` driver scheme.
- **CORS Error in Browser:**
  Ensure the origin `http://127.0.0.1:5173` is listed in `CORS_ORIGINS` in `backend/.env`.
- **Alembic migration conflicts:**
  Run `alembic current` and `alembic heads` inside the `backend` directory to inspect revision state.
- **JWT Signature / Expiry Issues:**
  Ensure `SECRET_KEY` in `backend/.env` matches between backend restarts and is kept confidential.
