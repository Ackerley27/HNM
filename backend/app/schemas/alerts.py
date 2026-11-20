from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AlertStatus = Literal["open", "acknowledged", "resolved"]
AlertSeverity = Literal["info", "warning", "critical"]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID | None
    device_id: UUID | None
    alert_type: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str | None
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None


class AlertCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    severity: AlertSeverity
    department_id: UUID | None = None
    device_id: UUID | None = None


class AlertStatusUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]


class AlertThresholds(BaseModel):
    high_bandwidth_bps: int = Field(default=500_000_000, ge=1_000_000, le=10**12)
    unusual_traffic_multiplier: float = Field(default=3.0, ge=1.5, le=20)
    unusual_traffic_min_bps: int = Field(default=5_000_000, ge=100_000, le=10**12)
    offline_detection_enabled: bool = True
