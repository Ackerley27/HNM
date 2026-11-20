from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import Department, NetworkDevice, TrafficRecord


def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.org",
            "password": "correct horse battery staple",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_requires_authentication(client):
    response = client.get("/api/dashboard/overview")
    assert response.status_code == 401


def test_empty_dashboard_reports_unavailable_measurements(client):
    response = client.get("/api/dashboard/overview", headers=admin_headers(client))
    history = client.get("/api/dashboard/traffic", headers=admin_headers(client))

    assert response.status_code == 200
    assert response.json()["data_mode"] == "live"
    assert response.json()["total_devices"] == 0
    assert response.json()["download_bps"] is None
    assert response.json()["traffic_bytes_24h"] is None
    assert response.json()["availability_percent"] is None
    assert response.json()["department_usage"] == []
    assert history.json() == {"window_hours": 24, "has_data": False, "points": []}


def test_dashboard_aggregates_real_database_records(client):
    now = datetime.now(timezone.utc)
    with client.app.state.database_engine.begin() as connection:
        department_id = uuid4()
        device_id = uuid4()
        connection.execute(
            Department.__table__.insert().values(
                id=department_id,
                code="RAD",
                name="รังสีวิทยา",
            )
        )
        connection.execute(
            NetworkDevice.__table__.insert().values(
                id=device_id,
                department_id=department_id,
                name="Core switch",
                hostname="switch-01",
                ip_address="192.0.2.10",
                device_type="switch",
                status="online",
                source="manual",
                monitoring_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            TrafficRecord.__table__.insert(),
            [
                {
                    "id": uuid4(),
                    "interval_start": now - timedelta(minutes=2),
                    "interval_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "device_id": device_id,
                    "direction": "ingress",
                    "bytes_transferred": 1200,
                    "bit_rate_bps": 64000,
                    "source": "test",
                    "source_record_id": "download-1",
                    "created_at": now,
                },
                {
                    "id": uuid4(),
                    "interval_start": now - timedelta(minutes=2),
                    "interval_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "device_id": device_id,
                    "direction": "egress",
                    "bytes_transferred": 600,
                    "bit_rate_bps": 32000,
                    "source": "test",
                    "source_record_id": "upload-1",
                    "created_at": now,
                },
            ],
        )

    headers = admin_headers(client)
    overview = client.get("/api/dashboard/overview", headers=headers)
    history = client.get("/api/dashboard/traffic?hours=1", headers=headers)

    assert overview.status_code == 200
    body = overview.json()
    assert body["online_devices"] == 1
    assert body["availability_percent"] == 100
    assert body["download_bps"] == 64000
    assert body["upload_bps"] == 32000
    assert body["traffic_bytes_24h"] == 1800
    assert body["department_usage"][0]["bytes_transferred"] == 1800
    assert history.json()["has_data"] is True
    assert history.json()["points"][0]["download_bps"] == 64000
    assert history.json()["points"][0]["upload_bps"] == 32000


def test_dashboard_separates_demo_and_live_records(client):
    now = datetime.now(timezone.utc)
    with client.app.state.database_engine.begin() as connection:
        department_id = uuid4()
        connection.execute(
            Department.__table__.insert().values(
                id=department_id,
                code="DEMO",
                name="ข้อมูลสาธิต",
            )
        )
        connection.execute(
            NetworkDevice.__table__.insert(),
            [
                {
                    "id": uuid4(),
                    "department_id": department_id,
                    "name": "Demo device",
                    "ip_address": "192.0.2.11",
                    "device_type": "switch",
                    "status": "online",
                    "source": "demo",
                    "monitoring_enabled": True,
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": uuid4(),
                    "department_id": None,
                    "name": "Live device",
                    "ip_address": "192.0.2.12",
                    "device_type": "router",
                    "status": "offline",
                    "source": "manual",
                    "monitoring_enabled": True,
                    "created_at": now,
                    "updated_at": now,
                },
            ],
        )
        connection.execute(
            TrafficRecord.__table__.insert(),
            [
                {
                    "id": uuid4(),
                    "interval_start": now - timedelta(minutes=2),
                    "interval_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "direction": "ingress",
                    "bytes_transferred": 9000,
                    "bit_rate_bps": 8000,
                    "source": "demo",
                    "source_record_id": "demo-traffic",
                    "created_at": now,
                },
                {
                    "id": uuid4(),
                    "interval_start": now - timedelta(minutes=2),
                    "interval_end": now - timedelta(minutes=1),
                    "department_id": None,
                    "direction": "ingress",
                    "bytes_transferred": 100,
                    "bit_rate_bps": 100,
                    "source": "zabbix",
                    "source_record_id": "live-traffic",
                    "created_at": now,
                },
            ],
        )

    client.app.state.settings.monitoring_mode = "demo"
    response = client.get(
        "/api/dashboard/overview",
        headers=admin_headers(client),
    )
    history = client.get(
        "/api/dashboard/traffic?hours=1",
        headers=admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["data_mode"] == "demo"
    assert response.json()["total_devices"] == 1
    assert response.json()["online_devices"] == 1
    assert response.json()["download_bps"] == 8000
    assert response.json()["traffic_bytes_24h"] == 9000
    assert history.json()["points"][0]["bytes_transferred"] == 9000
