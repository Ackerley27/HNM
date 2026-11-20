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


def test_department_usage_aggregates_traffic_and_flows_in_active_mode(client):
    now = datetime.now(timezone.utc)
    department_id = uuid4()
    with client.app.state.database_engine.begin() as connection:
        connection.execute(
            Department.__table__.insert().values(
                id=department_id,
                code="CARD",
                name="หัวใจ",
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            TrafficRecord.__table__.insert().values(
                id=uuid4(),
                interval_start=now - timedelta(minutes=2),
                interval_end=now - timedelta(minutes=1),
                department_id=department_id,
                direction="ingress",
                bytes_transferred=700,
                bit_rate_bps=9000,
                source="ntopng",
                source_record_id="dept-traffic",
                created_at=now,
            )
        )
        connection.execute(
            FlowRecord.__table__.insert().values(
                id=uuid4(),
                flow_start=now - timedelta(minutes=2),
                flow_end=now - timedelta(minutes=1),
                department_id=department_id,
                source_ip="192.0.2.11",
                destination_ip="198.51.100.11",
                source_port=50000,
                destination_port=443,
                protocol="TCP",
                bytes_transferred=300,
                source="ntopng",
                source_record_id="dept-flow",
                created_at=now,
            )
        )

    headers = admin_headers(client)
    usage = client.get(
        f"/api/departments/{department_id}/usage?period=day&periods=1",
        headers=headers,
    )
    departments = client.get("/api/departments", headers=headers)

    assert usage.status_code == 200
    assert usage.json()["ingress_bytes"] == 700
    assert usage.json()["total_traffic_bytes"] == 700
    assert usage.json()["flow_bytes"] == 300
    assert usage.json()["flow_count"] == 1
    assert len(usage.json()["points"]) == 1
    assert any(item["id"] == str(department_id) for item in departments.json())


def test_department_crud_normalizes_codes_and_preserves_referenced_records(client):
    headers = admin_headers(client)
    created = client.post(
        "/api/departments",
        json={"code": "lab", "name": "ห้องปฏิบัติการ"},
        headers=headers,
    )
    department_id = created.json()["id"]
    duplicate = client.post(
        "/api/departments",
        json={"code": "LAB", "name": "แผนกซ้ำ"},
        headers=headers,
    )
    updated = client.put(
        f"/api/departments/{department_id}",
        json={"name": "ห้องปฏิบัติการกลาง"},
        headers=headers,
    )
    deleted = client.delete(
        f"/api/departments/{department_id}",
        headers=headers,
    )

    assert created.status_code == 201
    assert created.json()["code"] == "LAB"
    assert duplicate.status_code == 409
    assert updated.status_code == 200
    assert updated.json()["name"] == "ห้องปฏิบัติการกลาง"
    assert deleted.status_code == 204
