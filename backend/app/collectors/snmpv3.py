import asyncio
from collections.abc import Awaitable, Callable
import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, SecretStr

from app.core.config import Settings
from app.database.base import utc_now
from app.schemas.monitoring import CollectorResult, DeviceStatusObservation

logger = logging.getLogger(__name__)


class Snmpv3Target(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ip_address: IPvAnyAddress
    username: str = Field(min_length=1, max_length=32)
    auth_key: SecretStr = Field(min_length=8)
    privacy_key: SecretStr = Field(min_length=8)
    auth_protocol: Literal["SHA256", "SHA1"] = "SHA256"
    privacy_protocol: Literal["AES128"] = "AES128"
    port: int = Field(default=161, ge=1, le=65535)


Probe = Callable[[Snmpv3Target], Awaitable[None]]


class Snmpv3Collector:
    def __init__(
        self,
        settings: Settings,
        probe: Probe | None = None,
    ) -> None:
        self.settings = settings
        self.probe = probe or self._probe

    async def collect(self) -> CollectorResult:
        if self.settings.snmpv3_targets is None:
            return CollectorResult(
                provider="snmpv3",
                checked_at=utc_now(),
                service_status="unavailable",
                configured=False,
                message="SNMPv3 targets are not configured",
            )

        try:
            target_data = json.loads(
                self.settings.snmpv3_targets.get_secret_value()
            )
        except json.JSONDecodeError as error:
            raise ValueError("SNMPV3_TARGETS must contain a JSON array") from error
        if not isinstance(target_data, list):
            raise ValueError("SNMPV3_TARGETS must contain a JSON array")
        if len(target_data) > 256:
            raise ValueError("SNMPV3_TARGETS may contain at most 256 targets")
        targets = [Snmpv3Target.model_validate(target) for target in target_data]
        if not targets:
            return CollectorResult(
                provider="snmpv3",
                checked_at=utc_now(),
                service_status="unavailable",
                configured=False,
                message="No SNMPv3 targets are configured",
            )

        checked_at = utc_now()
        observations: list[DeviceStatusObservation] = []
        successes = 0
        for target in targets:
            try:
                await self.probe(target)
                status = "online"
                successes += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("SNMPv3 probe failed for %s", target.ip_address)
                status = "unavailable"
            observations.append(
                DeviceStatusObservation(
                    ip_address=target.ip_address,
                    status=status,
                    observed_at=checked_at,
                )
            )

        return CollectorResult(
            provider="snmpv3",
            checked_at=checked_at,
            service_status="available" if successes else "unavailable",
            message=(
                None
                if successes == len(targets)
                else f"SNMPv3 responded from {successes} of {len(targets)} targets"
            ),
            devices=observations,
        )

    @staticmethod
    async def _probe(target: Snmpv3Target) -> None:
        from pysnmp.hlapi.v3arch.asyncio import (
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            Udp6TransportTarget,
            UsmUserData,
            get_cmd,
            usmAesCfb128Protocol,
            usmHMAC192SHA256AuthProtocol,
            usmHMACSHAAuthProtocol,
        )

        engine = SnmpEngine()
        try:
            target_class = (
                Udp6TransportTarget
                if target.ip_address.version == 6
                else UdpTransportTarget
            )
            transport = await target_class.create(
                (str(target.ip_address), target.port),
                timeout=2,
                retries=0,
            )
            response = await get_cmd(
                engine,
                UsmUserData(
                    target.username,
                    authKey=target.auth_key.get_secret_value(),
                    privKey=target.privacy_key.get_secret_value(),
                    authProtocol=(
                        usmHMAC192SHA256AuthProtocol
                        if target.auth_protocol == "SHA256"
                        else usmHMACSHAAuthProtocol
                    ),
                    privProtocol=usmAesCfb128Protocol,
                ),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),
            )
            error_indication, error_status, _, _ = response
            if error_indication or error_status:
                raise RuntimeError("SNMPv3 read-only GET failed")
        finally:
            engine.close_dispatcher()
