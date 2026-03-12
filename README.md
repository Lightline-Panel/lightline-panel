# Lightline VPN Panel

A production-ready VPN management panel built with **FastAPI**, **React**, **PostgreSQL**, and **Redis**. Manage Outline VPN servers, users, access keys, licenses, and traffic — all from a sleek cyberpunk-inspired dashboard.

> **This software requires a valid license key to operate.** Without activation, the panel will not function. Contact the Lightline team to purchase a license.

---

## What You Need Before Starting

Before installing, make sure you have:

- A **Linux VPS** (Ubuntu 20.04+ or Debian 11+ recommended) with at least 1GB RAM
- **Root access** (you need to run commands as `sudo`)
- A **license key** (provided by the Lightline team after purchase)
- (Optional) A **domain name** pointed to your server IP

If you don't have any of these yet, get them first before continuing.

---

## Installation (Step by Step)

### Option A: One-Line Install (Easiest)

This is the fastest way. Just paste this single command into your server terminal:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/installer/install.sh)"
```

**What this does:**
1. Installs Docker and Docker Compose (if not already installed)
2. Downloads the Lightline Panel
3. Creates secure passwords automatically
4. Starts all services (database, backend, frontend)

**When it finishes, you'll see:**
```
  Panel URL:    http://YOUR_SERVER_IP
  Backend API:  http://127.0.0.1:8000/api
```

### Option B: Manual Install with Docker Compose

If you prefer to do it yourself:

```bash
# Step 1: Download the panel
git clone https://github.com/Lightline-Panel/lightline-panel.git
cd lightline-panel

# Step 2: Create your config file
cp backend/env.example .env

# Step 3: Edit the config (change the passwords!)
nano .env

# Step 4: Start everything
docker compose up -d --build
```

**Wait about 30 seconds** for everything to start, then open `http://YOUR_SERVER_IP` in your browser.

---

## Domain Name and SSL Setup (Recommended)

For production use, you should set up a domain name and SSL certificate:

### Step 1: Point your domain to the server

1. Buy a domain name (e.g., `vpn.yourdomain.com`)
2. Go to your domain's DNS settings
3. Create an **A record** pointing to your server's IP:
   - Type: `A`
   - Name: `vpn` (or `@` for the root domain)
   - Value: `YOUR_SERVER_IP`
   - TTL: `300` (or leave default)

4. Wait 5-30 minutes for DNS to propagate

### Step 2: Configure the panel to use your domain

Edit the `.env` file on your server:

```bash
nano /opt/lightline/.env
```

Add or update these lines:

```env
PANEL_DOMAIN=vpn.yourdomain.com
PANEL_PORT=443
```

### Step 3: Enable automatic SSL with Let's Encrypt

The panel includes Caddy reverse proxy for automatic SSL:

1. Make sure port 80 and 443 are open in your firewall:
   ```bash
   sudo ufw allow 80
   sudo ufw allow 443
   ```

2. Restart the panel to apply domain changes:
   ```bash
   cd /opt/lightline
   docker compose restart
   ```

3. Caddy will automatically obtain and renew a free SSL certificate from Let's Encrypt

4. Your panel will now be available at: `https://vpn.yourdomain.com`

### Step 4: Update your Outline clients

The subscription URL format will change to:
```
ssconf://vpn.yourdomain.com/api/sub/TOKEN
```

---

## First Login

1. Open your browser and go to `https://YOUR_DOMAIN` (or `http://YOUR_SERVER_IP` if no domain)
2. You'll see the login page
3. Default credentials: **username:** `admin` / **password:** `admin123`
4. **Change your password immediately** after first login in Settings

---

## Activating Your License

The panel **will not work** without a valid license. Here's how to activate it:

### If you have a license key:

1. Log in to the panel
2. Go to the **Licenses** page (in the sidebar)
3. Click **Activate**
4. Paste your license key (looks like: `LL-A1B2C3D4-E5F6G7H8-I9J0K1L2-M3N4O5P6`)
5. Click **Activate** — done!

### Via terminal (alternative):

```bash
# If using Docker:
cd /opt/lightline
docker compose exec backend python cli.py license activate LL-XXXX-XXXX-XXXX-XXXX

# Check your license status:
docker compose exec backend python cli.py license show
```

