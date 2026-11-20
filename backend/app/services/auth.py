from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User

_DUMMY_PASSWORD_HASH = hash_password("unusable-dummy-password")


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    password_matches = verify_password(password, user.password_hash)
    if not user.is_active or not password_matches:
        return None
    return user
