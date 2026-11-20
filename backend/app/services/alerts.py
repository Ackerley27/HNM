from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    MonitoringSetting,
    NetworkAlert,
    NetworkDevice,
    TrafficRecord,
)
from app.schemas.alerts import AlertThresholds

ACTIVE_STATUSES = ("open", "acknowledged")


def load_alert_thresholds(db: Session) -> AlertThresholds:
    setting = db.scalar(
        select(MonitoringSetting).where(
            MonitoringSetting.provider == "alerts",
            MonitoringSetting.setting_key == "thresholds",
        )
    )
    return AlertThresholds() if setting is None else AlertThresholds.model_validate(
        setting.setting_value
    )


def evaluate_live_alerts(db: Session, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    thresholds = load_alert_thresholds(db)

    offline_devices = db.scalars(
        select(NetworkDevice).where(
            NetworkDevice.monitoring_enabled.is_(True),
            NetworkDevice.status == "offline",
            NetworkDevice.source != "demo",
        )
    ).all()
    offline_ids = {device.id for device in offline_devices}
    if thresholds.offline_detection_enabled:
        for device in offline_devices:
            _ensure_alert(
                db,
                alert_type="device_offline",
                device_id=device.id,
                department_id=device.department_id,
                title="ตรวจพบอุปกรณ์เครือข่ายออฟไลน์",
                description=f"ไม่พบสถานะออนไลน์ของ {device.name}",
                severity="critical",
                now=now,
            )
    if thresholds.offline_detection_enabled:
        active_offline = db.scalars(
            select(NetworkAlert).where(
                NetworkAlert.alert_type == "device_offline",
                NetworkAlert.status.in_(ACTIVE_STATUSES),
                NetworkAlert.device_id.is_not(None),
            )
        ).all()
        for alert in active_offline:
            device = db.get(NetworkDevice, alert.device_id)
            if (
                device is not None
                and device.status == "online"
                and device.id not in offline_ids
            ):
                _resolve_alert(alert, now)

    current_rates = _grouped_rates(db, now - timedelta(minutes=5), now)
    if current_rates:
        total_current_rate = sum(current_rates.values())
        high_bandwidth_alerts = db.scalars(
            select(NetworkAlert).where(
                NetworkAlert.alert_type == "high_bandwidth",
                NetworkAlert.device_id.is_(None),
                NetworkAlert.status.in_(ACTIVE_STATUSES),
            )
        ).all()
        if total_current_rate >= thresholds.high_bandwidth_bps:
            _ensure_alert(
                db,
                alert_type="high_bandwidth",
                device_id=None,
                department_id=None,
                title="ตรวจพบการใช้แบนด์วิดท์สูง",
                description=(
                    f"อัตรารับและส่งรวม {total_current_rate} bps "
                    "สูงกว่าเกณฑ์ที่กำหนด"
                ),
                severity=(
                    "critical"
                    if total_current_rate >= thresholds.high_bandwidth_bps * 2
                    else "warning"
                ),
                now=now,
            )
        else:
            for alert in high_bandwidth_alerts:
                _resolve_alert(alert, now)

        baseline_rates = _grouped_rates(
            db, now - timedelta(hours=24), now - timedelta(minutes=5)
        )
        anomalous_devices: set[UUID] = set()
        has_global_anomaly = False
        for key, current_rate in current_rates.items():
            baseline = baseline_rates.get(key)
            if (
                baseline is None
                or baseline < thresholds.unusual_traffic_min_bps
                or current_rate <= baseline * thresholds.unusual_traffic_multiplier
            ):
                continue
            device_id = key[1]
            if device_id is None:
                has_global_anomaly = True
            else:
                anomalous_devices.add(device_id)
                device = db.get(NetworkDevice, device_id)
                department_id = device.department_id if device is not None else None
                _ensure_alert(
                    db,
                    alert_type="unusual_traffic",
                    device_id=device_id,
                    department_id=department_id,
                    title="ตรวจพบรูปแบบการใช้งานผิดปกติ",
                    description="อัตราการใช้งานสูงกว่าค่าเฉลี่ยย้อนหลังตามเกณฑ์ที่กำหนด",
                    severity="warning",
                    now=now,
                )
        global_anomalies = db.scalars(
            select(NetworkAlert).where(
                NetworkAlert.alert_type == "unusual_traffic",
                NetworkAlert.device_id.is_(None),
                NetworkAlert.status.in_(ACTIVE_STATUSES),
            )
        ).all()
        if has_global_anomaly:
            _ensure_alert(
                db,
                alert_type="unusual_traffic",
                device_id=None,
                department_id=None,
                title="ตรวจพบรูปแบบการใช้งานผิดปกติ",
                description="อัตราการใช้งานสูงกว่าค่าเฉลี่ยย้อนหลังตามเกณฑ์ที่กำหนด",
                severity="warning",
                now=now,
            )
        else:
            for alert in global_anomalies:
                _resolve_alert(alert, now)

        active_unusual = db.scalars(
            select(NetworkAlert).where(
                NetworkAlert.alert_type == "unusual_traffic",
                NetworkAlert.device_id.is_not(None),
                NetworkAlert.status.in_(ACTIVE_STATUSES),
            )
        ).all()
        for alert in active_unusual:
            if alert.device_id not in anomalous_devices:
                _resolve_alert(alert, now)

    db.commit()


def _grouped_rates(
    db: Session,
    start: datetime,
    end: datetime,
) -> dict[tuple[str, UUID | None, UUID | None, str], float]:
    rows = db.execute(
        select(
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
            TrafficRecord.direction,
            func.avg(TrafficRecord.bit_rate_bps),
        )
        .where(
            TrafficRecord.interval_start >= start,
            TrafficRecord.interval_start < end,
            TrafficRecord.source != "demo",
            TrafficRecord.bit_rate_bps.is_not(None),
        )
        .group_by(
            TrafficRecord.source,
            TrafficRecord.device_id,
            TrafficRecord.interface_id,
            TrafficRecord.direction,
        )
    ).all()
    return {
        (source, device_id, interface_id, direction): float(rate)
        for source, device_id, interface_id, direction, rate in rows
        if rate is not None
    }


def _ensure_alert(
    db: Session,
    *,
    alert_type: str,
    device_id: UUID | None,
    department_id: UUID | None,
    title: str,
    description: str,
    severity: str,
    now: datetime,
) -> None:
    existing = db.scalar(
        select(NetworkAlert).where(
            NetworkAlert.alert_type == alert_type,
            NetworkAlert.device_id == device_id,
            NetworkAlert.status.in_(ACTIVE_STATUSES),
        )
    )
    if existing is not None:
        existing.description = description
        existing.severity = severity
        return
    db.add(
        NetworkAlert(
            alert_type=alert_type,
            device_id=device_id,
            department_id=department_id,
            title=title,
            description=description,
            severity=severity,
            status="open",
            detected_at=now,
        )
    )
    db.flush()


def _resolve_alert(alert: NetworkAlert, now: datetime) -> None:
    alert.status = "resolved"
    alert.resolved_at = now
