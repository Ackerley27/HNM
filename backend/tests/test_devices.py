from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@example.org",
            "password": "correct horse battery staple",
        },
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_manage_device_inventory_and_audit_changes(client):
    headers = admin_headers(client)
    department = client.post(
        "/api/departments",
        json={"code": "it", "name": "สารสนเทศ"},
        headers=headers,
    )
    created = client.post(
        "/api/devices",
        json={
            "name": "Core switch",
            "hostname": "core-switch.example.invalid",
            "ip_address": "192.0.2.90",
            "device_type": "switch",
            "department_id": department.json()["id"],
        },
        headers=headers,
    )

    assert department.status_code == 201
    assert department.json()["code"] == "IT"
    assert created.status_code == 201
    assert created.json()["status"] == "unknown"
    assert created.json()["source"] == "manual"
    assert created.json()["department_name"] == "สารสนเทศ"

    device_id = created.json()["id"]
    duplicate = client.post(
        "/api/devices",
        json={
            "name": "Duplicate switch",
            "ip_address": "192.0.2.90",
            "device_type": "switch",
        },
        headers=headers,
    )
    updated = client.put(
        f"/api/devices/{device_id}",
        json={"name": "Updated core switch", "monitoring_enabled": False},
        headers=headers,
    )
    filtered = client.get(
        "/api/devices?search=Updated%20core",
        headers=headers,
    )
    deleted = client.delete(f"/api/devices/{device_id}", headers=headers)

    assert duplicate.status_code == 409
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated core switch"
    assert updated.json()["monitoring_enabled"] is False
    assert len(filtered.json()) == 1
    assert deleted.status_code == 204
    with Session(client.app.state.database_engine) as db:
        actions = set(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.action.in_(
                        ["device.create", "device.update", "device.delete"]
                    )
                )
            ).all()
        )
    assert actions == {"device.create", "device.update", "device.delete"}


def test_device_mutations_are_admin_only_and_demo_inventory_is_scoped(client):
    viewer_response = client.post(
        "/api/auth/login",
        json={
            "email": "viewer@example.org",
            "password": "viewer password 123",
        },
    )
    viewer_headers = {
        "Authorization": f"Bearer {viewer_response.json()['access_token']}"
    }
    forbidden = client.post(
        "/api/devices",
        json={
            "name": "Viewer device",
            "ip_address": "192.0.2.91",
            "device_type": "router",
        },
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    headers = admin_headers(client)
    client.app.state.settings.monitoring_mode = "demo"
    demo_device = client.post(
        "/api/devices",
        json={
            "name": "Demo device",
            "ip_address": "192.0.2.92",
            "device_type": "router",
        },
        headers=headers,
    )
    devices = client.get("/api/devices", headers=headers)

    assert demo_device.status_code == 201
    assert demo_device.json()["source"] == "demo"
    assert [device["id"] for device in devices.json()] == [
        demo_device.json()["id"]
    ]
