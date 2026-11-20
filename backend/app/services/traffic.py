from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models import TrafficRecord

MonitoringMode = Literal["demo", "live"]


def source_filter(source_column: ColumnElement[str], mode: MonitoringMode):
    return source_column == "demo" if mode == "demo" else source_column != "demo"


def resolve_time_window(
    *,
    hours: int,
    start: datetime | None,
    end: datetime | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    if start is not None and start.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start must include a timezone",
        )
    if end is not None and end.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end must include a timezone",
        )

    resolved_end = (end or now).astimezone(timezone.utc)
    resolved_start = (start or resolved_end - timedelta(hours=hours)).astimezone(
        timezone.utc
    )
    if resolved_start >= resolved_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start must be earlier than end",
        )
    if resolved_end > now + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end cannot be more than five minutes in the future",
        )
    if resolved_end - resolved_start > timedelta(hours=168):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The requested time window cannot exceed 168 hours",
        )
    return resolved_start, resolved_end


def bandwidth_by_direction(
    db: Session,
    *,
    start: datetime,
    end: datetime,
    mode: MonitoringMode,
    department_id=None,
) -> dict[str, int | None]:
    statement = (
        select(
            TrafficRecord.direction,
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
            func.avg(TrafficRecord.bit_rate_bps),
        )
        .where(
            TrafficRecord.interval_start >= start,
            TrafficRecord.interval_start < end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(
            TrafficRecord.direction,
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
        )
    )
    if department_id is not None:
        statement = statement.where(TrafficRecord.department_id == department_id)

    totals: dict[str, int | None] = {"ingress": None, "egress": None}
    for direction, _source, _device_id, _interface_id, average_rate in db.execute(
        statement
    ).all():
        if average_rate is not None:
            totals[direction] = (totals[direction] or 0) + int(average_rate)
    return totals
