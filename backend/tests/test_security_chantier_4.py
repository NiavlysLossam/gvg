import subprocess
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User
from app.core.security import hash_password
from app.api.v1.endpoints import auth


def test_auth_login_sliding_window_rate_limiting_per_account(client: TestClient, db_session: Session):
    """Verify that repeated failed login attempts for a specific account trigger HTTP 429."""
    test_email = "ratelimit_victim@test.fr"
    user = db_session.query(User).filter(User.email == test_email).first()
    if not user:
        user = User(
            email=test_email,
            hashed_password=hash_password("SuperSecretPass123!"),
            role="event_admin",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

    from app.api.v1.endpoints.auth import _clear_failures, MAX_FAILED_ATTEMPTS_PER_ACCOUNT
    account_key = f"acc:{test_email}"
    ip_key = "ip:testclient"
    _clear_failures(account_key)
    _clear_failures(ip_key)

    for i in range(MAX_FAILED_ATTEMPTS_PER_ACCOUNT):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401, f"Attempt {i+1} should fail with 401"
        assert resp.json()["detail"] == "Incorrect email or password"

    resp_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": "WrongPassword123!"},
    )
    assert resp_blocked.status_code == 429
    assert "Trop de tentatives échouées pour ce compte" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers
    retry_val = resp_blocked.headers["Retry-After"]
    assert retry_val.isdigit()
    assert 1 <= int(retry_val) <= 60

    _clear_failures(account_key)
    _clear_failures(ip_key)


def test_auth_login_rate_limiting_protects_against_password_spraying(client: TestClient, db_session: Session):
    """Verify that attempting many different accounts from the same IP triggers IP rate limit."""
    from app.api.v1.endpoints.auth import _clear_failures, MAX_FAILED_ATTEMPTS_PER_IP
    ip_key = "ip:testclient"
    _clear_failures(ip_key)

    for i in range(MAX_FAILED_ATTEMPTS_PER_IP):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": f"spray_user_{i}@test.fr", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401

    resp_ip_blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "another_target@test.fr", "password": "WrongPassword!"},
    )
    assert resp_ip_blocked.status_code == 429
    assert "Trop de tentatives échouées depuis cette adresse IP" in resp_ip_blocked.json()["detail"]

    _clear_failures(ip_key)


def test_auth_login_successful_clears_failures(client: TestClient, db_session: Session):
    """Verify that a successful login resets the failure counter."""
    test_email = "reset_success@test.fr"
    password = "CorrectPass123!"
    user = db_session.query(User).filter(User.email == test_email).first()
    if not user:
        user = User(
            email=test_email,
            hashed_password=hash_password(password),
            role="event_admin",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

    account_key = f"acc:{test_email}"
    ip_key = "ip:testclient"
    from app.api.v1.endpoints.auth import _clear_failures
    _clear_failures(account_key)
    _clear_failures(ip_key)

    for _ in range(2):
        client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )

    resp_success = client.post(
        "/api/v1/auth/login",
        json={"email": test_email, "password": password},
    )
    assert resp_success.status_code == 200

    for _ in range(4):
        resp_retry = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword!"},
        )
        assert resp_retry.status_code == 401

    _clear_failures(account_key)
    _clear_failures(ip_key)


def test_nginx_configurations_ordering_and_rate_limiting():
    """Verify that Nginx configuration files define rate limit zones and order auth before generic API."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    ubuntu_conf = repo_root / "deploy" / "nginx" / "gvg.conf"
    docker_conf = repo_root / "deploy" / "nginx" / "nginx.prod.conf"

    assert ubuntu_conf.exists()
    assert docker_conf.exists()

    for path in (ubuntu_conf, docker_conf):
        content = path.read_text()
        assert "limit_req_zone $binary_remote_addr zone=api_general_limit:10m rate=30r/s;" in content
        assert "limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;" in content
        assert "limit_req_status 429;" in content
        assert "location ~ ^/api/v1/auth/(login|token)$ {" in content
        assert "limit_req zone=auth_limit burst=5 nodelay;" in content
        assert "limit_req zone=api_general_limit burst=20 nodelay;" in content

        # Check order: auth location must be declared before general api location
        idx_auth = content.find("location ~ ^/api/v1/auth/(login|token)$")
        idx_api = content.find("location ~ ^/(api|docs|redoc|openapi.json|health|webhooks)")
        assert idx_auth != -1 and idx_api != -1
        assert idx_auth < idx_api, f"In {path.name}, auth location block must appear before generic API block!"


def test_rotate_secrets_script_functional_and_syntax():
    """Verify scripts/rotate-secrets.sh passes bash syntax check and handles errors cleanly."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "rotate-secrets.sh"

    assert script_path.exists()
    content = script_path.read_text()
    assert "#!/usr/bin/env bash" in content
    assert "set -euo pipefail" in content
    assert "openssl rand -hex 32" in content

    # Test bash syntax
    syntax_check = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True)
    assert syntax_check.returncode == 0, f"Bash syntax error: {syntax_check.stderr}"

    # Non-root invocation should exit with code 1
    run_non_root = subprocess.run(["bash", str(script_path)], capture_output=True, text=True)
    assert run_non_root.returncode == 1
    assert "must be run as root" in run_non_root.stderr
