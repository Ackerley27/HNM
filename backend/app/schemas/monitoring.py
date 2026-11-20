from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, model_validator


DeviceStatus = Literal["online", "offline", "unknown", "unavailable"]


class DeviceStatusObservation(BaseModel):
    source_device_id: str | None = None
    ip_address: IPvAnyAddress | None = None
    status: DeviceStatus
    observed_at: datetime

    @model_validator(mode="after")
    def require_device_identity(self) -> "DeviceStatusObservation":
        if self.source_device_id is None and self.ip_address is None:
            raise ValueError("An observation needs a source device ID or IP address")
        return self


class MetricObservation(BaseModel):
    source_device_id: str
    metric_name: Literal["cpu_percent", "memory_percent"]
    value: float = Field(ge=0, le=100)
    unit: Literal["percent"] = "percent"
    recorded_at: datetime
    source_record_id: str


class TrafficObservation(BaseModel):
    direction: Literal["ingress", "egress"]
    interval_start: datetime
    interval_end: datetime
    bytes_transferred: int = Field(ge=0)
    bit_rate_bps: int | None = Field(default=None, ge=0)
    source_record_id: str


class HostObservation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_host_id: str
    ip_address: IPvAnyAddress
    hostname: str | None = Field(default=None, max_length=253)
    first_seen_at: datetime
    last_seen_at: datetime


class CollectorResult(BaseModel):
    provider: Literal["zabbix", "ntopng", "snmpv3"]
    checked_at: datetime
    service_status: Literal["available", "unavailable"]
    configured: bool = True
    message: str | None = None
    devices: list[DeviceStatusObservation] = Field(default_factory=list)
    metrics: list[MetricObservation] = Field(default_factory=list)
    traffic: list[TrafficObservation] = Field(default_factory=list)
    hosts: list[HostObservation] = Field(default_factory=list)
