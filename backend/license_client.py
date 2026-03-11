"""
Lightline License Server Client

Handles communication between the Lightline VPN Panel and the external
Lightline License Server for license activation, validation, and heartbeat.
"""

import logging
import platform
import hashlib
import uuid
import os

import httpx

logger = logging.getLogger(__name__)

LICENSE_SERVER_URL = os.environ.get('LICENSE_SERVER_URL', '').rstrip('/')
LICENSE_SERVER_TIMEOUT = int(os.environ.get('LICENSE_SERVER_TIMEOUT', '10'))


def get_server_fingerprint() -> str:
    """Generate a unique fingerprint for this server instance."""
    raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def is_external_license_server_configured() -> bool:
    return bool(LICENSE_SERVER_URL)


async def activate_license(license_key: str, hostname: str | None = None) -> dict:
    """
    Activate a license key on the external license server.

    Returns: {"success": bool, "message"/"error": str, "server_id": str, "expires_at": str}
    """
    if not LICENSE_SERVER_URL:
        return {"success": False, "error": "License server not configured"}

    fingerprint = get_server_fingerprint()
    try:
        async with httpx.AsyncClient(timeout=LICENSE_SERVER_TIMEOUT, verify=False) as client:
            resp = await client.post(f"{LICENSE_SERVER_URL}/api/v1/license/activate", json={
                "license_key": license_key,
                "server_fingerprint": fingerprint,
                "hostname": hostname or platform.node(),
            })
            data = resp.json()
            if resp.status_code == 200:
                return data
            return {"success": False, "error": data.get("detail", f"HTTP {resp.status_code}")}
    except httpx.TimeoutException:
        logger.error("License server activation timed out")
        return {"success": False, "error": "License server timeout"}
    except Exception as e:
        logger.error(f"License server activation error: {e}")
        return {"success": False, "error": str(e)}


async def validate_license(license_key: str) -> dict:
    """
    Validate a license key on the external license server.

    Returns: {"valid": bool, "error": str, "expires_at": str, ...}
    """
    if not LICENSE_SERVER_URL:
        return {"valid": False, "error": "License server not configured"}

    fingerprint = get_server_fingerprint()
    try:
        async with httpx.AsyncClient(timeout=LICENSE_SERVER_TIMEOUT, verify=False) as client:
            resp = await client.post(f"{LICENSE_SERVER_URL}/api/v1/license/validate", json={
                "license_key": license_key,
                "server_fingerprint": fingerprint,
            })
            data = resp.json()
            if resp.status_code == 200:
                return data
            return {"valid": False, "error": data.get("detail", f"HTTP {resp.status_code}")}
    except httpx.TimeoutException:
        logger.error("License server validation timed out")
        return {"valid": False, "error": "License server timeout"}
    except Exception as e:
        logger.error(f"License server validation error: {e}")
        return {"valid": False, "error": str(e)}


async def heartbeat(license_key: str) -> dict:
    """
    Send a heartbeat to the external license server.

    Returns: {"success": bool, "next_heartbeat_seconds": int, "expires_at": str, ...}
    """
    if not LICENSE_SERVER_URL:
        return {"success": False, "error": "License server not configured"}

    fingerprint = get_server_fingerprint()
    try:
        async with httpx.AsyncClient(timeout=LICENSE_SERVER_TIMEOUT, verify=False) as client:
            resp = await client.post(f"{LICENSE_SERVER_URL}/api/v1/license/heartbeat", json={
                "license_key": license_key,
                "server_fingerprint": fingerprint,
            })
            data = resp.json()
            if resp.status_code == 200:
                return data
            return {"success": False, "error": data.get("detail", f"HTTP {resp.status_code}")}
    except httpx.TimeoutException:
        logger.error("License server heartbeat timed out")
        return {"success": False, "error": "License server timeout"}
    except Exception as e:
        logger.error(f"License server heartbeat error: {e}")
        return {"success": False, "error": str(e)}
