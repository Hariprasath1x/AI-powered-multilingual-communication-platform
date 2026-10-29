"""Idempotent database seeding utilities for default roles and initial system setup."""

import logging
import os
import sys
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import Role, User
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
    else:
        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            roles = seed_default_roles(session)
            print(f"Role seeding verified. Total active roles: {len(roles)}")
        finally:
            session.close()
