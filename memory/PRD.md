# Lightline VPN Management Panel — PRD

## Problem Statement
Commercial multi-node Outline VPN management panel. Manage multiple Outline VPN servers from a single web interface with license management, traffic monitoring, user management, and i18n support.

## Architecture
- **Backend**: FastAPI + PostgreSQL (SQLAlchemy async) on port 8001
- **Frontend**: React + TailwindCSS + shadcn/ui on port 3000
- **Database**: PostgreSQL (lightline DB)
- **Auth**: JWT + bcrypt password hashing
- **Outline Integration**: Mock mode (OUTLINE_MODE=mock) / Production mode
- **Default Admin**: admin / admin123

## User Personas
1. **Server Admin** — Manages VPN nodes, users, licenses from central dashboard
2. **VPN Service Provider** — Generates licenses, monitors traffic, manages billing

## Core Requirements (Static)
- Multi-node Outline VPN management
- VPN user CRUD with access key generation
- QR code generation for mobile clients
- Multi-node switching for users
- Traffic monitoring with daily statistics
- License key generation and validation system
- i18n support (English, Russian, Turkmen)
- Dark/Light theme toggle
- Audit logging
- Backup/Restore
- JWT authentication with refresh tokens

## What's Been Implemented (March 11, 2026)
### Backend (FastAPI + PostgreSQL)
- Full auth system (login, setup, refresh, me)
- Dashboard stats aggregation
- Nodes CRUD + health check + sync keys
- Users CRUD + node switching + Outline key generation
- Traffic tracking (daily + by-user + by-node)
- License CRUD + validation + activation
- Audit logging with pagination
- Settings management
- Backup export
- Background tasks: node health monitoring (5min), mock traffic generation (1hr)
- Mock data seeder (5 nodes, 10 users, 30 days traffic, 1 license)

### Frontend (React + shadcn/ui)
- Login page with setup flow
- Dashboard with bento grid stats, node health, recent activity
- Node management page (table, add/edit/delete, health check)
- User management page (table, CRUD, QR codes, node switching, search)
- Traffic page (area chart, bar chart, by-user/by-node tabs)
- License management page (table, generate, validate, revoke)
- Settings page (language, theme, backup, admin profile)
- Audit logs page with pagination
- Responsive sidebar navigation
- i18n context (EN/RU/TK)
- Dark-first cyberpunk theme

### Testing Results
- Backend: 100% pass rate (33/33 endpoints)
- Frontend: 95% pass rate (minor console warnings fixed)

## Prioritized Backlog
### P0 (Next Iteration)
- [ ] License server as separate microservice
- [ ] License heartbeat system (6hr validation)
- [ ] Server fingerprint binding
- [ ] Panel suspended mode on license expiry

### P1
- [ ] Admin CLI commands (lightline admin create)
- [ ] Auto-update system (lightline update)
- [ ] Installer script (Docker + systemd + PostgreSQL setup)
- [ ] Rate limiting on API endpoints
- [ ] 2FA/TOTP support
- [ ] API tokens for Telegram bot integration

### P2
- [ ] GitHub CI/CD pipeline
- [ ] Docker Compose deployment
- [ ] systemd service wrapper
- [ ] Encrypted config files
- [ ] Binary/bytecode obfuscation
- [ ] Integrity checksum validation
- [ ] Remote disable capability
- [ ] Backup restore functionality
- [ ] Redis caching layer

## Next Tasks
1. Implement license server microservice with heartbeat
2. Add rate limiting and API security middleware
3. Create installer script and Docker Compose
4. Build Telegram bot API integration
5. Add 2FA/TOTP support
