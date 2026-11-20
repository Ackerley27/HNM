from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import RevokedToken, User

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_minutes)
    claims = {
        "sub": str(user.id),
        "jti": str(uuid4()),
        "iat": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(
        claims,
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any] | None:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]},
        )
    except jwt.InvalidTokenError:
        return None
    if not isinstance(claims.get("jti"), str):
        return None
    return claims


def revoke_access_token(db: Session, claims: dict[str, Any]) -> None:
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    db.add(RevokedToken(jti=claims["jti"], expires_at=expires_at))
    db.commit()
