from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.types import TypeDecorator


class InetAddress(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(INET())
        return dialect.type_descriptor(String(45))


class CidrNetwork(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect: Any):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CIDR())
        return dialect.type_descriptor(String(64))
