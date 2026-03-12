#!/usr/bin/env bash
set -e

# ══════════════════════════════════════════════════════════════
# Lightline VPN Panel — Management Script
# Usage:
#   Quick install:
#     sudo bash -c "$(curl -sL https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/lightline.sh)" @ install
#   After install, use:
#     lightline <command>
# ══════════════════════════════════════════════════════════════

APP_NAME="lightline"
INSTALL_DIR="/opt/lightline"
DATA_DIR="/var/lib/lightline"
COMPOSE_FILE="$INSTALL_DIR/docker-compose.yml"
ENV_FILE="$INSTALL_DIR/.env"
REPO_URL="https://github.com/Lightline-Panel/lightline-panel.git"
SCRIPT_URL="https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/lightline.sh"

# ── Colors ──

colorize() {
    local color=$1; local text=$2
    case $color in
        red)     printf "\e[91m%s\e[0m\n" "$text" ;;
        green)   printf "\e[92m%s\e[0m\n" "$text" ;;
        yellow)  printf "\e[93m%s\e[0m\n" "$text" ;;
        blue)    printf "\e[94m%s\e[0m\n" "$text" ;;
        cyan)    printf "\e[96m%s\e[0m\n" "$text" ;;
        *)       echo "$text" ;;
    esac
}

# ── Helpers ──

check_root() {
    if [ "$(id -u)" != "0" ]; then
        colorize red "Error: This command must be run as root."
        exit 1
    fi
}

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE="docker compose"
    elif docker-compose version >/dev/null 2>&1; then
        COMPOSE="docker-compose"
    else
        colorize red "Error: docker compose not found. Install Docker first."
        exit 1
    fi
}

is_installed() {
    [ -d "$INSTALL_DIR" ] && [ -f "$COMPOSE_FILE" ]
}

check_installed() {
    if ! is_installed; then
        colorize red "Lightline is not installed. Run: lightline install"
        exit 1
    fi
}

get_server_ip() {
    hostname -I 2>/dev/null | awk '{print $1}' || curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP"
}

install_lightline_script() {
    colorize blue "Installing 'lightline' command..."
    # Install this script to /usr/local/bin/lightline
    curl -sSL "$SCRIPT_URL" | install -m 755 /dev/stdin /usr/local/bin/lightline 2>/dev/null || {
        # Fallback: copy from local if curl fails
        if [ -f "$INSTALL_DIR/lightline.sh" ]; then
            install -m 755 "$INSTALL_DIR/lightline.sh" /usr/local/bin/lightline
        fi
    }
    colorize green "'lightline' command installed. You can now use: lightline <command>"
}

# ══════════════════════════════════════════════════════════════
# COMMANDS
# ══════════════════════════════════════════════════════════════

# ── install ──

