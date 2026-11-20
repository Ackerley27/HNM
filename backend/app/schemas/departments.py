from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VlanResponse(BaseModel):
    id: UUID
    vlan_number: int
    name: str
    subnet: str | None


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper()


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class DepartmentResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    device_count: int
    traffic_bytes_24h: int | None
    vlans: list[VlanResponse]
    created_at: datetime
    updated_at: datetime


class DepartmentUsagePoint(BaseModel):
    period_start: datetime
    ingress_bytes: int | None
    egress_bytes: int | None
    flow_bytes: int | None
    flow_count: int


class DepartmentUsageResponse(BaseModel):
    department_id: UUID
    department_name: str
    data_mode: Literal["demo", "live"]
    period: Literal["hour", "day", "month"]
    period_count: int
    start: datetime
    end: datetime
    ingress_bytes: int | None
    egress_bytes: int | None
    total_traffic_bytes: int | None
    flow_bytes: int | None
    flow_count: int
    points: list[DepartmentUsagePoint]

