"""Lightline Panel — Certificate management for node mTLS.

Generates and stores a panel certificate + key pair.
The certificate is shown to admins in the UI — they copy it to the node
as ssl_client_cert.pem (same pattern as Marzban).

The panel uses this cert as a client certificate when connecting to nodes via HTTPS.
"""

import os
import logging
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta, timezone

logger = logging.getLogger('lightline')

# Default paths for panel cert/key
PANEL_CERT_DIR = os.environ.get('PANEL_CERT_DIR', '/var/lib/lightline/certs')
PANEL_CERT_FILE = os.path.join(PANEL_CERT_DIR, 'panel_cert.pem')
PANEL_KEY_FILE = os.path.join(PANEL_CERT_DIR, 'panel_key.pem')


def generate_panel_certificate():
    """Generate a self-signed certificate for the panel (used as client cert for mTLS).

    Returns the PEM-encoded certificate string.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'lightline-panel'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Lightline'),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    Path(PANEL_CERT_DIR).mkdir(parents=True, exist_ok=True)

    with open(PANEL_CERT_FILE, 'w') as f:
        f.write(cert_pem)

    with open(PANEL_KEY_FILE, 'w') as f:
        f.write(key_pem)

    logger.info(f"Panel certificate generated: {PANEL_CERT_FILE}")
    return cert_pem


def get_panel_certificate() -> str:
    """Get the panel's certificate PEM string. Generate if missing."""
    if os.path.isfile(PANEL_CERT_FILE):
        with open(PANEL_CERT_FILE) as f:
            return f.read()
    return generate_panel_certificate()


def get_panel_cert_and_key() -> tuple:
    """Get paths to panel cert and key files. Generate if missing."""
    if not os.path.isfile(PANEL_CERT_FILE) or not os.path.isfile(PANEL_KEY_FILE):
        generate_panel_certificate()
    return PANEL_CERT_FILE, PANEL_KEY_FILE
