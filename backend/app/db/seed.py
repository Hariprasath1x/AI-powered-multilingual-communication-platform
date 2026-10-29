"""Idempotent database seeding utilities for default roles and initial system setup."""

import logging
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
) -> User | None:
    """
    Explicit development/initial deployment bootstrap for an administrative user.
    Credentials must be supplied programmatically or via environment variables; never hardcoded.
    """
    email_clean = email.strip().lower()
    existing_user = db.execute(select(User).where(User.email == email_clean)).scalar_one_or_none()
    if existing_user:
        return existing_user

    roles = seed_default_roles(db)
    admin_role = roles.get("Admin")
    if not admin_role:
        raise RuntimeError("Admin role not found during bootstrap.")

    admin = User(
        full_name=full_name,
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


if __name__ == "__main__":
    from app.db.session import SessionLocal

    logging.basicConfig(level=logging.INFO)
    session = SessionLocal()
    try:
        roles = seed_default_roles(session)
        print(f"Role seeding verified. Total active roles: {len(roles)}")
    finally:
        session.close()

