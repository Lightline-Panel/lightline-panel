#!/usr/bin/env python3
"""Lightline VPN Panel CLI — License and admin management commands."""

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

import httpx


def get_server_fingerprint() -> str:
    raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


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


async def cmd_activate_license(key: str = None):
    """Activate a license key on this server."""
    await init_db()
    LICENSE_SERVER_URL = os.environ.get('LICENSE_SERVER_URL', '')

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

    if LICENSE_SERVER_URL:
        # Activate via external license server
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{LICENSE_SERVER_URL}/api/license/activate", json={
                    "license_key": key,
                    "hostname": platform.node(),
                    "fingerprint": fingerprint,
                })
                result = resp.json()
                if resp.status_code == 200 and result.get('success'):
                    # Store locally
                    async with async_session() as session:
                        lic = (await session.execute(
                            select(License).where(License.license_key == key)
                        )).scalar_one_or_none()
                        if not lic:
                            lic = License(license_key=key, expire_days=0, max_servers=1,
                                          activated_servers=1, status='active',
                                          server_fingerprint=fingerprint)
                            session.add(lic)
                        else:
                            lic.status = 'active'
                            lic.server_fingerprint = fingerprint
                        await session.commit()
                    print(f"  [OK] License activated via license server")
                    print(f"    Key:         {key}")
                    print(f"    Expires at:  {result.get('expires_at', 'N/A')}")
                    print(f"    Server ID:   {result.get('server_id', 'N/A')}")
                    print(f"    Fingerprint: {fingerprint}")
                else:
                    print(f"  [ERROR] {result.get('error', 'Activation failed')}")
        except Exception as e:
            print(f"  [ERROR] Could not reach license server: {e}")
        return

    # Local-only activation
    async with async_session() as session:
        lic = (await session.execute(
            select(License).where(License.license_key == key)
        )).scalar_one_or_none()
        if not lic:
            # Store as active (no external server configured)
            lic = License(license_key=key, expire_days=365, max_servers=1,
                          activated_servers=1, status='active',
                          server_fingerprint=fingerprint)
            session.add(lic)
            await session.commit()
            print(f"  [OK] License stored and activated locally")
            print(f"    Key:         {key}")
            print(f"    Fingerprint: {fingerprint}")
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
        else:
            print(f"  [OK] License already active on this server")
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
            print("[INFO] No licenses found. Activate one with: python cli.py license activate")
            return
        for lic in lics:
            if lic.expire_days > 0:
                expire_date = lic.created_at + timedelta(days=lic.expire_days)
                days_left = max(0, (expire_date - datetime.now(timezone.utc)).days)
            else:
                days_left = 'N/A'
            print(f"  [{lic.status.upper():>10}] {lic.license_key}  "
                  f"expires={days_left}d  servers={lic.activated_servers}/{lic.max_servers}  "
                  f"fp={lic.server_fingerprint or 'none'}")


async def cmd_fingerprint():
    print(f"Server Fingerprint: {get_server_fingerprint()}")


def print_usage():
    print()
    print("  Lightline VPN Panel CLI")
    print()
    print("  Usage: python cli.py <command> [args]")
    print()
    print("  Commands:")
    print("    admin create                    Create a new admin account (interactive)")
    print("    admin reset [--user U] [--pass P]  Reset admin password")
    print("    license activate [KEY]          Activate a license key (interactive if no key)")
    print("    license show                    Show all licenses")
    print("    fingerprint                     Show this server's fingerprint")
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
