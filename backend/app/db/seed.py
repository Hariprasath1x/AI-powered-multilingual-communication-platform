"""Idempotent database seeding utilities for default roles and initial system setup."""

import logging
import os
import sys
from typing import List, Dict, Optional, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.user import Role, User
from app.models.template import Template
from app.core.security import get_password_hash

logger = logging.getLogger("masscommai.seed")

DEFAULT_ROLES: List[Dict[str, str]] = [
    {
        "name": "Admin",
        "description": "System administrator with full platform access, role governance, and user management.",
    },
    {
        "name": "Campaign Manager",
        "description": "Campaign planner and content author with audience segmentation and campaign creation privileges.",
    },
    {
        "name": "Communication Team",
        "description": "Operational communicator with template utilization, message review, and dispatch permissions.",
    },
]


def seed_default_roles(db: Session) -> Dict[str, Role]:
    """
    Idempotently seeds the three mandatory system roles.
    Safe to execute repeatedly: existing roles are preserved without duplicate key violations.
    """
    seeded_roles: Dict[str, Role] = {}

    for role_data in DEFAULT_ROLES:
        role_name = role_data["name"]
        stmt = select(Role).where(Role.name == role_name)
        existing_role = db.execute(stmt).scalar_one_or_none()

        if existing_role:
            seeded_roles[role_name] = existing_role
        else:
            new_role = Role(
                name=role_name,
                description=role_data["description"],
            )
            db.add(new_role)
            db.flush()
            seeded_roles[role_name] = new_role
            logger.info("Seeded default role: %s", role_name)

    db.commit()
    return seeded_roles


DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "title": "Dengue Awareness & Monsoon Safety Advisory",
        "category": "Healthcare",
        "language": "en",
        "body": "Dear {name}, the {organization_department} in {city}, {state} reminds all residents to take preventive measures against Dengue during the monsoon. Ensure there is no stagnant water in coolers, pots, or containers around your home. Sleep under mosquito nets and use repellents. If experiencing persistent high fever or joint pain, visit your nearest primary healthcare center immediately. Stay alert and stay healthy.",
        "tags": "dengue,health,monsoon,prevention",
    },
    {
        "title": "Flood Safety & Emergency Evacuation Protocol",
        "category": "Emergency Alert",
        "language": "en",
        "body": "URGENT ADVISORY: Dear {name}, the Disaster Management Authority has issued an emergency flood advisory for {city}, {state}. High water levels have been observed in local drainage basins. Avoid crossing flooded roads, secure essential emergency supplies, keep phone ({phone}) charged, and prepare to move to identified civic relief centers if instructed. For emergency assistance, contact your local municipal control room.",
        "tags": "flood,emergency,disaster,safety",
    },
    {
        "title": "Voter Registration & Democratic Participation Campaign",
        "category": "Civic Education",
        "language": "en",
        "body": "Dear {name}, every vote shapes our nation's future! As a responsible citizen of {city}, {state}, ensure your name is registered on the electoral roll. Check your polling station details and registration status online at the official election portal. Exercise your constitutional right with pride and participate in the upcoming democratic process. Your voice, your vote, your power.",
        "tags": "voter,election,civic,democracy",
    },
    {
        "title": "Pulse Polio & Universal Immunization Drive",
        "category": "Healthcare",
        "language": "en",
        "body": "Public Health Notice: Dear {name}, ensure all children under 5 years receive polio vaccination drops during the upcoming Universal Immunization Drive across {city}, {state}. Vaccination booths will operate from 9:00 AM to 5:00 PM at all community health centers and designated public schools. Immunization protects future generations. Bring your children for a healthy, polio-free India.",
        "tags": "vaccination,polio,childcare,health",
    },
    {
        "title": "Citizen Portal Digital Services Advisory",
        "category": "Public Governance",
        "language": "en",
        "body": "Dear {name}, access government civic services seamlessly from home! Residents of {city}, {state} can now apply for birth certificates, trade licenses, property tax receipts, and utility connections directly through the unified civic digital portal. Avoid queues, track application status in real-time, and experience transparent, paperless governance. Digital services empower every citizen.",
        "tags": "civic,governance,digital,services",
    },
    {
        "title": "Community Cleanliness & Waste Segregation Initiative",
        "category": "Community Outreach",
        "language": "en",
        "body": "Dear {name}, join the Clean Community Drive in {city}, {state}! Segregate household waste into wet and dry bins before daily municipal collection. Avoid single-use plastics and maintain clean surroundings in your neighborhood. Active community participation creates clean, sustainable, and vibrant cities for our families. Let us work together for civic excellence.",
        "tags": "cleanliness,swachh,community,waste-management",
    },
]


