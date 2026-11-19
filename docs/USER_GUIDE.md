# Civora — Platform User Guide
## Comprehensive Role-Based Operational Manual for Public Administration & Civic Messaging
### Powered by MassCommAI — Bringing communities closer.

- **Document Version:** 2.0.0
- **Release Date:** November 19, 2026
- **Architecture Lead:** MassCommAI Core Engineering Team
- **Product Identity:** Civora (Public Brand) | MassCommAI (Underlying Technical Engine)

---

## 1. About Civora

**Civora** is an enterprise-grade AI-powered mass communication, public awareness, and audience segmentation platform built upon the **MassCommAI** core architecture. Designed specifically for civic administrations, emergency disaster management bodies, public health institutions, and governmental agencies, Civora bridges communication chasms across linguistically diverse populations.

The platform provides a complete end-to-end institutional workflow:
`Audience Ingestion -> Demographic Segmentation -> Campaign Composition -> AI Content Synthesis -> Multilingual Translation -> Compliance Quality Audit -> Multi-Channel Dispatch -> Delivery Tracking -> Citizen Sentiment Feedback -> Executive Analytics`.

---

## 2. Institutional Role & Permission Matrix

Civora enforces Role-Based Access Control (RBAC) across three distinct organizational personas:

| Capability / Module | System Administrator | Campaign Manager | Communication Team |
| :--- | :---: | :---: | :---: |
| **System Dashboard & Health Status** | Full Access | Full Access | Full Access |
| **Audience Database — View & Search** | Full Access | Full Access | Full Access (Read-Only) |
| **Audience Database — Ingest & Modify** | Full Access | Full Access | Forbidden |
| **Audience Segments — Create & Edit** | Full Access | Full Access | Forbidden |
| **Message Templates — Author & Manage** | Full Access | Full Access | Full Access |
| **Campaign Studio — Create & Plan** | Full Access | Full Access | Forbidden |
| **Campaign Governance — Approve Campaign**| Full Access | Full Access | Forbidden |
| **AI Content Studio & Translations** | Full Access | Full Access | Forbidden |
| **Campaign Dispatch & Broadcasting** | Full Access | Full Access | Forbidden |
| **Delivery Tracking & Failed Messages**| Full Access | Full Access | Full Access |
| **Citizen Feedback & Inbound Replies** | Full Access | Full Access | Full Access |
| **Analytics Dashboards & Export** | Full Access | Full Access | Full Access |
| **User Governance & Role Assignment** | Full Access | Forbidden | Forbidden |
| **Channel Telephony & API Settings** | Full Access | Forbidden | Forbidden |
| **Global Compliance Policies** | Full Access | Forbidden | Forbidden |

---

## 3. Getting Started

### 3.1 Accessing the Platform
1. Open your web browser and navigate to the application URL: `http://localhost:5173` (or production host).
2. Click **"Log In"** in the top navigation bar.
3. Enter your assigned institutional email and password:
   - System Administrator: `admin@masscomm.gov.in`
   - Campaign Manager: `manager@masscomm.gov.in`
   - Communication Team: `team@masscomm.gov.in`

### 3.2 Switching Interface Language
The platform supports real-time bilingual interface switching between **English** and **Hindi (हिंदी)**:
- Locate the language switcher toggle pill in the top header (next to the system health indicator).
- Click **"हिंदी"** to toggle interface labels to Hindi; click **"English"** to return to English.

---

## 4. Audience Management & Citizen Consent

The **Audience Database** (`/audience`) maintains localized demographic profiles while preserving strict citizen privacy.

### 4.1 Tri-State Consent Framework
Civora enforces strict legal privacy standards via tri-state consent:
- **Opt-in (`consent_status = True`, Green):** Citizen has explicitly consented to receive broadcast advisories. Messages can be dispatched.
- **Opt-out (`consent_status = False`, Red):** Citizen has explicitly revoked consent. Dispatches are permanently blocked and withheld.
- **Unconfirmed (`consent_status = None`, Amber):** Affirmative consent is missing. The system prevents broadcasts until consent is verified.

