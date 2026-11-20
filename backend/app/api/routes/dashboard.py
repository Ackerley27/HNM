from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database.session import get_db
from app.models import (
    Department,
    MonitoringSetting,
    NetworkAlert,
    NetworkDevice,
    TrafficRecord,
    User,
)
from app.schemas.dashboard import (
    DashboardOverview,
    DepartmentUsage,
    DeviceStatusSummary,
    MonitoringServiceStatus,
    RecentAlert,
    TrafficHistory,
    TrafficPoint,
)
from app.services.traffic import bandwidth_by_direction, source_filter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
KNOWN_DEVICE_STATES = ("online", "offline")
ALL_DEVICE_STATES = ("online", "offline", "unknown", "unavailable")


@router.get("/overview", response_model=DashboardOverview)
def get_overview(
    request: Request,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOverview:
    now = datetime.now(timezone.utc)
    data_mode = request.app.state.settings.monitoring_mode
    device_source_filter = (
        NetworkDevice.source == "demo"
        if data_mode == "demo"
        else NetworkDevice.source != "demo"
    )
    counts = dict(
        db.execute(
            select(NetworkDevice.status, func.count())
            .where(device_source_filter)
            .group_by(NetworkDevice.status)
        ).all()
    )
    total_devices = sum(counts.values())
    known_devices = sum(counts.get(state, 0) for state in KNOWN_DEVICE_STATES)
    availability = (
        round(counts.get("online", 0) / known_devices * 100, 1)
        if known_devices
        else None
    )

    bandwidth = bandwidth_by_direction(
        db,
        start=now - timedelta(minutes=5),
        end=now,
        mode=data_mode,
    )
    traffic_filter = (
        TrafficRecord.source == "demo"
        if data_mode == "demo"
        else TrafficRecord.source != "demo"
    )
    traffic_total, traffic_records = db.execute(
        select(func.sum(TrafficRecord.bytes_transferred), func.count(TrafficRecord.id))
        .where(
            TrafficRecord.interval_start >= now - timedelta(hours=24),
            traffic_filter,
        )
    ).one()

    department_rows = db.execute(
        select(
            Department.id,
            Department.name,
            func.sum(TrafficRecord.bytes_transferred),
        )
        .join(Department, Department.id == TrafficRecord.department_id)
        .where(
            TrafficRecord.interval_start >= now - timedelta(hours=24),
            traffic_filter,
        )
        .group_by(Department.id, Department.name)
        .order_by(desc(func.sum(TrafficRecord.bytes_transferred)))
        .limit(8)
    ).all()

    alert_filter = (
        NetworkAlert.alert_type.startswith("demo_")
        if data_mode == "demo"
        else ~NetworkAlert.alert_type.startswith("demo_")
    )
    alert_rows = db.scalars(
        select(NetworkAlert)
        .where(alert_filter)
        .order_by(NetworkAlert.detected_at.desc())
        .limit(6)
    ).all()

    monitoring_rows = db.scalars(
        select(MonitoringSetting)
        .where(
            MonitoringSetting.provider == "demo"
            if data_mode == "demo"
            else MonitoringSetting.provider != "demo",
            MonitoringSetting.setting_key == "collector",
        )
        .order_by(MonitoringSetting.provider, MonitoringSetting.setting_key)
    ).all()

    return DashboardOverview(
        generated_at=now,
        data_mode=request.app.state.settings.monitoring_mode,
        total_devices=total_devices,
        online_devices=counts.get("online", 0),
        offline_devices=counts.get("offline", 0),
        unknown_devices=counts.get("unknown", 0),
        unavailable_devices=counts.get("unavailable", 0),
        download_bps=bandwidth["ingress"],
        upload_bps=bandwidth["egress"],
        traffic_bytes_24h=int(traffic_total) if traffic_records else None,
        availability_percent=availability,
        department_usage=[
            DepartmentUsage(
                id=department_id,
                name=name,
                bytes_transferred=int(byte_count),
            )
            for department_id, name, byte_count in department_rows
        ],
        recent_alerts=[
            RecentAlert(
                id=alert.id,
                title=alert.title,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                detected_at=alert.detected_at,
            )
            for alert in alert_rows
        ],
        monitoring_services=[
            MonitoringServiceStatus(
                provider=setting.provider,
                setting_key=setting.setting_key,
                status=setting.service_status,
                last_checked_at=setting.last_checked_at,
            )
            for setting in monitoring_rows
        ],
    )


@router.get("/traffic", response_model=TrafficHistory)
def get_traffic_history(
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    department_id: UUID | None = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrafficHistory:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        bucket = func.date_trunc("hour", TrafficRecord.interval_start)
    else:
        bucket = func.strftime("%Y-%m-%d %H:00:00", TrafficRecord.interval_start)

    data_mode = request.app.state.settings.monitoring_mode
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
            TrafficRecord.interval_start >= cutoff,
            source_filter(TrafficRecord.source, data_mode),
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
    for (
        bucket_value,
        direction,
        _source,
        _device_id,
        _interface_id,
        average_rate,
        bytes_transferred,
    ) in db.execute(statement).all():
        if isinstance(bucket_value, str):
            point_time = datetime.fromisoformat(bucket_value)
        else:
            point_time = bucket_value
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
        point["bytes_transferred"] += int(bytes_transferred or 0)

    points = [TrafficPoint(**point) for point in points_by_time.values()]
    return TrafficHistory(
        window_hours=hours,
        has_data=bool(points),
        points=points,
    )


@router.get("/device-status", response_model=DeviceStatusSummary)
def get_device_status(
    request: Request,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceStatusSummary:
    counts = dict(
        db.execute(
            select(NetworkDevice.status, func.count())
            .where(
                NetworkDevice.source == "demo"
                if request.app.state.settings.monitoring_mode == "demo"
                else NetworkDevice.source != "demo"
            )
            .group_by(NetworkDevice.status)
        ).all()
    )
    return DeviceStatusSummary(
        total=sum(counts.values()),
        online=counts.get("online", 0),
        offline=counts.get("offline", 0),
        unknown=counts.get("unknown", 0),
        unavailable=counts.get("unavailable", 0),
    )
