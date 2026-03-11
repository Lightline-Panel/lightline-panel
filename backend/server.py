from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
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
import platform
import uuid
import random
from pathlib import Path
from dotenv import load_dotenv
import pyotp
import qrcode

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from database import async_session, get_db, engine, Base
from models import Admin, Node, VPNUser, TrafficLog, License, AuditLog, PanelSettings
from auth import (hash_password, verify_password, create_access_token,
                  create_refresh_token, decode_token, get_current_admin)
from outline_client import OutlineClient
from cache import cache_get_json, cache_set_json, cache_delete, close_redis
from license_client import (
    is_external_license_server_configured,
    activate_license as external_activate_license,
    validate_license as external_validate_license,
    heartbeat as external_heartbeat,
    get_server_fingerprint as get_fingerprint_from_client,
)

OUTLINE_MODE = os.environ.get('OUTLINE_MODE', 'mock')
LICENSE_SERVER_URL = os.environ.get('LICENSE_SERVER_URL', '')

app = FastAPI(title="Lightline VPN Panel")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    api_port: int
    api_key: str
    country: Optional[str] = None

class NodeUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    api_port: Optional[int] = None
    api_key: Optional[str] = None
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


# ===== Auth Routes =====

@api_router.get("/")
async def root():
    return {"message": "Lightline VPN Panel API", "version": "1.0.0"}