### What happens after activation:

- Your server's **unique fingerprint** is bound to the license
- The panel sends a **heartbeat** every 6 hours to verify the license is still valid
- If the license expires or is revoked, the panel will stop working

---

## Adding Your First VPN Server (Node)

After activating your license:

1. Go to **Nodes** in the sidebar
2. Click **Add Node**
3. Fill in:
   - **Name**: Any name (e.g., "Frankfurt Server")
   - **IP**: Your Outline server IP address
   - **API Port**: The Outline management API port
   - **API Key**: The Outline management API key
   - **Country**: (optional) Country code like `DE`, `US`, `NL`
4. Click **Save**
5. The panel will check if the server is reachable (green = online)

### Where to find your Outline API details:

When you install Outline VPN server, it gives you a management URL like:
```
https://1.2.3.4:12345/AbCdEfGh123456
```
- **IP**: `1.2.3.4`
- **API Port**: `12345`
- **API Key**: `AbCdEfGh123456`

---

## Creating VPN Users

1. Go to **Users** in the sidebar
2. Click **Add User**
3. Fill in:
   - **Username**: Any name for this user
   - **Traffic Limit**: Max data in bytes (0 = unlimited)
   - **Device Limit**: How many devices can connect (default: 1)
   - **Expire Date**: When this user's access expires
   - **Node**: Which server to assign them to
4. Click **Save**
5. The panel creates an Outline access key automatically
6. Share the **QR code** or **access URL** with your user

---

## Common Commands

All commands run from the install directory (`/opt/lightline` by default):

```bash
# View logs (see what's happening)
docker compose logs -f

# Restart everything
docker compose restart

# Stop the panel
docker compose down

# Rebuild after updates
docker compose up -d --build

# Update to latest version
cd /opt/lightline
git pull origin main
docker compose up -d --build
```

---

## CLI Commands

The CLI lets you manage things from the terminal:

```bash
# License management
docker compose exec backend python cli.py license generate --days 365 --servers 5
docker compose exec backend python cli.py license activate LL-XXXX-XXXX-XXXX-XXXX
docker compose exec backend python cli.py license show

# Reset admin password (if you forgot it)
docker compose exec backend python cli.py admin reset --user admin --pass newpassword

# Show server fingerprint
docker compose exec backend python cli.py fingerprint
```

---

## License Server Integration (Advanced)

