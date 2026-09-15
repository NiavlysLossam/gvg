#!/usr/bin/env bash
# ==============================================================================
# GVG (Gestion de Vide-Greniers) - Automated Ubuntu Installation Script
# Target OS: Ubuntu 22.04 LTS / Ubuntu 24.04 LTS (x86_64 / arm64)
# Implements: AD-8 (Native Linux Deployment)
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# 1. Root / Sudo check
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run as root or with sudo"
    exit 1
fi

INSTALL_DIR="/opt/gvg"
APP_USER="gvg"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_ENV="$INSTALL_DIR/backend/.env"
SOURCE_ENV="$SCRIPT_DIR/.env"
SOURCE_ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

log_info "Starting GVG installation on Ubuntu..."

# 2. System update & packages installation
log_info "Installing system packages, PostgreSQL, PostGIS, Python, Nginx..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    "curl" \
    "git" \
    "build-essential" \
    "python3" \
    "python3-venv" \
    "python3-pip" \
    "python3-dev" \
    "postgresql" \
    "postgresql-contrib" \
    "postgis" \
    "postgresql-*-postgis-*" \
    "nginx" \
    "libcairo2" \
    "libpango-1.0-0" \
    "libpangocairo-1.0-0" \
    "libgdk-pixbuf2.0-0" \
    "shared-mime-info" \
    "fonts-liberation" \
    "libpq-dev" \
    "ca-certificates" \
    "openssl"

# Install Node.js 20 LTS if node is not found
if ! command -v node >/dev/null 2>&1; then
    log_info "Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# 3. Dedicated system user
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    log_info "Creating system user $APP_USER..."
    useradd -m -s /bin/bash "$APP_USER"
fi

# 4. Project files setup in $INSTALL_DIR
log_info "Setting up application files in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# Preserve existing target .env during directory copy
TEMP_BACKUP_ENV=""
if [ -f "$TARGET_ENV" ]; then
    TEMP_BACKUP_ENV="$(mktemp)"
    cp "$TARGET_ENV" "$TEMP_BACKUP_ENV"
fi

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r "$SCRIPT_DIR/backend" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/frontend" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/deploy" "$INSTALL_DIR/"
fi

# Restore target .env if it was present
if [ -n "$TEMP_BACKUP_ENV" ] && [ -f "$TEMP_BACKUP_ENV" ]; then
    cp "$TEMP_BACKUP_ENV" "$TARGET_ENV"
    rm -f "$TEMP_BACKUP_ENV"
fi

# 5. Environment configuration (.env)
if [ -f "$TARGET_ENV" ]; then
    log_info "Existing .env found at $TARGET_ENV. Preserving existing configuration."
elif [ -f "$SOURCE_ENV" ]; then
    log_info "Source .env found at $SOURCE_ENV. Copying to $TARGET_ENV..."
    cp "$SOURCE_ENV" "$TARGET_ENV"
elif [ -f "$SOURCE_ENV_EXAMPLE" ]; then
    log_info "No .env found. Initializing from $SOURCE_ENV_EXAMPLE..."
    cp "$SOURCE_ENV_EXAMPLE" "$TARGET_ENV"
    # Generate a strong DB password
    GENERATED_DB_PASS="$(openssl rand -hex 16)"
    sed -i -E "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$GENERATED_DB_PASS|" "$TARGET_ENV"
    sed -i -E "s|^DATABASE_URL=\"?postgresql\+psycopg://([^:]+):([^@]+)@([^:]+):5432/([^\"[:space:]]*)\"?|DATABASE_URL=postgresql+psycopg://\1:$GENERATED_DB_PASS@localhost:5432/\4|" "$TARGET_ENV"
    sed -i -E "s|^ENVIRONMENT=.*|ENVIRONMENT=production|" "$TARGET_ENV"
    log_info "Strong database password generated in $TARGET_ENV."
