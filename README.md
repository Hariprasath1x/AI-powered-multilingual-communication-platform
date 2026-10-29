# MassCommAI — AI-Powered Multilingual Public Awareness and Mass Communication Platform

[![Infosys Springboard](https://img.shields.io/badge/Infosys_Springboard-Virtual_Internship-blue.svg)](https://springboard.infosys.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.142+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_18_|_Vite_6-61DAFB.svg?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_14+-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS_3.4-38B2AC.svg?logo=tailwind-css)](https://tailwindcss.com)

**MassCommAI** is a full-stack, enterprise-grade public communication and awareness platform developed as part of the **Infosys Springboard Virtual Internship**. The platform empowers government departments, educational institutions, healthcare agencies, and public organizations to design, translate, personalize, distribute, and analyze multilingual awareness campaigns across multiple Indian languages and communication channels (Email, SMS, WhatsApp, Web).

---

## 1. Milestone 1 Roadmap & Task Tracking

| Task | Module / Deliverable | Status | Description |
| :---: | :--- | :---: | :--- |
| **Task 1** | **Project Foundation, Database Design & Landing Page** | **COMPLETE** | Monorepo setup, PostgreSQL schema, Alembic migrations, database-aware `/health` probe, modern SaaS landing page, Axios API client. |
| **Task 2** | **User Registration & Role Seeding** | *Next* | Default role seed, `POST /auth/register` with bcrypt password hashing, Pydantic validation, registration UI. |
| **Task 3** | **JWT Authentication & Role-Based Access Control** | *Pending* | `POST /auth/login`, `GET /auth/me`, `require_role(...)` guards, token expiry handling, role-gated dashboard shell. |
| **Task 4** | **Audience Database Management** | *Pending* | Audience CRUD, deduplication, CSV bulk upload with row-by-row validation, language distribution stats. |
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
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Backend environment template
│   ├── .env                  # Local backend secrets (git-ignored)
│   └── app/
│       ├── __init__.py
│       ├── main.py           # FastAPI entrypoint, CORS, OpenAPI & Lifespan
│       ├── core/             # Pydantic Settings & configuration
│       │   ├── __init__.py
│       │   └── config.py
│       ├── db/               # Engine, Sessionmaker & Declarative Base
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── session.py
│       ├── models/           # SQLAlchemy 2.0 ORM Models
│       │   ├── __init__.py
│       │   ├── user.py       # Role & User
│       │   ├── audience.py   # AudienceMember
│       │   ├── segment.py    # Segment & campaign_segments
│       │   ├── campaign.py   # Campaign
│       │   ├── template.py   # Template
│       │   └── communication.py # Message, DeliveryLog, Feedback
│       ├── routers/          # API Route handlers
│       │   ├── __init__.py
│       │   └── health.py     # GET /health with live database probing
│       └── services/         # Business logic layer
│           └── __init__.py
└── frontend/                 # React SPA (Vite)
    ├── package.json
    ├── vite.config.js
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── index.html
    ├── .env.example          # Frontend environment template
    ├── .env                  # Local frontend configuration (git-ignored)
    └── src/
        ├── main.jsx          # App bootstrap
        ├── App.jsx           # Router & layout provider
        ├── index.css         # Tailwind & theme tokens
        ├── components/
        │   └── layout/
        │       ├── Navbar.jsx # Header with live backend connection badge
        │       └── Footer.jsx
        ├── pages/
        │   ├── LandingPage.jsx     # High-conversion SaaS landing page
        │   └── PlaceholderAuth.jsx # Friendly placeholders for Tasks 2 & 3
        └── services/
            └── api.js        # Reusable Axios client with health diagnostics
```

---

## 3. Technology Stack

- **Backend:** Python 3.12+ / 3.14, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`.
- **Database & ORM:** PostgreSQL 14+, SQLAlchemy 2.0+, Alembic, `psycopg` 3.x driver.
- **Frontend:** React 18, Vite 6, Tailwind CSS 3.4, React Router DOM 6, Axios, Lucide Icons.
- **Development Ports:**
  - Backend: `http://127.0.0.1:8000`
  - Frontend: `http://127.0.0.1:5173`

---

## 4. Prerequisites

1. **Python 3.10+** (Python 3.14 is tested and verified).
2. **Node.js 18+** & **npm 9+** (Node v26 / npm 11 verified).
3. **PostgreSQL 14+** running locally or in Docker.

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
   # Edit .env to ensure your DATABASE_URL matches your local PostgreSQL credentials
   ```

5. Run Alembic database migrations:
   ```bash
   alembic upgrade head
   ```

6. Start the FastAPI development server:
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

## 6. Endpoints & Verification URLs

| Service | URL | Description |
| :--- | :--- | :--- |
| **Landing Page** | `http://127.0.0.1:5173` | Responsive React landing page with live backend health pill |
| **API Health Probe** | `http://127.0.0.1:8000/health` | Validates live DB connectivity (`SELECT 1`), returns 200 OK or 503 |
| **Interactive Docs (Swagger)** | `http://127.0.0.1:8000/docs` | OpenAPI interactive documentation |
| **Alternative Docs (ReDoc)** | `http://127.0.0.1:8000/redoc` | OpenAPI ReDoc specification |

---

## 7. Troubleshooting Guide

- **Backend fails to connect to database:**
  Verify PostgreSQL is active using `pg_isready`. Ensure the `DATABASE_URL` in `backend/.env` uses the `postgresql+psycopg://` driver scheme.
- **CORS Error in Browser:**
  Ensure the origin `http://127.0.0.1:5173` is listed in `CORS_ORIGINS` in `backend/.env`.
- **Alembic migration conflicts:**
  Run `alembic current` and `alembic heads` inside the `backend` directory to inspect revision state.

