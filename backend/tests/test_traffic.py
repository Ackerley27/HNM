from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import Department, FlowRecord, TrafficRecord


def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.org",
            "password": "correct horse battery staple",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_traffic_endpoints_return_aggregated_records_and_department_options(client):
    now = datetime.now(timezone.utc)
    department_id = uuid4()
    with client.app.state.database_engine.begin() as connection:
        connection.execute(
            Department.__table__.insert().values(
                id=department_id,
                code="ER",
                name="ฉุกเฉิน",
            )
        )
        connection.execute(
            TrafficRecord.__table__.insert().values(
                id=uuid4(),
                interval_start=now - timedelta(minutes=2),
                interval_end=now - timedelta(minutes=1),
                department_id=department_id,
                direction="ingress",
                bytes_transferred=2048,
                bit_rate_bps=120_000,
                source="ntopng",
                source_record_id="traffic-1",
                created_at=now,
            )
        )
        connection.execute(
            FlowRecord.__table__.insert(),
            [
                {
                    "id": uuid4(),
                    "flow_start": now - timedelta(minutes=2),
                    "flow_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "source_ip": "192.0.2.10",
                    "destination_ip": "198.51.100.20",
                    "source_port": 51000,
                    "destination_port": 443,
                    "protocol": "TCP",
                    "application_name": "HTTPS",
                    "bytes_transferred": 1024,
                    "source": "ntopng",
                    "source_record_id": "flow-1",
                    "created_at": now,
                },
                {
                    "id": uuid4(),
                    "flow_start": now - timedelta(minutes=2),
                    "flow_end": now - timedelta(minutes=1),
                    "department_id": department_id,
                    "source_ip": "192.0.2.11",
                    "destination_ip": "198.51.100.21",
                    "source_port": 51001,
                    "destination_port": 443,
                    "protocol": "TCP",
                    "application_name": "HTTPS",
                    "bytes_transferred": 3072,
                    "source": "ntopng",
                    "source_record_id": "flow-2",
                    "created_at": now,
                },
            ],
        )

    headers = admin_headers(client)
    summary = client.get("/api/traffic/summary?hours=1", headers=headers)
    departments = client.get("/api/traffic/departments", headers=headers)
    protocols = client.get("/api/traffic/protocols?hours=1", headers=headers)
    top_hosts = client.get("/api/traffic/top-hosts?hours=1", headers=headers)

    assert summary.status_code == 200
    assert summary.json()["total_bytes"] == 2048
    assert summary.json()["flow_count"] == 2
    assert departments.json() == [{"id": str(department_id), "name": "ฉุกเฉิน"}]
    assert protocols.json()[0]["name"] == "TCP"
    assert protocols.json()[0]["bytes_transferred"] == 4096
    assert {host["ip_address"] for host in top_hosts.json()} == {
        "192.0.2.10",
        "192.0.2.11",
        "198.51.100.20",
        "198.51.100.21",
    }


def test_traffic_endpoints_enforce_auth_and_time_window(client):
    unauthorized = client.get("/api/traffic/summary")
    invalid_window = client.get(
        "/api/traffic/history?start=2026-01-02T00:00:00Z&end=2026-01-01T00:00:00Z",
        headers=admin_headers(client),
    )

    assert unauthorized.status_code == 401
    assert invalid_window.status_code == 422
