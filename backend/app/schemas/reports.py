from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DepartmentReportRow(BaseModel):
    department_id: UUID
    department_name: str
    bytes_transferred: int


class NetworkReport(BaseModel):
    data_mode: Literal["demo", "live"]
    period_start: datetime
    period_end: datetime
    traffic_bytes: int | None
    download_bytes: int | None
    upload_bytes: int | None
    flow_bytes: int | None
    flow_count: int
    total_devices: int
    online_devices: int
    offline_devices: int
    unknown_devices: int
    unavailable_devices: int
    department_usage: list[DepartmentReportRow]