### 4.2 Bulk Audience Ingestion
1. Navigate to **Audience Database** → Click **"Import Audience"**.
2. Upload a `.csv` or `.xlsx` spreadsheet matching the standard columns: `name`, `email`, `phone`, `age`, `gender`, `city`, `state`, `preferred_language`, `preferred_channel`, `occupation`, `consent_status`.
3. The parser validates phone numbers, email syntax, and normalizes 22 Indian language codes with row-level error isolation.

---

## 5. Visual Audience Segmentation

The **Audience Segments** module (`/segments`) allows campaign planners to group citizens into demographic cohorts using a visual query builder.

### 5.1 Building Query Rules
1. Click **"New Segment"**.
2. Enter a descriptive name (e.g., `Maharashtra Farmers - Monsoon Advisory`).
3. Choose a logical connector:
   - **AND:** All conditions must match simultaneously.
   - **OR:** Any condition match includes the citizen.
4. Add atomic conditions:
   - `State equals Maharashtra`
   - `Occupation equals Farmer`
   - `Consent Status equals True`
5. Click **"Preview Segment Reach"** to verify real-time matching count and sample members before saving.

---

## 6. AI Content Studio & Multilingual Generation

The **AI Content Studio** (`/content`) generates channel-constrained public communication copy and localized Indian language translations.

### 6.1 Synthesizing Content Briefs
1. Select target distribution channel (`SMS`, `WhatsApp`, `Email`, `Voice`, `Web Push`, `Web Broadcast`).
2. Select desired institutional tone:
   - `Formal`: Official governmental administrative notifications.
   - `Informative`: Educational guidelines and public welfare programs.
   - `Friendly`: Community drives and public surveys.
   - `Urgent`: Disaster warnings and emergency advisories.
   - `Empathetic`: Healthcare notices and civic assistance advisories.
3. Provide key factual anchors (e.g., helplines, dates, safe zones).
4. Click **"Synthesize Copy"**. The engine enforces telecommunication constraints:
   - **SMS:** Automatic character segment count calculation (160 GSM-7 / 70 UCS-2).
   - **WhatsApp:** 1024 character limit with preview formatting.
   - **Email:** Subject line character boundaries and structured HTML formatting.

### 6.2 High-Fidelity Regional Translations
- Click **"Translate"** or **"Batch Translate"** to synthesize variants in Hindi, Tamil, Telugu, Marathi, Bengali, Kannada, and other scheduled languages.
- The engine guarantees 100% preservation of personalization placeholders (`{name}`, `{city}`, `{state}`).

---

## 7. Editorial Review & Compliance Audit

Before any communication can be approved or sent, it must pass automated compliance checks.

### 7.1 Running Quality Evaluation
1. In the Content Studio or Campaign View, click **"Evaluate Quality"**.
2. The audit assesses:
   - **Fact Preservation:** Compares generated statements against reference facts.
   - **Panic Word Detection:** Hard-blocks alarmist or unverified phrasing.
   - **Helpline Compliance:** Verifies presence of mandatory civic emergency helplines for disaster and health categories.
   - **Readability & Sentiment:** Evaluates clarity and emotional polarity.
3. Review findings: High-severity violations block approval until resolved.

---

## 8. Multi-Channel Distribution & Fallback

Approved campaigns can be broadcast across SMS, WhatsApp, Email, Push Notifications, and Web Broadcast.

### 8.1 Sending a Campaign
1. Open the approved campaign on `/campaigns/{id}`.
2. Click **"Send Broadcast Now"**.
3. Select active delivery channels and specify fallback order (e.g., `WhatsApp -> SMS -> Email`).
4. Click **"Confirm Dispatch"**.
5. Real-time progress displays total intended recipients, eligible messages, and withheld opt-outs.

