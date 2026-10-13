#!/usr/bin/env bash
# ==============================================================================
# GVG (Gestion de Vide-Greniers) - Secure Secret Key Rotation Script
# Target: Native Ubuntu deployment (/opt/gvg/backend/.env)
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# 1. Privileges check
if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run as root or with sudo"
    exit 1
fi

TARGET_ENV="${1:-/opt/gvg/backend/.env}"
APP_USER="gvg"

if [ ! -f "$TARGET_ENV" ]; then
    log_error "Target environment file not found at: $TARGET_ENV"
    log_info "Usage: sudo $0 [/path/to/.env]"
    exit 1
fi

log_info "Rotating secrets for environment file: $TARGET_ENV"

# 2. Automated timestamped backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${TARGET_ENV}.bak.${TIMESTAMP}"
cp -p "$TARGET_ENV" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"
log_info "Created backup at: $BACKUP_FILE"

# 3. Generate strong cryptographic keys
NEW_JWT_SECRET="$(openssl rand -hex 32)"

# 4. Update JWT_SECRET_KEY in target .env (handles optional leading whitespace)
if grep -q -E '^\s*JWT_SECRET_KEY=' "$TARGET_ENV"; then
    sed -i -E "s|^\s*JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$NEW_JWT_SECRET|" "$TARGET_ENV"
else
    echo "JWT_SECRET_KEY=$NEW_JWT_SECRET" >> "$TARGET_ENV"
fi

# Ensure correct file permissions
chmod 600 "$TARGET_ENV"
chown "$APP_USER:$APP_USER" "$TARGET_ENV" 2>/dev/null || true

log_success "Successfully rotated JWT_SECRET_KEY (new length: ${#NEW_JWT_SECRET} chars)."

# 5. Restart application service if present and active
if systemctl is-active --quiet gvg.service 2>/dev/null; then
    log_info "Restarting gvg.service to apply new secrets..."
    systemctl restart gvg.service
    log_success "gvg.service restarted successfully."
else
    log_warn "gvg.service is not currently running. Please restart your application process to apply changes."
fi

log_success "Secret rotation completed successfully."

