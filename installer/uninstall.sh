#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Lightline VPN Panel — Uninstaller
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
  err "Please run as root: sudo bash uninstall.sh"
fi

if [ ! -d "$INSTALL_DIR" ]; then
  err "Lightline is not installed at $INSTALL_DIR"
fi

echo ""
warn "This will stop all Lightline services and remove the installation."
warn "Database volumes will be preserved unless you pass --purge."
echo ""
read -rp "Are you sure? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  log "Uninstall cancelled."
  exit 0
fi

cd "$INSTALL_DIR"

log "Stopping services..."
if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi

$COMPOSE_CMD down

if [[ "${1:-}" == "--purge" ]]; then
  log "Removing Docker volumes..."
  $COMPOSE_CMD down -v
  ok "Volumes removed"
fi

log "Removing installation directory..."
rm -rf "$INSTALL_DIR"

ok "Lightline VPN Panel has been uninstalled."
echo ""
echo -e "  Docker and its images were ${YELLOW}not${NC} removed."
echo -e "  To remove unused Docker images: ${CYAN}docker image prune -a${NC}"
echo ""
