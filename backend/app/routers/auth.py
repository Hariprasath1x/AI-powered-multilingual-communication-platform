"""Authentication endpoints for user registration and access management."""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserRegisterRequest, UserRegisterResponse, UserRead
from app.services.auth_service import register_user

logger = logging.getLogger("masscommai.routers.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a new user with bcrypt password hashing and safe default role assignment. Admin role cannot be acquired through public registration.",
    responses={
        201: {
            "description": "User successfully created.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Account registered successfully.",
                        "user": {
                            "id": 1,
                            "full_name": "Priya Sharma",
                            "email": "priya.sharma@dept.gov.in",
                            "phone": "+919876543210",
                            "organization": "Health Services Directorate",
                            "role_id": 3,
                            "role_name": "Communication Team",
                            "is_active": True,
                            "created_at": "2026-10-29T12:00:00Z",
                        },
                    }
                }
            },
        },
        400: {"description": "Bad Request or unprocessable input."},
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

