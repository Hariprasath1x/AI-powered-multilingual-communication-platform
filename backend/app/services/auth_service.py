"""Authentication and registration service layer handling business logic, hashing, and transactions."""

import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User, Role
from app.schemas.user import UserRegisterRequest, DEFAULT_REGISTRATION_ROLE
from app.core.security import get_password_hash
from app.db.seed import seed_default_roles

logger = logging.getLogger("masscommai.auth")


def register_user(db: Session, request: UserRegisterRequest) -> User:
    """
    Validates, hashes password, and persists a new user account with the safe Communication Team role.
    Commits only upon full validation success; rolls back completely on any database exception.
    """
    normalized_email = request.email.strip().lower()

    # 1. Pre-check for duplicate email to provide friendly conflict response
    existing_user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if existing_user:
        logger.info("Registration attempt rejected: duplicate email %s", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 2. Server-enforced least-privileged role assignment (Communication Team)
    target_role_name = DEFAULT_REGISTRATION_ROLE
    role = db.execute(
        select(Role).where(Role.name == target_role_name)
    ).scalar_one_or_none()

    # Self-healing fallback if roles haven't been seeded yet
    if not role:
        roles_map = seed_default_roles(db)
        role = roles_map.get(target_role_name)

    if not role:
        logger.critical("Failed to resolve mandatory registration role: %s", target_role_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System role configuration error. Please contact the administrator.",
        )

    # 3. Secure password hashing with bcrypt
    try:
        hashed_password = get_password_hash(request.password)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        )

    # 4. Create new user entity with least-privileged role
    new_user = User(
        full_name=request.full_name.strip(),
        email=normalized_email,
        phone=request.phone.strip() if request.phone else None,
        organization=request.organization.strip() if request.organization else None,
        hashed_password=hashed_password,
        role_id=role.id,
        is_active=True,
    )

    # 5. Atomic persistence with rollback protection
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info("Successfully registered user id=%d, role=%s", new_user.id, role.name)
        return new_user
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Integrity violation during user commit for %s: %s",
            normalized_email,
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "Unexpected error committing user record %s: %s",
            normalized_email,
            exc.__class__.__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to complete account registration at this time.",
        )
