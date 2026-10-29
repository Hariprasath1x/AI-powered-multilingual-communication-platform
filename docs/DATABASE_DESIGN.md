# MassCommAI — Relational Database Architecture (Milestone 1)

This document specifies the initial relational database schema for the **AI-Powered Multilingual Public Awareness and Mass Communication Platform** (Infosys Springboard Virtual Internship).

All tables are versioned and managed through **Alembic** migrations using **PostgreSQL 14+** and **SQLAlchemy 2.x**.

---

## 1. Entity Relationship (ER) Diagram

```mermaid
erDiagram
    ROLES ||--o{ USERS : "assigned to"
    USERS ||--o{ CAMPAIGNS : "creates"
    USERS ||--o{ SEGMENTS : "creates"
    USERS ||--o{ TEMPLATES : "creates"
    
    CAMPAIGNS ||--o{ CAMPAIGN_SEGMENTS : "targets"
    SEGMENTS ||--o{ CAMPAIGN_SEGMENTS : "targeted in"
    
    CAMPAIGNS ||--o{ MESSAGES : "generates"
    AUDIENCE_MEMBERS ||--o{ MESSAGES : "receives"
    TEMPLATES ||--o{ MESSAGES : "formats"
    
    MESSAGES ||--o{ DELIVERY_LOGS : "logs status"
    
    CAMPAIGNS ||--o{ FEEDBACK : "receives"
    AUDIENCE_MEMBERS ||--o{ FEEDBACK : "submits"

    ROLES {
        int id PK
        string name UK "Admin, Campaign Manager, Communication Team"
        string description
        datetime created_at
    }

    USERS {
        int id PK
        string full_name
        string email UK
        string phone
        string organization
        string hashed_password
        int role_id FK
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    AUDIENCE_MEMBERS {
        int id PK
        string name
        string email UK "Partial unique (WHERE email IS NOT NULL)"
        string phone UK "Partial unique (WHERE phone IS NOT NULL)"
        int age
        string gender
        string city
        string state
        string preferred_language "Hindi, Tamil, Telugu, etc."
        string occupation
        string organization_department
        string preferred_channel "Email, SMS, WhatsApp"
        boolean consent_status
        datetime created_at
        datetime updated_at
    }

    SEGMENTS {
        int id PK
        string name
        string description
        jsonb filter_rules "Dynamic query criteria (AND/OR, field, operator, value)"
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    CAMPAIGN_SEGMENTS {
        int campaign_id PK, FK
        int segment_id PK, FK
    }

    CAMPAIGNS {
        int id PK
        string name
        string campaign_type "Awareness, Emergency Alert, Educational, Announcement"
        string objective
        string priority "Low, Medium, High"
        string status "Draft, In Review, Approved, Scheduled, Running, Completed, Failed"
        jsonb channels "['Email', 'SMS', 'WhatsApp']"
        datetime start_date
        datetime end_date
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    TEMPLATES {
        int id PK
        string title
        string category "Healthcare, Disaster, Education, Governance"
        text body "Content with {name}, {area} placeholders"
        string language
        string tags
        int created_by FK
        datetime created_at
        datetime updated_at
    }

    MESSAGES {
        int id PK
        int campaign_id FK
        int audience_member_id FK
        int template_id FK
        string channel
        string language
        text rendered_content
        string status "Pending, Sent, Delivered, Failed"
        datetime scheduled_at
        datetime sent_at
        datetime created_at
    }

    DELIVERY_LOGS {
        int id PK
        int message_id FK
        string channel
        string status "Sent, Delivered, Failed"
        text error_message
        int retry_count
        datetime timestamp
    }

    FEEDBACK {
        int id PK
        int campaign_id FK
        int audience_member_id FK
        int rating "1 to 5 stars"
        text comment
        string sentiment_label "Positive, Neutral, Negative (Milestone 3)"
        float sentiment_score "Milestone 3"
        string language
        datetime created_at
    }
```

---

## 2. Table Specifications & Constraints

| Table Name | Primary Purpose | Key Constraints & Indexes |
| :--- | :--- | :--- |
| `roles` | Access-level definitions | `UNIQUE(name)` |
| `users` | Staff, Manager, and Admin credentials | `UNIQUE(email)`, Index on `email`, FK to `roles.id` |
| `audience_members` | Recipient directory for public communication | Partial unique indexes on `email` and `phone` (`WHERE ... IS NOT NULL`), indexes on `preferred_language`, `city`, `preferred_channel` |
| `segments` | Reusable demographic filter definitions | `filter_rules` stored as native PostgreSQL `JSONB`, FK to `users.id` |
| `campaign_segments` | Many-to-Many association | Composite PK `(campaign_id, segment_id)`, Cascading Foreign Keys |
| `campaigns` | Campaign metadata, channels & lifecycle | FK to `users.id`, indexes on `status`, `priority`, `campaign_type` |
| `templates` | Reusable content templates with `{name}` placeholders | FK to `users.id`, indexes on `category`, `language` |
| `messages` | Generated outgoing communication items | FKs to `campaigns`, `audience_members`, and `templates` |
| `delivery_logs` | Channel dispatch audit trail & retries | FK to `messages.id`, index on `status` |
| `feedback` | Recipient satisfaction & future sentiment metrics | FKs to `campaigns` and `audience_members`, rating constraint (1–5) |

---

## 3. Migration Management

- **Tool:** Alembic 1.13+
- **Initial Migration:** `0de49a2cf7ef_initial_schema_all_models.py`
- **Execution Command:** `alembic upgrade head`
- **Rollback Command:** `alembic downgrade -1`
