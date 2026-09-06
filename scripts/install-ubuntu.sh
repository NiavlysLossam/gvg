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
    log_error "This script must be run as root or with sudo."
    exit 1
fi

INSTALL_DIR="/opt/gvg"
DB_NAME="gvg"
DB_USER="gvg"
DB_PASSWORD="${GVG_DB_PASSWORD:-$(openssl rand -hex 16)}"
APP_USER="gvg"

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

# 4. PostgreSQL setup with PostGIS
log_info "Configuring PostgreSQL database and user..."
systemctl start postgresql
systemctl enable postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# 5. Project files copy / setup
log_info "Setting up application files in $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    cp -r "$SCRIPT_DIR/backend" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/frontend" "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR/deploy" "$INSTALL_DIR/"
fi

# 6. Backend virtualenv and dependencies
log_info "Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/backend/.venv"
"$INSTALL_DIR/backend/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/backend/.venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt"

# Create .env for backend
cat > "$INSTALL_DIR/backend/.env" <<EOF
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
ENVIRONMENT=production
CORS_ORIGINS=http://localhost
PROJECT_NAME="GVG (Gestion de Vide-Greniers)"
EOF

# Run database migrations
log_info "Running Alembic migrations..."
(
    cd "$INSTALL_DIR/backend"
    .venv/bin/alembic upgrade head
)

# 7. Frontend build
log_info "Building frontend assets..."
(
    cd "$INSTALL_DIR/frontend"
    npm install
    npm run build
)

# Set permissions
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

# 8. Systemd service configuration
log_info "Configuring systemd service..."
cp "$INSTALL_DIR/deploy/systemd/gvg.service" /etc/systemd/system/gvg.service
systemctl daemon-reload
systemctl enable gvg.service
systemctl restart gvg.service

# 9. Nginx configuration
log_info "Configuring Nginx reverse proxy..."
cp "$INSTALL_DIR/deploy/nginx/gvg.conf" /etc/nginx/sites-available/gvg.conf
ln -sf /etc/nginx/sites-available/gvg.conf /etc/nginx/sites-enabled/gvg.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

log_success "GVG has been successfully installed and started!"
log_info "Access GVG at: http://localhost"
log_info "API Docs available at: http://localhost/docs"
log_info "Database credentials saved in: $INSTALL_DIR/backend/.env"