install_cmd() {
    check_root

    colorize cyan "══════════════════════════════════════════════"
    colorize cyan "   Lightline VPN Panel — Installer"
    colorize cyan "══════════════════════════════════════════════"
    echo ""

    if is_installed; then
        colorize yellow "Lightline is already installed at $INSTALL_DIR"
        printf "Do you want to update instead? (y/N): "
        read -r confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            update_cmd
            return
        fi
        colorize yellow "Installation cancelled."
        return
    fi

    # Install Docker if needed
    if ! command -v docker &>/dev/null; then
        colorize blue "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        colorize green "Docker installed"
    else
        colorize green "Docker already installed: $(docker --version)"
    fi

    # Install git if needed
    if ! command -v git &>/dev/null; then
        colorize blue "Installing git..."
        apt-get update -qq && apt-get install -y -qq git
        colorize green "Git installed"
    fi

    # Clone repository
    colorize blue "Cloning Lightline repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    colorize green "Repository cloned to $INSTALL_DIR"

    cd "$INSTALL_DIR"

    # Generate .env
    if [ ! -f "$ENV_FILE" ]; then
        colorize blue "Generating configuration..."

        local server_ip
        server_ip=$(get_server_ip)

        local jwt_secret pg_password
        jwt_secret=$(openssl rand -hex 32)
        pg_password=$(openssl rand -hex 16)

        printf "Enter your server's public IP [%s]: " "$server_ip"
        read -r input_ip
        [ -n "$input_ip" ] && server_ip="$input_ip"

        local panel_port=80
        printf "Panel port [%s]: " "$panel_port"
        read -r input_port
        [ -n "$input_port" ] && panel_port="$input_port"

        local ss_port=8388
        printf "Shadowsocks port [%s]: " "$ss_port"
        read -r input_ss
        [ -n "$input_ss" ] && ss_port="$input_ss"

        cat > "$ENV_FILE" <<EOF
# Lightline VPN Panel — Configuration
# Generated on $(date -u +"%Y-%m-%dT%H:%M:%SZ")

POSTGRES_PASSWORD=$pg_password
JWT_SECRET=$jwt_secret
SERVER_IP=$server_ip
SS_PORT=$ss_port
PANEL_PORT=$panel_port
CORS_ORIGINS=http://$server_ip,http://$server_ip:$panel_port,http://localhost
EOF

        chmod 600 "$ENV_FILE"
        colorize green "Configuration saved to $ENV_FILE"
    fi

    # Create data directory
    mkdir -p "$DATA_DIR"

    # Build and start
    detect_compose

    echo ""
    colorize blue "[1/4] Pulling base images..."
    $COMPOSE pull 2>&1 || true

    echo ""
    colorize blue "[2/4] Building backend..."
    $COMPOSE build --progress=plain backend 2>&1

    echo ""
    colorize blue "[3/4] Building frontend..."
    $COMPOSE build --progress=plain frontend 2>&1

    echo ""
    colorize blue "[4/4] Starting services..."
    $COMPOSE up -d 2>&1
    colorize green "All services started"

    # Wait for backend
    echo ""
    colorize blue "Waiting for backend to be ready..."
    for i in $(seq 1 30); do
        if curl -sf http://127.0.0.1:8000/api/system/health &>/dev/null; then
            colorize green "Backend is healthy!"
            break
        fi
        [ "$i" -eq 30 ] && colorize yellow "Backend not responding yet. Check: lightline logs"
        printf "\r  Waiting... (%d/30)" "$i"
        sleep 2
    done
    echo ""

    # Install the lightline command
    install_lightline_script

    # Print summary
    local server_ip_env
    server_ip_env=$(grep -E '^SERVER_IP=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "$server_ip")
    local panel_port_env
    panel_port_env=$(grep -E '^PANEL_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "80")

    echo ""
    colorize cyan "══════════════════════════════════════════════"
    colorize green "  Lightline VPN Panel — Installed!"
    colorize cyan "══════════════════════════════════════════════"
    echo ""
    echo "  Panel URL:    http://${server_ip_env}:${panel_port_env}"
    echo "  Install dir:  ${INSTALL_DIR}"
    echo ""
    colorize yellow "  Next steps:"
    echo "  1. Create admin account:"
    colorize cyan "     lightline admin create"
    echo "  2. Activate your license:"
    colorize cyan "     lightline license activate <KEY>"
    echo "  3. Open the panel in your browser"
    echo ""
    colorize cyan "  Type 'lightline' to see all available commands."
    colorize cyan "══════════════════════════════════════════════"
    echo ""
}

# ── uninstall ──

uninstall_cmd() {
    check_root
    check_installed

    echo ""
    colorize red "══════════════════════════════════════════════"
    colorize red "  WARNING: This will completely remove"
    colorize red "  Lightline VPN Panel from this server."
    colorize red "══════════════════════════════════════════════"
    echo ""

    printf "Type 'DELETE' to confirm complete removal: "
    read -r confirm
    if [ "$confirm" != "DELETE" ]; then
        colorize yellow "Uninstall cancelled."
        return
    fi

    cd "$INSTALL_DIR"
    detect_compose

    colorize blue "Stopping all services..."
    $COMPOSE down 2>&1 || true

    printf "Also remove database volumes (all data will be lost)? (y/N): "
    read -r purge
    if [[ "$purge" =~ ^[Yy]$ ]]; then
        colorize blue "Removing Docker volumes..."
        $COMPOSE down -v 2>&1 || true
        colorize green "Volumes removed"
    fi

    colorize blue "Removing installation directory..."
    rm -rf "$INSTALL_DIR"

    colorize blue "Removing data directory..."
    rm -rf "$DATA_DIR"

    # Remove the lightline command
    if [ -f /usr/local/bin/lightline ]; then
        rm -f /usr/local/bin/lightline
        colorize green "'lightline' command removed"
    fi

    echo ""
    colorize green "Lightline VPN Panel has been completely removed."
    echo ""
    echo "  Docker and its images were NOT removed."
    colorize cyan "  To clean up Docker images: docker image prune -a"
    echo ""
}

# ── update ──

update_cmd() {
    check_root
    check_installed

    cd "$INSTALL_DIR"
    detect_compose

    colorize cyan "══════════════════════════════════════════════"
    colorize cyan "   Lightline VPN Panel — Update"
    colorize cyan "══════════════════════════════════════════════"
    echo ""

    colorize blue "Pulling latest changes..."
    git stash 2>/dev/null || true
    git pull origin main
    colorize green "Repository updated"

    echo ""
    colorize blue "Rebuilding containers (no cache)..."
    # --no-cache ensures the frontend picks up all code changes (theme, i18n, etc.)
    # We only stop backend/frontend — postgres and redis stay running to preserve data
    $COMPOSE stop backend frontend 2>/dev/null || true
    $COMPOSE build --no-cache backend frontend
    $COMPOSE up -d
    colorize green "Containers rebuilt and restarted"

    # Update the script itself
    install_lightline_script

    # Wait for backend
    colorize blue "Waiting for backend..."
    for i in $(seq 1 20); do
        if curl -sf http://127.0.0.1:8000/api/system/health &>/dev/null; then
            colorize green "Backend is healthy!"
            break
        fi
        [ "$i" -eq 20 ] && colorize yellow "Backend not responding yet. Check: lightline logs"
        sleep 2
    done

    echo ""
    colorize green "Lightline VPN Panel updated successfully."
    colorize green "Database and license preserved."
    echo ""
}

# ── start / stop / restart ──

start_cmd() {
    check_root
    check_installed
    cd "$INSTALL_DIR"
    detect_compose
    colorize blue "Starting Lightline..."
    $COMPOSE up -d
    colorize green "Lightline started."
}

stop_cmd() {
    check_root
    check_installed
    cd "$INSTALL_DIR"
    detect_compose
    colorize blue "Stopping Lightline..."
    $COMPOSE down
    colorize green "Lightline stopped."
}

restart_cmd() {
    check_root
    check_installed
    cd "$INSTALL_DIR"
    detect_compose
    colorize blue "Restarting Lightline (rebuilding to apply any code changes)..."
    $COMPOSE stop backend frontend 2>/dev/null || true
    $COMPOSE build --no-cache backend frontend
    $COMPOSE up -d
    colorize green "Lightline restarted (rebuilt)."
}

# ── status ──

status_cmd() {
    check_installed
    cd "$INSTALL_DIR"
    detect_compose

    echo ""
    colorize cyan "Lightline VPN Panel — Status"
    colorize cyan "════════════════════════════"
    echo ""
    $COMPOSE ps
    echo ""

    # Check backend health
    if curl -sf http://127.0.0.1:8000/api/system/health &>/dev/null; then
        colorize green "Backend API: Healthy"
    else
        colorize red "Backend API: Not responding"
    fi

    # Show server info
    if [ -f "$ENV_FILE" ]; then
        local server_ip panel_port
        server_ip=$(grep -E '^SERVER_IP=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "?")
        panel_port=$(grep -E '^PANEL_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "80")
        echo ""
        echo "  Panel URL:   http://${server_ip}:${panel_port}"
        echo "  Install dir: ${INSTALL_DIR}"
    fi
    echo ""
}

# ── logs ──

logs_cmd() {
    check_installed
    cd "$INSTALL_DIR"
    detect_compose

    local service="${1:-}"
    if [ -n "$service" ]; then
        $COMPOSE logs -f --tail=100 "$service"
    else
        $COMPOSE logs -f --tail=100
    fi
}

# ── admin ──

admin_cmd() {
    check_installed
    cd "$INSTALL_DIR"
    detect_compose

    local subcmd="${1:-}"
    shift 2>/dev/null || true
    case "$subcmd" in
        create)
            colorize blue "Creating admin account..."
            $COMPOSE exec backend python cli.py admin create
            ;;
        delete)
            local username="${1:-}"
            if [ -z "$username" ]; then
                printf "  Username to delete: "
                read -r username
            fi
            if [ -z "$username" ]; then
                colorize red "No username provided."
                return
            fi
            colorize blue "Deleting admin '$username'..."
            $COMPOSE exec backend python cli.py admin delete --user "$username"
            ;;
        reset)
            colorize blue "Resetting admin password..."
            $COMPOSE exec backend python cli.py admin reset "$@"
            ;;
        list)
            $COMPOSE exec backend python cli.py admin list
            ;;
        *)
            echo "Usage:"
            echo "  lightline admin create          — Create admin account"
            echo "  lightline admin delete [USER]    — Delete an admin account"
            echo "  lightline admin reset            — Reset admin password"
            echo "  lightline admin list             — List all admins"
            ;;
    esac
}

