import os
import stat
import subprocess
from pathlib import Path
import yaml
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEPLOY_DIR = REPO_ROOT / "deploy"


# ------------------------------------------------------------------------------
# 1. Validation de la syntaxe Bash (bash -n) & Exécution de l'Entrypoint
# ------------------------------------------------------------------------------

def test_bash_syntax_install_ubuntu():
    """Vérifie la conformité syntaxique du script d'installation Ubuntu via bash -n."""
    script_path = SCRIPTS_DIR / "install-ubuntu.sh"
    assert script_path.exists(), f"{script_path} n'existe pas"
    
    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Erreur de syntaxe bash dans {script_path}: {result.stderr}"


def test_bash_syntax_backend_entrypoint():
    """Vérifie la conformité syntaxique du script d'entrypoint Docker backend."""
    entrypoint_path = BACKEND_DIR / "entrypoint.sh"
    assert entrypoint_path.exists(), f"{entrypoint_path} n'existe pas"
    
    result = subprocess.run(
        ["bash", "-n", str(entrypoint_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Erreur de syntaxe bash dans {entrypoint_path}: {result.stderr}"


def test_entrypoint_script_properties():
    """Vérifie les permissions exécutables et le contenu fonctionnel de entrypoint.sh."""
    entrypoint_path = BACKEND_DIR / "entrypoint.sh"
    assert os.access(entrypoint_path, os.X_OK), "backend/entrypoint.sh doit être exécutable (+x)"
    
    content = entrypoint_path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content or "set -e" in content
    assert "alembic upgrade head" in content, "entrypoint.sh doit exécuter les migrations Alembic"
    assert 'exec "$@"' in content or 'exec "$*"' in content, "entrypoint.sh doit passer la main à la commande avec exec"


def test_entrypoint_execution_success(tmp_path):
    """Vérifie l'exécution réelle de entrypoint.sh avec succès de migration et passage d'arguments."""
    entrypoint_path = BACKEND_DIR / "entrypoint.sh"
    
    # Créer un faux binaire alembic dans un dossier temporaire
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_alembic = bin_dir / "alembic"
    fake_alembic.write_text("#!/usr/bin/env bash\necho 'Fake alembic migration OK'\nexit 0\n")
    fake_alembic.chmod(0o755)
    
    custom_env = os.environ.copy()
    custom_env["PATH"] = f"{bin_dir}:{custom_env.get('PATH', '')}"
    custom_env["MIGRATION_MAX_RETRIES"] = "3"
    custom_env["MIGRATION_RETRY_INTERVAL"] = "0"
    
    result = subprocess.run(
        [str(entrypoint_path), "echo", "HELLOFROMENTRYPOINT"],
        capture_output=True,
        text=True,
        env=custom_env
    )
    assert result.returncode == 0, f"Erreur d'exécution: {result.stderr}"
    assert "Migrations Alembic appliquées avec succès" in result.stdout
    assert "HELLOFROMENTRYPOINT" in result.stdout


def test_entrypoint_execution_failure_retry(tmp_path):
    """Vérifie que entrypoint.sh échoue avec code 1 après épuisement des tentatives."""
    entrypoint_path = BACKEND_DIR / "entrypoint.sh"
    
    # Créer un faux binaire alembic qui échoue toujours
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_alembic = bin_dir / "alembic"
    fake_alembic.write_text("#!/usr/bin/env bash\necho 'DB unavailable' >&2\nexit 1\n")
    fake_alembic.chmod(0o755)
    
    custom_env = os.environ.copy()
    custom_env["PATH"] = f"{bin_dir}:{custom_env.get('PATH', '')}"
    custom_env["MIGRATION_MAX_RETRIES"] = "2"
    custom_env["MIGRATION_RETRY_INTERVAL"] = "0"
    
    result = subprocess.run(
        [str(entrypoint_path), "echo", "SHOULDNOTRUN"],
        capture_output=True,
        text=True,
        env=custom_env
    )
    assert result.returncode == 1
    assert "Échec de l'application des migrations Alembic" in result.stderr
    assert "SHOULDNOTRUN" not in result.stdout


# ------------------------------------------------------------------------------
# 2. Validation du Dockerfile Backend
# ------------------------------------------------------------------------------

def test_backend_dockerfile_configuration():
    """Vérifie que backend/Dockerfile installe WeasyPrint, les polices et déclare l'entrypoint."""
    dockerfile_path = BACKEND_DIR / "Dockerfile"
    assert dockerfile_path.exists(), "backend/Dockerfile n'existe pas"
    
    content = dockerfile_path.read_text(encoding="utf-8")
    
    # Base image Python 3.12
    assert "python:3.12" in content
    
    # Dépendances C WeasyPrint et polices Liberation
    assert "libcairo2" in content
    assert "libpango-1.0-0" in content
    assert "shared-mime-info" in content
    assert "fonts-liberation" in content, "fonts-liberation doit être installé pour le rendu PDF WeasyPrint"
    
    # Entrypoint
    assert "entrypoint.sh" in content
    assert 'ENTRYPOINT ["/app/entrypoint.sh"]' in content or "ENTRYPOINT" in content
    assert "uvicorn" in content


# ------------------------------------------------------------------------------
# 3. Validation de Docker Compose (Dev et Prod)
# ------------------------------------------------------------------------------

def test_docker_compose_dev_structure():
    """Valide la structure et les invariants du docker-compose.yml de développement."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml n'existe pas"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    assert "services" in config, "docker-compose.yml doit définir un bloc services"
    services = config["services"]
    
    assert "db" in services
    assert "backend" in services
    assert "frontend" in services
    
    # Service db
    db_service = services["db"]
    assert "postgis" in db_service.get("image", "").lower()
    assert "healthcheck" in db_service
    assert "pg_isready" in str(db_service["healthcheck"].get("test", ""))
    
    # Service backend
    backend_service = services["backend"]
    assert "depends_on" in backend_service
    db_dependency = backend_service["depends_on"]
    if isinstance(db_dependency, dict):
        assert "db" in db_dependency
        assert db_dependency["db"].get("condition") == "service_healthy"
    else:
        assert "db" in db_dependency
    
    # Prise en charge de .env
    assert "env_file" in backend_service or "env_file" in db_service


def test_docker_compose_prod_structure():
    """Valide la configuration Docker Compose de production avec Nginx sur le port 80."""
    prod_compose_path = REPO_ROOT / "docker-compose.prod.yml"
    assert prod_compose_path.exists(), "docker-compose.prod.yml n'existe pas"
    
    with open(prod_compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    assert "services" in config
    services = config["services"]
    
    assert "db" in services
    assert "backend" in services
    assert "frontend" in services
    assert "nginx" in services, "docker-compose.prod.yml doit inclure un reverse proxy Nginx"
    
    # Nginx reverse proxy sur le port 80
    nginx_service = services["nginx"]
    nginx_ports = [str(p) for p in nginx_service.get("ports", [])]
    assert any("80:80" in p or p == "80" for p in nginx_ports), "Nginx doit exposer le port 80"
    
    # Dépendance frontend buildée avec succès
    nginx_deps = nginx_service.get("depends_on", {})
    assert isinstance(nginx_deps, dict)
    assert "frontend" in nginx_deps
    assert nginx_deps["frontend"].get("condition") == "service_completed_successfully"
    
    # Service DB PostGIS avec healthcheck
    db_service = services["db"]
    assert "postgis" in db_service.get("image", "").lower()
    assert "healthcheck" in db_service
    
    # Service Backend
    backend_service = services["backend"]
    assert "depends_on" in backend_service
    assert "env_file" in backend_service


# ------------------------------------------------------------------------------
# 4. Validation du Fichier Modèle Universel .env.example
# ------------------------------------------------------------------------------

def test_env_example_completeness_and_documentation():
    """Vérifie que .env.example est documenté en français et contient toutes les variables requises."""
    env_example_path = REPO_ROOT / ".env.example"
    assert env_example_path.exists(), ".env.example n'existe pas à la racine du projet"
    
    content = env_example_path.read_text(encoding="utf-8")
    
    # Clés requises
    required_keys = [
        "PROJECT_NAME",
        "ENVIRONMENT",
        "DATABASE_URL",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "FRONTEND_BASE_URL",
        "VITE_API_URL",
        "CORS_ORIGINS",
        "STRIPE_SECRET_KEY",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "EMAILS_FROM_EMAIL",
    ]
    
    for key in required_keys:
        assert f"{key}=" in content or f"{key} =" in content, f"Variable manquante dans .env.example : {key}"
    
    # Documentation en français
    assert "BASE DE DONNÉES" in content or "base de données" in content
    assert "STRIPE" in content or "Stripe" in content
    assert "SMTP" in content or "e-mails" in content or "emails" in content


def test_cors_origins_parsing_comma_separated(monkeypatch):
    """Vérifie que pydantic-settings gère les chaînes séparées par des virgules sans erreur JSON."""
    monkeypatch.setenv("CORS_ORIGINS", "http://34.140.50.12,http://localhost:5173")
    from app.core.config import Settings
    s = Settings()
    assert s.CORS_ORIGINS == ["http://34.140.50.12", "http://localhost:5173"]


# ------------------------------------------------------------------------------
# 5. Validation du Service Systemd
# ------------------------------------------------------------------------------

def test_systemd_service_file():
    """Valide la présence et la configuration du service systemd gvg.service."""
    service_path = DEPLOY_DIR / "systemd" / "gvg.service"
    assert service_path.exists(), "deploy/systemd/gvg.service n'existe pas"
    
    content = service_path.read_text(encoding="utf-8")
    
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    
    assert "User=gvg" in content
    assert "WorkingDirectory=/opt/gvg/backend" in content
    assert "PYTHONPATH=/opt/gvg/backend" in content, "PYTHONPATH explicite requis dans gvg.service"
    assert "EnvironmentFile=/opt/gvg/backend/.env" in content
    assert "Restart=always" in content
    assert "WantedBy=multi-user.target" in content


# ------------------------------------------------------------------------------
# 6. Validation des Fichiers de Configuration Nginx
# ------------------------------------------------------------------------------

def test_nginx_native_configuration():
    """Valide la configuration Nginx pour installation native Ubuntu (gvg.conf)."""
    nginx_conf_path = DEPLOY_DIR / "nginx" / "gvg.conf"
    assert nginx_conf_path.exists(), "deploy/nginx/gvg.conf n'existe pas"
    
    content = nginx_conf_path.read_text(encoding="utf-8")
    
    assert "listen 80;" in content
    assert "root /opt/gvg/frontend/dist;" in content
    assert "try_files $uri $uri/ /index.html;" in content
    assert "proxy_pass http://127.0.0.1:8000;" in content
    assert "api" in content
    assert "docs" in content
    assert "health" in content
    assert "webhooks" in content, "gvg.conf doit router les webhooks Stripe vers le backend"


def test_nginx_prod_configuration():
    """Valide la configuration Nginx pour conteneur Docker de production (nginx.prod.conf)."""
    nginx_prod_path = DEPLOY_DIR / "nginx" / "nginx.prod.conf"
    assert nginx_prod_path.exists(), "deploy/nginx/nginx.prod.conf n'existe pas"
    
    content = nginx_prod_path.read_text(encoding="utf-8")
    
    assert "listen 80;" in content
    assert "try_files $uri $uri/ /index.html;" in content
    assert "proxy_pass http://backend:8000;" in content
    assert "api" in content
    assert "docs" in content
    assert "health" in content
    assert "webhooks" in content, "nginx.prod.conf doit router les webhooks Stripe vers le backend"


# ------------------------------------------------------------------------------
# 7. Validation du Script d'Installation Ubuntu (install-ubuntu.sh)
# ------------------------------------------------------------------------------

def test_install_ubuntu_script_content():
    """Vérifie la conformité et la robustesse du script scripts/install-ubuntu.sh."""
    script_path = SCRIPTS_DIR / "install-ubuntu.sh"
    assert script_path.exists()
    assert os.access(script_path, os.X_OK), "scripts/install-ubuntu.sh doit être exécutable"
    
    content = script_path.read_text(encoding="utf-8")
    
    # Sécurité et idempotence
    assert "set -euo pipefail" in content
    assert 'This script must be run as root or with sudo' in content
    assert 'exit 1' in content
    
    # Paquets APT requis
    assert "postgresql" in content
    assert "postgis" in content
    assert "python3" in content
    assert "nginx" in content
    assert "fonts-liberation" in content, "fonts-liberation doit être installé par le script Ubuntu"
    assert "libcairo2" in content
    assert "libpango-1.0-0" in content
    
    # Gestion du fichier .env
    assert ".env" in content
    assert ".env.example" in content
    assert "openssl rand -hex 16" in content, "Génération d'un mot de passe fort via openssl"
    
    # Exécution des migrations Alembic
    assert "alembic upgrade head" in content
    
    # Configuration des services
    assert "gvg.service" in content
    assert "systemctl enable gvg.service" in content
    assert "systemctl enable nginx" in content, "nginx doit être activé au démarrage"
    assert "GRANT ALL ON SCHEMA public" in content, "Permissions schéma public PostgreSQL 15+"


def test_install_ubuntu_sed_env_substitution(tmp_path):
    """Vérifie que les commandes sed du script produisent un .env valide et cohérent."""
    target_env = tmp_path / ".env"
    env_example = REPO_ROOT / ".env.example"
    target_env.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
    
    # Exécuter les commandes sed telles que définies dans install-ubuntu.sh
    generated_db_pass = "a1b2c3d4e5f67890"
    sed_script = f"""
    sed -i -E "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD={generated_db_pass}|" "{target_env}"
    sed -i -E "s|^DATABASE_URL=\\"?postgresql\\+psycopg://([^:]+):([^@]+)@([^:]+):5432/([^\\"[:space:]]*)\\"?|DATABASE_URL=postgresql+psycopg://\\1:{generated_db_pass}@localhost:5432/\\4|" "{target_env}"
    sed -i -E "s|^ENVIRONMENT=.*|ENVIRONMENT=production|" "{target_env}"
    """
    res = subprocess.run(["bash", "-c", sed_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Sed script failed: {res.stderr}"
    
    modified_content = target_env.read_text(encoding="utf-8")
    assert f"POSTGRES_PASSWORD={generated_db_pass}" in modified_content
    assert f"postgresql+psycopg://gvg:{generated_db_pass}@localhost:5432/gvg" in modified_content
    assert "ENVIRONMENT=production" in modified_content
