from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import Department, FlowRecord, NetworkDevice, TrafficRecord


def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.org",
            "password": "correct horse battery staple",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_daily_monthly_and_csv_reports_use_active_mode_aggregates(client):
    now = datetime.now(timezone.utc)
    department_id = uuid4()
    device_id = uuid4()
    with client.app.state.database_engine.begin() as connection:
        connection.execute(
            Department.__table__.insert().values(
                id=department_id,
                code="RAD",
                name="รังสี",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            NetworkDevice.__table__.insert().values(
                id=device_id,
                department_id=department_id,
                name="Radiology switch",
                ip_address="192.0.2.40",
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
                    "bit_rate_bps": 8000,
                    "source": "ntopng",
                    "source_record_id": "report-live",
                    "created_at": now,
                },
                {
                    "id": uuid4(),
                    "interval_start": now - timedelta(minutes=2),
                    "interval_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "device_id": None,
                    "direction": "ingress",
                    "bytes_transferred": 9900,
                    "bit_rate_bps": 10000,
                    "source": "demo",
                    "source_record_id": "report-demo",
                    "created_at": now,
                },
            ],
        )
        connection.execute(
            FlowRecord.__table__.insert().values(
                id=uuid4(),
                flow_start=now - timedelta(minutes=2),
                flow_end=now - timedelta(minutes=1),
                department_id=department_id,
                source_ip="192.0.2.40",
                destination_ip="198.51.100.40",
                source_port=50000,
                destination_port=443,
                protocol="TCP",
                bytes_transferred=300,
                source="ntopng",
                source_record_id="report-flow",
                created_at=now,
            )
        )

    headers = admin_headers(client)
    daily = client.get(
        f"/api/reports/daily?date={now.date().isoformat()}",
        headers=headers,
    )
    monthly = client.get(
        f"/api/reports/monthly?year={now.year}&month={now.month}",
        headers=headers,
    )
    export = client.get(
        f"/api/reports/export?period=daily&date={now.date().isoformat()}",
        headers=headers,
    )

    assert daily.status_code == 200
    assert daily.json()["traffic_bytes"] == 1200
    assert daily.json()["download_bytes"] == 1200
    assert daily.json()["flow_bytes"] == 300
    assert daily.json()["total_devices"] == 1
    assert daily.json()["department_usage"][0]["bytes_transferred"] == 1200
    assert monthly.json()["traffic_bytes"] == 1200
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "report-live" not in export.text
    assert "192.0.2.40" not in export.text
