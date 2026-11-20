from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user, require_admin
from app.database.session import get_db
from app.models import (
    AuditLog,
    Department,
    MonitoringSetting,
    NetworkAlert,
    NetworkDevice,
    User,
)
from app.schemas.alerts import (
    AlertCreate,
    AlertSeverity,
    AlertResponse,
    AlertStatus,
    AlertStatusUpdate,
    AlertThresholds,
)
from app.services.alerts import load_alert_thresholds

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    request: Request,
    alert_status: AlertStatus | None = Query(default=None, alias="status"),
    severity: AlertSeverity | None = None,
    department_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NetworkAlert]:
    statement = select(NetworkAlert).where(_mode_filter(request))
    if alert_status is not None:
        statement = statement.where(NetworkAlert.status == alert_status)
    if severity is not None:
        statement = statement.where(NetworkAlert.severity == severity)
    if department_id is not None:
        statement = statement.where(NetworkAlert.department_id == department_id)
    return db.scalars(
        statement.order_by(NetworkAlert.detected_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreate,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NetworkAlert:
    data_mode = request.app.state.settings.monitoring_mode
    department_id = payload.department_id
    if department_id is not None and db.get(Department, department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")

    if payload.device_id is not None:
        device = db.get(NetworkDevice, payload.device_id)
        if device is None or not _matches_mode(device.source, data_mode):
            raise HTTPException(status_code=404, detail="Device not found")
        if department_id is not None and device.department_id not in (
            None,
            department_id,
        ):
            raise HTTPException(
                status_code=422,
                detail="Department does not match the selected device",
            )
        department_id = department_id or device.department_id

    alert = NetworkAlert(
        department_id=department_id,
        device_id=payload.device_id,
        alert_type="demo_manual" if data_mode == "demo" else "manual",
        severity=payload.severity,
        status="open",
        title=payload.title,
        description=payload.description,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.flush()
    _audit(
        db,
        actor=actor,
        action="alert.create",
        resource_id=alert.id,
        metadata={"severity": alert.severity},
    )
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/{alert_id}/status", response_model=AlertResponse)
def update_alert_status(
    alert_id: UUID,
    payload: AlertStatusUpdate,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NetworkAlert:
    alert = db.scalar(
        select(NetworkAlert).where(
            NetworkAlert.id == alert_id,
            _mode_filter(request),
        )
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.status == payload.status:
        return alert
    if alert.status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Resolved alerts cannot be reopened",
        )

    now = datetime.now(timezone.utc)
    alert.status = payload.status
    if payload.status == "acknowledged":
        alert.acknowledged_by = actor.id
        alert.acknowledged_at = now
    else:
        alert.resolved_at = now
    _audit(
        db,
        actor=actor,
        action=f"alert.{payload.status}",
        resource_id=alert.id,
        metadata={"status": payload.status},
    )
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/thresholds", response_model=AlertThresholds)
def get_thresholds(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertThresholds:
    return load_alert_thresholds(db)


@router.put("/thresholds", response_model=AlertThresholds)
def update_thresholds(
    payload: AlertThresholds,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertThresholds:
    setting = db.scalar(
        select(MonitoringSetting).where(
            MonitoringSetting.provider == "alerts",
            MonitoringSetting.setting_key == "thresholds",
        )
    )
    if setting is None:
        setting = MonitoringSetting(provider="alerts", setting_key="thresholds")
        db.add(setting)
    setting.setting_value = payload.model_dump(mode="json")
    setting.enabled = True
    setting.updated_by = actor.id
    db.flush()
    _audit(
        db,
        actor=actor,
        action="alert.thresholds.update",
        resource_id=setting.id,
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    return payload


def _mode_filter(request: Request):
    is_demo = NetworkAlert.alert_type.startswith("demo_")
    return is_demo if request.app.state.settings.monitoring_mode == "demo" else ~is_demo


def _matches_mode(source: str, data_mode: Literal["demo", "live"]) -> bool:
    return source == "demo" if data_mode == "demo" else source != "demo"


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
            resource_type="network_alert",
            resource_id=resource_id,
            outcome="success",
            metadata_json=metadata,
        )
    )
