from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


DeviceType = Literal["router", "switch", "firewall", "access_point"]
DeviceStatus = Literal["online", "offline", "unknown", "unavailable"]


class DeviceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    hostname: str | None = Field(default=None, max_length=253)
    ip_address: IPvAnyAddress
    device_type: DeviceType
    department_id: UUID | None = None
    vlan_id: UUID | None = None
    monitoring_enabled: bool = True


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=120)
    hostname: str | None = Field(default=None, max_length=253)
    ip_address: IPvAnyAddress | None = None
    device_type: DeviceType | None = None
    department_id: UUID | None = None
    vlan_id: UUID | None = None
    monitoring_enabled: bool | None = None


class DeviceResponse(BaseModel):
    id: UUID
    department_id: UUID | None
    department_name: str | None
    vlan_id: UUID | None
    vlan_number: int | None
    name: str
    hostname: str | None
    ip_address: str
    device_type: DeviceType
    status: DeviceStatus
    source: str
    monitoring_enabled: bool
    last_seen_at: datetime | None
    cpu_percent: float | None
    memory_percent: float | None
    created_at: datetime
    updated_at: datetime


class DeviceMetricPoint(BaseModel):
    metric_name: Literal["cpu_percent", "memory_percent"]
    value: float
    unit: str
    recorded_at: datetime


class DeviceTrafficPoint(BaseModel):
    direction: Literal["ingress", "egress"]
    bytes_transferred: int
    bit_rate_bps: int | None
    interval_start: datetime


class DeviceHistory(BaseModel):
    device_id: UUID
    window_hours: int
    metrics: list[DeviceMetricPoint]
    traffic: list[DeviceTrafficPoint]
