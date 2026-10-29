"""Reusable FastAPI authentication and role-based authorization dependencies."""

from typing import List, Union, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.user import User, Role
from app.core.security import decode_access_token

# Bearer token extractor without auto_error to allow custom 401 handling
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates JWT bearer token, extracts subject user ID, and resolves user
    and role dynamically from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not auth or not auth.credentials:
        raise credentials_exception

    payload = decode_access_token(auth.credentials)
    if not payload:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    # Always fetch trusted current user and role state from the database
    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(User.id == user_id)
    )
    user = db.execute(stmt).scalar_one_or_none()

    if not user:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the authenticated user account is currently active.
    Deactivated accounts are denied access immediately even with a valid token.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Please contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_role(allowed_roles: Union[str, List[str]]):
    """
    Factory creating a dependency that enforces server-side role-based access control.
    Resolves role membership from trusted database state and returns 403 Forbidden
    if the active user lacks the required role.
    """
    if isinstance(allowed_roles, str):
        target_roles = {allowed_roles}
    else:
        target_roles = set(allowed_roles)

    def role_dependency(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.role or current_user.role.name not in target_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Insufficient permissions for this resource.",
            )
        return current_user

    return role_dependency

