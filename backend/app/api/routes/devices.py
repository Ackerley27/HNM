from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import String, cast, desc, or_, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user, require_admin
from app.database.session import get_db
from app.models import (
    AuditLog,
    Department,
    DeviceMetric,
    NetworkDevice,
    TrafficRecord,
    User,
    Vlan,
)
from app.schemas.devices import (
    DeviceCreate,
    DeviceHistory,
    DeviceMetricPoint,
    DeviceResponse,
    DeviceTrafficPoint,
    DeviceType,
    DeviceUpdate,
)
from app.services.traffic import MonitoringMode, source_filter

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    request: Request,
    department_id: UUID | None = None,
    device_type: DeviceType | None = None,
    device_status: Literal["online", "offline", "unknown", "unavailable"] | None = Query(
        default=None, alias="status"
    ),
    search: str | None = Query(default=None, max_length=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeviceResponse]:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    statement = _device_query(mode)
    if department_id is not None:
        statement = statement.where(NetworkDevice.department_id == department_id)
    if device_type is not None:
        statement = statement.where(NetworkDevice.device_type == device_type)
    if device_status is not None:
        statement = statement.where(NetworkDevice.status == device_status)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                NetworkDevice.name.ilike(pattern),
                NetworkDevice.hostname.ilike(pattern),
                cast(NetworkDevice.ip_address, String).ilike(pattern),
            )
        )
    rows = db.execute(statement.order_by(NetworkDevice.name)).all()
    latest_metrics = _latest_metrics(
        db, [device.id for device, _department, _vlan in rows], mode
    )
    return [
        _serialize_device(device, department_name, vlan_number, latest_metrics)
        for device, department_name, vlan_number in rows
    ]


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    ip_address = str(payload.ip_address)
    _ensure_unique_ip(db, ip_address)
    department_id = _validate_department_vlan(
        db, payload.department_id, payload.vlan_id
    )
    source = "demo" if mode == "demo" else "manual"
    device = NetworkDevice(
        name=payload.name,
        hostname=payload.hostname,
        ip_address=ip_address,
        device_type=payload.device_type,
        status="unknown",
        source=source,
        department_id=department_id,
        vlan_id=payload.vlan_id,
        monitoring_enabled=payload.monitoring_enabled,
    )
    db.add(device)
    db.flush()
    _audit(
        db,
        actor=actor,
        action="device.create",
        resource_id=device.id,
        metadata={"device_type": device.device_type, "source": source},
    )
    db.commit()
    db.refresh(device)
    return _serialize_device(
        device,
        _department_name(db, device.department_id),
        _vlan_number(db, device.vlan_id),
        {},
    )


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: UUID,
    request: Request,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    row = db.execute(_device_query(mode).where(NetworkDevice.id == device_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device, department_name, vlan_number = row
    metrics = _latest_metrics(db, [device.id], mode)
    return _serialize_device(device, department_name, vlan_number, metrics)


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeviceResponse:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    device = _get_device(db, device_id, mode)
    changes = payload.model_dump(exclude_unset=True)
    for required_field in ("name", "ip_address", "device_type", "monitoring_enabled"):
        if required_field in changes and changes[required_field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{required_field} cannot be null",
            )

    department_id = changes.get("department_id", device.department_id)
    vlan_id = changes.get("vlan_id", device.vlan_id)
    validated_department_id = _validate_department_vlan(db, department_id, vlan_id)
    changes["department_id"] = validated_department_id
    changes["vlan_id"] = vlan_id

    if "ip_address" in changes:
        changes["ip_address"] = str(changes["ip_address"])
        _ensure_unique_ip(db, changes["ip_address"], excluding_id=device.id)
    for field, value in changes.items():
        setattr(device, field, value)
    _audit(
        db,
        actor=actor,
        action="device.update",
        resource_id=device.id,
        metadata={"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(device)
    return _serialize_device(
        device,
        _department_name(db, device.department_id),
        _vlan_number(db, device.vlan_id),
        _latest_metrics(db, [device.id], mode),
    )


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_device(
    device_id: UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    device = _get_device(db, device_id, mode)
    _audit(
        db,
        actor=actor,
        action="device.delete",
        resource_id=device.id,
        metadata={"device_type": device.device_type, "source": device.source},
    )
    db.delete(device)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{device_id}/history", response_model=DeviceHistory)
def get_device_history(
    device_id: UUID,
    request: Request,
    hours: int = Query(default=24, ge=1, le=168),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceHistory:
    mode: MonitoringMode = request.app.state.settings.monitoring_mode
    _get_device(db, device_id, mode)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    metrics = db.scalars(
        select(DeviceMetric)
        .where(
            DeviceMetric.device_id == device_id,
            DeviceMetric.recorded_at >= cutoff,
            source_filter(DeviceMetric.source, mode),
        )
        .order_by(desc(DeviceMetric.recorded_at))
        .limit(500)
    ).all()
    traffic = db.scalars(
        select(TrafficRecord)
        .where(
            TrafficRecord.device_id == device_id,
            TrafficRecord.interval_start >= cutoff,
            source_filter(TrafficRecord.source, mode),
        )
        .order_by(desc(TrafficRecord.interval_start))
        .limit(500)
    ).all()
    return DeviceHistory(
        device_id=device_id,
        window_hours=hours,
        metrics=[
            DeviceMetricPoint(
                metric_name=metric.metric_name,
                value=float(metric.value),
                unit=metric.unit,
                recorded_at=metric.recorded_at,
            )
            for metric in metrics
        ],
        traffic=[
            DeviceTrafficPoint(
                direction=record.direction,
                bytes_transferred=record.bytes_transferred,
                bit_rate_bps=record.bit_rate_bps,
                interval_start=record.interval_start,
            )
            for record in traffic
        ],
    )


def _device_query(mode: MonitoringMode):
    return (
        select(NetworkDevice, Department.name, Vlan.vlan_number)
        .outerjoin(Department, Department.id == NetworkDevice.department_id)
        .outerjoin(Vlan, Vlan.id == NetworkDevice.vlan_id)
        .where(source_filter(NetworkDevice.source, mode))
    )


def _get_device(db: Session, device_id: UUID, mode: MonitoringMode) -> NetworkDevice:
    device = db.scalar(
        select(NetworkDevice).where(
            NetworkDevice.id == device_id,
            source_filter(NetworkDevice.source, mode),
        )
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _latest_metrics(
    db: Session,
    device_ids: list[UUID],
    mode: MonitoringMode,
) -> dict[UUID, dict[str, float]]:
    if not device_ids:
        return {}
    rows = db.execute(
        select(DeviceMetric.device_id, DeviceMetric.metric_name, DeviceMetric.value)
        .where(
            DeviceMetric.device_id.in_(device_ids),
            source_filter(DeviceMetric.source, mode),
        )
        .order_by(desc(DeviceMetric.recorded_at))
    ).all()
    latest: dict[UUID, dict[str, float]] = {}
    for device_id, metric_name, value in rows:
        device_metrics = latest.setdefault(device_id, {})
        device_metrics.setdefault(metric_name, float(value))
    return latest


def _serialize_device(
    device: NetworkDevice,
    department_name: str | None,
    vlan_number: int | None,
    metrics: dict[UUID, dict[str, float]],
) -> DeviceResponse:
    device_metrics = metrics.get(device.id, {})
    return DeviceResponse(
        id=device.id,
        department_id=device.department_id,
        department_name=department_name,
        vlan_id=device.vlan_id,
        vlan_number=vlan_number,
        name=device.name,
        hostname=device.hostname,
        ip_address=str(device.ip_address),
        device_type=device.device_type,
        status=device.status,
        source=device.source,
        monitoring_enabled=device.monitoring_enabled,
        last_seen_at=device.last_seen_at,
        cpu_percent=device_metrics.get("cpu_percent"),
        memory_percent=device_metrics.get("memory_percent"),
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


def _ensure_unique_ip(
    db: Session,
    ip_address: str,
    excluding_id: UUID | None = None,
) -> None:
    statement = select(NetworkDevice.id).where(NetworkDevice.ip_address == ip_address)
    if excluding_id is not None:
        statement = statement.where(NetworkDevice.id != excluding_id)
    if db.scalar(statement.limit(1)) is not None:
        raise HTTPException(status_code=409, detail="A device with this IP already exists")


def _validate_department_vlan(
    db: Session,
    department_id: UUID | None,
    vlan_id: UUID | None,
) -> UUID | None:
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    if vlan_id is None:
        return department_id
    vlan = db.get(Vlan, vlan_id)
    if vlan is None:
        raise HTTPException(status_code=404, detail="VLAN not found")
    if department_id is not None and vlan.department_id != department_id:
        raise HTTPException(
            status_code=422,
            detail="VLAN does not belong to the selected department",
        )
    return vlan.department_id


def _department_name(db: Session, department_id: UUID | None) -> str | None:
    if department_id is None:
        return None
    return db.scalar(select(Department.name).where(Department.id == department_id))


def _vlan_number(db: Session, vlan_id: UUID | None) -> int | None:
    if vlan_id is None:
        return None
    return db.scalar(select(Vlan.vlan_number).where(Vlan.id == vlan_id))


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
            resource_type="network_device",
            resource_id=resource_id,
            outcome="success",
            metadata_json=metadata,
        )
    )
