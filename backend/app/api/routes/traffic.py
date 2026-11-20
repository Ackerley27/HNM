from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, func, select, union_all
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database.session import get_db
from app.models import Department, FlowRecord, MonitoredHost, TrafficRecord, User
from app.schemas.dashboard import TrafficHistory, TrafficPoint
from app.schemas.traffic import (
    TopHost,
    TrafficBreakdown,
    TrafficDepartment,
    TrafficSummary,
)
from app.services.traffic import bandwidth_by_direction, resolve_time_window, source_filter

router = APIRouter(prefix="/traffic", tags=["traffic"])


def _window(
    hours: int,
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime, datetime]:
    return resolve_time_window(hours=hours, start=start, end=end)


def _flow_filters(
    start: datetime,
    end: datetime,
    mode: str,
    department_id: UUID | None,
):
    filters = [
        FlowRecord.flow_start >= start,
        FlowRecord.flow_start < end,
        source_filter(FlowRecord.source, mode),
    ]
    if department_id is not None:
        filters.append(FlowRecord.department_id == department_id)
    return filters


@router.get("/summary", response_model=TrafficSummary)
def get_traffic_summary(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    start: datetime | None = None,
    end: datetime | None = None,
    department_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrafficSummary:
    window_start, window_end = _window(hours, start, end)
    mode = request.app.state.settings.monitoring_mode
    traffic_filter = [
        TrafficRecord.interval_start >= window_start,
        TrafficRecord.interval_start < window_end,
        source_filter(TrafficRecord.source, mode),
    ]
    if department_id is not None:
        traffic_filter.append(TrafficRecord.department_id == department_id)

    direction_rows = db.execute(
        select(
            TrafficRecord.direction,
            func.sum(TrafficRecord.bytes_transferred),
            func.count(TrafficRecord.id),
        )
        .where(*traffic_filter)
        .group_by(TrafficRecord.direction)
    ).all()
    bytes_by_direction: dict[str, int | None] = {
        "ingress": None,
        "egress": None,
    }
    record_count = 0
    for direction, byte_count, count in direction_rows:
        bytes_by_direction[direction] = int(byte_count or 0)
        record_count += count

    current_time = datetime.now(timezone.utc)
    rates = bandwidth_by_direction(
        db,
        start=current_time - timedelta(minutes=5),
        end=current_time,
        mode=mode,
        department_id=department_id,
    )
    flow_bytes, flow_count = db.execute(
        select(func.sum(FlowRecord.bytes_transferred), func.count(FlowRecord.id)).where(
            *_flow_filters(window_start, window_end, mode, department_id)
        )
    ).one()
    return TrafficSummary(
        data_mode=mode,
        start=window_start,
        end=window_end,
        total_bytes=(
            sum(value or 0 for value in bytes_by_direction.values())
            if record_count
            else None
        ),
        download_bytes=bytes_by_direction["ingress"],
        upload_bytes=bytes_by_direction["egress"],
        current_download_bps=rates["ingress"],
        current_upload_bps=rates["egress"],
        flow_count=flow_count,
        flow_bytes=int(flow_bytes) if flow_count else None,
    )


@router.get("/history", response_model=TrafficHistory)
def get_traffic_history(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    start: datetime | None = None,
    end: datetime | None = None,
    department_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrafficHistory:
    window_start, window_end = _window(hours, start, end)
    mode = request.app.state.settings.monitoring_mode
    dialect = db.get_bind().dialect.name
    bucket = (
        func.date_trunc("hour", TrafficRecord.interval_start)
        if dialect == "postgresql"
        else func.strftime("%Y-%m-%d %H:00:00", TrafficRecord.interval_start)
    )
    statement = (
        select(
            bucket.label("bucket"),
            TrafficRecord.direction,
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
            func.avg(TrafficRecord.bit_rate_bps),
            func.sum(TrafficRecord.bytes_transferred),
        )
        .where(
            TrafficRecord.interval_start >= window_start,
            TrafficRecord.interval_start < window_end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(
            bucket,
            TrafficRecord.direction,
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
        )
        .order_by(bucket)
    )
    if department_id is not None:
        statement = statement.where(TrafficRecord.department_id == department_id)

    points_by_time: dict[datetime, dict[str, Any]] = {}
    for bucket_value, direction, _source, _device, _interface, average_rate, byte_count in db.execute(
        statement
    ).all():
        point_time = (
            datetime.fromisoformat(bucket_value)
            if isinstance(bucket_value, str)
            else bucket_value
        )
        if point_time.tzinfo is None:
            point_time = point_time.replace(tzinfo=timezone.utc)
        point = points_by_time.setdefault(
            point_time,
            {
                "time": point_time,
                "download_bps": None,
                "upload_bps": None,
                "bytes_transferred": 0,
            },
        )
        rate_key = "download_bps" if direction == "ingress" else "upload_bps"
        if average_rate is not None:
            point[rate_key] = (point[rate_key] or 0) + int(average_rate)
        point["bytes_transferred"] += int(byte_count or 0)

    points = [TrafficPoint(**point) for point in points_by_time.values()]
    return TrafficHistory(
        window_hours=ceil((window_end - window_start).total_seconds() / 3600),
        has_data=bool(points),
        points=points,
    )


@router.get("/top-hosts", response_model=list[TopHost])
def get_top_hosts(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    start: datetime | None = None,
    end: datetime | None = None,
    department_id: UUID | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TopHost]:
    window_start, window_end = _window(hours, start, end)
    filters = _flow_filters(
        window_start,
        window_end,
        request.app.state.settings.monitoring_mode,
        department_id,
    )
    source_endpoints = (
        select(
            FlowRecord.source_ip.label("ip_address"),
            FlowRecord.bytes_transferred.label("bytes_transferred"),
        )
        .where(*filters)
    )
    destination_endpoints = (
        select(
            FlowRecord.destination_ip.label("ip_address"),
            FlowRecord.bytes_transferred.label("bytes_transferred"),
        )
        .where(*filters)
    )
    endpoints = union_all(source_endpoints, destination_endpoints).subquery()
    rows = db.execute(
        select(
            endpoints.c.ip_address,
            func.sum(endpoints.c.bytes_transferred),
            func.count(),
        )
        .group_by(endpoints.c.ip_address)
        .order_by(desc(func.sum(endpoints.c.bytes_transferred)))
        .limit(limit)
    ).all()
    ip_addresses = [ip_address for ip_address, _, _ in rows]
    host_filter = source_filter(
        MonitoredHost.source, request.app.state.settings.monitoring_mode
    )
    host_rows = db.execute(
        select(MonitoredHost.ip_address, MonitoredHost.hostname)
        .where(MonitoredHost.ip_address.in_(ip_addresses), host_filter)
        .order_by(MonitoredHost.last_seen_at.desc())
    ).all() if ip_addresses else []
    hostname_by_ip: dict[str, str] = {}
    for ip_address, hostname in host_rows:
        if hostname and ip_address not in hostname_by_ip:
            hostname_by_ip[ip_address] = hostname
    return [
        TopHost(
            ip_address=ip_address,
            hostname=hostname_by_ip.get(ip_address),
            bytes_transferred=int(byte_count),
            flow_count=count,
        )
        for ip_address, byte_count, count in rows
    ]


@router.get("/protocols", response_model=list[TrafficBreakdown])
def get_protocol_usage(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    start: datetime | None = None,
    end: datetime | None = None,
    department_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrafficBreakdown]:
    window_start, window_end = _window(hours, start, end)
    rows = db.execute(
        select(
            FlowRecord.protocol,
            func.sum(FlowRecord.bytes_transferred),
            func.count(FlowRecord.id),
        )
        .where(
            *_flow_filters(
                window_start,
                window_end,
                request.app.state.settings.monitoring_mode,
                department_id,
            )
        )
        .group_by(FlowRecord.protocol)
        .order_by(desc(func.sum(FlowRecord.bytes_transferred)))
        .limit(20)
    ).all()
    total_bytes = db.scalar(
        select(func.sum(FlowRecord.bytes_transferred)).where(
            *_flow_filters(
                window_start,
                window_end,
                request.app.state.settings.monitoring_mode,
                department_id,
            )
        )
    )
    return _breakdown(rows, int(total_bytes or 0))


@router.get("/applications", response_model=list[TrafficBreakdown])
def get_application_usage(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    start: datetime | None = None,
    end: datetime | None = None,
    department_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrafficBreakdown]:
    window_start, window_end = _window(hours, start, end)
    filters = [
        FlowRecord.application_name.is_not(None),
        *_flow_filters(
            window_start,
            window_end,
            request.app.state.settings.monitoring_mode,
            department_id,
        ),
    ]
    rows = db.execute(
        select(
            FlowRecord.application_name,
            func.sum(FlowRecord.bytes_transferred),
            func.count(FlowRecord.id),
        )
        .where(*filters)
        .group_by(FlowRecord.application_name)
        .order_by(desc(func.sum(FlowRecord.bytes_transferred)))
        .limit(20)
    ).all()
    total_bytes = db.scalar(
        select(func.sum(FlowRecord.bytes_transferred)).where(*filters)
    )
    return _breakdown(rows, int(total_bytes or 0))


@router.get("/departments", response_model=list[TrafficDepartment])
def get_departments_with_traffic(
    request: Request,
    hours: int = Query(default=168, ge=1, le=168),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TrafficDepartment]:
    window_start, window_end = _window(hours, None, None)
    mode = request.app.state.settings.monitoring_mode
    rows = db.execute(
        select(Department.id, Department.name)
        .select_from(TrafficRecord)
        .join(Department, Department.id == TrafficRecord.department_id)
        .where(
            TrafficRecord.interval_start >= window_start,
            TrafficRecord.interval_start < window_end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(Department.id, Department.name)
        .order_by(Department.name)
    ).all()
    return [TrafficDepartment(id=department_id, name=name) for department_id, name in rows]


def _breakdown(rows, total: int) -> list[TrafficBreakdown]:
    return [
        TrafficBreakdown(
            name=name,
            bytes_transferred=int(byte_count or 0),
            flow_count=count,
            percent=round(int(byte_count or 0) / total * 100, 1) if total else 0,
        )
        for name, byte_count, count in rows
    ]
