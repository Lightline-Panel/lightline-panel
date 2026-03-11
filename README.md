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

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_URL` | — | PostgreSQL async connection string |
| `JWT_SECRET` | — | Secret key for JWT token signing |
| `OUTLINE_MODE` | `mock` | `mock` for dev, `live` for production |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `LICENSE_SERVER_URL` | — | External license validation endpoint |
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
