from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse, JSONResponse
from sqlalchemy import select, func, desc, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncio
import os
import io
import base64
import logging
import secrets
import hashlib
import hmac
import struct
import time as _time
import platform
import uuid
from pathlib import Path
from dotenv import load_dotenv
import pyotp
import qrcode
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from database import async_session, get_db, engine, Base
from models import Admin, Node, VPNUser, TrafficLog, License, AuditLog, PanelSettings
from auth import (hash_password, verify_password, create_access_token,
                  create_refresh_token, decode_token, get_current_admin)
from ss_manager import generate_password, build_ss_url, SS_METHOD
from cache import cache_get_json, cache_set_json, cache_delete, close_redis
from panel_certificate import get_panel_certificate, get_panel_cert_and_key

app = FastAPI(title="Lightline VPN Panel")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== HMAC-Signed License Keys =====
LICENSE_SECRET = os.environ.get('LICENSE_SECRET', 'lightline-hmac-2024-secure-key').encode()


def verify_license_key(key: str) -> dict | None:
    """Verify an HMAC-signed license key. Returns decoded info or None."""
    try:
        parts = key.replace("LL-", "").replace("-", "")
        if len(parts) != 40:
            return None
        raw = bytes.fromhex(parts)
        payload, sig = raw[:12], raw[12:20]
        expected = hmac.new(LICENSE_SECRET, payload, hashlib.sha256).digest()[:8]
        if not hmac.compare_digest(sig, expected):
            return None
        created, expire_days, max_servers = struct.unpack('>IIH', payload[:10])
        expire_ts = created + expire_days * 86400
        return {
            "created": created,
            "expire_days": expire_days,
            "max_servers": max_servers,
            "expired": _time.time() > expire_ts,
            "expires_in_days": max(0, int((expire_ts - _time.time()) / 86400)),
        }
    except Exception:
        return None


# ===== Pydantic Schemas =====
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class NodeCreate(BaseModel):
    name: str
    ip: str
    port: Optional[int] = 62050       # SERVICE_PORT (like Marzban)
    ss_port: Optional[int] = None     # Shadowsocks port (uses global if not specified)
    country: Optional[str] = None

class NodeUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None        # SERVICE_PORT (like Marzban)
    ss_port: Optional[int] = None     # Shadowsocks port
    country: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    traffic_limit: Optional[int] = 0
    expire_date: Optional[str] = None
    assigned_node_id: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    traffic_limit: Optional[int] = None
    expire_date: Optional[str] = None
    assigned_node_id: Optional[int] = None
    status: Optional[str] = None

class SwitchNodeRequest(BaseModel):
    node_id: int

class BulkSwitchNodeRequest(BaseModel):
    node_id: int

class LicenseValidate(BaseModel):
    license_key: str

class SettingsUpdate(BaseModel):
    settings: dict

class TOTPEnableRequest(BaseModel):
    totp_code: str

class TOTPDisableRequest(BaseModel):
    totp_code: str

class LoginTOTPRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

class LicenseActivate(BaseModel):
    license_key: str

class TOTPConfirmRequest(BaseModel):
    secret: str
    code: str


# ===== License Persistence (survives container rebuilds) =====
LICENSE_BACKUP_PATH = Path('/var/lib/lightline/certs/license_backup.json')


def _save_license_to_file(license_key: str, server_fingerprint: str):
    """Save license key to a persistent file so it survives DB resets."""
    try:
        LICENSE_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        _json.dump({
            "license_key": license_key,
            "server_fingerprint": server_fingerprint,
        }, open(LICENSE_BACKUP_PATH, 'w'))
        logger.info(f"License backed up to {LICENSE_BACKUP_PATH}")
    except Exception as e:
        logger.error(f"Failed to backup license: {e}")


def _load_license_from_file() -> dict | None:
    """Load license key from persistent file."""
    try:
        if LICENSE_BACKUP_PATH.exists():
            import json as _json
            data = _json.load(open(LICENSE_BACKUP_PATH))
            if data.get("license_key"):
                return data
    except Exception as e:
        logger.error(f"Failed to load license backup: {e}")
    return None


# ===== Runtime Node Stats Cache =====
# Stores latest stats from each node (polled every 60s by background task)
# Key: node_id, Value: {"upload": int, "download": int, "connected_devices": int, "connected_ips": [...]}
_node_stats_cache: dict = {}
# Tracks last-known cumulative bytes per node so we can compute deltas for TrafficLog
_node_last_bytes: dict = {}


# ===== User Validation Helpers =====

async def validate_user_access(user: VPNUser, db: AsyncSession) -> dict:
    """Check if user is allowed to access VPN based on traffic limit and expiry."""
    errors = []
    
    # Check expiry date
    if user.expire_date and datetime.now(timezone.utc) > user.expire_date:
        errors.append("User account has expired")
    
    # Check traffic limit (if set)
    if user.traffic_limit > 0:
        # Get total traffic used
        total_used = (await db.execute(
            select(func.sum(TrafficLog.bytes_transferred)).where(TrafficLog.user_id == user.id)
        )).scalar() or 0
        
        if total_used >= user.traffic_limit * 1024**3:  # Convert GB to bytes
            errors.append("Traffic limit exceeded")
    
    return {
        "allowed": len(errors) == 0,
        "errors": errors
    }


async def _node_connect_and_action(node: Node, action: str) -> bool:
    """Connect to a node and perform a session-authenticated action (/start, /stop, /restart).
    
    Node endpoints require session_id from a prior /connect call.
    """
    try:
        # Step 1: Establish session
        connect_resp = await _node_request(node, 'POST', '/connect')
        if not connect_resp or connect_resp.status_code != 200:
            logger.warning(f"Node {node.name}: failed to connect for {action}")
            return False
        session_id = connect_resp.json().get('session_id')
        if not session_id:
            logger.warning(f"Node {node.name}: /connect returned no session_id")
            return False
        
        # Step 2: Perform the action with session_id
        resp = await _node_request(node, 'POST', f'/{action}', json={"session_id": session_id})
        if resp and resp.status_code == 200:
            logger.info(f"Node {node.name}: {action} succeeded")
            return True
        else:
            logger.warning(f"Node {node.name}: {action} failed (status={resp.status_code if resp else 'no response'})")
            return False
    except Exception as e:
        logger.error(f"Node {node.name}: {action} error: {e}")
        return False


