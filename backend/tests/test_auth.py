from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def login(client, email="admin@example.org", password="correct horse battery staple"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def test_login_and_me_return_only_public_user_fields(client):
    response = login(client)
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.org"
    assert me.json()["role"] == "admin"
    assert "password_hash" not in me.json()


def test_invalid_and_inactive_accounts_cannot_login(client):
    wrong_password = login(client, password="wrong password")
    inactive = login(client, "disabled@example.org", "disabled password 123")

    assert wrong_password.status_code == 401
    assert inactive.status_code == 401
    assert wrong_password.json() == inactive.json()


def test_logout_revokes_the_access_token(client):
    token = login(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/auth/logout", headers=headers)
    after_logout = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 204
    assert after_logout.status_code == 401


def test_malformed_and_missing_tokens_are_rejected(client):
    malformed = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    missing = client.get("/api/auth/me")
    assert malformed.status_code == 401
    assert missing.status_code == 401


def test_admin_can_create_user_and_action_is_audited(client):
    admin_token = login(client).json()["access_token"]
    response = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "new.viewer@example.org",
            "password": "a sufficiently long password",
            "role": "viewer",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "viewer"
    with Session(client.app.state.database_engine) as db:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "user.create",
                AuditLog.resource_id == UUID(response.json()["id"]),
            )
        )
    assert audit is not None
    assert audit.metadata_json == {"role": "viewer"}


def test_viewer_cannot_create_users(client):
    viewer_token = login(
        client, "viewer@example.org", "viewer password 123"
    ).json()["access_token"]
    response = client.post(
        "/api/auth/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={
            "email": "forbidden@example.org",
            "password": "a sufficiently long password",
            "role": "admin",
        },
    )
    assert response.status_code == 403
