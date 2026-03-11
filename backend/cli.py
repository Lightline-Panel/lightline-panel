#!/usr/bin/env python3
"""Lightline VPN Panel CLI — Admin and license management commands."""

import asyncio
import sys
import os
import getpass
import secrets
import hashlib
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


def get_server_fingerprint() -> str:
    raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def generate_license_key() -> str:
    return f"LL-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"


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


async def cmd_license_create(expire_days: int = None, max_servers: int = None):
    """Create a new license key."""
    await init_db()
    print()
    print("  Lightline VPN Panel — Create License Key")
    print("  " + "=" * 42)
    print()

    if expire_days is None:
        val = input("  Expire days [30]: ").strip()
        expire_days = int(val) if val else 30
    if max_servers is None:
        val = input("  Max servers [1]: ").strip()
        max_servers = int(val) if val else 1

    key = generate_license_key()
    async with async_session() as session:
        lic = License(license_key=key, expire_days=expire_days, max_servers=max_servers,
                      activated_servers=0, status='active')
        session.add(lic)
        await session.commit()

    print()
    print(f"  [OK] License created successfully")
    print()
    print(f"    Key:         {key}")
    print(f"    Expire days: {expire_days}")
    print(f"    Max servers: {max_servers}")
    print()


async def cmd_activate_license(key: str = None):
    """Activate a license key on this server."""
    await init_db()

    if not key:
        print()
        print("  Lightline VPN Panel — License Activation")
        print("  " + "=" * 42)
        print()
        key = input("  License key: ").strip()
    if not key:
        print("[ERROR] License key cannot be empty")
        return

    fingerprint = get_server_fingerprint()

    async with async_session() as session:
        lic = (await session.execute(
            select(License).where(License.license_key == key)
        )).scalar_one_or_none()
        if not lic:
            print(f"  [ERROR] License key not found. Create one first with: python cli.py license create")
            return
        if lic.status != 'active':
            print(f"  [ERROR] License is {lic.status}")
            return
        expire_date = lic.created_at + timedelta(days=lic.expire_days)
        if lic.expire_days > 0 and datetime.now(timezone.utc) > expire_date:
            print("  [ERROR] License expired")
            return
        if not lic.server_fingerprint:
            lic.server_fingerprint = fingerprint
            lic.activated_servers += 1
            await session.commit()
            print(f"  [OK] License activated on this server")
        elif lic.server_fingerprint == fingerprint:
            print(f"  [OK] License already active on this server")
        else:
            print(f"  [ERROR] License bound to a different server")
            return
        days_left = (expire_date - datetime.now(timezone.utc)).days if lic.expire_days > 0 else 'unlimited'
        print(f"    Key:         {lic.license_key}")
        print(f"    Expires in:  {days_left} days")
        print(f"    Fingerprint: {fingerprint}")


async def cmd_show_license():
    await init_db()
    async with async_session() as session:
        lics = (await session.execute(
            select(License).order_by(License.created_at.desc())
        )).scalars().all()
        if not lics:
            print("[INFO] No licenses found. Create one with: python cli.py license create")
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
    print("    admin reset [--user U] [--pass P]      Reset admin password")
    print("    license create [--days N] [--servers N] Create a new license key")
    print("    license activate [KEY]                 Activate a license key on this server")
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
        if sub == 'create':
            expire_days = None
            max_servers = None
            i = 2
            while i < len(args):
                if args[i] == '--days' and i + 1 < len(args):
                    expire_days = int(args[i + 1]); i += 2
                elif args[i] == '--servers' and i + 1 < len(args):
                    max_servers = int(args[i + 1]); i += 2
                else:
                    i += 1
            asyncio.run(cmd_license_create(expire_days, max_servers))
        elif sub == 'activate':
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
