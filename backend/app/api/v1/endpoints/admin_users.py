import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.event import Event
from app.api.deps import require_super_admin
from app.schemas.auth import (
    AdminUserResponse,
    UserCreate,
    UserUpdate,
    ResetPasswordRequest,
)

router = APIRouter()


@router.get(
    "",
    response_model=List[AdminUserResponse],
    summary="List all users with event counts (Super-Admin only)",
)
def list_admin_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> List[AdminUserResponse]:
    """Retrieve all user accounts on the platform with their assigned role and event count."""
    events_count_subq = (
        db.query(Event.owner_id, func.count(Event.id).label("cnt"))
        .group_by(Event.owner_id)
        .subquery()
    )

    results = (
        db.query(User, func.coalesce(events_count_subq.c.cnt, 0).label("events_count"))
        .outerjoin(events_count_subq, User.id == events_count_subq.c.owner_id)
        .order_by(User.created_at.desc())
        .all()
    )

    items: List[AdminUserResponse] = []
    for u, count in results:
        items.append(
            AdminUserResponse(
                id=u.id,
                email=u.email,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                updated_at=u.updated_at,
                events_count=count,
            )
        )
    return items


@router.post(
    "",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organizer or super-admin account (Super-Admin only)",
)
def create_admin_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> AdminUserResponse:
    """Create a new user with email, temporary password, and role."""
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cette adresse email existe déjà",
        )

    new_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cette adresse email existe déjà",
        )

    return AdminUserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        events_count=0,
    )


@router.patch(
    "/{user_id}",
    response_model=AdminUserResponse,
    summary="Update user active status or role (Super-Admin only)",
)
def update_admin_user(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> AdminUserResponse:
    """Update role, activation status, or email of a user."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    # Protect self-lockout
    if current_user.id == target_user.id:
        if user_in.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas désactiver votre propre compte",
            )
        if user_in.role and user_in.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas révoquer vos propres droits super-admin",
            )

    if user_in.email and user_in.email != target_user.email:
        conflict = db.query(User).filter(User.email == user_in.email).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte avec cette adresse email existe déjà",
            )
        target_user.email = user_in.email

    if user_in.role:
        target_user.role = user_in.role

    if user_in.is_active is not None:
        target_user.is_active = user_in.is_active

    if user_in.password:
        target_user.hashed_password = hash_password(user_in.password)

    try:
        db.commit()
        db.refresh(target_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cette adresse email existe déjà",
        )

    events_count = db.query(Event).filter(Event.owner_id == target_user.id).count()

    return AdminUserResponse(
        id=target_user.id,
        email=target_user.email,
        role=target_user.role,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
        updated_at=target_user.updated_at,
        events_count=events_count,
    )


@router.post(
    "/{user_id}/reset-password",
    summary="Reset a user's password (Super-Admin only)",
)
def reset_admin_user_password(
    user_id: uuid.UUID,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> dict:
    """Assign a new password to the specified user."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    target_user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Mot de passe réinitialisé avec succès"}