### 8.2 Fallback Delivery Logic
If delivery over the primary channel (e.g., WhatsApp) encounters temporary carrier failure, the dispatch worker automatically retries over the secondary fallback channel (e.g., SMS), recording attempt history in `delivery_attempts`.

---

## 9. Administrative Channel Settings & Push Authentication

Administrators can configure live and simulated provider credentials via **Channel Settings** (`/admin/channels`).

### 9.1 Configuring Firebase Cloud Messaging (FCM HTTP v1)
Civora implements modern Google Cloud OAuth2 service-account authentication for FCM push notifications:
1. Log in as an **Administrator** and navigate to **Channel Settings** (`/admin/channels`).
2. Select or create the **Web Push (FCM)** channel configuration.
3. Under **Authentication Method**, select **Google Service Account JSON**.
4. Paste the content of your Google Cloud Service Account private key JSON file (or upload it). The JSON must contain:
   - `type`: `"service_account"`
   - `project_id`: Your Google Cloud / Firebase Project ID
   - `private_key`: RSA private key
   - `client_email`: Service account email (`...@...iam.gserviceaccount.com`)
5. The platform securely stores the configuration in PostgreSQL, restricts access strictly to the Administrator role, and masks private keys and secrets (`••••••••`) in all API responses and application logs.
6. During dispatch, the backend uses Google OAuth2 to exchange the key for short-lived, scoped Bearer tokens cached for 50 minutes with thread-safe refresh.
7. If an endpoint encounters an invalid or unregistered device token (`UNREGISTERED` error), the system automatically marks the token inactive in `device_tokens`.
8. *(Optional Legacy Fallback):* A static Server Key field is available strictly for backward compatibility with legacy testing scripts, but standard production push delivery uses OAuth2 service-account credentials.
9. Click **"Test Connection"** to verify credential handshake without transmitting public citizen notifications.

---

## 10. Citizen Feedback & Sentiment Analysis

Citizens receiving broadcasts can interact through two-way reply webhooks or the secure public feedback portal (`/feedback/{token}`).

### 10.1 Zero-PII Public Portal
- The public link allows citizens to rate the communication (1 to 5 stars) and submit comments in their local language.
- The form displays campaign metadata without exposing phone numbers, names, or email addresses.

### 10.2 Real-Time Sentiment Scoring
- Submitted feedback is analyzed for sentiment polarity:
  - **Positive (`score > 0.15`):** Citizen satisfaction, gratitude, clarity.
  - **Neutral (`-0.15 <= score <= 0.15`):** General inquiries, acknowledgment.
  - **Negative (`score < -0.15`):** Complaints, delays, technical difficulties.
- Negative feedback is flagged for administrative review and resolution notes.

---

## 11. Analytics Dashboards & Executive Reports

The **Analytics Dashboard** (`/analytics`) aggregates performance metrics:
- **Delivery Funnel:** Visualizes message drop-off at each stage (Sent → Delivered → Opened → Clicked → Feedback).
- **Channel Effectiveness:** Compares delivery reliability across channels.
- **Language-Wise Reach:** Displays recipient volume and response rates across Indian languages.
- **Sentiment Breakdown:** Visual distribution of citizen satisfaction.
- **Executive Exports:** One-click downloads for **CSV Summary** and formatted **PDF Briefing Reports**.

---

## 12. Frequently Asked Questions (FAQ) & Troubleshooting

- **Why is a campaign blocked from being approved?**
  *A campaign must have an attached message template and its content asset must pass quality assessment without critical violations.*
- **Why was an audience member excluded from broadcast?**
  *The recipient either lacks affirmative consent (`consent_status = None` or `False`), or lacks a valid phone/email address for the selected channel.*
- **How do I configure FCM push notifications?**
  *Navigate to `/admin/channels`, configure the Web Push channel, and upload your Google Cloud Service Account JSON key. Civora uses OAuth2 HTTP v1 authentication.*
- **How do I reset demonstration data?**
  *Run `python -m app.db.seed_demo` in your terminal to idempotently repopulate clean demo records.*