async def deactivate_user_on_node(user: VPNUser, node: Node, db: AsyncSession, reason: str) -> bool:
    """In single-password mode, we stop ss-server if no active users remain."""
    try:
        # Check if there are any other active users on this node (excluding this user)
        active_count = (await db.execute(
            select(func.count(VPNUser.id)).where(
                VPNUser.assigned_node_id == node.id,
                VPNUser.status == 'active',
                VPNUser.id != user.id
            )
        )).scalar() or 0
        
        # If this was the last active user, stop the server
        if active_count == 0:
            success = await _node_connect_and_action(node, 'stop')
            if success:
                logger.info(f"Stopped ss-server on node {node.name} (no active users): {reason}")
            else:
                logger.warning(f"Failed to stop ss-server on node {node.name}: {reason}")
        else:
            logger.info(f"Node {node.name} still has {active_count} active users, keeping server running")
        
        return True
                
    except Exception as e:
        logger.error(f"Error deactivating user {user.username}: {e}")
        return False


async def ensure_server_running(node: Node) -> bool:
    """Start ss-server on node if it's not already running."""
    try:
        # Check if already running via health endpoint (no session needed)
        resp = await _node_request(node, 'GET', '/health')
        if resp and resp.status_code == 200:
            data = resp.json()
            if data.get('ss_running'):
                return True
        
        # Server not running, connect and start it
        return await _node_connect_and_action(node, 'start')
    except Exception as e:
        logger.error(f"Error ensuring server running on {node.name}: {e}")
        return False


# ===== Auth Routes =====

@api_router.get("/")
async def root():
    return {"message": "Lightline VPN Panel API", "version": "1.0.0"}

@api_router.get("/auth/check-setup")
async def check_setup(db: AsyncSession = Depends(get_db)):
    admin_count = (await db.execute(select(func.count(Admin.id)))).scalar()
    lic = (await db.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
    lic_info = None
    if lic:
        expire_date = lic.created_at + timedelta(days=lic.expire_days)
        lic_info = {"expires_in_days": max(0, (expire_date - datetime.now(timezone.utc)).days), "key": lic.license_key[:16] + "..."}
    return {
        "setup_required": admin_count == 0,
        "license_active": lic is not None,
        "license_info": lic_info,
        "message": "Create admin via CLI: docker exec -it lightline-backend python cli.py admin create" if admin_count == 0 else None
    }

@api_router.post("/auth/login")
async def login(req: LoginTOTPRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # License gate — reject login if no active license
    lic = (await db.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
    if not lic:
        raise HTTPException(403, "No active license. Please activate a license key first.")
    result = await db.execute(select(Admin).where(Admin.username == req.username))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if admin.totp_secret:
        if not req.totp_code:
            return {"requires_totp": True, "message": "TOTP code required"}
        totp = pyotp.TOTP(admin.totp_secret)
        if not totp.verify(req.totp_code, valid_window=1):
            raise HTTPException(401, "Invalid TOTP code")
    token_data = {"sub": str(admin.id), "username": admin.username, "role": admin.role}
    db.add(AuditLog(admin_id=admin.id, action='login', ip_address=request.client.host if request.client else None))
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data)
    )

@api_router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get('type') != 'refresh':
        raise HTTPException(401, "Invalid refresh token")
    token_data = {"sub": payload["sub"], "username": payload["username"], "role": payload["role"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data)
    )

@api_router.get("/auth/me")
async def get_me(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.id == int(admin["sub"])))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Admin not found")
    return {"id": a.id, "username": a.username, "role": a.role,
            "totp_enabled": bool(a.totp_secret), "created_at": a.created_at.isoformat()}


# ===== TOTP 2FA =====

@api_router.post("/auth/totp/setup")
async def totp_setup(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    a = (await db.execute(select(Admin).where(Admin.id == int(admin["sub"])))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Admin not found")
    if a.totp_secret:
        raise HTTPException(400, "TOTP already enabled. Disable first.")
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=a.username, issuer_name="Lightline VPN")
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"secret": secret, "provisioning_uri": provisioning_uri,
            "qr_code": f"data:image/png;base64,{qr_b64}"}

