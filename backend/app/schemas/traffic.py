from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class TrafficSummary(BaseModel):
    data_mode: Literal["demo", "live"]
    start: datetime
    end: datetime
    total_bytes: int | None
    download_bytes: int | None
    upload_bytes: int | None
    current_download_bps: int | None
    current_upload_bps: int | None
    flow_count: int
    flow_bytes: int | None


class TrafficDepartment(BaseModel):
    id: UUID
    name: str


class TopHost(BaseModel):
    ip_address: str
    hostname: str | None
    bytes_transferred: int
    flow_count: int


class TrafficBreakdown(BaseModel):
    name: str
    bytes_transferred: int
    flow_count: int
    percent: float
