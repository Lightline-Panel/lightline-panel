"""Lightline — Internal Shadowsocks credential manager.

Generates proper ss:// URLs without requiring Outline Server.
SS URL format: ss://BASE64(method:password)@host:port#tag
"""

import base64
import secrets
import string


SS_METHOD = "chacha20-ietf-poly1305"


def generate_password(length: int = 24) -> str:
    """Generate a random password for a Shadowsocks user."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def build_ss_url(password: str, host: str, port: int, tag: str = "") -> str:
    """Build a proper ss:// URL.

    Format: ss://BASE64(method:password)@host:port#tag
    This is the SIP002 URI format used by Outline and Shadowsocks clients.
    """
    userinfo = f"{SS_METHOD}:{password}"
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
    if ':' not in decoded:
        return {}
    method, password = decoded.split(':', 1)
    if ':' in hostport:
        host, port_str = hostport.rsplit(':', 1)
        port = int(port_str)
    else:
        host = hostport
        port = 0
    return {"method": method, "password": password, "host": host, "port": port, "tag": tag}
