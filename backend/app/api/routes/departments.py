from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.routes.auth import get_current_user, require_admin
from app.database.session import get_db
from app.models import (
    AuditLog,
    Department,
    FlowRecord,
    MonitoredHost,
    NetworkAlert,
    NetworkDevice,
    TrafficRecord,
    User,
    Vlan,
)
from app.schemas.departments import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    DepartmentUsagePoint,
    DepartmentUsageResponse,
    VlanResponse,
)
from app.services.traffic import MonitoringMode, source_filter

router = APIRouter(prefix="/departments", tags=["departments"])
UsagePeriod = Literal["hour", "day", "month"]


@router.get("", response_model=list[DepartmentResponse])
def list_departments(
    request: Request,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DepartmentResponse]:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    departments = db.scalars(
        select(Department)
        .options(selectinload(Department.vlans))
        .order_by(Department.name)
    ).all()
    if not departments:
        return []

    department_ids = [department.id for department in departments]
    device_counts = dict(
        db.execute(
            select(NetworkDevice.department_id, func.count(NetworkDevice.id))
            .where(
                NetworkDevice.department_id.in_(department_ids),
                source_filter(NetworkDevice.source, mode),
            )
            .group_by(NetworkDevice.department_id)
        ).all()
    )
    now = datetime.now(timezone.utc)
    traffic_rows = db.execute(
        select(
            TrafficRecord.department_id,
            func.sum(TrafficRecord.bytes_transferred),
        )
        .where(
            TrafficRecord.department_id.in_(department_ids),
            TrafficRecord.interval_start >= now - timedelta(hours=24),
            TrafficRecord.interval_start < now,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(TrafficRecord.department_id)
    ).all()
    traffic_bytes = {
        department_id: int(byte_count)
        for department_id, byte_count in traffic_rows
        if byte_count is not None
    }
    return [
        _serialize_department(
            department,
            device_counts.get(department.id, 0),
            traffic_bytes.get(department.id),
        )
        for department in departments
    ]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    _ensure_unique_code(db, payload.code)
    department = Department(
        code=payload.code,
        name=payload.name,
        description=payload.description,
    )
    db.add(department)
    db.flush()
    _audit(
        db,
        actor=actor,
        action="department.create",
        resource_id=department.id,
        metadata={"code": department.code},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department code already exists") from None
    db.refresh(department)
    return _serialize_department(department, 0, None)


@router.get("/{department_id}/usage", response_model=DepartmentUsageResponse)
def get_department_usage(
    department_id: UUID,
    request: Request,
    period: UsagePeriod = "day",
    periods: int = Query(default=30, ge=1, le=730),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DepartmentUsageResponse:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    now = datetime.now(timezone.utc)
    start, end = _period_window(period, periods, now)
    if periods > {"hour": 168, "day": 90, "month": 24}[period]:
        raise HTTPException(
            status_code=422,
            detail=f"periods cannot exceed the limit for {period}",
        )
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        traffic_bucket = func.date_trunc(period, TrafficRecord.interval_start)
        flow_bucket = func.date_trunc(period, FlowRecord.flow_start)
    else:
        formats = {
            "hour": "%Y-%m-%d %H:00:00",
            "day": "%Y-%m-%d 00:00:00",
            "month": "%Y-%m-01 00:00:00",
        }
        traffic_bucket = func.strftime(formats[period], TrafficRecord.interval_start)
        flow_bucket = func.strftime(formats[period], FlowRecord.flow_start)

    traffic_rows = db.execute(
        select(
            traffic_bucket.label("period_start"),
            TrafficRecord.direction,
            func.sum(TrafficRecord.bytes_transferred),
        )
        .where(
            TrafficRecord.department_id == department_id,
            TrafficRecord.interval_start >= start,
            TrafficRecord.interval_start < end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(traffic_bucket, TrafficRecord.direction)
        .order_by(traffic_bucket)
    ).all()
    flow_rows = db.execute(
        select(
            flow_bucket.label("period_start"),
            func.sum(FlowRecord.bytes_transferred),
            func.count(FlowRecord.id),
        )
        .where(
            FlowRecord.department_id == department_id,
            FlowRecord.flow_start >= start,
            FlowRecord.flow_start < end,
            source_filter(FlowRecord.source, mode),
        )
        .group_by(flow_bucket)
        .order_by(flow_bucket)
    ).all()

    points: dict[datetime, dict[str, int | None]] = {}
    ingress_total = 0
    egress_total = 0
    traffic_count = 0
    for bucket_value, direction, byte_count in traffic_rows:
        point_time = _as_utc_datetime(bucket_value)
        point = points.setdefault(
            point_time,
            {
                "ingress_bytes": None,
                "egress_bytes": None,
                "flow_bytes": None,
                "flow_count": 0,
            },
        )
        value = int(byte_count or 0)
        if direction == "ingress":
            point["ingress_bytes"] = value
            ingress_total += value
        else:
            point["egress_bytes"] = value
            egress_total += value
        traffic_count += 1

    flow_total = 0
    flow_count = 0
    for bucket_value, byte_count, count in flow_rows:
        point_time = _as_utc_datetime(bucket_value)
        point = points.setdefault(
            point_time,
            {
                "ingress_bytes": None,
                "egress_bytes": None,
                "flow_bytes": None,
                "flow_count": 0,
            },
        )
        point["flow_bytes"] = int(byte_count or 0)
        point["flow_count"] = count
        flow_total += int(byte_count or 0)
        flow_count += count

    return DepartmentUsageResponse(
        department_id=department.id,
        department_name=department.name,
        data_mode=mode,
        period=period,
        period_count=periods,
        start=start,
        end=end,
        ingress_bytes=ingress_total if traffic_count else None,
        egress_bytes=egress_total if traffic_count else None,
        total_traffic_bytes=(ingress_total + egress_total) if traffic_count else None,
        flow_bytes=flow_total if flow_rows else None,
        flow_count=flow_count,
        points=[
            DepartmentUsagePoint(period_start=period_start, **values)
            for period_start, values in sorted(points.items())
        ],
    )


@router.put("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: UUID,
    payload: DepartmentUpdate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DepartmentResponse:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    changes = payload.model_dump(exclude_unset=True)
    for required_field in ("code", "name"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{required_field} cannot be null",
            )
    if "code" in changes:
        _ensure_unique_code(db, changes["code"], excluding_id=department.id)
    for field, value in changes.items():
        setattr(department, field, value)
    _audit(
        db,
        actor=actor,
        action="department.update",
        resource_id=department.id,
        metadata={"fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department code already exists") from None
    db.refresh(department)
    return _serialize_department(department, 0, None)


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_department(
    department_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    references = (
        (NetworkDevice, NetworkDevice.department_id),
        (MonitoredHost, MonitoredHost.department_id),
        (TrafficRecord, TrafficRecord.department_id),
        (FlowRecord, FlowRecord.department_id),
        (NetworkAlert, NetworkAlert.department_id),
        (Vlan, Vlan.department_id),
    )
    for model, department_column in references:
        if db.scalar(
            select(model.id).where(department_column == department_id).limit(1)
        ) is not None:
            raise HTTPException(
                status_code=409,
                detail="Department is still referenced by network data",
            )
    _audit(
        db,
        actor=actor,
        action="department.delete",
        resource_id=department.id,
        metadata={"code": department.code},
    )
    db.delete(department)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _period_window(
    period: UsagePeriod,
    periods: int,
    now: datetime,
) -> tuple[datetime, datetime]:
    if period == "hour":
        start = now.replace(minute=0, second=0, microsecond=0) - timedelta(
            hours=periods - 1
        )
    elif period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=periods - 1
        )
    else:
        month_index = now.year * 12 + now.month - 1 - (periods - 1)
        year, month_zero_based = divmod(month_index, 12)
        start = datetime(year, month_zero_based + 1, 1, tzinfo=timezone.utc)
    return start, now


def _as_utc_datetime(value: datetime | str) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result


def _serialize_department(
    department: Department,
    device_count: int,
    traffic_bytes_24h: int | None,
) -> DepartmentResponse:
    return DepartmentResponse(
        id=department.id,
        code=department.code,
        name=department.name,
        description=department.description,
        device_count=device_count,
        traffic_bytes_24h=traffic_bytes_24h,
        vlans=[
            VlanResponse(
                id=vlan.id,
                vlan_number=vlan.vlan_number,
                name=vlan.name,
                subnet=str(vlan.subnet) if vlan.subnet is not None else None,
            )
            for vlan in department.vlans
        ],
        created_at=department.created_at,
        updated_at=department.updated_at,
    )


def _ensure_unique_code(
    db: Session,
    code: str,
    excluding_id: UUID | None = None,
) -> None:
    statement = select(Department.id).where(Department.code == code)
    if excluding_id is not None:
        statement = statement.where(Department.id != excluding_id)
    if db.scalar(statement.limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Department code already exists")


def _audit(
    db: Session,
    *,
    actor: User,
    action: str,
    resource_id: UUID,
    metadata: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action=action,
            resource_type="department",
            resource_id=resource_id,
            outcome="success",
            metadata_json=metadata,
        )
    )