@api_router.get("/auth/check-setup")
async def check_setup(db: AsyncSession = Depends(get_db)):
    admin_count = (await db.execute(select(func.count(Admin.id)))).scalar()
    lic = (await db.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
    return {
        "setup_required": admin_count == 0,
        "license_active": lic is not None,
        "message": "Create admin via CLI: docker exec -it lightline-backend python cli.py admin create" if admin_count == 0 else None
    }

@api_router.post("/auth/login")
async def login(req: LoginTOTPRequest, request: Request, db: AsyncSession = Depends(get_db)):
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

def get_server_fingerprint() -> str:
    raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ===== QR Code Generation =====

@api_router.get("/users/{user_id}/qrcode")
async def get_user_qrcode(user_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    url = user.ss_url or user.access_url
    if not url:
        raise HTTPException(404, "No access URL available")
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return {"qr_code": f"data:image/png;base64,{qr_b64}", "url": url}


# ===== Public Access Endpoint (ssconf:// subscription) =====

def _build_ssconf_url(request: Request, access_token: str) -> str:
    """Build ssconf:// URL from the request host"""
    host = request.headers.get('x-forwarded-host') or request.headers.get('host') or 'localhost'
    return f"ssconf://{host}/api/access/{access_token}"

@api_router.get("/access/{access_token}", response_class=PlainTextResponse)
async def get_access_config(access_token: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint: Outline clients fetch current SS config via ssconf:// URL"""
    user = (await db.execute(
        select(VPNUser).where(VPNUser.access_token == access_token)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Access key not found")
    if user.status != 'active':
        raise HTTPException(403, "Access key disabled")
    if not user.ss_url:
        raise HTTPException(404, "No active connection config")
    return PlainTextResponse(user.ss_url, media_type="text/plain")


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

    result = {
        "nodes": {"total": nodes_total, "online": nodes_online, "offline": nodes_total - nodes_online},
        "users": {"total": users_total, "active": users_active},
        "traffic": {"today": traffic_today, "total": traffic_total},
        "license": {
            "active": lic is not None,
            "key": lic.license_key[:12] + "..." if lic else None,
            "expires_in": lic.expire_days if lic else None,
            "status": lic.status if lic else "none"
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
    result = []
    for n in nodes:
        uc = (await db.execute(select(func.count(VPNUser.id)).where(VPNUser.assigned_node_id == n.id))).scalar()
        result.append({
            "id": n.id, "name": n.name, "ip": n.ip, "api_port": n.api_port,
            "api_key": n.api_key[:16] + "..." if len(n.api_key) > 16 else n.api_key,
            "country": n.country, "status": n.status,
            "last_heartbeat": n.last_heartbeat.isoformat() if n.last_heartbeat else None,
            "created_at": n.created_at.isoformat(), "user_count": uc
        })
    return result

@api_router.post("/nodes")
async def create_node(req: NodeCreate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = Node(name=req.name, ip=req.ip, api_port=req.api_port, api_key=req.api_key, country=req.country, status='unknown')
    db.add(node)
    await db.flush()
    client = OutlineClient(f"https://{req.ip}:{req.api_port}", req.api_key)
    try:
        healthy = await client.check_health()
        node.status = 'online' if healthy else 'offline'
        node.last_heartbeat = datetime.now(timezone.utc)
    except Exception:
        node.status = 'offline'
    db.add(AuditLog(admin_id=int(admin["sub"]), action='node_created',
                    details=f'Node "{req.name}" ({req.country}) added',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"id": node.id, "name": node.name, "status": node.status}

@api_router.put("/nodes/{node_id}")
async def update_node(node_id: int, req: NodeUpdate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    for k, v in req.model_dump(exclude_none=True).items():
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

@api_router.post("/nodes/{node_id}/health-check")
async def health_check(node_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    client = OutlineClient(f"https://{node.ip}:{node.api_port}", node.api_key)
    try:
        healthy = await client.check_health()
        node.status = 'online' if healthy else 'offline'
        node.last_heartbeat = datetime.now(timezone.utc)
    except Exception:
        node.status = 'offline'
    await cache_delete('dashboard')
    return {"status": node.status, "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None}

@api_router.post("/nodes/{node_id}/sync-keys")
async def sync_keys(node_id: int, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    node = (await db.execute(select(Node).where(Node.id == node_id))).scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    client = OutlineClient(f"https://{node.ip}:{node.api_port}", node.api_key)
    keys_data = await client.get_access_keys()
    return {"keys": keys_data.get("accessKeys", []), "synced": True}


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
        result.append({
            "id": u.id, "username": u.username, "traffic_limit": u.traffic_limit,
            "device_limit": u.device_limit,
            "expire_date": u.expire_date.isoformat() if u.expire_date else None,
            "assigned_node_id": u.assigned_node_id, "node_name": node_name,
            "outline_key_id": u.outline_key_id, "access_url": u.ss_url or u.access_url,
            "subscription_url": u.access_url if u.access_url and u.access_url.startswith('ssconf://') else None,
            "ss_url": u.ss_url, "access_token": u.access_token,
            "status": u.status, "created_at": u.created_at.isoformat(), "traffic_used": traffic
        })
    return result

@api_router.post("/users")
async def create_user(req: UserCreate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(VPNUser).where(VPNUser.username == req.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Username already exists")
    token = secrets.token_urlsafe(32)
    user = VPNUser(
        username=req.username,
        traffic_limit=req.traffic_limit or 0,
        expire_date=datetime.fromisoformat(req.expire_date) if req.expire_date else None,
        assigned_node_id=req.assigned_node_id, status='active',
        access_token=token
    )
    db.add(user)
    await db.flush()
    if req.assigned_node_id:
        node = (await db.execute(select(Node).where(Node.id == req.assigned_node_id))).scalar_one_or_none()
        if node:
            client = OutlineClient(f"https://{node.ip}:{node.api_port}", node.api_key)
            key_data = await client.create_access_key(name=req.username)
            user.outline_key_id = key_data.get('id')
            user.ss_url = key_data.get('accessUrl')
            user.access_url = _build_ssconf_url(request, token)
            if req.traffic_limit and req.traffic_limit > 0:
                await client.set_data_limit(key_data['id'], req.traffic_limit)
    else:
        user.access_url = _build_ssconf_url(request, token)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_created',
                    details=f'VPN user "{req.username}" created',
                    ip_address=request.client.host if request.client else None))
    await cache_delete('dashboard')
    return {"id": user.id, "username": user.username, "access_url": user.ss_url or user.access_url, "outline_key_id": user.outline_key_id}

@api_router.put("/users/{user_id}")
async def update_user(user_id: int, req: UserUpdate, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(VPNUser).where(VPNUser.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    data = req.model_dump(exclude_none=True)
    if 'expire_date' in data and data['expire_date']:
        data['expire_date'] = datetime.fromisoformat(data['expire_date'])
    for k, v in data.items():
        setattr(user, k, v)
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
    if user.outline_key_id and user.assigned_node_id:
        node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
        if node:
            client = OutlineClient(f"https://{node.ip}:{node.api_port}", node.api_key)
            await client.delete_access_key(user.outline_key_id)
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
    if user.outline_key_id and user.assigned_node_id:
        old_node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
        if old_node:
            await OutlineClient(f"https://{old_node.ip}:{old_node.api_port}", old_node.api_key).delete_access_key(user.outline_key_id)
    new_client = OutlineClient(f"https://{new_node.ip}:{new_node.api_port}", new_node.api_key)
    key_data = await new_client.create_access_key(name=user.username)
    user.assigned_node_id = req.node_id
    user.outline_key_id = key_data.get('id')
    user.ss_url = key_data.get('accessUrl')
    if not user.access_token:
        user.access_token = secrets.token_urlsafe(32)
    if not user.access_url or not user.access_url.startswith('ssconf://'):
        user.access_url = _build_ssconf_url(request, user.access_token)
    db.add(AuditLog(admin_id=int(admin["sub"]), action='user_node_switched',
                    details=f'User "{user.username}" switched to "{new_node.name}"',
                    ip_address=request.client.host if request.client else None))
    return {"message": "Node switched", "access_url": user.ss_url or user.access_url}

@api_router.post("/users/bulk-switch-node")
async def bulk_switch_node(req: BulkSwitchNodeRequest, request: Request, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Switch ALL active users with assigned nodes to a new target node"""
    new_node = (await db.execute(select(Node).where(Node.id == req.node_id))).scalar_one_or_none()
    if not new_node:
        raise HTTPException(404, "Target node not found")
    if new_node.status != 'online':
        raise HTTPException(400, "Target node is not online")
    users = (await db.execute(
        select(VPNUser).where(VPNUser.status == 'active', VPNUser.assigned_node_id.isnot(None), VPNUser.assigned_node_id != req.node_id)
    )).scalars().all()
    switched = 0
    new_client = OutlineClient(f"https://{new_node.ip}:{new_node.api_port}", new_node.api_key)
    for user in users:
        try:
            if user.outline_key_id and user.assigned_node_id:
                old_node = (await db.execute(select(Node).where(Node.id == user.assigned_node_id))).scalar_one_or_none()
                if old_node:
                    await OutlineClient(f"https://{old_node.ip}:{old_node.api_port}", old_node.api_key).delete_access_key(user.outline_key_id)
            key_data = await new_client.create_access_key(name=user.username)
            user.assigned_node_id = req.node_id
            user.outline_key_id = key_data.get('id')
            user.ss_url = key_data.get('accessUrl')
            if not user.access_token:
                user.access_token = secrets.token_urlsafe(32)
            if not user.access_url or not user.access_url.startswith('ssconf://'):
                user.access_url = _build_ssconf_url(request, user.access_token)
            switched += 1
        except Exception as e:
            logger.error(f"Bulk switch error for user {user.username}: {e}")
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
        "activated_servers": l.activated_servers, "server_fingerprint": l.server_fingerprint
    } for l in lics]

@api_router.post("/licenses/validate")
async def validate_license(req: LicenseValidate, db: AsyncSession = Depends(get_db)):
    # Use external license server if configured
    if is_external_license_server_configured():
        result = await external_validate_license(req.license_key)
        if result.get('valid'):
            return {"valid": True, "expires_at": result.get('expires_at'),
                    "max_servers": result.get('max_servers'),
                    "activated_servers": result.get('activated_servers')}
        return {"valid": False, "reason": result.get('error', 'Validation failed')}

    # Fallback: local validation
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
    # Use external license server if configured
    if is_external_license_server_configured():
        result = await external_activate_license(req.license_key, hostname=platform.node())
        if result.get('success'):
            # Store/update local license record for dashboard display
            lic = (await db.execute(select(License).where(License.license_key == req.license_key))).scalar_one_or_none()
            if not lic:
                lic = License(license_key=req.license_key, expire_days=0, max_servers=1,
                              activated_servers=1, status='active',
                              server_fingerprint=get_server_fingerprint())
                db.add(lic)
            else:
                lic.status = 'active'
                lic.server_fingerprint = get_server_fingerprint()
            db.add(AuditLog(admin_id=None, action='license_activated',
                            details=f'License activated via external server: {req.license_key[:16]}...',
                            ip_address=request.client.host if request.client else None))
            return {"activated": True, "message": result.get('message'),
                    "server_id": result.get('server_id'),
                    "expires_at": result.get('expires_at'),
                    "fingerprint": get_server_fingerprint()}
        return {"activated": False, "reason": result.get('error', 'Activation failed')}

    # Fallback: local activation
    lic = (await db.execute(select(License).where(License.license_key == req.license_key))).scalar_one_or_none()
    if not lic:
        return {"activated": False, "reason": "License key not found"}
    if lic.status != 'active':
        return {"activated": False, "reason": f"License is {lic.status}"}
    expire_date = lic.created_at + timedelta(days=lic.expire_days)
    if datetime.now(timezone.utc) > expire_date:
        lic.status = 'expired'
        return {"activated": False, "reason": "License expired"}
    fingerprint = get_server_fingerprint()
    if lic.server_fingerprint and lic.server_fingerprint != fingerprint:
        return {"activated": False, "reason": "License bound to a different server"}
    if not lic.server_fingerprint:
        if lic.activated_servers >= lic.max_servers:
            return {"activated": False, "reason": "Maximum activations reached"}
        lic.server_fingerprint = fingerprint
        lic.activated_servers += 1
    return {"activated": True, "expires_in_days": (expire_date - datetime.now(timezone.utc)).days,
            "fingerprint": fingerprint}

@api_router.get("/system/fingerprint")
async def system_fingerprint(admin=Depends(get_current_admin)):
    return {"fingerprint": get_server_fingerprint()}

@api_router.get("/system/health")
async def system_health():
    return {"status": "ok", "version": "1.0.0", "mode": OUTLINE_MODE}


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
    for key, value in req.settings.items():
        existing = (await db.execute(select(PanelSettings).where(PanelSettings.key == key))).scalar_one_or_none()
        if existing:
            existing.value = str(value)
        else:
            db.add(PanelSettings(key=key, value=str(value)))
    db.add(AuditLog(admin_id=int(admin["sub"]), action='settings_updated',
                    details='Panel settings updated', ip_address=request.client.host if request.client else None))
    return {"message": "Settings updated"}


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

async def check_all_nodes_health():
    while True:
        try:
            async with async_session() as session:
                nodes = (await session.execute(select(Node))).scalars().all()
                for node in nodes:
                    client = OutlineClient(f"https://{node.ip}:{node.api_port}", node.api_key)
                    try:
                        healthy = await client.check_health()
                        node.status = 'online' if healthy else 'offline'
                        node.last_heartbeat = datetime.now(timezone.utc)
                    except Exception:
                        node.status = 'offline'
                await session.commit()
                logger.info(f"Health check: {len(nodes)} nodes checked")
        except Exception as e:
            logger.error(f"Health check error: {e}")
        await asyncio.sleep(300)

async def license_heartbeat():
    """Validate license every 6 hours. Suspend panel if invalid."""
    while True:
        try:
            async with async_session() as session:
                lic = (await session.execute(
                    select(License).where(License.status == 'active').limit(1)
                )).scalar_one_or_none()
                if lic:
                    # External license server heartbeat (preferred)
                    if is_external_license_server_configured():
                        result = await external_heartbeat(lic.license_key)
                        if result.get('success'):
                            logger.info(f"External heartbeat OK — expires at {result.get('expires_at')}")
                        else:
                            error = result.get('error', 'Unknown')
                            logger.warning(f"External heartbeat failed: {error}")
                            # Only suspend on definitive failures, not timeouts
                            if 'timeout' not in error.lower() and 'unreachable' not in error.lower():
                                lic.status = 'suspended'
                                logger.warning("License suspended by external server")
                    else:
                        # Local-only validation
                        expire_date = lic.created_at + timedelta(days=lic.expire_days)
                        if datetime.now(timezone.utc) > expire_date:
                            lic.status = 'expired'
                            logger.warning("License expired — panel suspended")
                        elif lic.server_fingerprint and lic.server_fingerprint != get_server_fingerprint():
                            lic.status = 'suspended'
                            logger.warning("License fingerprint mismatch — panel suspended")
                        else:
                            logger.info(f"License heartbeat OK — expires in {(expire_date - datetime.now(timezone.utc)).days} days")
                    await session.commit()
                else:
                    logger.info("No active license found")
        except Exception as e:
            logger.error(f"License heartbeat error: {e}")
        await asyncio.sleep(21600)  # 6 hours


# ===== App Events =====

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    async with async_session() as session:
        admin_count = (await session.execute(select(func.count(Admin.id)))).scalar()
        lic = (await session.execute(select(License).where(License.status == 'active').limit(1))).scalar_one_or_none()
        if admin_count == 0:
            logger.warning("No admin account found. Create one with: docker exec -it lightline-backend python cli.py admin create")
        if not lic:
            logger.warning("No active license. Activate with: docker exec -it lightline-backend python cli.py license activate <KEY>")
    asyncio.create_task(check_all_nodes_health())
    asyncio.create_task(license_heartbeat())
    logger.info(f"Lightline VPN Panel started (mode={OUTLINE_MODE})")

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
