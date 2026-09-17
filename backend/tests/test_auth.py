import uuid
from datetime import datetime, timezone, timedelta
import pytest
import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
import sys
import importlib.util
from pathlib import Path

from app.models.user import User, UserRole
from app.models.event import Event
from app.api.deps import check_event_ownership, require_super_admin
from fastapi import HTTPException

# Dynamically load create_superadmin from scripts directory
SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "create_superadmin.py"
spec = importlib.util.spec_from_file_location("create_superadmin_script", SCRIPT_PATH)
create_superadmin_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(create_superadmin_mod)
create_or_update_superadmin = create_superadmin_mod.create_or_update_superadmin



def test_password_hashing():
    """Vérifie le hachage bcrypt et la vérification des mots de passe."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False

    with pytest.raises(ValueError):
        hash_password("")


def test_jwt_token_lifecycle():
    """Vérifie la génération, l'expiration et le décodage d'un token JWT."""
    payload = {"sub": str(uuid.uuid4()), "email": "test@gvg.local", "role": "event_admin"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))

    decoded = decode_access_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["email"] == payload["email"]
    assert decoded["role"] == payload["role"]
    assert "exp" in decoded

    # Test token expiré
    expired_token = create_access_token(payload, expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(expired_token)

    # Test token altéré
    tampered_token = token[:-5] + "ABCDE"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered_token)


def test_login_success(client: TestClient, db_session: Session):
    """Vérifie l'authentification avec identifiants valides et retour du token JWT."""
    user = User(
        email="organisateur@cambon.fr",
        hashed_password=hash_password("MotDePasseFort123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "organisateur@cambon.fr", "password": "MotDePasseFort123!"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "organisateur@cambon.fr"
    assert data["user"]["role"] == UserRole.EVENT_ADMIN
    assert data["user"]["is_active"] is True
    assert "hashed_password" not in data["user"]


def test_login_case_insensitivity(client: TestClient, db_session: Session):
    """Vérifie que la casse de l'email est normalisée lors du login."""
    user = User(
        email="admin.caps@test.fr",
        hashed_password=hash_password("Secret123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "Admin.Caps@Test.FR ", "password": "Secret123!"},
    )
    assert response.status_code == 200


def test_login_invalid_credentials(client: TestClient, db_session: Session):
    """Vérifie le message d'erreur générique en cas d'email inconnu ou mot de passe faux."""
    user = User(
        email="valid@gvg.fr",
        hashed_password=hash_password("RealPassword123"),
        role=UserRole.EVENT_ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    # Mauvais mot de passe
    res1 = client.post(
        "/api/v1/auth/login",
        json={"email": "valid@gvg.fr", "password": "WrongPassword"},
    )
    assert res1.status_code == 401
    assert res1.json()["detail"] == "Incorrect email or password"

    # Email inconnu
    res2 = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@gvg.fr", "password": "AnyPassword"},
    )
    assert res2.status_code == 401
    assert res2.json()["detail"] == "Incorrect email or password"


def test_login_inactive_user(client: TestClient, db_session: Session):
    """Vérifie le rejet d'un compte désactivé (is_active=False)."""
    user = User(
        email="inactive@gvg.fr",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@gvg.fr", "password": "Pass123!"},
    )
    assert response.status_code == 400
    assert "Inactive user" in response.json()["detail"]


def test_get_current_user_profile(client: TestClient, db_session: Session):
    """Vérifie l'accès à /api/v1/auth/me avec header Authorization Bearer."""
    user = User(
        email="profil@gvg.fr",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.SUPER_ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})

    # Sans token
    res_no_auth = client.get("/api/v1/auth/me")
    assert res_no_auth.status_code == 401

    # Avec token valide
    res_auth = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert data["email"] == "profil@gvg.fr"
    assert data["role"] == UserRole.SUPER_ADMIN


def test_refresh_token(client: TestClient, db_session: Session):
    """Vérifie le renouvellement du token via /api/v1/auth/refresh."""
    user = User(
        email="refresh@gvg.fr",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.EVENT_ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    response = client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "refresh@gvg.fr"


def test_role_and_ownership_dependencies(db_session: Session):
    """Vérifie les fonctions de contrôle d'accès RBAC et scope événement."""
    super_admin = User(
        email="super@gvg.fr",
        hashed_password="hash",
        role=UserRole.SUPER_ADMIN,
    )
    admin_owner = User(
        email="owner@gvg.fr",
        hashed_password="hash",
        role=UserRole.EVENT_ADMIN,
    )
    admin_other = User(
        email="other@gvg.fr",
        hashed_password="hash",
        role=UserRole.EVENT_ADMIN,
    )
    db_session.add_all([super_admin, admin_owner, admin_other])
    db_session.commit()

    # Test require_super_admin
    assert require_super_admin(super_admin) == super_admin
    with pytest.raises(HTTPException) as exc_info:
        require_super_admin(admin_owner)
    assert exc_info.value.status_code == 403

    # Test check_event_ownership
    event = Event(
        title="Vide-grenier privé",
        slug="vide-grenier-prive",
        map_type="geographic",
        price_per_meter_cents=500,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(hours=8),
        owner_id=admin_owner.id,
    )
    db_session.add(event)
    db_session.commit()

    # Le propriétaire a le droit
    check_event_ownership(event, admin_owner)

    # Le super-admin a toujours le droit
    check_event_ownership(event, super_admin)

    # Un autre admin est rejeté en 403
    with pytest.raises(HTTPException) as exc_own:
        check_event_ownership(event, admin_other)
    assert exc_own.value.status_code == 403


def test_create_superadmin_cli(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Vérifie l'exécution du script CLI d'initialisation du Super-Admin et le rattachement rétrocompatible."""
    # Créer un événement sans propriétaire (comme en v1)
    old_event = Event(
        title="Édition 2026 sans owner",
        slug="edition-2026-sans-owner",
        map_type="geographic",
        price_per_meter_cents=500,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(hours=8),
        owner_id=None,
    )
    db_session.add(old_event)
    db_session.commit()

    # Brancher SessionLocal sur la db_session de test sans la fermer
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(
        create_superadmin_mod,
        "SessionLocal",
        lambda: db_session,
    )

    # 1. Exécution initiale
    create_or_update_superadmin("boss@videgrenier.fr", "MasterKey123!")

    super_user = db_session.query(User).filter(User.email == "boss@videgrenier.fr").first()
    assert super_user is not None
    assert super_user.role == UserRole.SUPER_ADMIN
    assert verify_password("MasterKey123!", super_user.hashed_password) is True

    # Vérifier que l'ancien événement a été rattaché
    reloaded_event = db_session.query(Event).filter(Event.id == old_event.id).first()
    assert reloaded_event.owner_id == super_user.id

    # 2. Exécution idempotente (mise à jour du mot de passe)
    create_or_update_superadmin("boss@videgrenier.fr", "NewMasterKey456!")
    reloaded_user = db_session.query(User).filter(User.email == "boss@videgrenier.fr").first()
    assert verify_password("NewMasterKey456!", reloaded_user.hashed_password) is True