@api_router.post("/auth/totp/confirm")
async def totp_confirm(req: TOTPConfirmRequest, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    a = (await db.execute(select(Admin).where(Admin.id == int(admin["sub"])))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Admin not found")
    totp = pyotp.TOTP(req.secret)
    if not totp.verify(req.code, valid_window=1):
        raise HTTPException(400, "Invalid TOTP code. Try again.")
    a.totp_secret = req.secret
    db.add(AuditLog(admin_id=a.id, action='totp_enabled', details='TOTP 2FA enabled'))
    return {"message": "TOTP 2FA enabled successfully"}

@api_router.post("/auth/totp/disable")
async def totp_disable(req: TOTPDisableRequest, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    a = (await db.execute(select(Admin).where(Admin.id == int(admin["sub"])))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "Admin not found")
    if not a.totp_secret:
        raise HTTPException(400, "TOTP is not enabled")
    totp = pyotp.TOTP(a.totp_secret)
    if not totp.verify(req.totp_code, valid_window=1):
        raise HTTPException(401, "Invalid TOTP code")
    a.totp_secret = None
    db.add(AuditLog(admin_id=a.id, action='totp_disabled', details='TOTP 2FA disabled'))
    return {"message": "TOTP 2FA disabled"}


# ===== Server Fingerprint =====

FINGERPRINT_PATH = Path('/var/lib/lightline/certs/server_fingerprint')

def get_server_fingerprint() -> str:
    """Stable server fingerprint that survives container rebuilds.
    
    Saved to persistent volume on first generation. Never changes.
    Does NOT use platform.node() because Docker changes the container
    hostname on every recreate, which would invalidate the license.
    """
    # Return saved fingerprint if it exists (stable across rebuilds)
    try:
        if FINGERPRINT_PATH.exists():
            saved = FINGERPRINT_PATH.read_text().strip()
            if saved:
                return saved
    except Exception:
        pass
    # Generate from stable identifiers (MAC address + architecture)
    raw = f"{uuid.getnode()}-{platform.machine()}"
    fp = hashlib.sha256(raw.encode()).hexdigest()[:32]
    # Save so it's always the same
    try:
        FINGERPRINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FINGERPRINT_PATH.write_text(fp)
    except Exception:
        pass
    return fp


# ===== QR Code Generation =====

@api_router.get("/users/{user_id}/qrcode")
async def get_user_qrcode(user_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    # Build URL dynamically so it always reflects the current port/password
    url = ""
    if user.assigned_node_id:
        node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
        if node:
            url = await _build_user_ss_url_from_node(user, node, db)
    if not url:
        url = user.access_url or ""
    if not url:
        raise HTTPException(404, "No access URL available")
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"qr_code": f"data:image/png;base64,{qr_b64}", "url": url}


# ===== SS URL Helper =====

async def _get_global_ss_port(db) -> int:
    """Get the global SS port from panel settings, fallback to env/default."""
    row = (await db.execute(select(PanelSettings).where(PanelSettings.key == 'ss_port'))).scalar_one_or_none()
    if row and row.value:
        try:
            return int(row.value)
        except ValueError:
            pass
    return int(os.environ.get('SS_PORT', '8388'))


def _get_node_http_client() -> httpx.AsyncClient:
    """Create an httpx client configured for node connections.
    
    Uses the panel's client certificate for mTLS if available.
    Falls back to plain HTTPS with verify=False if cert not available.
    """
    try:
        cert_file, key_file = get_panel_cert_and_key()
        return httpx.AsyncClient(
            timeout=8,
            verify=False,  # node uses self-signed cert
            cert=(cert_file, key_file),  # panel's client cert for mTLS
        )
    except Exception:
        return httpx.AsyncClient(timeout=8, verify=False)


# Cache which scheme (http/https) works for each node IP to avoid slow fallbacks
_node_scheme_cache: dict = {}

async def _node_request(node, method: str, path: str, **kwargs) -> httpx.Response:
    """Make a request to a node's REST API.
    
    Tries the last-known working scheme first, then the other.
    Uses panel's client certificate for mTLS authentication.
    """
    api_port = node.api_port or 62050
    token = node.api_key or ''
    headers = kwargs.pop('headers', {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Use cached scheme first, then try both (http first since most nodes don't use SSL)
    cached = _node_scheme_cache.get(node.ip)
    schemes = [cached, 'http', 'https'] if cached else ['http', 'https']
    seen = set()
    for scheme in schemes:
        if scheme in seen:
            continue
        seen.add(scheme)
        url = f"{scheme}://{node.ip}:{api_port}{path}"
        try:
            async with _get_node_http_client() as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                _node_scheme_cache[node.ip] = scheme  # remember working scheme
                return resp
        except Exception as e:
            logger.debug(f"Node {node.name} {scheme} request to {path} failed: {e}")
            continue
    return None


async def _get_node_server_info(node) -> dict:
    """Fetch server password, port, and method from the node agent.
    
    In single-password mode (Outline model), all users share one server password.
    Returns dict with 'password', 'port', 'method' keys.
    Falls back to panel defaults if the node API is unreachable.
    """
    resp = await _node_request(node, 'GET', '/server-info')
    if resp and resp.status_code == 200:
        return resp.json()
    return {}


async def _build_user_ss_url_from_node(user, node, db, force_port: int = None) -> str:
    """Build a proper ss:// URL by fetching real config from the node.
    
    Fetches the actual server password and port from the node's /server-info.
    Port priority: force_port > node /server-info (actual running port) > node.ss_port (DB) > global settings.
    The node-reported port is the ACTUAL port ss-server is listening on.
    """
    if not node:
        return ""
    info = await _get_node_server_info(node)
    password = info.get('password', '')
    # Port: the node's /server-info returns the ACTUAL running port
    # This is the most reliable source — it's what ss-server is actually bound to
    node_reported_port = info.get('port', 0)
    ss_port = force_port or node_reported_port or node.ss_port or await _get_global_ss_port(db)
    if not password:
        # Fallback: use user's stored password (legacy)
        password = user.ss_password or ''
    if not password:
        return ""
    return build_ss_url(
        password=password,
        host=node.ip,
        port=ss_port,
        tag=user.username,
    )


# ===== Dashboard =====

@api_router.get("/dashboard")
async def get_dashboard(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    cached = await cache_get_json('dashboard')
    if cached:
        return cached
    nodes_total = (await db.execute(select(func.count(Node.id)))).scalar()
    nodes_online = (await db.execute(select(func.count(Node.id)).where(Node.status == 'online'))).scalar()
    users_total = (await db.execute(select(func.count(VPNUser.id)))).scalar()
    users_active = (await db.execute(select(func.count(VPNUser.id)).where(VPNUser.status == 'active'))).scalar()

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    traffic_today = (await db.execute(
        select(func.coalesce(func.sum(TrafficLog.bytes_transferred), 0)).where(TrafficLog.recorded_at >= today)
    )).scalar()
    traffic_total = (await db.execute(
        select(func.coalesce(func.sum(TrafficLog.bytes_transferred), 0))
    )).scalar()

    lic = (await db.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()

    logs = (await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10))).scalars().all()
    nodes = (await db.execute(select(Node).order_by(Node.name))).scalars().all()

    # Sum connected devices across all online nodes
    total_devices = sum(s.get("connected_devices", 0) for s in _node_stats_cache.values())
    all_ips = []
    for s in _node_stats_cache.values():
        all_ips.extend(s.get("connected_ips", []))

    result = {
        "nodes": {"total": nodes_total, "online": nodes_online, "offline": nodes_total - nodes_online},
        "users": {"total": users_total, "active": users_active},
        "traffic": {"today": traffic_today, "total": traffic_total},
        "connected_devices": total_devices,
        "connected_ips": list(set(all_ips)),
        "license": {
            "active": lic is not None,
            "key": lic.license_key[:12] + "..." if lic else None,
            "expires_in": lic.expire_days if lic else None,
            "status": lic.status if lic else "none",
            "days_left": max(0, (lic.created_at + timedelta(days=lic.expire_days) - datetime.now(timezone.utc)).days) if lic and lic.expire_days > 0 else None
        },
        "recent_activity": [
            {"id": l.id, "action": l.action, "details": l.details, "created_at": l.created_at.isoformat()}
            for l in logs
        ],
        "node_health": [
            {"id": n.id, "name": n.name, "country": n.country, "status": n.status,
             "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None}
            for n in nodes
        ]
    }
    await cache_set_json('dashboard', result, ttl=30)
    return result


# ===== Node Routes =====

@api_router.get("/nodes")
async def get_nodes(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    nodes = (await db.execute(select(Node).order_by(Node.name))).scalars().all()
    ss_port = await _get_global_ss_port(db)
    result = []
    for n in nodes:
        uc = (await db.execute(select(func.count(VPNUser.id)).where(VPNUser.assigned_node_id == n.id))).scalar()
        stats = _node_stats_cache.get(n.id, {})
        result.append({
            "id": n.id, "name": n.name, "ip": n.ip,
            "port": n.api_port or 62050,
            "country": n.country, "status": n.status,
            "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
            "created_at": n.created_at.isoformat(), "user_count": uc,
            "connected_devices": stats.get("connected_devices", 0),
            "connected_ips": stats.get("connected_ips", []),
            "traffic_upload": stats.get("upload", 0),
            "traffic_download": stats.get("download", 0),
        })
    return result

@api_router.get("/nodes/certificate")
async def get_node_certificate(admin=Depends(get_current_admin)):
    """Show the panel's certificate for node mTLS setup.
    
    Admin copies this certificate to the node as ssl_client_cert.pem.
    Same pattern as Marzban's 'Show Certificate' button.
    """
    cert_pem = get_panel_certificate()
    return {"certificate": cert_pem}


@api_router.post("/nodes")
async def create_node(req: NodeCreate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    port = req.port or 62050
    # Get current global SS port for new node
    ss_port = req.ss_port or await _get_global_ss_port(db)
    node = Node(name=req.name, ip=req.ip, api_port=port, ss_port=ss_port,
                country=req.country, status='offline')
    db.add(node)
    await db.flush()
    db.add(AuditLog(admin_id=int(admin["sub"]), action='node_created',
                    details=f'Node "{req.name}" ({req.country}) added — API port {port}, SS port {ss_port}',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"id": node.id, "name": node.name, "status": node.status, "port": port, "ss_port": ss_port}

@api_router.put("/nodes/{node_id}")
async def update_node(node_id: int, req: NodeUpdate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    data = req.model_dump(exclude_none=True)
    # Map 'port' from API model to 'api_port' DB column
    if 'port' in data:
        data['api_port'] = data.pop('port')
    for k, v in data.items():
        setattr(node, k, v)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='node_updated',
                    details=f'Node "{node.name}" updated',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"message": "Node updated"}

@api_router.delete("/nodes/{node_id}")
async def delete_node(node_id: int, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    await db.execute(update(VPNUser).where(VPNUser.assigned_node_id == node_id).values(assigned_node_id=None))
    db.add(AuditLog(admin_id=int(admin["sub"]), action='node_deleted',
                    details=f'Node "{node.name}" deleted',
                    ip_address=request.client.host if request.client else None))
    await db.delete(node)
    await cache_delete('dashboard')
    return {"message": "Node deleted"}

@api_router.post("/nodes/refresh-all")
async def refresh_all_nodes(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Connect + health-check all nodes at once."""
    nodes = (await db.execute(select(Node))).scalars().all()
    results = {}
    for node in nodes:
        # Try /connect first to establish session
        try:
            await _node_request(node, 'POST', '/connect')
        except Exception:
            pass
        node.status = await _check_node_health(node)
        if node.status == 'online':
            node.last_heartbeat = datetime.now(timezone.utc)
        results[node.name] = node.status
    await cache_delete('dashboard')
    return {"message": f"{len(nodes)} nodes checked", "results": results}

@api_router.post("/nodes/regenerate-urls")
async def regenerate_all_urls(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Regenerate all users' ss:// access URLs by fetching real config from nodes.
    
    Use this after redeploying nodes or fixing SS port issues to fix broken URLs.
    """
    users = (await db.execute(
        select(VPNUser).where(VPNUser.assigned_node_id.isnot(None))
    )).scalars().all()
    updated = 0
    errors = 0
    for user in users:
        try:
            node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
            if node:
                new_url = await _build_user_ss_url_from_node(user, node, db)
                if new_url:
                    user.access_url = new_url
                    updated += 1
        except Exception as e:
            logger.error(f"Failed to regenerate URL for {user.username}: {e}")
            errors += 1
    await cache_delete('dashboard')
    return {"message": f"Regenerated {updated} URLs ({errors} errors)", "updated": updated, "errors": errors}

@api_router.post("/nodes/{node_id}/health-check")
async def health_check(node_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Reconnect button — establishes session with node, then checks health."""
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    # Step 1: Try to establish a session (like Marzban /connect)
    connect_resp = await _node_request(node, 'POST', '/connect')
    if connect_resp and connect_resp.status_code == 200:
        logger.info(f"Node {node.name}: session established")

    # Step 2: Check health
    node.status = await _check_node_health(node)
    if node.status == 'online':
        node.last_heartbeat = datetime.now(timezone.utc)
    await cache_delete('dashboard')
    return {"status": node.status, "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None}


async def _check_node_health(node) -> str:
    """Check node health via REST API (mTLS), fallback to TCP on SS port."""
    api_port = node.api_port or 62050

    # Method 1: REST API health check — if node agent responds, it's online
    resp = await _node_request(node, 'GET', '/health')
    if resp:
        logger.info(f"Node {node.name}: /health returned {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                ss_running = data.get('healthy') or data.get('ss_running')
                if not ss_running:
                    logger.warning(f"Node {node.name}: agent reachable but ss-server NOT running")
                # Node agent responded 200 = node is online regardless of SS state
                return 'online'
            except Exception:
                return 'online'
        # Any response from node agent means it's reachable
        if resp.status_code in (503, 500):
            logger.warning(f"Node {node.name}: agent returned {resp.status_code}")
            return 'online'
    else:
        logger.warning(f"Node {node.name}: no response from {node.ip}:{api_port}")

    # Method 2: Fallback — TCP connect to SS port
    try:
        ss_port = node.ss_port or int(os.environ.get('SS_PORT', '8388'))
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(node.ip, ss_port), timeout=5
        )
        writer.close()
        await writer.wait_closed()
        logger.info(f"Node {node.name}: SS port {ss_port} reachable via TCP")
        return 'online'
    except Exception:
        pass

    return 'offline'


# ===== User Routes =====

@api_router.get("/users")
async def get_users(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(VPNUser).order_by(desc(VPNUser.created_at)))).scalars().all()
    result = []
    for u in users:
        traffic = (await db.execute(
            select(func.coalesce(func.sum(TrafficLog.bytes_transferred), 0)).where(TrafficLog.user_id == u.id)
        )).scalar()
        node_name = None
        if u.assigned_node_id:
            node_name = (await db.execute(select(Node.name).where(Node.id == u.assigned_node_id))).scalar_one_or_none()
        sub_path = f"/api/sub/{u.access_token}" if u.access_token else None
        node_stats = _node_stats_cache.get(u.assigned_node_id, {}) if u.assigned_node_id else {}
        result.append({
            "id": u.id, "username": u.username, "traffic_limit": u.traffic_limit,
            "expire_date": u.expire_date.isoformat() if u.expire_date else None,
            "assigned_node_id": u.assigned_node_id, "node_name": node_name,
            "access_url": u.access_url or u.ss_url,
            "sub_url": sub_path,
            "status": u.status, "created_at": u.created_at.isoformat(), "traffic_used": traffic,
            "online_devices": node_stats.get("connected_devices", 0),
            "connected_ips": node_stats.get("connected_ips", []),
            "last_connected_at": u.last_connected_at.isoformat() if u.last_connected_at else None,
        })
    return result

@api_router.post("/users")
async def create_user(req: UserCreate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(VPNUser).where(VPNUser.username == req.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Username already exists")
    ss_password = generate_password()
    token = secrets.token_urlsafe(32)
    user = VPNUser(
        username=req.username,
        traffic_limit=req.traffic_limit or 0,
        expire_date=datetime.fromisoformat(req.expire_date) if req.expire_date else None,
        assigned_node_id=req.assigned_node_id, status='active',
        ss_password=ss_password, access_token=token
    )
    db.add(user)
    await db.flush()
    if req.assigned_node_id:
        node = (await db.execute(select(Node).where(Node.id == req.assigned_node_id))).scalar_one_or_none()
        if node:
            user.access_url = await _build_user_ss_url_from_node(user, node, db)
            # Ensure server is running for the new user
            await ensure_server_running(node)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_created',
                    details=f'VPN user "{req.username}" created',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"id": user.id, "username": user.username, "access_url": user.access_url}

@api_router.put("/users/{user_id}")
async def update_user(user_id: int, req: UserUpdate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    data = req.model_dump(exclude_none=True)
    if 'expire_date' in data and data['expire_date']:
        data['expire_date'] = datetime.fromisoformat(data['expire_date'])
    node_changed = 'assigned_node_id' in data and data['assigned_node_id'] != user.assigned_node_id
    for k, v in data.items():
        setattr(user, k, v)
    # Regenerate ss:// URL if node changed or user has no ss_password yet
    if node_changed or (user.assigned_node_id and not user.ss_password):
        if not user.ss_password:
            user.ss_password = generate_password()
        if user.assigned_node_id:
            node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
            if node:
                user.access_url = await _build_user_ss_url_from_node(user, node, db)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_updated',
                    details=f'VPN user "{user.username}" updated',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"message": "User updated"}

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: int, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    await db.execute(delete(TrafficLog).where(TrafficLog.user_id == user_id))
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_deleted',
                    details=f'VPN user "{user.username}" deleted',
                    ip_address=request.client.host if request.client else None))
    await db.delete(user)
    await cache_delete('dashboard')
    return {"message": "User deleted"}

@api_router.post("/users/{user_id}/switch-node")
async def switch_node(user_id: int, req: SwitchNodeRequest, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    new_node = (await db.execute(select(Node).where(Node.id == req.node_id))).scalar_one_or_none()
    if not new_node:
        raise HTTPException(404, "Target node not found")
    if new_node.status != 'online':
        raise HTTPException(400, "Target node is not online")
    user.assigned_node_id = req.node_id
    if not user.ss_password:
        user.ss_password = generate_password()
    user.access_url = await _build_user_ss_url_from_node(user, new_node, db)
    # Ensure server is running on the new node
    await ensure_server_running(new_node)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_node_switched',
                    details=f'User "{user.username}" switched to "{new_node.name}"',
                    ip_address=request.client.host if request.client else None))
    return {"message": "Node switched", "access_url": user.access_url}

@api_router.post("/users/bulk-switch-node")
async def bulk_switch_node(req: BulkSwitchNodeRequest, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Switch ALL active users with assigned nodes to a new target node."""
    new_node = (await db.execute(select(Node).where(Node.id == req.node_id))).scalar_one_or_none()
    if not new_node:
        raise HTTPException(404, "Target node not found")
    if new_node.status != 'online':
        raise HTTPException(400, "Target node is not online")
    users = (await db.execute(
        select(VPNUser).where(VPNUser.status == 'active', VPNUser.assigned_node_id.isnot(None), VPNUser.assigned_node_id != req.node_id)
    )).scalars().all()
    switched = 0
    for user in users:
        try:
            user.assigned_node_id = req.node_id
            if not user.ss_password:
                user.ss_password = generate_password()
            user.access_url = await _build_user_ss_url_from_node(user, new_node, db)
            switched += 1
        except Exception as e:
            logger.error(f"Bulk switch error for user {user.username}: {e}")
    
    # Ensure server is running on the new node if any users were switched
    if switched > 0:
        await ensure_server_running(new_node)
    
    db.add(AuditLog(admin_id=int(admin["sub"]), action='bulk_node_switch',
                    details=f'{switched} users switched to "{new_node.name}"',
                    ip_address=request.client.host if request.client else None))
    return {"message": f"{switched} users switched to {new_node.name}", "switched": switched}


# ===== Traffic Routes =====

@api_router.get("/traffic")
async def get_traffic(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    by_user = (await db.execute(
        select(VPNUser.id, VPNUser.username, func.coalesce(func.sum(TrafficLog.bytes_transferred), 0).label('total'))
        .outerjoin(TrafficLog, TrafficLog.user_id == VPNUser.id)
        .group_by(VPNUser.id, VPNUser.username).order_by(desc('total'))
    )).all()
    by_node = (await db.execute(
        select(Node.id, Node.name, Node.country, func.coalesce(func.sum(TrafficLog.bytes_transferred), 0).label('total'))
        .outerjoin(TrafficLog, TrafficLog.node_id == Node.id)
        .group_by(Node.id, Node.name, Node.country).order_by(desc('total'))
    )).all()
    return {
        "by_user": [{"user_id": r[0], "username": r[1], "bytes": r[2]} for r in by_user],
        "by_node": [{"node_id": r[0], "name": r[1], "country": r[2], "bytes": r[3]} for r in by_node]
    }

@api_router.get("/traffic/daily")
async def get_daily_traffic(days: int = 30, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = (await db.execute(
        select(func.date(TrafficLog.recorded_at).label('date'), func.sum(TrafficLog.bytes_transferred).label('bytes'))
        .where(TrafficLog.recorded_at >= start)
        .group_by(func.date(TrafficLog.recorded_at))
        .order_by(func.date(TrafficLog.recorded_at))
    )).all()
    return [{"date": str(r[0]), "bytes": r[1]} for r in result]


# ===== License Routes =====

@api_router.get("/licenses")
async def get_licenses(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    lics = (await db.execute(select(License).order_by(desc(License.created_at)))).scalars().all()
    return [{
        "id": l.id, "license_key": l.license_key, "created_at": l.created_at.isoformat(),
        "expire_days": l.expire_days, "status": l.status, "max_servers": l.max_servers,
        "activated_servers": l.activated_servers, "server_fingerprint": l.server_fingerprint,
        "days_left": max(0, (l.created_at + timedelta(days=l.expire_days) - datetime.now(timezone.utc)).days) if l.expire_days > 0 else None
    } for l in lics]

@api_router.delete("/licenses/{license_id}")
async def revoke_license(license_id: int, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    lic = (await db.execute(select(License).where(License.id == license_id))).scalar_one_or_none()
    if not lic:
        raise HTTPException(404, "License not found")
    lic.status = 'revoked'
    db.add(AuditLog(admin_id=int(admin["sub"]), action='license_revoked',
                    details=f'License revoked: {lic.license_key}',
                    ip_address=request.client.host if request.client else None))
    return {"message": "License revoked"}

@api_router.post("/licenses/validate")
async def validate_license(req: LicenseValidate, db: AsyncSession = Depends(get_db)):
    lic = (await db.execute(select(License).where(License.license_key == req.license_key))).scalar_one_or_none()
    if not lic:
        return {"valid": False, "reason": "License key not found"}
    if lic.status != 'active':
        return {"valid": False, "reason": f"License is {lic.status}"}
    expire_date = lic.created_at + timedelta(days=lic.expire_days)
    if datetime.now(timezone.utc) > expire_date:
        lic.status = 'expired'
        return {"valid": False, "reason": "License expired"}
    if lic.activated_servers >= lic.max_servers:
        return {"valid": False, "reason": "Maximum activations reached"}
    return {"valid": True, "expires_in_days": (expire_date - datetime.now(timezone.utc)).days,
            "max_servers": lic.max_servers, "activated_servers": lic.activated_servers}

@api_router.post("/licenses/activate")
async def activate_license(req: LicenseActivate, request: Request, db: AsyncSession = Depends(get_db)):
    # Verify HMAC signature of the license key
    info = verify_license_key(req.license_key)
    if not info:
        return {"activated": False, "reason": "Invalid license key"}
    if info["expired"]:
        return {"activated": False, "reason": "License key has expired"}

    fingerprint = get_server_fingerprint()

    # Check if this key is already stored
    lic = (await db.execute(select(License).where(License.license_key == req.license_key))).scalar_one_or_none()
    if lic:
        if lic.status == 'active':
            return {"activated": True, "reason": "License already active",
                    "expires_in_days": info["expires_in_days"], "fingerprint": fingerprint}
        if lic.status == 'revoked':
            return {"activated": False, "reason": "License has been revoked"}

    # Check max_servers across all active licenses with same fingerprint
    if not lic:
        lic = License(
            license_key=req.license_key,
            expire_days=info["expire_days"],
            max_servers=info["max_servers"],
            activated_servers=1,
            status='active',
            server_fingerprint=fingerprint,
        )
        db.add(lic)
    else:
        lic.status = 'active'
        lic.server_fingerprint = fingerprint
        lic.activated_servers = 1

    db.add(AuditLog(admin_id=None, action='license_activated',
                    details=f'License activated: {req.license_key[:16]}...',
                    ip_address=request.client.host if request.client else None))
    
    # Backup license to persistent file so it survives DB resets
    _save_license_to_file(req.license_key, fingerprint)
    
    return {"activated": True, "expires_in_days": info["expires_in_days"],
            "fingerprint": fingerprint}

@api_router.get("/system/health")
async def system_health():
    return {"status": "ok", "version": "1.0.0"}


# ===== Subscription (ssconf) Endpoint =====

@api_router.get("/sub/{access_token}")
async def get_subscription(access_token: str, db: AsyncSession = Depends(get_db)):
    """Outline-compatible dynamic access key endpoint.
    
    Returns the ss:// URL directly (supported by Outline Client v1.8.1+).
    Used via ssconf:// protocol: ssconf://https://domain/api/sub/TOKEN
    
    The Outline client fetches this URL and reads the ss:// link to connect.
    """
    # Block subscription if license expired or missing — check in real-time
    lic = (await db.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
    if not lic:
        raise HTTPException(403, "Service unavailable")
    # Real-time expiry check (don't wait for background heartbeat)
    if lic.expire_days > 0:
        expire_date = lic.created_at + timedelta(days=lic.expire_days)
        if datetime.now(timezone.utc) > expire_date:
            lic.status = 'expired'
            await db.commit()
            raise HTTPException(403, "Service unavailable")
    user = (await db.execute(select(VPNUser).where(VPNUser.access_token == access_token))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Not found")
    if user.status != 'active':
        raise HTTPException(403, "Account suspended")
    # Check user expiry and traffic inline
    if user.expire_date and datetime.now(timezone.utc) > user.expire_date:
        raise HTTPException(403, "Account expired")
    if user.traffic_limit and user.traffic_limit > 0:
        total_used = (await db.execute(
            select(func.coalesce(func.sum(TrafficLog.bytes_transferred), 0)).where(TrafficLog.user_id == user.id)
        )).scalar()
        if total_used >= user.traffic_limit * 1024**3:
            raise HTTPException(403, "Traffic limit exceeded")
    # Build ss:// URL dynamically so port/password changes take effect immediately
    # without needing to regenerate or redistribute subscription URLs
    if not user.assigned_node_id:
        raise HTTPException(404, "No server assigned")
    node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Server not found")
    ss_url = await _build_user_ss_url_from_node(user, node, db)
    if not ss_url:
        raise HTTPException(404, "No access URL configured")
    if '?' not in ss_url:
        ss_url += '/?outline=1'
    return PlainTextResponse(ss_url, media_type="text/plain")


# ===== Audit Logs =====

@api_router.get("/audit-logs")
async def get_audit_logs(page: int = 1, limit: int = 50, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(AuditLog.id)))).scalar()
    logs = (await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).offset((page - 1) * limit).limit(limit)
    )).scalars().all()
    return {
        "total": total, "page": page, "limit": limit,
        "logs": [{"id": l.id, "admin_id": l.admin_id, "action": l.action, "details": l.details,
                  "ip_address": l.ip_address, "created_at": l.created_at.isoformat()} for l in logs]
    }


# ===== Settings =====

@api_router.get("/settings")
async def get_settings(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    settings = (await db.execute(select(PanelSettings))).scalars().all()
    return {s.key: s.value for s in settings}

@api_router.put("/settings")
async def update_settings(req: SettingsUpdate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    ss_port_changed = False
    new_ss_port = None

    # Save ALL settings to DB first (always succeeds)
    for key, value in req.settings.items():
        existing = (await db.execute(select(PanelSettings).where(PanelSettings.key == key))).scalar_one_or_none()
        if existing:
            if key == 'ss_port' and existing.value != str(value):
                ss_port_changed = True
                new_ss_port = int(value)
            existing.value = str(value)
        else:
            db.add(PanelSettings(key=key, value=str(value)))
            if key == 'ss_port':
                ss_port_changed = True
                new_ss_port = int(value)

    # If port changed, push the change to all nodes AND update their DB records
    node_ok = 0
    node_errors = 0
    error_details = []
    if ss_port_changed and new_ss_port:
        nodes = (await db.execute(select(Node))).scalars().all()
        for node in nodes:
            # Always update the node's ss_port in DB so URLs are consistent
            node.ss_port = new_ss_port
            # Also try to tell the actual node to change its running ss-server port
            try:
                connect_resp = await _node_request(node, 'POST', '/connect')
                if connect_resp and connect_resp.status_code == 200:
                    sid = connect_resp.json().get('session_id')
                    if sid:
                        resp = await _node_request(node, 'POST', '/config/port',
                                                   json={"session_id": sid, "port": new_ss_port})
                        if resp and resp.status_code == 200:
                            node_ok += 1
                            logger.info(f"Node {node.name}: SS port changed to {new_ss_port}")
                        else:
                            code = resp.status_code if resp else 'no response'
                            body = resp.text[:200] if resp else ''
                            error_details.append(f"{node.name}: ({code}) {body}")
                            node_errors += 1
                    else:
                        error_details.append(f"{node.name}: no session from /connect")
                        node_errors += 1
                else:
                    code = connect_resp.status_code if connect_resp else 'unreachable'
                    error_details.append(f"{node.name}: ({code})")
                    node_errors += 1
            except Exception as e:
                error_details.append(f"{node.name}: {str(e)[:80]}")
                node_errors += 1
        logger.info(f"SS port → {new_ss_port}: {node_ok} OK, {node_errors} errors")

        # Regenerate stored access_url for ALL users so QR codes show the new port
        users = (await db.execute(
            select(VPNUser).where(VPNUser.assigned_node_id.isnot(None), VPNUser.ss_password.isnot(None))
        )).scalars().all()
        url_count = 0
        for user in users:
            node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
            if node:
                user.access_url = await _build_user_ss_url_from_node(user, node, db, force_port=new_ss_port)
                url_count += 1
        logger.info(f"Regenerated {url_count} user access URLs with new port {new_ss_port}")

    db.add(AuditLog(admin_id=int(admin["sub"]), action='settings_updated',
                    details=f'Settings updated' + (f' — SS port → {new_ss_port} ({node_ok} nodes live)' if ss_port_changed else ''),
                    ip_address=request.client.host if request.client else None))
    msg = "Settings saved"
    if ss_port_changed:
        if node_ok > 0 and node_errors == 0:
            msg = f"Port changed to {new_ss_port} on all nodes"
        elif node_ok > 0:
            msg = f"Port changed to {new_ss_port} on {node_ok} node(s), {node_errors} failed"
        else:
            msg = (f"Port saved as {new_ss_port}. "
                   f"Warning: could not reach nodes to apply live — "
                   f"restart your node(s) to apply. {'; '.join(error_details)}")
    return {"message": msg}


# ===== Backup =====

@api_router.post("/backup")
async def create_backup(request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    nodes = (await db.execute(select(Node))).scalars().all()
    users = (await db.execute(select(VPNUser))).scalars().all()
    lics = (await db.execute(select(License))).scalars().all()
    settings = (await db.execute(select(PanelSettings))).scalars().all()
    db.add(AuditLog(admin_id=int(admin["sub"]), action='backup_created',
                    details='Database backup created', ip_address=request.client.host if request.client else None))
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(), "version": "1.0.0",
        "nodes": [{"name": n.name, "ip": n.ip, "api_port": n.api_port, "country": n.country} for n in nodes],
        "users": [{"username": u.username, "traffic_limit": u.traffic_limit, "device_limit": u.device_limit, "status": u.status} for u in users],
        "licenses": [{"license_key": l.license_key, "expire_days": l.expire_days, "status": l.status, "max_servers": l.max_servers} for l in lics],
        "settings": {s.key: s.value for s in settings}
    }


# ===== Background Tasks =====

async def collect_node_stats():
    """Poll /stats from each online node every 15s.
    
    - Stores connected devices/IPs in _node_stats_cache for API responses.
    - Computes traffic deltas and writes to TrafficLog (distributed across
      active users on each node, since single-password mode can't distinguish users).
    - Updates last_connected_at for users on nodes with active connections.
    """
    while True:
        try:
            async with async_session() as session:
                nodes = (await session.execute(select(Node))).scalars().all()
                for node in nodes:
                    if node.status != 'online':
                        continue
                    try:
                        resp = await _node_request(node, 'GET', '/stats')
                        if not resp or resp.status_code != 200:
                            continue
                        data = resp.json()
                        upload = data.get('upload', 0)
                        download = data.get('download', 0)
                        total_bytes = upload + download
                        
                        # Store in runtime cache for API responses
                        _node_stats_cache[node.id] = {
                            "upload": upload,
                            "download": download,
                            "connected_devices": data.get('connected_devices', 0),
                            "connected_ips": data.get('connected_ips', []),
                        }
                        
                        # Compute delta since last poll
                        last = _node_last_bytes.get(node.id, 0)
                        delta = total_bytes - last if total_bytes > last else 0
                        _node_last_bytes[node.id] = total_bytes
                        
                        if delta > 0 and last > 0:
                            # Distribute delta across active users on this node
                            active_users = (await session.execute(
                                select(VPNUser).where(
                                    VPNUser.assigned_node_id == node.id,
                                    VPNUser.status == 'active'
                                )
                            )).scalars().all()
                            
                            if active_users:
                                per_user = delta // len(active_users)
                                remainder = delta % len(active_users)
                                for i, user in enumerate(active_users):
                                    user_bytes = per_user + (1 if i < remainder else 0)
                                    if user_bytes > 0:
                                        session.add(TrafficLog(
                                            user_id=user.id,
                                            node_id=node.id,
                                            bytes_transferred=user_bytes,
                                        ))
                            else:
                                # No active users — log traffic to node only
                                session.add(TrafficLog(
                                    user_id=None,
                                    node_id=node.id,
                                    bytes_transferred=delta,
                                ))
                        
                        # Update last_connected_at for active users on this node if there are connections
                        if data.get('connected_devices', 0) > 0:
                            connected_users = (await session.execute(
                                select(VPNUser).where(
                                    VPNUser.assigned_node_id == node.id,
                                    VPNUser.status == 'active'
                                )
                            )).scalars().all()
                            now = datetime.now(timezone.utc)
                            for cu in connected_users:
                                cu.last_connected_at = now

                        logger.debug(f"Node {node.name} stats: up={upload}, down={download}, devices={data.get('connected_devices', 0)}, delta={delta}")
                    except Exception as e:
                        logger.debug(f"Failed to collect stats from {node.name}: {e}")
                await session.commit()
        except Exception as e:
            logger.error(f"Stats collection error: {e}")
        await asyncio.sleep(15)


async def check_all_nodes_health():
    while True:
        try:
            async with async_session() as session:
                nodes = (await session.execute(select(Node))).scalars().all()
                for node in nodes:
                    # Try to establish/maintain session with each node
                    try:
                        await _node_request(node, 'POST', '/connect')
                    except Exception:
                        pass
                    node.status = await _check_node_health(node)
                    if node.status == 'online':
                        node.last_heartbeat = datetime.now(timezone.utc)
                await session.commit()
                online = sum(1 for n in nodes if n.status == 'online')
                logger.info(f"Health check: {online}/{len(nodes)} nodes online")
        except Exception as e:
            logger.error(f"Health check error: {e}")
        await asyncio.sleep(300)

async def license_heartbeat():
    """Validate license every 6 hours. Stop all nodes if license expired/invalid."""
    while True:
        try:
            async with async_session() as session:
                lic = (await session.execute(
                    select(License).where(License.status == 'active').limit(1)
                )).scalar_one_or_none()
                if lic:
                    expire_date = lic.created_at + timedelta(days=lic.expire_days)
                    if lic.expire_days > 0 and datetime.now(timezone.utc) > expire_date:
                        lic.status = 'expired'
                        logger.warning("License expired — stopping all nodes")
                        # Stop ss-server on all online nodes
                        nodes = (await session.execute(select(Node).where(Node.status == 'online'))).scalars().all()
                        for node in nodes:
                            try:
                                await _node_connect_and_action(node, 'stop')
                            except Exception:
                                pass
                    elif lic.server_fingerprint and lic.server_fingerprint != get_server_fingerprint():
                        # Fingerprint changed (e.g. container rebuilt) — update it
                        # The fingerprint is now stable (persisted to volume), but handle
                        # legacy cases where old fingerprint used container hostname
                        old_fp = lic.server_fingerprint
                        lic.server_fingerprint = get_server_fingerprint()
                        logger.info(f"License fingerprint updated: {old_fp[:8]}... → {lic.server_fingerprint[:8]}...")
                    else:
                        days_left = (expire_date - datetime.now(timezone.utc)).days if lic.expire_days > 0 else 'unlimited'
                        logger.info(f"License heartbeat OK — expires in {days_left} days")
                    await session.commit()
                else:
                    logger.info("No active license found")
        except Exception as e:
            logger.error(f"License heartbeat error: {e}")
        await asyncio.sleep(1800)  # Check every 30 minutes


async def user_validation_task():
    """Check user limits and deactivate expired/over-limit users every 5 minutes."""
    while True:
        try:
            async with async_session() as session:
                # Get all active users with assigned nodes
                users = (await session.execute(
                    select(VPNUser).where(VPNUser.status == 'active', VPNUser.assigned_node_id.isnot(None))
                )).scalars().all()
                
                disabled_count = 0
                for user in users:
                    validation = await validate_user_access(user, session)
                    
                    if not validation["allowed"]:
                        node = (await session.execute(
                            select(Node).where(Node.id == user.assigned_node_id)
                        )).scalar_one_or_none()
                        
                        reason = ", ".join(validation["errors"])
                        user.status = 'disabled'
                        session.add(AuditLog(
                            admin_id=None,
                            action='user_auto_disabled',
                            details=f'User "{user.username}" automatically disabled: {reason}'
                        ))
                        disabled_count += 1
                        
                        if node:
                            await deactivate_user_on_node(user, node, session, reason)
                
                if disabled_count > 0:
                    await session.commit()
                    logger.info(f"User validation: disabled {disabled_count} users")
                                
        except Exception as e:
            logger.error(f"User validation task error: {e}")
        
        await asyncio.sleep(60)  # Check every 60 seconds for quick enforcement


# ===== App Events =====

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    async with async_session() as session:
        admin_count = (await session.execute(select(func.count(Admin.id)))).scalar()
        lic = (await session.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
        node_count = (await session.execute(select(func.count(Node.id)))).scalar()
        if admin_count == 0:
            logger.warning("No admin account found. Create one with: docker exec -it lightline-backend python cli.py admin create")
        if not lic:
            # Check for suspended license (old fingerprint bug) — reactivate it
            suspended = (await session.execute(
                select(License).where(License.status == 'suspended').limit(1)
            )).scalar_one_or_none()
            if suspended:
                info = verify_license_key(suspended.license_key)
                if info and not info["expired"]:
                    suspended.status = 'active'
                    suspended.server_fingerprint = get_server_fingerprint()
                    lic = suspended
                    session.add(AuditLog(admin_id=None, action='license_reactivated',
                                        details=f'Suspended license reactivated (fingerprint updated)'))
                    await session.commit()
                    logger.info("Reactivated suspended license (fingerprint was stale)")
            
            if not lic:
                # Try to restore license from persistent backup file
                backup = _load_license_from_file()
                if backup and backup.get("license_key"):
                    logger.info("Restoring license from backup file...")
                    info = verify_license_key(backup["license_key"])
                    if info and not info["expired"]:
                        # Check if this key already exists in DB (maybe with wrong status)
                        existing = (await session.execute(
                            select(License).where(License.license_key == backup["license_key"])
                        )).scalar_one_or_none()
                        if existing:
                            existing.status = 'active'
                            existing.server_fingerprint = get_server_fingerprint()
                            lic = existing
                        else:
                            lic = License(
                                license_key=backup["license_key"],
                                expire_days=info["expire_days"],
                                max_servers=info["max_servers"],
                                activated_servers=1,
                                status='active',
                                server_fingerprint=get_server_fingerprint(),
                            )
                            session.add(lic)
                        session.add(AuditLog(admin_id=None, action='license_restored',
                                            details=f'License restored from backup: {backup["license_key"][:16]}...'))
                        await session.commit()
                        logger.info("License restored successfully from backup")
                    else:
                        logger.warning("Backup license is expired or invalid")
                else:
                    logger.warning("No active license found. Activate with: lightline activate")
        if node_count == 0:
            # Create default node using environment variables
            default_ip = os.environ.get('SERVER_IP', '127.0.0.1')
            default_port = int(os.environ.get('SS_PORT', '8388'))
            default_node = Node(
                name="Main Server",
                ip=default_ip,
                ss_port=default_port,
                api_port=62050,
                status='offline'
            )
            session.add(default_node)
            await session.commit()
            logger.info(f"Created default node: {default_ip}:{default_port}")
    
    # Start background tasks
    asyncio.create_task(collect_node_stats())
    asyncio.create_task(license_heartbeat())
    asyncio.create_task(user_validation_task())
    logger.info("Lightline VPN Panel started")

@app.on_event("shutdown")
async def shutdown():
    await close_redis()
    await engine.dispose()

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
