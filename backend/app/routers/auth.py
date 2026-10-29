"""Authentication endpoints for user registration, login, and profile retrieval."""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.core.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth_service import register_user, authenticate_user

logger = logging.getLogger("masscommai.routers.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a new user with bcrypt password hashing and safe default Communication Team role. Admin role cannot be acquired through public registration.",
    responses={
        201: {"description": "User successfully created."},
        409: {"description": "Conflict: Account with this email already exists."},
        422: {"description": "Validation Error: Missing required fields or password policy failure."},
    },
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """Endpoint for user registration."""
    new_user = register_user(db=db, request=request)

    return UserRegisterResponse(
        status="success",
        message="Account registered successfully.",
        user=UserRead(
            id=new_user.id,
            full_name=new_user.full_name,
            email=new_user.email,
            phone=new_user.phone,
            organization=new_user.organization,
            role_id=new_user.role_id,
            role_name=new_user.role.name,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
        ),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login & Token Generation",
    description="Authenticates credentials and issues a signed JWT access token. Rejects inactive users.",
    responses={
        200: {"description": "Authentication successful; access token returned."},
        401: {"description": "Invalid credentials or inactive account."},
        422: {"description": "Validation Error: Invalid email format or missing fields."},
    },
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """Verifies email/password and returns a JWT access token."""
    user = authenticate_user(
        db=db,
        email=request.email,
        password=request.password,
    )

    token = create_access_token(subject=user.id)
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in_seconds,
        user=UserRead(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            organization=user.organization,
            role_id=user.role_id,
            role_name=user.role.name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Resolves authenticated user and current role from database state via Bearer token.",
    responses={
        200: {"description": "Profile data for the current user."},
        401: {"description": "Unauthorized: Missing, expired, or deactivated credentials."},
    },
)
def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Returns the authenticated profile of the current user."""
    return UserRead(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        organization=current_user.organization,
        role_id=current_user.role_id,
        role_name=current_user.role.name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
