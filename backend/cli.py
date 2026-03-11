#!/usr/bin/env python3
"""Lightline VPN Panel CLI — License and admin management commands."""

import asyncio
import sys
import os
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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def cmd_activate_license(key: str):
    await init_db()
    async with async_session() as session:
        lic = (await session.execute(
            select(License).where(License.license_key == key)
        )).scalar_one_or_none()
        if not lic:
            print(f"[ERROR] License key not found: {key}")
            return
        if lic.status != 'active':
            print(f"[ERROR] License is {lic.status}")
            return
        expire_date = lic.created_at + timedelta(days=lic.expire_days)
        if datetime.now(timezone.utc) > expire_date:
            print("[ERROR] License expired")
            return
        fingerprint = get_server_fingerprint()
        if lic.server_fingerprint and lic.server_fingerprint != fingerprint:
            print("[ERROR] License bound to a different server")
            print(f"  Expected: {lic.server_fingerprint}")
            print(f"  Current:  {fingerprint}")
            return
        if not lic.server_fingerprint:
            if lic.activated_servers >= lic.max_servers:
                print("[ERROR] Maximum server activations reached")
                return
            lic.server_fingerprint = fingerprint
            lic.activated_servers += 1
            await session.commit()
            print(f"[OK] License activated on this server")
        else:
            print(f"[OK] License already active on this server")
        days_left = (expire_date - datetime.now(timezone.utc)).days
        print(f"  Key:         {lic.license_key}")
        print(f"  Expires in:  {days_left} days")
        print(f"  Fingerprint: {fingerprint}")
        print(f"  Servers:     {lic.activated_servers}/{lic.max_servers}")


async def cmd_generate_license(days: int = 30, servers: int = 1):
    await init_db()
    async with async_session() as session:
        key = f"LL-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        lic = License(license_key=key, expire_days=days, max_servers=servers, status='active')
        session.add(lic)
        await session.commit()
        print(f"[OK] License generated:")
        print(f"  Key:     {key}")
        print(f"  Expires: {days} days")
        print(f"  Servers: {servers}")


async def cmd_show_license():
    await init_db()
    async with async_session() as session:
        lics = (await session.execute(
            select(License).order_by(License.created_at.desc())
        )).scalars().all()
        if not lics:
            print("[INFO] No licenses found")
            return
        for lic in lics:
            expire_date = lic.created_at + timedelta(days=lic.expire_days)
            days_left = max(0, (expire_date - datetime.now(timezone.utc)).days)
            print(f"  [{lic.status.upper():>10}] {lic.license_key}  "
                  f"expires={days_left}d  servers={lic.activated_servers}/{lic.max_servers}  "
                  f"fp={lic.server_fingerprint or 'none'}")


async def cmd_fingerprint():
    print(f"Server Fingerprint: {get_server_fingerprint()}")


async def cmd_reset_admin(username: str = 'admin', password: str = 'admin123'):
    await init_db()
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


def print_usage():
    print("Lightline VPN Panel CLI")
    print()
    print("Usage: python cli.py <command> [args]")
    print()
    print("Commands:")
    print("  license activate <KEY>          Activate a license on this server")
    print("  license generate [--days N] [--servers N]  Generate a new license key")
    print("  license show                    Show all licenses")
    print("  fingerprint                     Show this server's fingerprint")
    print("  admin reset [--user U] [--pass P]  Reset or create admin account")
    print()


def main():
    args = sys.argv[1:]
    if not args:
        print_usage()
        return

    cmd = args[0]

    if cmd == 'license':
        if len(args) < 2:
            print_usage()
            return
        sub = args[1]
        if sub == 'activate':
            if len(args) < 3:
                print("Usage: python cli.py license activate <LICENSE_KEY>")
                return
            asyncio.run(cmd_activate_license(args[2]))
        elif sub == 'generate':
            days = 30
            servers = 1
            i = 2
            while i < len(args):
                if args[i] == '--days' and i + 1 < len(args):
                    days = int(args[i + 1]); i += 2
                elif args[i] == '--servers' and i + 1 < len(args):
                    servers = int(args[i + 1]); i += 2
                else:
                    i += 1
            asyncio.run(cmd_generate_license(days, servers))
        elif sub == 'show':
            asyncio.run(cmd_show_license())
        else:
            print_usage()

    elif cmd == 'fingerprint':
        asyncio.run(cmd_fingerprint())

    elif cmd == 'admin':
        if len(args) < 2:
            print_usage()
            return
        sub = args[1]
        if sub == 'reset':
            username = 'admin'
            password = 'admin123'
            i = 2
            while i < len(args):
                if args[i] == '--user' and i + 1 < len(args):
                    username = args[i + 1]; i += 2
                elif args[i] == '--pass' and i + 1 < len(args):
                    password = args[i + 1]; i += 2
                else:
                    i += 1
            asyncio.run(cmd_reset_admin(username, password))
        else:
            print_usage()
    else:
        print_usage()


if __name__ == '__main__':
    main()
