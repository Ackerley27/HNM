from datetime import datetime, timezone
import ipaddress
import logging
import math
from typing import Any

import httpx

from app.core.config import Settings
from app.database.base import utc_now
from app.schemas.monitoring import (
    CollectorResult,
    HostObservation,
    TrafficObservation,
)

logger = logging.getLogger(__name__)


class NtopngCollector:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self._last_counters: dict[int, tuple[int, int, datetime]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.ntopng_api_url
            and self.settings.ntopng_username
            and self.settings.ntopng_password
        )

    async def collect(self) -> CollectorResult:
        if not self.is_configured:
            return CollectorResult(
                provider="ntopng",
                checked_at=utc_now(),
                service_status="unavailable",
                configured=False,
                message="ntopng API URL or read-only account is not configured",
            )

        assert self.settings.ntopng_api_url is not None
        assert self.settings.ntopng_username is not None
        assert self.settings.ntopng_password is not None
        base_url = self.settings.ntopng_api_url.rstrip("/")
        auth = (
            self.settings.ntopng_username,
            self.settings.ntopng_password.get_secret_value(),
        )
        interface_id = self.settings.ntopng_interface_id

        async with httpx.AsyncClient(
            transport=self.transport,
            auth=auth,
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            interface_data = await self._get(
                client,
                f"{base_url}/lua/rest/v2/get/interface/data.lua",
                {"ifid": interface_id},
            )

            checked_at = utc_now()
            hosts: list[HostObservation] = []
            try:
                host_data = await self._get(
                    client,
                    f"{base_url}/lua/rest/v2/get/host/active.lua",
                    {"ifid": interface_id},
                )
                hosts = self._parse_hosts(host_data, interface_id, checked_at)
            except (httpx.HTTPError, ValueError) as error:
                logger.warning("ntopng active-host collection failed: %s", error)

        rsp = interface_data.get("rsp")
        if not isinstance(rsp, dict):
            raise ValueError("ntopng interface response is missing rsp data")
        traffic = self._parse_traffic(rsp, interface_id, checked_at)
        return CollectorResult(
            provider="ntopng",
            checked_at=checked_at,
            service_status="available",
            traffic=traffic,
            hosts=hosts,
        )

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, int],
    ) -> dict[str, Any]:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("ntopng response must be an object")
        if payload.get("rc") != 0:
            raise ValueError("ntopng returned a non-zero response code")
        return payload

    def _parse_traffic(
        self, response: dict[str, Any], interface_id: int, checked_at: datetime
    ) -> list[TrafficObservation]:
        counters = (
            _nonnegative_int(response.get("bytes_download")),
            _nonnegative_int(response.get("bytes_upload")),
        )
        previous = self._last_counters.get(interface_id)
        self._last_counters[interface_id] = (
            counters[0],
            counters[1],
            checked_at,
        )
        if previous is None:
            return []

        start = previous[2]
        if checked_at <= start:
            return []
        throughput = response.get("throughput")
        if not isinstance(throughput, dict):
            throughput = {}

        observations: list[TrafficObservation] = []
        for key, direction, counter_index in (
            ("download", "ingress", 0),
            ("upload", "egress", 1),
        ):
            delta = counters[counter_index] - previous[counter_index]
            if delta < 0:
                continue
            rate_data = throughput.get(key)
            rate = (
                _nonnegative_int(rate_data.get("bps"))
                if isinstance(rate_data, dict)
                else None
            )
            observations.append(
                TrafficObservation(
                    direction=direction,
                    interval_start=start,
                    interval_end=checked_at,
                    bytes_transferred=delta,
                    bit_rate_bps=rate,
                    source_record_id=(
                        f"interface-{interface_id}-{int(checked_at.timestamp())}-{direction}"
                    ),
                )
            )
        return observations

    @staticmethod
    def _parse_hosts(
        payload: dict[str, Any], interface_id: int, checked_at: datetime
    ) -> list[HostObservation]:
        rsp = payload.get("rsp")
        rows = rsp.get("data") if isinstance(rsp, dict) else None
        if not isinstance(rows, list):
            raise ValueError("ntopng active-host response is missing rsp.data")

        hosts: list[HostObservation] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                address = str(ipaddress.ip_address(row["ip"]))
            except (KeyError, TypeError, ValueError):
                continue

            first_seen = _epoch_datetime(row.get("first_seen")) or checked_at
            last_seen = _epoch_datetime(row.get("last_seen")) or checked_at
            if last_seen < first_seen:
                first_seen = last_seen
            vlan = row.get("vlan")
            hostname = row.get("name")
            if not isinstance(hostname, str) or hostname in {"", "0"}:
                hostname = None
            hosts.append(
                HostObservation(
                    source_host_id=f"{interface_id}:{address}@{vlan or 0}",
                    ip_address=address,
                    hostname=hostname,
                    first_seen_at=first_seen,
                    last_seen_at=last_seen,
                )
            )
        return hosts


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("ntopng numeric field must not be a boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("ntopng numeric field is invalid") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError("ntopng numeric field is out of range")
    return int(number)


def _epoch_datetime(value: Any) -> datetime | None:
    try:
        epoch = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(epoch) or epoch < 0:
        return None
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
