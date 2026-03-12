#!/usr/bin/env python3
"""Lightline VPN Panel CLI — Admin and license management commands."""

import asyncio
import sys
import os
import getpass
import secrets
import hashlib
import hmac
import struct
import time as _time
import platform
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from sqlalchemy import select, func
from database import async_session, engine, Base
from models import Admin, License
from auth import hash_password

LICENSE_SECRET = os.environ.get('LICENSE_SECRET', 'lightline-hmac-2024-secure-key').encode()


FINGERPRINT_PATH = Path('/var/lib/lightline/certs/server_fingerprint')

def get_server_fingerprint() -> str:
    """Stable server fingerprint — reads from persistent volume first."""
    try:
        if FINGERPRINT_PATH.exists():
            saved = FINGERPRINT_PATH.read_text().strip()
            if saved:
                return saved
    except Exception:
        pass
    raw = f"{uuid.getnode()}-{platform.machine()}"
    fp = hashlib.sha256(raw.encode()).hexdigest()[:32]
    try:
        FINGERPRINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        FINGERPRINT_PATH.write_text(fp)
    except Exception:
        pass
    return fp


def verify_license_key(key: str) -> dict | None:
    """Verify an HMAC-signed license key."""
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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def cmd_admin_create():
    """Interactive admin creation — prompts for username and password."""
    await init_db()
    print()
    print("  Lightline VPN Panel — Create Admin Account")
    print("  " + "=" * 44)
    print()
    username = input("  Username: ").strip()
    if not username:
        print("[ERROR] Username cannot be empty")
        return
    password = getpass.getpass("  Password: ").strip()
    if not password:
        print("[ERROR] Password cannot be empty")
        return
    confirm = getpass.getpass("  Confirm password: ").strip()
    if password != confirm:
        print("[ERROR] Passwords do not match")
        return
    async with async_session() as session:
        existing = (await session.execute(
            select(Admin).where(Admin.username == username)
        )).scalar_one_or_none()
        if existing:
            print(f"[ERROR] Admin '{username}' already exists. Use 'admin reset' to change password.")
            return
        admin = Admin(username=username, password_hash=hash_password(password), role='admin')
        session.add(admin)
        await session.commit()
        print()
        print(f"  [OK] Admin '{username}' created successfully")
        print(f"  You can now log in to the panel.")
        print()


async def cmd_admin_delete(username: str = None):
    """Delete an admin account."""
    await init_db()
    if not username:
        username = input("  Username to delete: ").strip()
    if not username:
        print("[ERROR] Username cannot be empty")
        return
    async with async_session() as session:
        admin = (await session.execute(
            select(Admin).where(Admin.username == username)
        )).scalar_one_or_none()
        if not admin:
            print(f"[ERROR] Admin '{username}' not found")
            return
        # Safety: don't delete the last admin
        count = (await session.execute(select(func.count(Admin.id)))).scalar()
        if count <= 1:
            print("[ERROR] Cannot delete the last admin account")
            return
        await session.delete(admin)
        await session.commit()
        print(f"[OK] Admin '{username}' deleted")


async def cmd_admin_list():
    """List all admin accounts."""
    await init_db()
    async with async_session() as session:
        admins = (await session.execute(
            select(Admin).order_by(Admin.created_at)
        )).scalars().all()
        if not admins:
            print("  No admin accounts found.")
            return
        print()
        print(f"  {'ID':<5} {'Username':<20} {'Role':<10} {'2FA':<5} {'Created'}")
        print(f"  {'—'*5} {'—'*20} {'—'*10} {'—'*5} {'—'*20}")
        for a in admins:
            has_2fa = 'Yes' if a.totp_secret else 'No'
            created = a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else '—'
            print(f"  {a.id:<5} {a.username:<20} {a.role:<10} {has_2fa:<5} {created}")
        print()


async def cmd_admin_reset(username: str = None, password: str = None):
    """Reset admin password or create if not exists."""
    await init_db()
    if not username:
        username = input("  Username to reset: ").strip()
    if not username:
        print("[ERROR] Username cannot be empty")
        return
    if not password:
        password = getpass.getpass("  New password: ").strip()
    if not password:
        print("[ERROR] Password cannot be empty")
        return
    async with async_session() as session:
        admin = (await session.execute(
            select(Admin).where(Admin.username == username)
        )).scalar_one_or_none()
        if admin:
            admin.password_hash = hash_password(password)
            admin.totp_secret = None
            await session.commit()
            print(f"[OK] Admin '{username}' password reset (2FA cleared)")
        else:
            admin = Admin(username=username, password_hash=hash_password(password), role='admin')
            session.add(admin)
            await session.commit()
            print(f"[OK] Admin '{username}' created")


