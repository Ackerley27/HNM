from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utc_now
from app.database.types import CidrNetwork, InetAddress

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'viewer')", name="valid_role"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_alerts: Mapped[list["NetworkAlert"]] = relationship(
        back_populates="acknowledged_by_user"
    )


class Department(TimestampMixin, Base):
    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    vlans: Mapped[list["Vlan"]] = relationship(back_populates="department")
    devices: Mapped[list["NetworkDevice"]] = relationship(back_populates="department")


class Vlan(TimestampMixin, Base):
    __tablename__ = "vlans"
    __table_args__ = (
        CheckConstraint("vlan_number BETWEEN 1 AND 4094", name="valid_vlan_number"),
        UniqueConstraint("vlan_number", name="uq_vlans_vlan_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    vlan_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subnet: Mapped[str | None] = mapped_column(CidrNetwork())
    department: Mapped[Department] = relationship(back_populates="vlans")


class NetworkDevice(TimestampMixin, Base):
    __tablename__ = "network_devices"
    __table_args__ = (
        CheckConstraint(
            "device_type IN ('router', 'switch', 'firewall', 'access_point')",
            name="valid_device_type",
        ),
        CheckConstraint(
            "status IN ('online', 'offline', 'unknown', 'unavailable')",
            name="valid_device_status",
        ),
        Index("ix_network_devices_status", "status"),
        Index("ix_network_devices_department_id", "department_id"),
        Index("ix_network_devices_device_type", "device_type"),
        Index(
            "uq_network_devices_source_id",
            "source",
            "source_device_id",
            unique=True,
            postgresql_where=text("source_device_id IS NOT NULL"),
            sqlite_where=text("source_device_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    vlan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vlans.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(253))
    ip_address: Mapped[str] = mapped_column(InetAddress(), nullable=False)
    device_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_device_id: Mapped[str | None] = mapped_column(String(160))
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    department: Mapped[Department | None] = relationship(back_populates="devices")
    interfaces: Mapped[list["NetworkInterface"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["DeviceMetric"]] = relationship(back_populates="device")


class NetworkInterface(TimestampMixin, Base):
    __tablename__ = "network_interfaces"
    __table_args__ = (
        CheckConstraint("if_index >= 0", name="valid_if_index"),
        CheckConstraint("speed_bps IS NULL OR speed_bps >= 0", name="valid_speed"),
        CheckConstraint(
            "admin_state IS NULL OR admin_state IN ('up', 'down', 'unknown')",
            name="valid_admin_state",
        ),
        CheckConstraint(
            "oper_state IS NULL OR oper_state IN ('up', 'down', 'unknown')",
            name="valid_oper_state",
        ),
        UniqueConstraint("device_id", "if_index", name="uq_interface_device_index"),
        Index("ix_network_interfaces_device_id", "device_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False
    )
    if_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    speed_bps: Mapped[int | None] = mapped_column(BigInteger)
    admin_state: Mapped[str | None] = mapped_column(String(16))
    oper_state: Mapped[str | None] = mapped_column(String(16))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device: Mapped[NetworkDevice] = relationship(back_populates="interfaces")


class MonitoredHost(TimestampMixin, Base):
    __tablename__ = "monitored_hosts"
    __table_args__ = (
        Index("ix_monitored_hosts_ip_address", "ip_address"),
        Index("ix_monitored_hosts_department_last_seen", "department_id", "last_seen_at"),
        Index("ix_monitored_hosts_vlan_last_seen", "vlan_id", "last_seen_at"),
        Index(
            "uq_monitored_hosts_source_id",
            "source",
            "source_host_id",
            unique=True,
            postgresql_where=text("source_host_id IS NOT NULL"),
            sqlite_where=text("source_host_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    vlan_id: Mapped[UUID | None] = mapped_column(ForeignKey("vlans.id", ondelete="SET NULL"))
    ip_address: Mapped[str] = mapped_column(InetAddress(), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(253))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_host_id: Mapped[str | None] = mapped_column(String(160))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrafficRecord(Base):
    __tablename__ = "traffic_records"
    __table_args__ = (
        CheckConstraint("interval_end >= interval_start", name="valid_interval"),
        CheckConstraint("bytes_transferred >= 0", name="valid_bytes"),
        CheckConstraint("packets IS NULL OR packets >= 0", name="valid_packets"),
        CheckConstraint("bit_rate_bps IS NULL OR bit_rate_bps >= 0", name="valid_bit_rate"),
        CheckConstraint("direction IN ('ingress', 'egress')", name="valid_direction"),
        Index("ix_traffic_records_interval_start", "interval_start"),
        Index("ix_traffic_records_department_interval", "department_id", "interval_start"),
        Index("ix_traffic_records_device_interval", "device_id", "interval_start"),
        Index("ix_traffic_records_interface_interval", "interface_id", "interval_start"),
        Index(
            "uq_traffic_records_source_id",
            "source",
            "source_record_id",
            unique=True,
            postgresql_where=text("source_record_id IS NOT NULL"),
            sqlite_where=text("source_record_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    interval_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    interval_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network_devices.id", ondelete="SET NULL")
    )
    interface_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network_interfaces.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    bytes_transferred: Mapped[int] = mapped_column(BigInteger, nullable=False)
    packets: Mapped[int | None] = mapped_column(BigInteger)
    bit_rate_bps: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class FlowRecord(Base):
    __tablename__ = "flow_records"
    __table_args__ = (
        CheckConstraint("flow_end >= flow_start", name="valid_flow_interval"),
        CheckConstraint("source_port IS NULL OR source_port BETWEEN 0 AND 65535", name="valid_source_port"),
        CheckConstraint(
            "destination_port IS NULL OR destination_port BETWEEN 0 AND 65535",
            name="valid_destination_port",
        ),
        CheckConstraint("bytes_transferred >= 0", name="valid_bytes"),
        CheckConstraint("packets IS NULL OR packets >= 0", name="valid_packets"),
        Index("ix_flow_records_flow_start", "flow_start"),
        Index("ix_flow_records_department_start", "department_id", "flow_start"),
        Index("ix_flow_records_protocol_start", "protocol", "flow_start"),
        Index("ix_flow_records_application_start", "application_name", "flow_start"),
        Index(
            "uq_flow_records_source_id",
            "source",
            "source_record_id",
            unique=True,
            postgresql_where=text("source_record_id IS NOT NULL"),
            sqlite_where=text("source_record_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    flow_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    flow_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    source_host_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("monitored_hosts.id", ondelete="SET NULL")
    )
    destination_host_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("monitored_hosts.id", ondelete="SET NULL")
    )
    source_ip: Mapped[str] = mapped_column(InetAddress(), nullable=False)
    destination_ip: Mapped[str] = mapped_column(InetAddress(), nullable=False)
    source_port: Mapped[int | None] = mapped_column(Integer)
    destination_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    application_name: Mapped[str | None] = mapped_column(String(120))
    bytes_transferred: Mapped[int] = mapped_column(BigInteger, nullable=False)
    packets: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class DeviceMetric(Base):
    __tablename__ = "device_metrics"
    __table_args__ = (
        Index("ix_device_metrics_device_recorded", "device_id", "recorded_at"),
        Index("ix_device_metrics_name_recorded", "metric_name", "recorded_at"),
        Index(
            "uq_device_metrics_source_id",
            "source",
            "source_record_id",
            unique=True,
            postgresql_where=text("source_record_id IS NOT NULL"),
            sqlite_where=text("source_record_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_devices.id", ondelete="CASCADE"), nullable=False
    )
    interface_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network_interfaces.id", ondelete="SET NULL")
    )
    metric_name: Mapped[str] = mapped_column(String(48), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    device: Mapped[NetworkDevice] = relationship(back_populates="metrics")


class NetworkAlert(TimestampMixin, Base):
    __tablename__ = "network_alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="valid_severity"),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')", name="valid_alert_status"
        ),
        Index("ix_network_alerts_status_detected", "status", "detected_at"),
        Index("ix_network_alerts_severity_detected", "severity", "detected_at"),
        Index("ix_network_alerts_department_detected", "department_id", "detected_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network_devices.id", ondelete="SET NULL")
    )
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_user: Mapped[User | None] = relationship(
        back_populates="acknowledged_alerts"
    )


class NetworkLog(Base):
    __tablename__ = "network_logs"
    __table_args__ = (
        Index("ix_network_logs_occurred_at", "occurred_at"),
        Index("ix_network_logs_device_occurred", "device_id", "occurred_at"),
        Index("ix_network_logs_severity_occurred", "severity", "occurred_at"),
        Index(
            "uq_network_logs_source_event_id",
            "source",
            "source_event_id",
            unique=True,
            postgresql_where=text("source_event_id IS NOT NULL"),
            sqlite_where=text("source_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network_devices.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MonitoringSetting(TimestampMixin, Base):
    __tablename__ = "monitoring_settings"
    __table_args__ = (UniqueConstraint("provider", "setting_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(80), nullable=False)
    setting_value: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT, default=dict, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    service_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("outcome IN ('success', 'failure')", name="valid_audit_outcome"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_resource_created", "resource_type", "resource_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON_DOCUMENT, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    __table_args__ = (Index("ix_revoked_tokens_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
