import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import Settings


def test_fastapi_security_headers_middleware_success(client: TestClient):
    """Verify that global security headers are injected on normal API responses."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_fastapi_security_headers_on_validation_error(client: TestClient):
    """Verify security headers are retained on HTTP 422 validation errors."""
    resp = client.post("/api/v1/auth/login", data={})
    assert resp.status_code == 422
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_fastapi_security_headers_on_404_error(client: TestClient):
    """Verify security headers are retained on HTTP 404 not found errors."""
    resp = client.get("/api/v1/non_existent_endpoint")
    assert resp.status_code == 404
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_secure_static_files_headers(client: TestClient):
    """Verify that static files served via /uploads include CSP sandbox and anti-sniffing headers."""
    from app.core.config import settings
    upload_dir = settings.upload_dir_path
    dummy_file = upload_dir / "test_secure_static.png"
    dummy_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")

    # Also test an SVG file to ensure CSP sandbox is properly attached
    dummy_svg = upload_dir / "test_vector.svg"
    dummy_svg.write_text("<svg><circle cx='50' cy='50' r='40'/></svg>")

    try:
        resp = client.get("/uploads/test_secure_static.png")
        assert resp.status_code == 200
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("content-security-policy") == "default-src 'none'; sandbox"
        assert resp.headers.get("cache-control") == "public, max-age=86400"

        resp_svg = client.get("/uploads/test_vector.svg")
        assert resp_svg.status_code == 200
        assert resp_svg.headers.get("x-content-type-options") == "nosniff"
        assert resp_svg.headers.get("content-security-policy") == "default-src 'none'; sandbox"
    finally:
        if dummy_file.exists():
            dummy_file.unlink()
        if dummy_svg.exists():
            dummy_svg.unlink()


def test_cors_origins_validation_in_production():
    """Verify that CORS_ORIGINS rejects '*' when ENVIRONMENT is production or staging."""
    valid_key = "x" * 32

    # Should raise ValueError when wildcard '*' is present in production
    with pytest.raises(ValueError, match="Wildcard '\\*' is strictly forbidden in CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=valid_key,
            CORS_ORIGINS=["*"],
        )

    # Should also raise when wildcard has whitespace e.g. " * "
    with pytest.raises(ValueError, match="Wildcard '\\*' is strictly forbidden in CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=valid_key,
            CORS_ORIGINS=[" * "],
        )

    # Should also raise when wildcard is in list of multiple origins
    with pytest.raises(ValueError, match="Wildcard '\\*' is strictly forbidden in CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="staging",
            JWT_SECRET_KEY=valid_key,
            CORS_ORIGINS=["https://example.com", "*"],
        )

    # Should succeed with explicit origin in production
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=valid_key,
        CORS_ORIGINS=["https://gvg.example.com"],
    )
    assert prod_settings.CORS_ORIGINS == ["https://gvg.example.com"]

    # In development/test, wildcard is tolerated for local convenience
    dev_settings = Settings(
        ENVIRONMENT="development",
        JWT_SECRET_KEY=valid_key,
        CORS_ORIGINS=["*"],
    )
    assert dev_settings.CORS_ORIGINS == ["*"]

    test_settings = Settings(
        ENVIRONMENT="test",
        JWT_SECRET_KEY=valid_key,
        CORS_ORIGINS=["*"],
    )
    assert test_settings.CORS_ORIGINS == ["*"]


def test_nginx_configurations_contain_security_headers():
    """Verify that Nginx configuration files contain required hardening directives in both Ubuntu and Docker configs."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    ubuntu_conf = repo_root / "deploy" / "nginx" / "gvg.conf"
    docker_conf = repo_root / "deploy" / "nginx" / "nginx.prod.conf"

    assert ubuntu_conf.exists(), "deploy/nginx/gvg.conf must exist"
    assert docker_conf.exists(), "deploy/nginx/nginx.prod.conf must exist"

    ubuntu_text = ubuntu_conf.read_text()
    docker_text = docker_conf.read_text()

    for text in (ubuntu_text, docker_text):
        assert "server_tokens off;" in text
        assert 'add_header X-Frame-Options "DENY" always;' in text
        assert 'add_header X-Content-Type-Options "nosniff" always;' in text
        assert 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' in text
        assert 'add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;' in text
        assert "location ^~ /uploads/ {" in text
        assert 'add_header Content-Security-Policy "default-src \'none\'; sandbox" always;' in text
        # Verify script execution blocking is present in both configs
        assert "location ~* \\.(php|pl|py|cgi|sh|bash|exe|bat|cmd|ps1|vbs|jar|html|htm|shtml)$ {" in text
        assert "return 403;" in text
