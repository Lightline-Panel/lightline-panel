#!/usr/bin/env python3
"""
Lightline License Key Generator — Standalone Script

Run this on ANY machine to generate license keys for Lightline VPN Panel.
No dependencies required — uses Python 3.6+ stdlib only.

Usage:
  python generate_license.py
  python generate_license.py --days 365 --servers 5
"""

import struct
import hmac
import hashlib
import secrets
import time
import sys
import os

# HMAC secret — must match the panel's LICENSE_SECRET env var (or default)
LICENSE_SECRET = os.environ.get('LICENSE_SECRET', 'lightline-hmac-2024-secure-key').encode()


def create_license_key(expire_days: int = 30, max_servers: int = 1) -> str:
    """Generate an HMAC-signed license key."""
    created = int(time.time())
    nonce = secrets.token_bytes(2)
    payload = struct.pack('>IIH', created, expire_days, max_servers) + nonce  # 12 bytes
    sig = hmac.new(LICENSE_SECRET, payload, hashlib.sha256).digest()[:8]  # 8 bytes
    raw = payload + sig  # 20 bytes = 40 hex chars
    hex_str = raw.hex().upper()
    parts = [hex_str[i:i+8] for i in range(0, 40, 8)]
    return f"LL-{'-'.join(parts)}"


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
            "expired": time.time() > expire_ts,
            "expires_in_days": max(0, int((expire_ts - time.time()) / 86400)),
        }
    except Exception:
        return None


def main():
    print()
    print("  Lightline License Key Generator")
    print("  ================================")
    print()

    expire_days = 30
    max_servers = 1

    # Parse CLI args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--days' and i + 1 < len(args):
            expire_days = int(args[i + 1])
            i += 2
        elif args[i] == '--servers' and i + 1 < len(args):
            max_servers = int(args[i + 1])
            i += 2
        elif args[i] == '--verify' and i + 1 < len(args):
            key = args[i + 1]
            info = verify_license_key(key)
            if info:
                print(f"  [OK] Valid license key")
                print(f"    Expire days:    {info['expire_days']}")
                print(f"    Max servers:    {info['max_servers']}")
                print(f"    Days remaining: {info['expires_in_days']}")
                print(f"    Expired:        {'Yes' if info['expired'] else 'No'}")
            else:
                print(f"  [ERROR] Invalid license key")
            print()
            return
        elif args[i] == '--help':
            print("  Usage: python generate_license.py [OPTIONS]")
            print()
            print("  Options:")
            print("    --days N       License validity in days (default: 30)")
            print("    --servers N    Max server activations (default: 1)")
            print("    --verify KEY   Verify an existing license key")
            print("    --help         Show this help")
            print()
            return
        else:
            i += 1

    # Interactive mode if no args
    if len(sys.argv) == 1:
        try:
            val = input("  Expire days [30]: ").strip()
            if val:
                expire_days = int(val)
            val = input("  Max servers [1]: ").strip()
            if val:
                max_servers = int(val)
        except (ValueError, EOFError):
            pass

    key = create_license_key(expire_days, max_servers)

    print()
    print(f"  License Key:  {key}")
    print(f"  Expire days:  {expire_days}")
    print(f"  Max servers:  {max_servers}")
    print()
    print("  Give this key to your customer. They enter it on the panel login page.")
    print()


if __name__ == '__main__':
    main()