# ── license ──

license_cmd() {
    check_installed
    cd "$INSTALL_DIR"
    detect_compose

    local subcmd="${1:-}"
    shift 2>/dev/null || true
    case "$subcmd" in
        activate)
            local key="${1:-}"
            if [ -z "$key" ]; then
                printf "Enter license key: "
                read -r key
            fi
            if [ -z "$key" ]; then
                colorize red "No key provided."
                return
            fi
            colorize blue "Activating license..."
            $COMPOSE exec backend python cli.py license activate "$key"
            ;;
        show)
            $COMPOSE exec backend python cli.py license show
            ;;
        *)
            echo "Usage:"
            echo "  lightline license activate <KEY>  — Activate a license key"
            echo "  lightline license show            — Show current license"
            ;;
    esac
}

# ── config / edit env ──

config_cmd() {
    check_root
    check_installed

    local subcmd="${1:-edit}"
    case "$subcmd" in
        edit)
            if command -v nano &>/dev/null; then
                nano "$ENV_FILE"
            elif command -v vi &>/dev/null; then
                vi "$ENV_FILE"
            else
                cat "$ENV_FILE"
            fi
            ;;
        show)
            cat "$ENV_FILE"
            ;;
        *)
            echo "Usage:"
            echo "  lightline config edit  — Edit configuration"
            echo "  lightline config show  — Show configuration"
            ;;
    esac
}

