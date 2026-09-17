from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticate with email and password to receive an HS256 JWT access token.",
)
@router.post(
    "/token",
    response_model=TokenResponse,
    include_in_schema=False,
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate an admin user and return a signed JWT token.
    Generic error message to prevent user enumeration.
    """
    clean_email = login_data.email.strip().lower()
    user = (
        db.query(User)
        .filter(func.lower(User.email) == clean_email)
        .first()
    )

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
        },
        expires_delta=timedelta(minutes=expires_minutes),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Retrieve the profile of the currently authenticated administrator.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Renew an active access token before expiry.",
)
def refresh_token(
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "email": current_user.email,
            "role": current_user.role,
        },
        expires_delta=timedelta(minutes=expires_minutes),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
        user=UserResponse.model_validate(current_user),
    )

