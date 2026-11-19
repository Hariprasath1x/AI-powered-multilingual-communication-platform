# Civora — Live Demonstration Walkthrough Script
## Complete End-to-End Workflow & Presentation Guide (Milestones 1–3 Final Release)
### Powered by MassCommAI — Bringing communities closer.

- **Document Version:** 2.0.0
- **Release Date:** November 19, 2026
- **Architecture Lead:** MassCommAI Core Engineering Team
- **Product Identity:** Civora (Public Brand) | MassCommAI (Underlying Technical Engine)

---

## 1. Executive Demonstration Overview

**Civora** is an enterprise-grade, cloud-native communication and civic messaging platform built upon the **MassCommAI** technical architecture. Designed for government departments, disaster management authorities, healthcare organizations, and public administration agencies, Civora unites multi-channel civic broadcast delivery with generative AI and automated statutory safety guardrails.

This demonstration script provides an end-to-end walkthrough across three distinct institutional personas, showcasing dynamic audience segmentation, AI-driven multilingual content synthesis, automated compliance audits, resilient multi-channel simulated broadcast dispatch, citizen feedback with sentiment analysis, and executive analytics dashboards.

---

## 2. Default Demonstration Credentials

The platform includes an idempotent seeding utility (`python -m app.db.seed_demo`) that initializes three fully provisioned institutional personas:

| Institutional Role | Login Email | Password | Primary Capabilities |
| :--- | :--- | :--- | :--- |
| **System Administrator** | `admin@masscomm.gov.in` | `Admin@12345` | Global user governance, channel provider credentials (including FCM OAuth2), compliance rules, security policies |
| **Campaign Manager** | `manager@masscomm.gov.in` | `Manager@12345` | Audience segmentation, campaign creation, AI content synthesis, editorial approval, dispatch, analytics |
| **Communication Team** | `team@masscomm.gov.in` | `Team@12345` | Template browsing, audience inspection, delivery log tracking, citizen feedback resolution |

---

## 3. Preparation & Startup

### Step A: Verify Services
Ensure the local database and servers are active:
```bash
# 1. Verify PostgreSQL is running
pg_isready

# 2. Seed or reset the demonstration dataset
python -m app.db.seed_demo
```

### Step B: Start Backend and Frontend
Using the unified orchestrator:
```bash
./start.sh
```
Or manually in separate terminals:
```bash
# Terminal 1 (FastAPI Backend)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 (React/Vite Frontend)
npm --prefix frontend run dev
```
Open your browser at `http://127.0.0.1:5173`.

---

## 4. Phase-by-Phase Demonstration Walkthrough

### Act 1: Persona Login & Global Governance (Admin)
1. **Navigate to:** `http://127.0.0.1:5173/login`
2. **Action:** Log in with `admin@masscomm.gov.in` / `Admin@12345`.
3. **Showcase:**
   - **System Connectivity Pill:** Point out the top header green pill ("API & DB Connected").
   - **Bilingual Interface Switcher:** Click the header language switcher pill ("English" / "हिंदी") to demonstrate real-time localized labels.
   - **User Governance (`/admin/users`):** Highlight user role assignment and account activation controls.
   - **Channel Settings (`/admin/channels`):** Demonstrate administrative channel adapters for Email, SMS, WhatsApp, Web, and Push:
     - Point out the **Web Push (FCM)** configuration accepting Google Cloud Service Account JSON for secure HTTP v1 OAuth2 authentication.
     - Note role-restricted administrative access, private key masking (`••••••••`), and non-destructive connection testing.

---

### Act 2: Audience Ingestion & Dynamic Segmentation (Campaign Manager)
1. **Switch User:** Log out and log in as `manager@masscomm.gov.in` / `Manager@12345`.
2. **Navigate to:** **Audience Database** (`/audience`).
3. **Showcase:**
   - Highlight diverse citizen records across Indian states (Uttar Pradesh, Maharashtra, Tamil Nadu, Karnataka, Telangana, Delhi).
   - Point out tri-state consent indicators: Opt-in (Green), Opt-out (Red), Unconfirmed (Amber).
   - Point out strict PII masking on citizen phone numbers (`+919****4455`) and emails.
4. **Navigate to:** **Audience Segments** (`/segments`).
5. **Action:** Click **"New Segment"** or inspect the pre-seeded segment `"South India Senior Citizens"`.
6. **Showcase:**
   - Visual AST Query Builder combining nested conditions (`Age >= 60 AND State IN [Karnataka, Tamil Nadu]`).
   - Click **"Preview Segment Reach"** to verify real-time SQL execution without saving.

---

### Act 3: Campaign Planning & AI Content Synthesis (Campaign Manager)
1. **Navigate to:** **Campaign Studio** (`/campaigns`).
2. **Action:** Click **"New Campaign"** (`/campaigns/new`).
3. **Fill Form:**
   - Campaign Name: `Universal Pulse Polio & Immunization Drive`
   - Category: `Healthcare`
   - Objective: `Notify parents and guardians regarding universal polio drops at primary health centers.`
   - Priority: `High`
   - Channels: Select `SMS` and `WhatsApp`.
   - Linked Segment: Select `Healthcare Workers & Medical Personnel`.
