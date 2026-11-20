from functools import lru_cache
import ipaddress
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    jwt_secret_key: SecretStr = Field(min_length=32)
    monitoring_mode: Literal["demo", "live"] = "demo"
    collector_interval_seconds: int = Field(default=60, ge=10, le=3600)
    zabbix_api_url: str | None = None
    zabbix_api_token: SecretStr | None = None
    ntopng_api_url: str | None = None
    ntopng_username: str | None = None
    ntopng_password: SecretStr | None = None
    ntopng_interface_id: int = Field(default=0, ge=0)
    snmpv3_targets: SecretStr | None = None
    netflow_v5_enabled: bool = False
    netflow_v5_host: str = "127.0.0.1"
    netflow_v5_port: int = Field(default=2055, ge=1, le=65535)
    netflow_allowed_exporters: list[str] = Field(default_factory=list)
    syslog_enabled: bool = False
    syslog_host: str = "127.0.0.1"
    syslog_port: int = Field(default=5514, ge=1, le=65535)
    syslog_allowed_exporters: list[str] = Field(default_factory=list)
    jwt_access_token_minutes: int = Field(default=20, ge=1, le=1440)
    cors_origins: list[str] = Field(default_factory=list)
    jwt_issuer: str = "hospital-network-monitor"
    jwt_audience: str = "hospital-network-monitor-api"

    @model_validator(mode="after")
    def validate_udp_collectors(self) -> "Settings":
        if self.netflow_v5_enabled and not self.netflow_allowed_exporters:
            raise ValueError("NETFLOW_ALLOWED_EXPORTERS is required when NetFlow is enabled")
        if self.syslog_enabled and not self.syslog_allowed_exporters:
            raise ValueError("SYSLOG_ALLOWED_EXPORTERS is required when syslog is enabled")
        for address in self.netflow_allowed_exporters + self.syslog_allowed_exporters:
            ipaddress.ip_address(address)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