else
    log_warn ".env.example not found. Creating default production configuration..."
    GENERATED_DB_PASS="$(openssl rand -hex 16)"
    cat > "$TARGET_ENV" <<EOF
POSTGRES_USER=gvg
POSTGRES_PASSWORD=$GENERATED_DB_PASS
POSTGRES_DB=gvg
DATABASE_URL=postgresql+psycopg://gvg:$GENERATED_DB_PASS@localhost:5432/gvg
ENVIRONMENT=production
PROJECT_NAME="GVG (Gestion de Vide-Greniers)"
CORS_ORIGINS=http://localhost
EOF
fi

chmod 600 "$TARGET_ENV"
chown "$APP_USER:$APP_USER" "$TARGET_ENV"

# Extract DB credentials from $TARGET_ENV
DB_USER=$(grep -E '^\s*POSTGRES_USER=' "$TARGET_ENV" | head -n 1 | cut -d '=' -f2- | tr -d ' "' | tr -d "'" || true)
[ -z "$DB_USER" ] && DB_USER="gvg"

DB_PASSWORD=$(grep -E '^\s*POSTGRES_PASSWORD=' "$TARGET_ENV" | head -n 1 | cut -d '=' -f2- | tr -d ' "' | tr -d "'" || true)
if [ -z "$DB_PASSWORD" ]; then
    DB_PASSWORD=$(grep -E '^\s*DATABASE_URL=' "$TARGET_ENV" | head -n 1 | sed -n 's/.*:\([^@]*\)@.*/\1/p' || true)
fi
[ -z "$DB_PASSWORD" ] && DB_PASSWORD="$(openssl rand -hex 16)"

DB_NAME=$(grep -E '^\s*POSTGRES_DB=' "$TARGET_ENV" | head -n 1 | cut -d '=' -f2- | tr -d ' "' | tr -d "'" || true)
[ -z "$DB_NAME" ] && DB_NAME="gvg"

# 6. PostgreSQL setup with PostGIS
log_info "Configuring PostgreSQL database and user..."
systemctl start postgresql
systemctl enable postgresql

# Wait for PostgreSQL service (timeout 30s)
PG_WAIT_COUNT=0
until pg_isready -q 2>/dev/null || pg_isready -h localhost -p 5432 -q 2>/dev/null; do
    PG_WAIT_COUNT=$((PG_WAIT_COUNT + 1))
    if [ "$PG_WAIT_COUNT" -ge 30 ]; then
        log_error "PostgreSQL did not become ready after 30 seconds."
        exit 1
    fi
    sleep 1
done

sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d "$DB_NAME" -c "ALTER SCHEMA public OWNER TO $DB_USER;"

# 7. Backend virtualenv and dependencies
log_info "Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/backend/.venv"
"$INSTALL_DIR/backend/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/backend/.venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"

# Run database migrations
log_info "Running Alembic migrations..."
(
    cd "$INSTALL_DIR/backend"
    .venv/bin/alembic upgrade head
)

# 8. Frontend build
log_info "Building frontend assets..."
(
    cd "$INSTALL_DIR/frontend"
    npm install
    npm run build
)

# Set permissions
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

# 9. Systemd service configuration
log_info "Configuring systemd service..."
cp "$INSTALL_DIR/deploy/systemd/gvg.service" /etc/systemd/system/gvg.service
systemctl daemon-reload
systemctl enable gvg.service
systemctl restart gvg.service

# 10. Nginx configuration
log_info "Configuring Nginx reverse proxy..."
cp "$INSTALL_DIR/deploy/nginx/gvg.conf" /etc/nginx/sites-available/gvg.conf
ln -sf /etc/nginx/sites-available/gvg.conf /etc/nginx/sites-enabled/gvg.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

log_success "GVG has been successfully installed and started!"
log_info "Access GVG at: http://localhost"
log_info "API Docs available at: http://localhost/docs"
log_info "Database credentials saved in: $INSTALL_DIR/backend/.env"