4. **Save Draft:** Click **"Create Campaign"**.
5. **Open AI Content Studio (`/content`):**
   - Click **"Generate with AI"**.
   - Select Tone: `Urgent`, Target Language: `English`, Channel: `SMS`.
   - Facts: `Pulse polio drops for children under 5. Centers open Sunday 9 AM to 5 PM. Helpline: 1075.`
   - Click **"Synthesize Copy"** to demonstrate channel-constrained copy generation.
   - Click **"Translate"** to synthesize high-fidelity regional variants (Hindi, Tamil, Marathi) with 100% placeholder retention.

---

### Act 4: Editorial Quality Assessment & Campaign Approval (Campaign Manager)
1. **Quality Audit:**
   - Click **"Run Quality Evaluation"** on the generated copy.
   - Demonstrate the automated compliance audit:
     - Fact consistency check against reference facts.
     - Telecommunication channel boundary audit (character counts, SMS segment estimation).
     - Hard-block panic detection (ensures no unverified claims or panic triggers).
     - Helpline verification (detects mandatory emergency helpline `1075`).
2. **Approve Content:** Click **"Approve Draft"** (transitions status from `Draft` to `Approved`).
3. **Approve Campaign:** On the Campaign Details page, click **"Approve Campaign"**.

---

### Act 5: Broadcast Dispatch & Resilient Delivery (Campaign Manager)
1. **Navigate to:** Campaign Details (`/campaigns/{id}`).
2. **Action:** Click **"Send Broadcast Now"**.
3. **Select Channels:** Confirm `SMS` and `WhatsApp`.
4. **Execution Showcase:**
   - Point out atomic recipient resolution: consented citizens are matched and queued.
   - Point out affirmative consent enforcement: opted-out and unconfirmed citizens are safely withheld with recorded audit logs.
   - Point out fallback mechanism: if primary channel delivery fails, system seamlessly cascades to secondary fallback channel.
   - Delivery outcome modal displays immediate delivery counts and unique tracking identifiers (`trk_...`).

---

### Act 6: Citizen Experience & Sentiment Feedback (Public Portal)
1. **Show Public Feedback:** Open a new browser window or tab.
2. **Simulate Citizen Interaction:** Navigate to `/feedback/{feedback_token}` (using the generated feedback token from the dispatch summary).
3. **Showcase Zero-PII Public Page:**
   - The feedback form displays official campaign title and department, with zero exposure of citizen personal details.
4. **Submit Feedback:**
   - Select 5 Stars.
   - Enter comment: `"Excellent advisory! Received clear instructions in our local language."`
   - Click **"Submit Feedback"**.
5. **Showcase Duplicate Prevention:** Refresh and attempt to submit again; verify instant rejection ("Feedback has already been submitted for this notification").

---

### Act 7: Executive Analytics & Performance Dashboards
1. **Navigate to:** **Analytics Dashboard** (`/analytics`).
2. **Showcase Global KPIs:**
   - Total Dispatched Messages, Confirmed Delivery Rate, Average Click-Through Rate.
3. **Showcase Visual Charts:**
   - **Delivery Funnel:** Sent → Delivered → Opened → Clicked → Feedback.
   - **Channel Breakdown:** Comparative delivery and response rates across SMS, WhatsApp, Email, Push.
   - **Language Performance:** Delivery volumes across Indian regional languages (`hi`, `en`, `ta`, `mr`, `kn`).
   - **Citizen Sentiment Distribution:** Real-time breakdown of Positive, Neutral, and Negative citizen sentiment scores.
4. **Export Options:** Click **"Export CSV"** and **"Export PDF"** to demonstrate one-click institutional executive reports.

---

## 5. Demonstration FAQ & Defensive Notes

- **Q: Are commercial telecoms contacted during the demo?**
  *A: The system operates in compliant Mock Mode by default, executing realistic carrier simulations and webhook callbacks without incurring network fees or billable API costs. Real credentials (SendGrid, Twilio, Meta Cloud API, Google Service Account JSON for FCM) can be configured in Admin Channel Settings for live delivery.*
- **Q: How is citizen privacy guaranteed?**
  *A: PII masking is systematically enforced at API serialization boundaries, in backend logs via `PIIRedactingFilter`, and in public feedback endpoints.*
- **Q: How does push notification authentication work?**
  *A: Civora uses Google Cloud OAuth2 service-account authentication (HTTP v1), exchanging private key JSON credentials for short-lived Bearer tokens cached for 50 minutes with thread-safe refresh locks.*
- **Q: What happens if an API endpoint receives sudden traffic spikes?**
  *A: Sliding-window rate limiters (backed by Redis sorted sets with thread-safe in-memory fallback) throttle excessive requests with standard HTTP 429 and `Retry-After` headers.*
