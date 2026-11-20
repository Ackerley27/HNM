import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-at-least-32-characters")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.database.base import Base
from app.main import create_app
from app.models import User
from app.core.security import hash_password


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite://",
        jwt_secret_key="test-only-secret-key-at-least-32-characters",
        monitoring_mode="live",
        cors_origins=[],
    )
    application = create_app(settings=settings, engine=engine)
    with Session(engine) as db:
        db.add_all(
            [
                User(
                    email="admin@example.org",
                    password_hash=hash_password("correct horse battery staple"),
                    role="admin",
                ),
                User(
                    email="viewer@example.org",
                    password_hash=hash_password("viewer password 123"),
                    role="viewer",
                ),
                User(
                    email="disabled@example.org",
                    password_hash=hash_password("disabled password 123"),
                    role="viewer",
                    is_active=False,
                ),
            ]
        )
        db.commit()
    with TestClient(application) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)
    engine.dispose()
