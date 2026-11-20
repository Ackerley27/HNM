from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    MonitoringSetting,
    NetworkAlert,
    NetworkDevice,
    TrafficRecord,
)
from app.services.alerts import evaluate_live_alerts


def login_headers(client, email="admin@example.org", password="correct horse battery staple"):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_alert_api_filters_demo_data_and_restricts_administration(client):
    now = datetime.now(timezone.utc)
    with client.app.state.database_engine.begin() as connection:
        connection.execute(
            NetworkAlert.__table__.insert(),
            [
                {
                    "id": uuid4(),
                    "alert_type": "demo_device_offline",
                    "severity": "warning",
                    "status": "open",
                    "title": "ข้อมูลสาธิต",
                    "description": None,
                    "detected_at": now,
                },
                {
                    "id": uuid4(),
                    "alert_type": "device_offline",
                    "severity": "critical",
                    "status": "open",
                    "title": "ข้อมูลจริง",
                    "description": None,
                    "detected_at": now,
                },
            ],
        )

    viewer_headers = login_headers(
        client,
        "viewer@example.org",
        "viewer password 123",
    )
    restricted = client.put(
        "/api/alerts/thresholds",
        json={"high_bandwidth_bps": 5_000_000},
        headers=viewer_headers,
    )
    assert restricted.status_code == 403

    client.app.state.settings.monitoring_mode = "demo"
    demo_alerts = client.get("/api/alerts", headers=viewer_headers)
    assert demo_alerts.status_code == 200
    assert [alert["alert_type"] for alert in demo_alerts.json()] == [
        "demo_device_offline"
    ]


def test_admin_manual_alert_is_scoped_to_the_active_mode(client):
    headers = login_headers(client)
    payload = {
        "title": "ตรวจสอบลิงก์สำรอง",
        "description": "มีการบำรุงรักษาตามแผน",
        "severity": "info",
    }

    live_alert = client.post("/api/alerts", json=payload, headers=headers)
    client.app.state.settings.monitoring_mode = "demo"
    demo_alert = client.post("/api/alerts", json=payload, headers=headers)
    visible_demo_alerts = client.get("/api/alerts", headers=headers)

    assert live_alert.status_code == 201
    assert live_alert.json()["alert_type"] == "manual"
    assert demo_alert.status_code == 201
    assert demo_alert.json()["alert_type"] == "demo_manual"
    assert [alert["id"] for alert in visible_demo_alerts.json()] == [
        demo_alert.json()["id"]
    ]


def test_admin_can_acknowledge_alert_and_update_thresholds_with_audit(client):
    now = datetime.now(timezone.utc)
    alert_id = uuid4()
    with client.app.state.database_engine.begin() as connection:
        connection.execute(
            NetworkAlert.__table__.insert().values(
                id=alert_id,
                alert_type="device_offline",
                severity="critical",
                status="open",
                title="อุปกรณ์ออฟไลน์",
                description="ตรวจพบอุปกรณ์ที่ไม่ตอบสนอง",
                detected_at=now,
            )
        )

    headers = login_headers(client)
    acknowledged = client.patch(
        f"/api/alerts/{alert_id}/status",
        json={"status": "acknowledged"},
        headers=headers,
    )
    thresholds = client.put(
        "/api/alerts/thresholds",
        json={
            "high_bandwidth_bps": 10_000_000,
            "unusual_traffic_multiplier": 4,
            "unusual_traffic_min_bps": 1_000_000,
            "offline_detection_enabled": False,
        },
        headers=headers,
    )

    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_at"] is not None
    resolved = client.patch(
        f"/api/alerts/{alert_id}/status",
        json={"status": "resolved"},
        headers=headers,
    )
    reopen = client.patch(
        f"/api/alerts/{alert_id}/status",
        json={"status": "acknowledged"},
        headers=headers,
    )
    assert thresholds.status_code == 200
    assert thresholds.json()["high_bandwidth_bps"] == 10_000_000
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert reopen.status_code == 409
    with Session(client.app.state.database_engine) as db:
        actions = set(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.action.in_(
                        [
                            "alert.acknowledged",
                            "alert.resolved",
                            "alert.thresholds.update",
                        ]
                    )
                )
            ).all()
        )
    assert actions == {
        "alert.acknowledged",
        "alert.resolved",
        "alert.thresholds.update",
    }
    overview = client.get("/api/dashboard/overview", headers=headers)
    assert overview.status_code == 200
    assert all(
        service["provider"] != "alerts"
        for service in overview.json()["monitoring_services"]
    )


def test_live_alert_evaluator_deduplicates_and_resolves_confirmed_conditions(client):
    now = datetime.now(timezone.utc)
    device_id = uuid4()
    with Session(client.app.state.database_engine) as db:
        db.add(
            NetworkDevice(
                id=device_id,
                name="Core switch",
                ip_address="192.0.2.30",
                device_type="switch",
                status="offline",
                source="manual",
                monitoring_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            MonitoringSetting(
                provider="alerts",
                setting_key="thresholds",
                setting_value={
                    "high_bandwidth_bps": 1_000_000,
                    "unusual_traffic_multiplier": 3,
                    "unusual_traffic_min_bps": 1_000_000,
                    "offline_detection_enabled": True,
                },
                enabled=True,
            )
        )
        db.add_all(
            [
                TrafficRecord(
                    interval_start=now - timedelta(hours=1),
                    interval_end=now - timedelta(hours=1) + timedelta(seconds=30),
                    device_id=device_id,
                    direction="ingress",
                    bytes_transferred=10_000_000,
                    bit_rate_bps=10_000_000,
                    source="ntopng",
                    source_record_id="baseline",
                ),
                TrafficRecord(
                    interval_start=now - timedelta(minutes=1),
                    interval_end=now - timedelta(seconds=30),
                    device_id=device_id,
                    direction="ingress",
                    bytes_transferred=31_000_000,
                    bit_rate_bps=31_000_000,
                    source="ntopng",
                    source_record_id="current",
                ),
                TrafficRecord(
                    interval_start=now - timedelta(seconds=30),
                    interval_end=now,
                    device_id=None,
                    direction="egress",
                    bytes_transferred=900_000_000,
                    bit_rate_bps=900_000_000,
                    source="demo",
                    source_record_id="demo-only",
                ),
            ]
        )
        db.commit()
        evaluate_live_alerts(db, now)
        evaluate_live_alerts(db, now)

        alerts = db.scalars(select(NetworkAlert)).all()
        assert len(alerts) == 3
        assert {alert.alert_type for alert in alerts} == {
            "device_offline",
            "high_bandwidth",
            "unusual_traffic",
        }
        device = db.get(NetworkDevice, device_id)
        device.status = "online"
        evaluate_live_alerts(db, now + timedelta(minutes=1))
        offline_alert = db.scalar(
            select(NetworkAlert).where(NetworkAlert.alert_type == "device_offline")
        )
        assert offline_alert.status == "resolved"
