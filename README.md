# MassCommAI — AI-Powered Multilingual Public Awareness and Mass Communication Platform

[![Infosys Springboard](https://img.shields.io/badge/Infosys_Springboard-Virtual_Internship-blue.svg)](https://springboard.infosys.com/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_18_|_Vite_6-61DAFB.svg?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_16+-336791.svg?logo=postgresql)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Cache-Redis_7+-DC382D.svg?logo=redis)](https://redis.io)
[![Docker](https://img.shields.io/badge/Deployment-Docker_Compose-2496ED.svg?logo=docker)](https://www.docker.com)
[![Test Suite](https://img.shields.io/badge/Tests-522_Passing-success.svg)](backend/tests/)

---

## 1. Project Title
**MassCommAI** — An Enterprise-Grade AI-Powered Multilingual Public Awareness, Audience Segmentation, and Mass Communication Platform.

---

## 2. Professional Project Description
MassCommAI is a secure, full-stack, cloud-native communication and civic messaging platform developed for the **Infosys Springboard Virtual Internship**. Designed specifically for civic bodies, disaster management authorities, healthcare organizations, and government departments, MassCommAI unifies audience demographic segmentation, automated AI-driven multilingual content synthesis, editorial compliance auditing, multi-channel simulated and carrier-ready delivery, citizen feedback sentiment analysis, and executive analytics into a resilient, auditable communication engine.

---

## 3. Project Vision
To bridge critical communication divides across diverse linguistic and demographic populations by providing civic administrators with an intelligent, reliable, and privacy-preserving platform capable of composing, translating, auditing, and dispatching localized public awareness and emergency notices in seconds.

---

## 4. Problem Statement
Public administration agencies and civic organizations face major bottlenecks during critical mass communication:
- **Linguistic Fragmentation:** India encompasses 22 scheduled languages with hundreds of regional dialects. Manual translation of urgent advisories causes fatal delays and semantic errors.
- **Demographic Misalignment:** One-size-fits-all broadcasts fail to engage vulnerable populations (e.g., senior citizens, rural agricultural workers, or students) who require distinct tone, context, and channel preferences.
- **Accidental PII Exposure:** Broadcast systems frequently leak citizen phone numbers, email addresses, and personal identities in dashboards, logs, and API responses.
- **Compliance & Panic Risks:** Poorly worded public health or disaster advisories can induce public panic or omit mandatory verified emergency helplines.
- **Unreliable Delivery Queues:** Distributed broadcast workers without robust lease fencing or atomic locks cause duplicate message bursts or drop jobs during worker failovers.
- **Channel Delivery Silos:** Lack of automated cross-channel fallback leaves citizens uninformed when an initial delivery attempt fails.

---

## 5. Objectives
1. **Audience Segmentation:** Provide dynamic AST-driven filtering of citizens based on age, location, occupation, language, and tri-state consent.
2. **AI Multilingual Engine:** Automate channel-constrained message generation and high-fidelity translation across major Indian languages with 100% placeholder retention.
3. **Editorial Compliance:** Enforce automated heuristic and LLM-assisted quality audits that hard-block unverified or panic-inducing communications.
4. **Resilient Distribution Engine:** Orchestrate multichannel dispatch (Email, SMS, WhatsApp, Push, Web Broadcast) with multi-channel fallback, worker lease fencing, and exponential backoff retry.
5. **Civic Engagement & Sentiment Intelligence:** Capture delivery logs, email opens, link clicks, and citizen replies with hybrid model-based and lexicon sentiment analysis.
6. **Executive Analytics:** Deliver real-time KPIs, conversion funnels, language rankings, and CSV/PDF report exports for administrative oversight.
7. **Privacy by Design & Enterprise Hardening:** Enforce strict PII masking, log redaction, sliding-window rate limiting, and hierarchical Role-Based Access Control (RBAC).

---

## 6. Key Features
- **Dynamic Audience Segmentation:** Visual query builder supporting nested AND/OR logic across civic demographic fields.
- **Bulk Audience Ingestion:** Streaming CSV and Excel (.xlsx) parser with independent row-level validation and duplicate contact rejection.
- **Campaign State Machine:** Enforced lifecycles (`Draft` $\to$ `Scheduled` $\to$ `Active` $\to$ `Completed`/`Cancelled`) with priority guardrails (Emergency Alerts locked to `High`).
- **AI Content Studio & Pipeline Wizard:** 5-step guided wizard for generating channel-tailored drafts, translating across 10 Indian languages, and evaluating readability.
- **Panic & Compliance Gate:** Automated detection of panic-inducing terminology and strict enforcement of mandatory official emergency helplines (108, 112, etc.).
- **Multi-Channel Fallback & Retry:** Automatic cascade (`WhatsApp` $\to$ `SMS` $\to$ `Email`) with maximum 3 retry attempts and exponential backoff.
- **Bilingual UI Experience:** Seamless English / Hindi (`हिंदी`) UI localization toggle for public administration staff.
- **Delivery Tracking & Webhooks:** Tracking pixels for email opens, shortened URLs for click tracking, and bidirectional webhooks for provider status updates.
- **Citizen Sentiment Analysis:** LLM-powered and lexicon fallback sentiment scoring for citizen replies and public feedback.
- **Executive Analytics Dashboards:** Real-time KPI summary cards, interactive charts, audience segment performance, and automated AI improvement suggestions.
- **Docker Ready:** Turnkey 4-tier containerization (`db`, `redis`, `backend`, `frontend`) ready for production deployment.

---

## 7. Implemented Capabilities Overview

| Capability Area | Module / Router | Implementation State | Verification Method |
| :--- | :--- | :---: | :--- |
| **Authentication & RBAC** | `backend/app/routers/auth.py`, `admin_users.py` | **Complete** | Automated pytest suite (25 tests) |
| **Audience Management** | `backend/app/routers/audience.py` | **Complete** | Automated pytest suite (10 tests) |
| **Audience Segmentation** | `backend/app/routers/segments.py` | **Complete** | Automated pytest suite (16 tests) |
| **Template Library** | `backend/app/routers/templates.py` | **Complete** | Automated pytest suite (seeded 6 templates) |
| **Campaign Lifecycle & Clone** | `backend/app/routers/campaigns.py` | **Complete** | Automated pytest suite (36 tests) |
| **AI Content Studio & Wizard** | `backend/app/routers/content.py`, `campaigns.py` | **Complete** | Automated pytest suite (32 tests) |
| **Quality & Compliance Engine**| `backend/app/routers/content_quality.py` | **Complete** | Automated pytest suite (19 tests) |
| **Email & SMS Channel Engine** | `backend/app/services/channels/email.py`, `sms.py`| **Complete** | Automated pytest suite (45 tests) |
| **WhatsApp, Push & Broadcast** | `backend/app/services/channels/` | **Complete** | Automated pytest suite (52 tests) |
| **Scheduling, Retry & Automation**| `backend/app/services/scheduling_service.py` | **Complete** | Automated pytest suite (48 tests) |
| **Engagement & Sentiment** | `backend/app/routers/feedback.py`, `sentiment_service.py`| **Complete**| Automated pytest suite (42 tests) |
| **Analytics Dashboards** | `backend/app/routers/analytics.py` | **Complete** | Automated pytest suite (38 tests) |
| **Security Hardening & E2E** | `backend/app/core/rate_limiter.py`, `logging_config.py`| **Complete**| Automated pytest suite (7 tests) |

---

## 8. Milestone Completion Status

```text
Milestone 1: Audience & Campaign Planning    [====================] 100% (Complete & Accepted)
Milestone 2: AI Content & Multilingual Engine[====================] 100% (Complete & Accepted)
Milestone 3: Channels, Analytics & Hardening [====================] 100% (Complete & Finalized)
Total Platform Readiness                     [====================] 100% (Production Ready)
```

- **Milestone 1 (Tasks 1–6):** Ingestion, AST Segmentation, Campaign Management, Template Engine.
- **Milestone 2 (Tasks 7–12):** Multilingual AI Generation, Placeholder Protection, Quality Auditing, Content Pipeline Wizard.
- **Milestone 3 (Tasks 13–18):** Multichannel Delivery, Fallbacks & Retries, Sentiment Analysis, Executive Analytics, Security Hardening, Containerization & Final Verification.

---

## 9. Technology Stack

### Backend
- **Language & Runtime:** Python 3.13.14 (via pyenv)
- **Web Framework:** FastAPI 0.115.6 with ASGI lifespan
- **Data Validation:** Pydantic v2 (2.10.4)
- **Database ORM:** SQLAlchemy 2.0.36
- **Database Driver:** Psycopg 3 (3.2.3)
- **Migrations:** Alembic 1.14.0 (8 linear migrations up to `b9c3d1e2f4a5`)
- **Caching & Rate Limiting:** Redis 7.2 with Py-Redis 5.2.1
- **Scheduling:** APScheduler 3.10.4 / BackgroundTasks
- **Security & Cryptography:** PyJWT 2.10.1, Passlib 1.7.4, Bcrypt 4.2.1
- **Testing:** Pytest 8.3.4, Pytest-Asyncio 0.25.0 (522 passing tests)

### Frontend
- **Framework & Runtime:** React 18.3.1, Node.js v20.x/v22.x, npm 10.x
- **Bundler:** Vite 6.0.3 with `manualChunks` vendor code splitting (<165 kB per chunk)
- **Routing:** React Router DOM 6.28.0 (with `React.lazy` and `Suspense`)
- **Styling:** Tailwind CSS 3.4.16, PostCSS 8.4.49, Autoprefixer 10.4.20
- **HTTP Client:** Axios 1.7.9 (with auth and error interceptors)
- **Icons:** Lucide React 0.468.0
- **Localization:** Bilingual UI Context (`en` English / `hi` Hindi)

### Database & Deployment
- **RDBMS:** PostgreSQL 16.15 (18 relational tables, composite B-tree indexes)
- **Caching:** Redis 7-alpine
- **Containerization:** Docker multi-stage images & Docker Compose
- **Web Server:** NGINX 1.25 Alpine (frontend static server and SPA reverse proxy)
- **AI Models:** Google Gemini 2.5 Flash via `@google/genai` (with offline `MockAIProvider` fallback)

---

## 10. System Architecture Diagram

```mermaid
flowchart TD
    subgraph Client["Frontend Client (React 18 + Vite 6)"]
        UI_Camp["Campaign Wizard & Detail"]
        UI_Aud["Audience & Segment Studio"]
        UI_Cont["Content Studio & Quality Audit"]
        UI_Dist["Multichannel Distribution"]
        UI_Dash["Executive Analytics Dashboard"]
        UI_Feed["Feedback & Sentiment Monitor"]
    end

    subgraph Security["Security & Perimeter Hardening"]
        RateLimit["Sliding-Window Rate Limiter (Redis/Memory)"]
        AuthM["JWT & RBAC Middleware"]
        CORSVal["Production CORS Origin Validator"]
        PIIScrub["PIIRedactingFilter (Logs & Responses)"]
        ErrSan["Global 500 Exception Sanitizer"]
    end

    subgraph API["FastAPI Application (Port 8000)"]
        R_Auth["/auth & /admin/users"]
        R_Aud["/audience & /segments"]
        R_Camp["/campaigns & /templates"]
        R_Cont["/content & /content/quality"]
        R_Send["/campaigns/{id}/send"]
        R_Track["/track/open & /track/click"]
        R_Hook["/webhooks/whatsapp & /webhooks/sms"]
        R_Feed["/feedback"]
        R_Anly["/analytics"]
    end

    subgraph CoreServices["Domain Services & Engine"]
        AudSvc["Audience & Segment Engine"]
        CampSvc["Campaign State Machine"]
        AISvc["AI Provider Factory (Gemini / Mock)"]
        QualSvc["Content Quality Heuristic Engine"]
        DistSvc["Multichannel Dispatch & Fallback"]
        SchedSvc["Scheduling & Retry Service"]
        SentSvc["Hybrid Sentiment Service (LLM / Lexicon)"]
    end

    subgraph Storage["Data & Cache Persistence"]
        DB[("PostgreSQL 16\n(18 Tables, B-Tree Indexes)")]
        RedisDB[("Redis 7\n(Rate Limiting & Queues)")]
    end

    Client --> Security
    Security --> API
    API --> CoreServices
    CoreServices --> Storage
    CoreServices --> SimulatedGateways["Simulated Gateways\n(Email, SMS, WhatsApp, Push, Broadcast)"]
```

---

## 11. Database Schema

The database schema consists of **18 relational tables** with **104 indexes** hosted on PostgreSQL 16:
- **Core Entities:** `roles`, `users`
- **Audience & Targeting:** `audience_members`, `segments`, `campaign_segments`
- **Campaigns & Templates:** `campaigns`, `templates`, `content_pipeline_runs`
- **Content & Quality:** `content_assets`, `content_variants`, `content_quality_assessments`, `content_quality_findings`, `compliance_rules`
- **Distribution & Delivery:** `messages`, `delivery_logs`, `tracked_links`, `engagement_events`, `feedback`
- **Migrations:** Managed via Alembic (`b9c3d1e2f4a5 (head)`)

---

## 12. API Documentation

Interactive Swagger/OpenAPI documentation is generated automatically by FastAPI:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema:** `http://127.0.0.1:8000/openapi.json`

### Summary of Registered Endpoints (85+ Routes)
- **Core / Health (3):** `GET /`, `GET /health`, `GET /healthz`
- **Authentication & Governance (6):** `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `GET /admin/users`, `PUT /admin/users/{id}/role`, `PATCH /admin/users/{id}/status`
- **Audience Management (7):** `GET /audience`, `POST /audience`, `POST /audience/import`, `GET /audience/stats`, `GET /audience/{id}`, `PUT /audience/{id}`, `DELETE /audience/{id}`
- **Audience Segmentation (8):** `GET /segments`, `POST /segments`, `GET /segments/fields`, `POST /segments/preview`, `GET /segments/{id}`, `PUT /segments/{id}`, `DELETE /segments/{id}`, `GET /segments/{id}/preview`
- **Templates (6):** `GET /templates`, `POST /templates`, `GET /templates/categories`, `GET /templates/{id}`, `PUT /templates/{id}`, `DELETE /templates/{id}`
- **Campaigns (12):** `GET /campaigns`, `POST /campaigns`, `GET /campaigns/meta`, `GET /campaigns/{id}`, `PUT /campaigns/{id}`, `DELETE /campaigns/{id}`, `POST /campaigns/{id}/clone`, `POST /campaigns/{id}/preview`, `PATCH /campaigns/{id}/status`, `POST /campaigns/{id}/send`, `POST /campaigns/{id}/schedule`, `POST /campaigns/{id}/content/pipeline`
- **Content Studio & Quality (15):** `GET /content`, `POST /content`, `POST /content/generate`, `POST /content/manual`, `GET /content/{id}`, `PUT /content/{id}`, `DELETE /content/{id}`, `POST /content/{id}/translate`, `POST /content/{id}/personalize`, `POST /content/{id}/evaluate`, `PATCH /content/{id}/review`, `GET /content/{id}/quality`, `GET /content/{id}/variants`, `GET /content/channels`, `GET /content/languages`
- **Engagement & Webhooks (12):** `GET /track/open/{message_id}`, `GET /track/click/{token}`, `POST /webhooks/whatsapp`, `POST /webhooks/sms`, `POST /feedback/submit`, `GET /feedback/campaign/{campaign_id}`, `GET /feedback/analysis`
- **Analytics & Dashboards (10):** `GET /analytics/kpis`, `GET /analytics/campaigns`, `GET /analytics/campaigns/{id}`, `GET /analytics/channels`, `GET /analytics/languages`, `GET /analytics/segments`, `GET /analytics/funnel`, `GET /analytics/insights`, `GET /analytics/export/csv`, `GET /analytics/export/pdf`

---

## 13. Installation Prerequisites

Before running MassCommAI, ensure your host has the following runtimes installed:
- **Python:** `3.13.x` (recommended via `pyenv`)
- **Node.js & npm:** `Node.js >= 20.x` and `npm >= 10.x`
- **PostgreSQL Server:** `PostgreSQL >= 14` (running locally on port `5432`)
- **Redis Server:** `Redis >= 7` (e.g. Redis 8.x via Homebrew on macOS)
  ```bash
  brew install redis
  brew services start redis
  redis-cli ping  # Returns PONG
  ```
  *(Note: An in-memory sliding-window limiter fallback activates automatically if Redis is unavailable, but Redis is required for shared multi-worker rate limiting).*
- **Docker & Docker Compose:** *(Optional, for containerized execution)*

---

## 14. Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/hariprasathc/MassCommAI.git
cd MassCommAI
```

### 2. Configure Backend Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Frontend Dependencies
```bash
cd ../frontend
npm install
```

---

## 15. Environment Configuration

### Backend Configuration (`backend/.env`)
Copy the template:
```bash
cp backend/.env.example backend/.env
```
Key configuration settings:
```ini
PROJECT_NAME="MassCommAI"
VERSION="1.0.0"
APP_ENV="development"
DEBUG=true

# Database Connection
DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/masscommai_dev"

# Redis Cache & Rate Limiting (Leave empty to use in-memory sliding window)
REDIS_URL="redis://127.0.0.1:6379/0"
RATE_LIMIT_ENABLED=true
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_AI_PER_MINUTE=20

# JWT Security
SECRET_KEY="replace-with-a-secure-random-secret-key-at-least-32-chars-long"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Allowed CORS Origins
CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173,http://localhost:3000"

# AI Provider Settings (auto, gemini, or mock)
AI_PROVIDER="auto"
AI_MODEL_NAME="gemini-2.5-flash"
GEMINI_API_KEY=""
```

### Frontend Configuration (`frontend/.env`)
```bash
cp frontend/.env.example frontend/.env
```
Ensure it points to your backend instance:
```ini
VITE_API_BASE_URL="http://127.0.0.1:8000"
```

---

## 16. Database Setup, Migrations & Demo Seed

### 1. Create PostgreSQL Database
```bash
psql -U postgres -c "CREATE DATABASE masscommai_dev;"
```

### 2. Run Alembic Migrations
```bash
cd backend
alembic upgrade head
```
*Applies all 8 linear migrations up to `b9c3d1e2f4a5`.*

### 3. Seed Repeatable Demo Dataset
MassCommAI provides an idempotent, zero-duplicate demo seeding script that populates all tables with realistic civic data:
```bash
cd backend
python -m app.db.seed_demo
```
This seeds:
- **3 Demo Users** across all hierarchical roles.
- **5 Configured Channels** (Email, SMS, WhatsApp, Web Push, Web Broadcast).
- **6 Emergency Templates** (Cyclone, Heatwave, Vaccine, Dengue, Flood, Election).
- **10 Diverse Citizens** spanning 6 Indian languages (`en`, `hi`, `ta`, `te`, `bn`, `mr`) with verified consent.
- **3 Audience Segments** with dynamic rules.
- **3 Active/Completed Campaigns** with linked templates and content variants.
- **Delivery logs, tracked links, click events, and sentiment feedback.**

---

## 17. Demo User Credentials

| Role | Email Address | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@masscomm.gov.in` | `Admin@12345` | Unrestricted access, user governance, compliance rule configuration. |
| **Campaign Manager** | `manager@masscomm.gov.in` | `Manager@12345` | Audience segmentation, campaign creation, AI generation, approval, dispatch & analytics. |
| **Communication Team** | `team@masscomm.gov.in` | `Team@12345` | Content draft creation, translation, read-only analytics. |

---

## 18. Running the Application

### Quick Start with the Unified Startup Script (`start.sh`)

MassCommAI includes an end-to-end startup and orchestration script (`start.sh`) at the repository root that verifies dependencies, tests database connectivity, runs pending Alembic migrations, starts both FastAPI backend and Vite frontend servers, and monitors health in a single command:

```bash
# Start application with local PostgreSQL and Redis
./start.sh
```

#### Available Script Modes and Commands

| Command | Description |
| :--- | :--- |
| `./start.sh` | Normal local startup. Verifies environment, runs migrations, and launches backend & frontend using local PostgreSQL. |
| `./start.sh --docker` | Starts or reuses PostgreSQL and Redis via Docker Compose (`db` and `redis`), runs migrations, and launches application servers. |
| `./start.sh --status` | Non-destructive status inspection. Reports health and PIDs of Backend API, Frontend UI, PostgreSQL, Redis, and Alembic head. |
| `./start.sh --stop` | Gracefully terminates only the backend and frontend processes spawned by this script without altering database state. |
| `./start.sh --help` | Displays usage summary, flag descriptions, and log file paths. |

#### Process Management & Graceful Shutdown
- **Graceful Shutdown:** Press `Ctrl+C` in the terminal running `./start.sh` or run `./start.sh --stop` from another terminal. Both methods cleanly shut down backend and frontend processes while preserving PostgreSQL and Redis data.
- **Log Files:**
  - Backend API output: `logs/backend.log`
  - Frontend UI output: `logs/frontend.log`
- **Initial Demo Seed Data:**
  To populate initial demonstration users, templates, and civic campaigns:
  ```bash
  cd backend && python -m app.db.seed_demo
  ```

#### Redis Integration & Fallback Behavior
- **Redis-Backed Mode (Default & Verified):** When Redis is active (e.g. via `brew services start redis`), MassCommAI enforces distributed sliding-window rate limits via Redis sorted sets (`ZSET`). Rate limit counters are shared atomically across all worker processes and server instances.
- **In-Memory Fallback:** If `REDIS_URL` is unset or Redis becomes unreachable, the application automatically falls back to an internal thread-safe in-memory sliding-window limiter (`MemoryRateLimiter`).
- **Fallback Limitations:** The in-memory limiter is process-bound; each worker process maintains its own memory counters. In multi-worker or load-balanced environments, a running Redis service is required for coordinated distributed rate limiting.

---

### Manual Component Startup (Alternative)

If you prefer running services in separate terminal windows manually:

#### 1. Start the Backend API Server
From the `backend` directory with the virtual environment activated:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API server starts on `http://127.0.0.1:8000` (docs at `http://127.0.0.1:8000/docs`).

#### 2. Start the Frontend Development Server
From the `frontend` directory:
```bash
npm run dev
```
Vite development server starts on `http://127.0.0.1:5173`. Open in your browser and log in using any demo account.

---

## 19. Docker Execution (Production Ready)

MassCommAI provides a turnkey 4-container production topology via Docker Compose:

```bash
docker compose up --build -d
```

### Containers Started:
- **`masscommai-frontend`** (Port `3000`): Production NGINX server with Gzip, SPA rewrite fallback, and security headers.
- **`masscommai-backend`** (Port `8000`): FastAPI ASGI service running under non-root user `appuser` (UID 10001).
- **`masscommai-db`** (Port `5432`): PostgreSQL 16 with persistent volume `masscommai_pgdata`.
- **`masscommai-redis`** (Port `6379`): Redis 7-alpine with persistent volume `masscommai_redisdata`.

To verify health status:
```bash
docker compose ps
```

To stop containers:
```bash
docker compose down
```

---

## 20. Testing & Verification

### Run Full Backend Pytest Suite
From the root directory:
```bash
PYTHONPATH=backend pytest backend/tests -v
```
To run quietly with summary:
```bash
PYTHONPATH=backend pytest backend/tests -q
```
**Actual Verified Result: 522 passed in ~140 seconds.**

### Run Frontend Production Build
From the `frontend` directory:
```bash
npm run build
```
**Actual Verified Result: Built cleanly in 1.23 seconds with route code splitting (<165 kB chunks).**

---

## 21. Offline Mock Mode vs Live AI Providers

MassCommAI operates seamlessly in air-gapped or offline development environments:
- **Offline Mock Mode (Default):** When `AI_PROVIDER="mock"` or `GEMINI_API_KEY=""`, the platform automatically activates `MockAIProvider`. Content generation, translation, tone analysis, and sentiment scoring operate deterministically using heuristic rule engines and multilingual lexicons without transmitting external network requests.
- **Live Gemini Mode:** When `GEMINI_API_KEY` is configured in `backend/.env` and `AI_PROVIDER="auto"` or `"gemini"`, the platform connects to Google Gemini 2.5 Flash for generative multilingual copy and contextual sentiment classification.
- **Provider Integrity:** All automated test suites enforce offline mock providers, ensuring zero billable tokens or network dependencies during CI/CD.

---

## 22. Security Hardening & PII Governance

- **Sliding-Window Rate Limiting:** Enforces strict request throttles on authentication and AI generation endpoints to prevent credential stuffing and resource exhaustion.
- **PII Scrubbing:** Application logs automatically redact email addresses, phone numbers, JWT bearer tokens, and webhook signatures via `PIIRedactingFilter`.
- **Global Error Sanitization:** Prevents internal database connection strings or stack traces from leaking in production 500 error responses.
- **Strict Production CORS:** Validates origins against an explicit allowlist and rejects wildcard `*` origins in production and staging environments.
- **Hierarchical RBAC:** Route-level authorization guards verify user roles before granting access to sensitive mutation endpoints.

---

## 23. Documentation Index

- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md):** Comprehensive role-based user manual with UI workflows and step-by-step instructions.
- **[docs/DEMO_WALKTHROUGH_SCRIPT.md](docs/DEMO_WALKTHROUGH_SCRIPT.md):** Step-by-step presentation script covering all 7 demonstration acts.
- **[docs/FINAL_PRESENTATION_MATERIAL.md](docs/FINAL_PRESENTATION_MATERIAL.md):** Slide deck content covering architecture, problem statement, innovations, and roadmap.
- **[docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md):** Database relational schema and entity relationships.
- **[docs/FEATURE_INVENTORY.md](docs/FEATURE_INVENTORY.md):** Granular capability matrix across Milestones 1, 2, and 3.
- **[docs/MASSCOMMAI_FINAL_END_TO_END_ACCEPTANCE_REPORT.md](docs/MASSCOMMAI_FINAL_END_TO_END_ACCEPTANCE_REPORT.md):** Authoritative full-stack acceptance report verifying all 18 roadmap tasks, Redis, and multi-service workflows.
- **[docs/M3_TASK18_SYSTEM_FINALIZATION_COMPLETION_REPORT.md](docs/M3_TASK18_SYSTEM_FINALIZATION_COMPLETION_REPORT.md):** Final milestone engineering completion report.

---

## 24. License & Academic Attribution
Developed as an enterprise-grade academic deliverable under the **Infosys Springboard Virtual Internship** program.
© 2026 MassCommAI Engineering Team. All rights reserved.