# ── backup ──

backup_cmd() {
    check_installed
    cd "$INSTALL_DIR"
    detect_compose

    colorize blue "Creating backup..."
    $COMPOSE exec backend python cli.py backup 2>/dev/null || {
        # Fallback: direct database dump
        local backup_file="$DATA_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"
        $COMPOSE exec postgres pg_dump -U lightline lightline > "$backup_file"
        colorize green "Database backup saved to: $backup_file"
    }
}

# ── version ──

version_cmd() {
    echo "Lightline VPN Panel"
    echo "Script version: 1.0.0"
    if is_installed; then
        cd "$INSTALL_DIR"
        local git_hash
        git_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        echo "Install version: $git_hash"
    fi
}

# ── install-script (install only the CLI command) ──

install_script_cmd() {
    check_root
    install_lightline_script
}

# ══════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════

show_help() {
    echo ""
    colorize cyan "  Lightline VPN Panel — Management CLI"
    colorize cyan "  ════════════════════════════════════════"
    echo ""
    echo "  Usage: lightline <command> [options]"
    echo ""
    colorize green "  Core commands:"
    echo "    install              Install Lightline on this server"
    echo "    update               Update to the latest version"
    echo "    uninstall            Completely remove Lightline"
    echo "    restart              Restart all services"
    echo "    stop                 Stop all services"
    echo "    start                Start all services"
    echo ""
    colorize green "  Info commands:"
    echo "    status               Show service status"
    echo "    logs [service]       View logs (backend, frontend, postgres, redis)"
    echo "    version              Show version info"
    echo ""
    colorize green "  Admin commands:"
    echo "    admin create         Create admin account"
    echo "    admin delete [USER]  Delete an admin account"
    echo "    admin reset          Reset admin password"
    echo "    admin list           List all admin accounts"
    echo "    license activate <K> Activate a license key"
    echo "    license show         Show current license"
    echo "    config edit          Edit .env configuration"
    echo "    config show          Show current configuration"
    echo "    backup               Create database backup"
    echo ""
    colorize green "  Script commands:"
    echo "    install-script       Install only the 'lightline' CLI command"
    echo "    help                 Show this help message"
    echo ""
    colorize cyan "  Quick install:"
    echo '    sudo bash -c "$(curl -sL https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/lightline.sh)" @ install'
    echo ""
}

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

main() {
    local command="${1:-}"
    shift 2>/dev/null || true

    case "$command" in
        install)          install_cmd "$@" ;;
        uninstall|remove) uninstall_cmd "$@" ;;
        update|upgrade)   update_cmd "$@" ;;
        start|up)         start_cmd "$@" ;;
        stop|down)        stop_cmd "$@" ;;
        restart)          restart_cmd "$@" ;;
        status)           status_cmd "$@" ;;
        logs|log)         logs_cmd "$@" ;;
        admin)            admin_cmd "$@" ;;
        license|lic)      license_cmd "$@" ;;
        config|env)       config_cmd "$@" ;;
        backup)           backup_cmd "$@" ;;
        version|-v)       version_cmd "$@" ;;
        install-script)   install_script_cmd "$@" ;;
        help|-h|--help)   show_help ;;
        "")               show_help ;;
        *)
            colorize red "Unknown command: $command"
            echo "Run 'lightline help' for usage."
            exit 1
            ;;
    esac
}

main "$@"
