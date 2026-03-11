# Lightline VPN Panel

A production-ready VPN management panel built with **FastAPI**, **React**, **PostgreSQL**, and **Redis**. Manage Outline VPN servers, users, access keys, licenses, and traffic — all from a sleek cyberpunk-inspired dashboard.

---

## Features

### Backend
- **Outline Node Manager** — Add, edit, remove nodes; health monitoring; user/key sync; multi-node switching
- **VPN User Management** — Create users with traffic/device limits, auto-generate Outline access keys, QR codes, ssconf:// subscriptions
- **License Validation** — Generate keys, server fingerprint binding, external license server integration, 6-hour heartbeat
- **Authentication** — JWT access + refresh tokens, bcrypt hashing, role system (admin / reseller), optional TOTP 2FA
- **Scheduler** — Node health checks (5 min), traffic logging (1 hr), license heartbeat (6 hr)
- **CLI** — License management, admin reset, server fingerprint

### Frontend
- **Dashboard** — Nodes, users, traffic stats, recent activity at a glance
- **Nodes** — Add/edit/remove servers, health check, status indicators
- **Users** — CRUD, traffic/device limits, QR codes, node switching, bulk migration
- **Traffic** — Daily charts, per-user and per-node breakdowns (Recharts)
- **Licenses** — Generate, validate, revoke, activate with fingerprint
- **Settings** — Language (EN/RU/TK), dark/light mode, 2FA setup, backup/export
- **Audit Logs** — Full action history with timestamps and IPs
- **i18n** — English, Russian, Turkmen

### Design
- Dark-first cyberpunk theme with glassmorphism cards
- Outfit / Inter / JetBrains Mono typography
- Responsive layout with mobile sidebar
- Micro-animations via Framer Motion

---

## Quick Start

### One-Line Install (Linux)

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Lightline-Panel/lightline-panel/main/installer/install.sh)"
```

### Docker Compose (Manual)

```bash
git clone https://github.com/Lightline-Panel/lightline-panel.git
cd lightline-panel

# Generate secrets
cp backend/env.example .env
# Edit .env with your values

docker compose up -d --build
```

Panel: `http://YOUR_SERVER_IP:80` | Default login: `admin` / `admin123`

### Development

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp env.example .env  # edit with your PostgreSQL URL + JWT_SECRET
uvicorn server:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
echo "REACT_APP_BACKEND_URL=http://localhost:8000" > .env
npm start
```

---

## CLI Commands

Run from the `backend/` directory or via Docker:

```bash
# License management
python cli.py license generate --days 365 --servers 5
python cli.py license activate LL-XXXX-XXXX-XXXX-XXXX
python cli.py license show

# Admin management
python cli.py admin reset --user admin --pass newpassword

# Server fingerprint
python cli.py fingerprint
```

Via Docker Compose:
```bash
docker compose exec backend python cli.py license show
```

---

## License Server Integration

Lightline Panel supports an external **Lightline License Server** for centralized license management across multiple panel instances.

### Setup

1. **Deploy the license server** (separate repo: [lightline-license-server](https://github.com/Lightline-Panel/lightline-license-server))

   ```bash
   git clone https://github.com/Lightline-Panel/lightline-license-server.git
   cd lightline-license-server/docker
   cp .env.example .env  # edit with strong secrets
   docker compose up -d --build
   ```

   The license server runs on port `8000` with an admin dashboard on port `80`.

2. **Create a license key** on the license server:

   ```bash
   # Via CLI script
   python scripts/generate_license.py \
     --url http://YOUR_LICENSE_SERVER:8000 \
     --username admin --password admin \
     --expire-days 365 --max-servers 5

   # Or via the admin dashboard at http://YOUR_LICENSE_SERVER
   ```

3. **Configure the panel** to use the license server:

   Add to your panel's `.env` file:
   ```env
   LICENSE_SERVER_URL=http://YOUR_LICENSE_SERVER:8000
   LICENSE_SERVER_TIMEOUT=10
   ```

   Or in `docker-compose.yml`:
   ```yaml
   environment:
     LICENSE_SERVER_URL: http://YOUR_LICENSE_SERVER:8000
   ```

4. **Activate the license** in the panel:

   - Go to the panel dashboard → **Licenses** page
   - Enter the license key generated in step 2
   - Click **Activate** — the panel sends its server fingerprint to the license server

   Or via API:
   ```bash
   curl -X POST http://YOUR_PANEL:8000/api/licenses/activate \
     -H 'Content-Type: application/json' \
     -d '{"license_key": "ABCD1234-EFGH5678-IJKL9012-MNOP3456-QRST7890"}'
   ```

### How It Works

| Action | Flow |
|---|---|
| **Activate** | Panel → `POST /api/v1/license/activate` → License Server binds key to server fingerprint |
| **Validate** | Panel → `POST /api/v1/license/validate` → License Server checks key + fingerprint |
| **Heartbeat** | Panel sends heartbeat every 6 hours → License Server confirms license is still valid |
| **Revoke** | Admin revokes on License Server → next panel heartbeat suspends the panel |

- The panel generates a **server fingerprint** from hostname + machine ID + MAC address
- If the license server is unreachable (timeout), the panel **does not** suspend — only definitive failures cause suspension
- When `LICENSE_SERVER_URL` is empty, the panel falls back to **local-only** license management

### License Server Admin Dashboard

The license server includes a React admin dashboard with:
- **License list** — create, view, revoke keys
- **Activation log** — see which servers activated which keys
- **Blacklist** — block specific server fingerprints
- **Audit log** — full history of all actions

Access at `http://YOUR_LICENSE_SERVER` (default login: `admin` / `admin`).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_URL` | — | PostgreSQL async connection string |
| `JWT_SECRET` | — | Secret key for JWT token signing |
| `OUTLINE_MODE` | `mock` | `mock` for dev, `live` for production |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LICENSE_SERVER_URL` | — | External license server URL (e.g. `http://license.example.com:8000`) |
| `LICENSE_SERVER_TIMEOUT` | `10` | License server request timeout in seconds |
| `REDIS_URL` | — | Redis connection string |
| `PANEL_PORT` | `80` | Frontend port (Docker) |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password (Docker) |

---

## Project Structure

```
lightline-panel/
  backend/
    server.py          # FastAPI app, routes, schedulers
    models.py          # SQLAlchemy ORM models
    database.py        # Async DB engine + session
    auth.py            # JWT + bcrypt helpers
    outline_client.py  # Outline VPN API client (+ mock)
    cli.py             # CLI for license/admin management
    Dockerfile
  frontend/
    src/
      pages/           # Dashboard, Nodes, Users, Traffic, License, Settings, Login
      components/      # Layout, Sidebar, shadcn/ui components
      contexts/        # AuthContext, I18nContext
      i18n/            # en.json, ru.json, tk.json
      lib/api.js       # Axios instance
    Dockerfile
    nginx.conf
  installer/
    install.sh         # One-line installer
    update.sh          # Updater
    uninstall.sh       # Uninstaller
  docker-compose.yml
  design_guidelines.json
```

---

## API Endpoints

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

MIT