async def cmd_activate_license(key: str = None):
    """Activate an HMAC-signed license key on this server."""
    await init_db()

    if not key:
        print()
        print("  Lightline VPN Panel — License Activation")
        print("  " + "=" * 42)
        print()
        key = input("  License key: ").strip()
    if not key:
        print("  [ERROR] License key cannot be empty")
        return

    # Verify HMAC signature
    info = verify_license_key(key)
    if not info:
        print("  [ERROR] Invalid license key (signature verification failed)")
        return
    if info["expired"]:
        print("  [ERROR] License key has expired")
        return

    fingerprint = get_server_fingerprint()

    async with async_session() as session:
        lic = (await session.execute(
            select(License).where(License.license_key == key)
        )).scalar_one_or_none()
        if lic and lic.status == 'revoked':
            print("  [ERROR] License has been revoked")
            return
        if not lic:
            lic = License(
                license_key=key, expire_days=info["expire_days"],
                max_servers=info["max_servers"], activated_servers=1,
                status='active', server_fingerprint=fingerprint,
            )
            session.add(lic)
        else:
            lic.status = 'active'
            lic.server_fingerprint = fingerprint
            lic.activated_servers = 1
        await session.commit()

    # Backup license to persistent file so it survives DB resets
    try:
        import json as _json
        backup_path = Path('/var/lib/lightline/certs/license_backup.json')
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        _json.dump({"license_key": key, "server_fingerprint": fingerprint},
                   open(backup_path, 'w'))
        print(f"  [OK] License backed up to {backup_path}")
    except Exception as e:
        print(f"  [WARN] Could not backup license: {e}")

    print()
    print(f"  [OK] License activated on this server")
    print()
    print(f"    Key:         {key[:24]}...")
    print(f"    Expires in:  {info['expires_in_days']} days")
    print(f"    Max servers: {info['max_servers']}")
    print(f"    Fingerprint: {fingerprint}")
    print()


async def cmd_show_license():
    await init_db()
    async with async_session() as session:
        lics = (await session.execute(
            select(License).order_by(License.created_at.desc())
        )).scalars().all()
        if not lics:
            print("[INFO] No licenses found. Activate one with: python cli.py license activate <KEY>")
            return
        print()
        for lic in lics:
            if lic.expire_days > 0:
                expire_date = lic.created_at + timedelta(days=lic.expire_days)
                days_left = max(0, (expire_date - datetime.now(timezone.utc)).days)
            else:
                days_left = 'N/A'
            print(f"  [{lic.status.upper():>10}] {lic.license_key}  "
                  f"expires={days_left}d  servers={lic.activated_servers}/{lic.max_servers}  "
                  f"fp={lic.server_fingerprint or 'none'}")
        print()


async def cmd_fingerprint():
    print(f"Server Fingerprint: {get_server_fingerprint()}")


def print_usage():
    print()
    print("  Lightline VPN Panel CLI")
    print()
    print("  Usage: python cli.py <command> [args]")
    print()
    print("  Commands:")
    print("    admin create                           Create a new admin account (interactive)")
    print("    admin delete [--user U]                Delete an admin account")
    print("    admin list                             List all admin accounts")
    print("    admin reset [--user U] [--pass P]      Reset admin password")
    print("    license activate [KEY]                 Activate an HMAC-signed license key")
    print("    license show                           Show all licenses")
    print("    fingerprint                            Show this server's fingerprint")
    print()


def main():
    args = sys.argv[1:]
    if not args:
        print_usage()
        return

    cmd = args[0]

    if cmd == 'admin':
        if len(args) < 2:
            print_usage()
            return
        sub = args[1]
        if sub == 'create':
            asyncio.run(cmd_admin_create())
        elif sub == 'delete':
            username = None
            i = 2
            while i < len(args):
                if args[i] == '--user' and i + 1 < len(args):
                    username = args[i + 1]; i += 2
                else:
                    i += 1
            asyncio.run(cmd_admin_delete(username))
        elif sub == 'list':
            asyncio.run(cmd_admin_list())
        elif sub == 'reset':
            username = None
            password = None
            i = 2
            while i < len(args):
                if args[i] == '--user' and i + 1 < len(args):
                    username = args[i + 1]; i += 2
                elif args[i] == '--pass' and i + 1 < len(args):
                    password = args[i + 1]; i += 2
                else:
                    i += 1
            asyncio.run(cmd_admin_reset(username, password))
        else:
            print_usage()

    elif cmd == 'license':
        if len(args) < 2:
            print_usage()
            return
        sub = args[1]
        if sub == 'activate':
            key = args[2] if len(args) > 2 else None
            asyncio.run(cmd_activate_license(key))
        elif sub == 'show':
            asyncio.run(cmd_show_license())
        else:
            print_usage()

    elif cmd == 'fingerprint':
        asyncio.run(cmd_fingerprint())

    else:
        print_usage()


if __name__ == '__main__':
    main()
