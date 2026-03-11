from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone


TZDateTime = DateTime(timezone=True)


class Admin(Base):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default='admin')
    totp_secret = Column(String(100), nullable=True)
    created_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))


class Node(Base):
    __tablename__ = 'nodes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ip = Column(String(45), nullable=False)
    api_port = Column(Integer, default=62050)  # node service port (Marzban-node style, default 62050)
    api_key = Column(Text, nullable=True)  # legacy — no longer used (mTLS replaces tokens)
    ss_port = Column(Integer, default=8388)  # Shadowsocks listen port on the node
    country = Column(String(100))
    status = Column(String(20), default='unknown')
    last_heartbeat = Column(TZDateTime, nullable=True)
    created_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))


class VPNUser(Base):
    __tablename__ = 'vpn_users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # legacy
    traffic_limit = Column(BigInteger, default=0)
    device_limit = Column(Integer, default=1)  # legacy
    expire_date = Column(TZDateTime, nullable=True)
    assigned_node_id = Column(Integer, ForeignKey('nodes.id', ondelete='SET NULL'), nullable=True)
    outline_key_id = Column(String(100), nullable=True)  # legacy
    ss_password = Column(String(100), nullable=True)  # Shadowsocks password for this user
    access_url = Column(Text, nullable=True)  # ss:// URL
    ss_url = Column(Text, nullable=True)  # legacy, same as access_url now
    access_token = Column(String(64), unique=True, nullable=True)
    status = Column(String(20), default='active')
    created_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))
    node = relationship('Node', backref='vpn_users')


class TrafficLog(Base):
    __tablename__ = 'traffic_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('vpn_users.id', ondelete='CASCADE'))
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='SET NULL'))
    bytes_transferred = Column(BigInteger, default=0)
    recorded_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))


class License(Base):
    __tablename__ = 'licenses'
    id = Column(Integer, primary_key=True, autoincrement=True)
    license_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))
    expire_days = Column(Integer, default=30)
    status = Column(String(20), default='active')
    max_servers = Column(Integer, default=1)
    activated_servers = Column(Integer, default=0)
    server_fingerprint = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey('admins.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(255), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(TZDateTime, default=lambda: datetime.now(timezone.utc))


class PanelSettings(Base):
    __tablename__ = 'panel_settings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