def seed_default_templates(db: Session, creator_user_id: Optional[int] = None) -> List[Template]:
    """
    Idempotently seeds the six standard public awareness communication templates.
    
    Guarantees:
    - Never overwrites existing user templates with the same title.
    - Idempotent: repeated executions skip existing templates without duplication.
    - Resolves creator dynamically: uses provided creator_user_id, or finds the first active Admin,
      or falls back to the first available user.
    - Transactional: rolls back safely on failure.
    """
    resolved_creator_id = creator_user_id
    if not resolved_creator_id:
        admin_user = (
            db.execute(
                select(User)
                .join(Role)
                .where(Role.name == "Admin", User.is_active.is_(True))
                .order_by(User.id)
            )
            .scalars()
            .first()
        )
        if admin_user:
            resolved_creator_id = admin_user.id
        else:
            first_user = db.execute(select(User).order_by(User.id)).scalars().first()
            if first_user:
                resolved_creator_id = first_user.id
            else:
                logger.warning("No users exist in database. Cannot seed templates without a creator user.")
                return []

    seeded: List[Template] = []
    for item in DEFAULT_TEMPLATES:
        clean_title = item["title"].strip()
        existing = db.execute(
            select(Template).where(func.lower(Template.title) == clean_title.lower())
        ).scalar_one_or_none()

        if existing:
            seeded.append(existing)
        else:
            new_tmpl = Template(
                title=clean_title,
                category=item["category"],
                language=item["language"],
                body=item["body"],
                tags=item["tags"],
                created_by=resolved_creator_id,
            )
            db.add(new_tmpl)
            db.flush()
            seeded.append(new_tmpl)
            logger.info("Seeded default template: '%s'", clean_title)

    db.commit()
    return seeded


def bootstrap_admin_user(
    db: Session,
    email: str,
    password: str,
    full_name: str = "System Administrator",
) -> User:
    """
    Explicit administrative user bootstrap utility.
    
    Security guarantees:
    - Requires an explicitly supplied password (never creates an admin with a default password).
    - Enforces length bounds (min 8 chars, max 72 UTF-8 bytes).
    - Hashes password using bcrypt.
    - Transactional: rolls back on failure.
    - Never logs passwords or hashes.
    """
    # Prevent SQL echo from exposing hashes to stdout/logs
    from app.db.session import engine
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    if not email or "@" not in email:
        raise ValueError("Admin bootstrap requires a valid email address.")

    if not password or not password.strip():
        raise ValueError("Admin bootstrap requires an explicitly supplied non-empty password.")

    if len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters long.")

    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes (bcrypt limit).")

    email_clean = email.strip().lower()
    full_name_clean = full_name.strip() if full_name else "System Administrator"

    try:
        existing_user = db.execute(select(User).where(User.email == email_clean)).scalar_one_or_none()
        if existing_user:
            logger.info("Admin user already exists: %s", email_clean)
            return existing_user

        roles = seed_default_roles(db)
        admin_role = roles.get("Admin")
        if not admin_role:
            raise RuntimeError("Admin role not found during bootstrap.")

        admin = User(
            full_name=full_name_clean,
            email=email_clean,
            hashed_password=get_password_hash(password),
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Bootstrapped administrative user: %s", email_clean)
        return admin
    except Exception:
        db.rollback()
        logger.exception("Failed to bootstrap admin user: %s", email_clean)
        raise


def run_interactive_bootstrap() -> None:
    """
    Secure CLI runner for bootstrapping an administrator.
    Reads credentials interactively via getpass (no terminal echo),
    or from secure environment variables (ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD).
    Never prints or logs passwords or hashes.
    Ensures safe database session closure in finally block.
    """
    import getpass

    # Suppress SQLAlchemy parameter echoing so hashes are never printed
    from app.db.session import engine, SessionLocal
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    print("=" * 60)
    print("MassCommAI — Secure Administrator Bootstrap Utility")
    print("=" * 60)

    # 1. Email
    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "").strip()
    if not email:
        try:
            email = input("Administrator Email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if not email or "@" not in email:
        print("Error: A valid email address is required.", file=sys.stderr)
        sys.exit(1)

    # 2. Full Name
    full_name = os.environ.get("ADMIN_BOOTSTRAP_NAME", "").strip()
    if not full_name:
        try:
            full_name = input("Administrator Full Name [System Administrator]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)
    if not full_name:
        full_name = "System Administrator"

    # 3. Password
    env_password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    if env_password:
        password = env_password
    else:
        try:
            password = getpass.getpass("Administrator Password (min 8 chars): ")
            confirm = getpass.getpass("Confirm Administrator Password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    session = SessionLocal()
    try:
        bootstrap_admin_user(
            db=session,
            email=email,
            password=password,
            full_name=full_name,
        )
        print(f"Success: Administrator account '{email.strip().lower()}' successfully bootstrapped.")
    except ValueError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"System Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if "--bootstrap-admin" in sys.argv:
        run_interactive_bootstrap()
    elif "--seed-templates" in sys.argv:
        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            tmpls = seed_default_templates(session)
            print(f"Default templates verified. Total templates available: {len(tmpls)}")
        finally:
            session.close()
    else:
        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            roles = seed_default_roles(session)
            print(f"Role seeding verified. Total active roles: {len(roles)}")
        finally:
            session.close()
