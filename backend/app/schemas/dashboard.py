from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class RecentAlert(BaseModel):
    id: UUID
    title: str
    description: str | None
    severity: str
    status: str
    detected_at: datetime


class DepartmentUsage(BaseModel):
    id: UUID
    name: str
    bytes_transferred: int


class MonitoringServiceStatus(BaseModel):
    provider: str
    setting_key: str
    status: str
    last_checked_at: datetime | None


class DashboardOverview(BaseModel):
    generated_at: datetime
    data_mode: Literal["demo", "live"]
    total_devices: int
    online_devices: int
    offline_devices: int
    unknown_devices: int
    unavailable_devices: int
    download_bps: int | None
    upload_bps: int | None
    traffic_bytes_24h: int | None
    availability_percent: float | None
    department_usage: list[DepartmentUsage]
    recent_alerts: list[RecentAlert]
    monitoring_services: list[MonitoringServiceStatus]


class TrafficPoint(BaseModel):
    time: datetime
    download_bps: int | None
    upload_bps: int | None
    bytes_transferred: int


class TrafficHistory(BaseModel):
    window_hours: int
    has_data: bool
    points: list[TrafficPoint]


class DeviceStatusSummary(BaseModel):
    total: int
    online: int
    offline: int
    unknown: int
    unavailable: int
