#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# Lightline VPN Panel — One-Line Installer
# Usage: sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/installer/install.sh)"
# ──────────────────────────────────────────────────────────────

REPO="https://github.com/Lightline-Panel/lightline-panel.git"
INSTALL_DIR="/opt/lightline"
COMPOSE_FILE="$INSTALL_DIR/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${CYAN}[Lightline]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Pre-flight checks ──

if [ "$EUID" -ne 0 ]; then
  err "Please run as root: sudo bash install.sh"
fi

log "Lightline VPN Panel Installer v1.0.0"
echo ""

# ── Check for existing installation ──

if [ -d "$INSTALL_DIR" ]; then
  warn "Existing installation found at $INSTALL_DIR"
  read -rp "Update existing installation? (y/N): " CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    log "Installation cancelled."
    exit 0
  fi
  UPDATE_MODE=true
else
  UPDATE_MODE=false
fi

# ── Install dependencies ──

install_docker() {
  if command -v docker &>/dev/null; then
    ok "Docker already installed: $(docker --version)"
    return
  fi
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
  ok "Docker installed"
}

install_docker_compose() {
  if docker compose version &>/dev/null; then
    ok "Docker Compose already available"
    return
  fi
  if command -v docker-compose &>/dev/null; then
    ok "Docker Compose (standalone) already installed"
    return
  fi
  log "Installing Docker Compose plugin..."
  apt-get update -qq
  apt-get install -y -qq docker-compose-plugin 2>/dev/null || {
    log "Installing Docker Compose standalone..."
    COMPOSE_VERSION=$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
    curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
  }
  ok "Docker Compose installed"
}

install_git() {
  if command -v git &>/dev/null; then
    ok "Git already installed"
    return
  fi
  log "Installing git..."
  apt-get update -qq
  apt-get install -y -qq git
  ok "Git installed"
}

log "Checking dependencies..."
install_docker
install_docker_compose
install_git

# ── Clone or update repository ──

if [ "$UPDATE_MODE" = true ]; then
  log "Updating repository..."
  cd "$INSTALL_DIR"
  git stash 2>/dev/null || true
  git pull origin main
  ok "Repository updated"
else
  log "Cloning repository..."
  git clone "$REPO" "$INSTALL_DIR"
  ok "Repository cloned to $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── Generate environment file ──

ENV_FILE="$INSTALL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  log "Generating environment configuration..."
  JWT_SECRET=$(openssl rand -hex 32)
  PG_PASSWORD=$(openssl rand -hex 16)

  cat > "$ENV_FILE" <<EOF
# Lightline VPN Panel — Environment Configuration
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

POSTGRES_PASSWORD=$PG_PASSWORD
JWT_SECRET=$JWT_SECRET
OUTLINE_MODE=mock
CORS_ORIGINS=http://localhost,http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'localhost')
PANEL_PORT=80
LICENSE_SERVER_URL=
EOF

  chmod 600 "$ENV_FILE"
  ok "Environment file created at $ENV_FILE"
else
  ok "Environment file already exists, keeping current configuration"
fi

# ── Build and start services ──

if docker compose version &>/dev/null; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"
fi

echo ""
log "═══════════════════════════════════════════════"
log "  Step 1/5: Pulling base images"
log "═══════════════════════════════════════════════"
log "Downloading PostgreSQL, Redis, Python, Node.js images..."
log "This may take a few minutes on first install."
$COMPOSE_CMD pull 2>&1 || true
ok "Base images pulled"

echo ""
log "═══════════════════════════════════════════════"
log "  Step 2/5: Building backend"
log "═══════════════════════════════════════════════"
log "Installing system packages and Python dependencies..."
log "This may take 2-5 minutes."
$COMPOSE_CMD build --progress=plain backend 2>&1
ok "Backend image built"

echo ""
log "═══════════════════════════════════════════════"
log "  Step 3/5: Building frontend"
log "═══════════════════════════════════════════════"
log "Installing Node.js packages and building React app..."
log "This may take 3-8 minutes."
$COMPOSE_CMD build --progress=plain frontend 2>&1
ok "Frontend image built"

echo ""
log "═══════════════════════════════════════════════"
log "  Step 4/5: Starting services"
log "═══════════════════════════════════════════════"
log "Starting PostgreSQL, Redis, backend, and frontend..."
$COMPOSE_CMD up -d 2>&1
ok "All services started"

echo ""
log "═══════════════════════════════════════════════"
log "  Step 5/5: Waiting for backend health check"
log "═══════════════════════════════════════════════"
log "Checking if backend is responding..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/system/health &>/dev/null; then
    ok "Backend is healthy and responding!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    warn "Backend not responding yet. This can be normal on first start."
    warn "Check logs with: $COMPOSE_CMD logs backend"
    warn "Wait a minute and try: curl http://127.0.0.1:8000/api/system/health"
  fi
  echo -ne "\r  Waiting... ($i/30)"
  sleep 2
done
echo ""

# ── Print summary ──

SERVER_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo 'YOUR_SERVER_IP')
PANEL_PORT=$(grep -E '^PANEL_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo '80')

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Lightline VPN Panel — Installation Complete${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Panel URL:    ${GREEN}http://${SERVER_IP}:${PANEL_PORT}${NC}"
echo -e "  Backend API:  ${GREEN}http://127.0.0.1:8000/api${NC}"
echo -e "  Install dir:  ${CYAN}${INSTALL_DIR}${NC}"
echo ""
echo -e "  Default login (mock mode):"
echo -e "    Username: ${YELLOW}admin${NC}"
echo -e "    Password: ${YELLOW}admin123${NC}"
echo ""
echo -e "  Useful commands:"
echo -e "    ${CYAN}cd $INSTALL_DIR && $COMPOSE_CMD logs -f${NC}        — View logs"
echo -e "    ${CYAN}cd $INSTALL_DIR && $COMPOSE_CMD restart${NC}        — Restart"
echo -e "    ${CYAN}cd $INSTALL_DIR && $COMPOSE_CMD down${NC}           — Stop"
echo -e "    ${CYAN}cd $INSTALL_DIR && $COMPOSE_CMD up -d --build${NC}  — Rebuild"
echo ""
echo -e "  License management:"
echo -e "    ${CYAN}$COMPOSE_CMD exec backend python cli.py license generate${NC}"
echo -e "    ${CYAN}$COMPOSE_CMD exec backend python cli.py license activate <KEY>${NC}"
echo -e "    ${CYAN}$COMPOSE_CMD exec backend python cli.py license show${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
echo ""