If you manage **multiple panels** and want centralized license control, you can deploy the separate [Lightline License Server](https://github.com/Lightline-Panel/lightline-license-server).

### Step 1: Deploy the license server on a separate VPS

```bash
git clone https://github.com/Lightline-Panel/lightline-license-server.git
cd lightline-license-server/docker
cp .env.example .env
nano .env    # Change SECRET_KEY, ENCRYPTION_KEY, and ADMIN_PASSWORD!
docker compose up -d --build
```

This gives you:
- **License API** at `http://YOUR_LICENSE_SERVER:8000`
- **Admin Dashboard** at `http://YOUR_LICENSE_SERVER` (login: `admin` / whatever you set)

### Step 2: Create license keys

Open the license server dashboard, go to **Licenses**, click **Create License**, and set:
- **Expire Days**: How long the license lasts (e.g., 365)
- **Max Servers**: How many panels can use this key (e.g., 1)

Copy the generated key.

### Step 3: Connect your panel to the license server

On each panel VPS, edit the `.env` file:

```bash
nano /opt/lightline/.env
```

Add this line (replace with your license server IP):

```env
LICENSE_SERVER_URL=http://YOUR_LICENSE_SERVER_IP:8000
```

Then restart:

```bash
cd /opt/lightline
docker compose restart
```

### Step 4: Activate

Go to the panel dashboard → **Licenses** → paste the key → **Activate**.

### How it works

| What happens | When |
|---|---|
| **Activate** | Panel sends its server fingerprint to the license server. The key is now bound to this specific server. |
| **Heartbeat** | Every 6 hours, the panel checks with the license server that the license is still valid. |
| **Revoke** | You revoke a key on the license server → the panel stops working at the next heartbeat. |
| **Blacklist** | You can block specific servers by fingerprint on the license server dashboard. |

---

## Troubleshooting

### Panel won't start
```bash
docker compose logs backend    # Check for errors
docker compose down
docker compose up -d --build   # Rebuild
```

### Can't connect to panel
- Make sure port 80 is open: `sudo ufw allow 80`
- Check if services are running: `docker compose ps`

### License activation failed
- Double-check the key (no extra spaces)
- Make sure `LICENSE_SERVER_URL` is correct and reachable
- Check license server logs: `docker compose logs backend`

### Forgot admin password
```bash
docker compose exec backend python cli.py admin reset --user admin --pass newpassword
```

---

## Environment Variables

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_URL` | — | Database connection string (auto-set by Docker) |
| `POSTGRES_PASSWORD` | `changeme` | Database password — **change this!** |
| `JWT_SECRET` | — | Secret for login tokens — **change this!** |
| `OUTLINE_MODE` | `mock` | `mock` = demo data, `live` = real Outline servers |
| `CORS_ORIGINS` | `*` | Which websites can access the API |
| `LICENSE_SERVER_URL` | — | External license server URL (optional) |
| `LICENSE_SERVER_TIMEOUT` | `10` | License server timeout in seconds |
| `REDIS_URL` | — | Redis cache connection (auto-set by Docker) |
| `PANEL_PORT` | `80` | Which port the panel runs on |

---

## Project Structure

```
lightline-panel/
  backend/
    server.py          # Main API server
    models.py          # Database tables
    database.py        # Database connection
    auth.py            # Login & security
    license_client.py  # License server communication
    outline_client.py  # Outline VPN API client
    cli.py             # Terminal commands
    Dockerfile
  frontend/
    src/
      pages/           # Dashboard, Nodes, Users, Traffic, License, Settings, Login
      components/      # UI components
      contexts/        # Auth & language state
      i18n/            # Translations (English, Russian, Turkmen)
      lib/api.js       # API client
    Dockerfile
    nginx.conf
  installer/
    install.sh         # One-line installer
    update.sh          # Updater
    uninstall.sh       # Uninstaller
  docker-compose.yml
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/system/health` | No | Health check |
| POST | `/api/auth/setup` | No | Initial admin creation |
| POST | `/api/auth/login` | No | Login (supports TOTP) |
| POST | `/api/auth/refresh` | No | Refresh JWT tokens |
| GET | `/api/auth/me` | Yes | Current admin info |
| POST | `/api/auth/totp/setup` | Yes | Generate TOTP secret + QR |
| POST | `/api/auth/totp/confirm` | Yes | Confirm and enable TOTP |
| POST | `/api/auth/totp/disable` | Yes | Disable TOTP 2FA |
| GET | `/api/dashboard` | Yes | Dashboard stats |
| GET/POST | `/api/nodes` | Yes | List / create nodes |
| PUT/DELETE | `/api/nodes/:id` | Yes | Update / delete node |
| POST | `/api/nodes/:id/health-check` | Yes | Manual health check |
| GET/POST | `/api/users` | Yes | List / create users |
| PUT/DELETE | `/api/users/:id` | Yes | Update / delete user |
| POST | `/api/users/:id/switch-node` | Yes | Switch user's node |
| POST | `/api/users/bulk-switch-node` | Yes | Bulk switch all users |
| GET | `/api/users/:id/qrcode` | Yes | Generate QR code |
| GET | `/api/traffic` | Yes | Traffic by user/node |
| GET | `/api/traffic/daily` | Yes | Daily traffic chart data |
| GET/POST | `/api/licenses` | Yes | List / generate licenses |
| DELETE | `/api/licenses/:id` | Yes | Revoke license |
| POST | `/api/licenses/validate` | No | Validate a license key |
| POST | `/api/licenses/activate` | No | Activate with fingerprint |
| GET | `/api/system/fingerprint` | Yes | Server fingerprint |
| GET | `/api/audit-logs` | Yes | Audit log history |
| GET/PUT | `/api/settings` | Yes | Panel settings |
| POST | `/api/backup` | Yes | Export backup JSON |
| GET | `/api/access/:token` | No | ssconf:// subscription |

---

## License

**Proprietary Software** — All rights reserved.

This software is licensed, not sold. You may only use it with a valid license key purchased from the Lightline team. Redistribution, modification for resale, or unauthorized use is prohibited.

For licensing inquiries, contact the Lightline team.
