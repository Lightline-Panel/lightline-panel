#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Lightline VPN Panel — Updater
# ──────────────────────────────────────────────────────────────

INSTALL_DIR="/opt/lightline"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${CYAN}[Lightline]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

if [ "$EUID" -ne 0 ]; then
  err "Please run as root: sudo bash update.sh"
fi

if [ ! -d "$INSTALL_DIR" ]; then
  err "Lightline is not installed at $INSTALL_DIR. Run install.sh first."
fi

cd "$INSTALL_DIR"

if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi

log "Creating backup before update..."
$COMPOSE_CMD exec -T backend python cli.py license show 2>/dev/null || true

log "Pulling latest changes..."
git stash 2>/dev/null || true
git pull origin main
ok "Repository updated"

log "Rebuilding containers..."
$COMPOSE_CMD build --no-cache
$COMPOSE_CMD up -d

log "Waiting for backend..."
for i in $(seq 1 20); do
  if curl -sf http://127.0.0.1:8000/api/system/health &>/dev/null; then
    ok "Backend is healthy"
    break
  fi
  [ "$i" -eq 20 ] && warn "Backend not responding yet"
  sleep 2
done

echo ""
ok "Lightline VPN Panel updated successfully."
echo ""
