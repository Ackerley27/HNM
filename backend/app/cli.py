import argparse
import getpass
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import AuditLog, User


def create_user(role: str, email: str) -> int:
    settings = get_settings()
    normalized_email = email.strip().lower()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12:
        print("Password must contain at least 12 characters.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with Session(engine) as db:
            if db.scalar(select(User.id).where(User.email == normalized_email)) is not None:
                print("A user with that email already exists.", file=sys.stderr)
                return 2
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.add(
                AuditLog(
                    actor_user_id=None,
                    action="user.create",
                    resource_type="user",
                    resource_id=user.id,
                    outcome="success",
                    metadata_json={"role": role},
                )
            )
            db.commit()
    finally:
        engine.dispose()
    print(f"Created {role} account for {normalized_email}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Hospital network monitor administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    user_parser = subparsers.add_parser("create-user")
    user_parser.add_argument("--email", required=True)
    user_parser.add_argument("--role", choices=("admin", "viewer"), required=True)
    args = parser.parse_args()
    if args.command == "create-user":
        return create_user(args.role, args.email)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
