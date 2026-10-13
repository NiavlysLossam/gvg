import time
from collections import defaultdict
from threading import Lock
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, DUMMY_BCRYPT_HASH
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user

router = APIRouter()

# Thread-safe in-memory rate limiter for failed login attempts
# Tracks timestamps of failed attempts per client key (IP or email)
_login_failures_lock = Lock()
_login_failures: dict[str, list[float]] = defaultdict(list)

MAX_FAILED_ATTEMPTS_PER_ACCOUNT = 5
MAX_FAILED_ATTEMPTS_PER_IP = 20
LOCKOUT_WINDOW_SECONDS = 60  # 1 minute lockout window


def _get_client_ip(request: Request) -> str:
    """Extract real client IP considering trusted reverse proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str, max_attempts: int, error_msg: str) -> None:
    """Raise HTTP 429 if key exceeded max_attempts within window. Evicts expired keys."""
    now = time.time()
    with _login_failures_lock:
        # Periodic cleanup of expired keys if dict grows large
        if len(_login_failures) > 2000:
            expired_keys = [k for k, v in _login_failures.items() if not v or (now - v[-1] >= LOCKOUT_WINDOW_SECONDS)]
            for k in expired_keys:
                _login_failures.pop(k, None)

        attempts = _login_failures.get(key, [])
        valid_attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
        if valid_attempts:
            _login_failures[key] = valid_attempts
        else:
            _login_failures.pop(key, None)

        if len(valid_attempts) >= max_attempts:
            retry_after = int(LOCKOUT_WINDOW_SECONDS - (now - valid_attempts[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg.format(retry_after=max(1, retry_after)),
                headers={"Retry-After": str(max(1, retry_after))},
            )


def _record_failure(key: str) -> None:
    now = time.time()
    with _login_failures_lock:
        _login_failures[key].append(now)


def _clear_failures(key: str) -> None:
    with _login_failures_lock:
        _login_failures.pop(key, None)


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
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate an admin user and return a signed JWT token.
    Protected against brute-force attacks via sliding window rate limiting on both IP and account.
    Generic error message to prevent user enumeration.
    """
    client_ip = _get_client_ip(request)
    clean_email = login_data.email.strip().lower()

    ip_key = f"ip:{client_ip}"
    account_key = f"acc:{clean_email}"

    # 1. Protect against distributed password guessing on this account
    _check_rate_limit(
        account_key,
        MAX_FAILED_ATTEMPTS_PER_ACCOUNT,
        "Trop de tentatives échouées pour ce compte. Veuillez réessayer dans {retry_after} secondes.",
    )
    # 2. Protect against password spraying from this IP across multiple accounts
    _check_rate_limit(
        ip_key,
        MAX_FAILED_ATTEMPTS_PER_IP,
        "Trop de tentatives échouées depuis cette adresse IP. Veuillez réessayer dans {retry_after} secondes.",
    )

    user = (
        db.query(User)
        .filter(func.lower(User.email) == clean_email)
        .first()
    )

    if not user:
        verify_password(login_data.password, DUMMY_BCRYPT_HASH)
        _record_failure(account_key)
        _record_failure(ip_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(login_data.password, user.hashed_password):
        _record_failure(account_key)
        _record_failure(ip_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _record_failure(account_key)
        _record_failure(ip_key)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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

    _clear_failures(account_key)
    _clear_failures(ip_key)

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

