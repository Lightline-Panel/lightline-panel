"""Lightline — Internal Shadowsocks credential manager.

Multi-user AEAD-2022 mode (2022-blake3-aes-128-gcm).
Each user gets a unique key. The server has a master key.

ss:// URL format for multi-user AEAD-2022:
  ss://BASE64(method:server-key:user-key)@host:port#tag
"""

import base64
import secrets


SS_METHOD = "2022-blake3-aes-128-gcm"
SS_KEY_BYTES = 16  # aes-128-gcm requires 16-byte keys


def generate_password() -> str:
    """Generate a base64-encoded random key for AEAD-2022 user."""
    return base64.b64encode(secrets.token_bytes(SS_KEY_BYTES)).decode()


def build_ss_url(server_key: str, user_key: str, host: str, port: int, tag: str = "") -> str:
    """Build a proper ss:// URL for multi-user AEAD-2022.

    Format: ss://BASE64(method:server-key:user-key)@host:port#tag
    The server-key is the node's master key, user-key is per-user.
    """
    userinfo = f"{SS_METHOD}:{server_key}:{user_key}"
    encoded = base64.urlsafe_b64encode(userinfo.encode()).decode().rstrip('=')
    url = f"ss://{encoded}@{host}:{port}"
    if tag:
        from urllib.parse import quote
        url += f"#{quote(tag)}"
    return url


def parse_ss_url(url: str) -> dict:
    """Parse an ss:// URL back into components."""
    if not url.startswith('ss://'):
        return {}
    rest = url[5:]
    tag = ""
    if '#' in rest:
        rest, tag = rest.rsplit('#', 1)
    if '@' in rest:
        encoded, hostport = rest.rsplit('@', 1)
    else:
        return {}
    # Add padding
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += '=' * padding
    try:
        decoded = base64.urlsafe_b64decode(encoded).decode()
    except Exception:
        return {}
    parts = decoded.split(':')
    if len(parts) == 3:
        method, server_key, user_key = parts
        return {"method": method, "server_key": server_key, "user_key": user_key,
                "host": hostport.rsplit(':', 1)[0] if ':' in hostport else hostport,
                "port": int(hostport.rsplit(':', 1)[1]) if ':' in hostport else 0, "tag": tag}
    elif len(parts) == 2:
        method, password = parts
        return {"method": method, "password": password,
                "host": hostport.rsplit(':', 1)[0] if ':' in hostport else hostport,
                "port": int(hostport.rsplit(':', 1)[1]) if ':' in hostport else 0, "tag": tag}
    return {}
