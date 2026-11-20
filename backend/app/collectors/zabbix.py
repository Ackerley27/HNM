from datetime import datetime, timezone
import math
from typing import Any

import httpx

from app.core.config import Settings
from app.database.base import utc_now
from app.schemas.monitoring import (
    CollectorResult,
    DeviceStatusObservation,
    MetricObservation,
)


class ZabbixCollector:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self._request_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.zabbix_api_url and self.settings.zabbix_api_token)

    async def collect(self) -> CollectorResult:
        if not self.is_configured:
            return CollectorResult(
                provider="zabbix",
                checked_at=utc_now(),
                service_status="unavailable",
                configured=False,
                message="Zabbix API URL or read-only API token is not configured",
            )

        assert self.settings.zabbix_api_url is not None
        assert self.settings.zabbix_api_token is not None
        url = self.settings.zabbix_api_url.rstrip("/")
        if not url.endswith("/api_jsonrpc.php"):
            url = f"{url}/api_jsonrpc.php"
        headers = {
            "Authorization": f"Bearer {self.settings.zabbix_api_token.get_secret_value()}",
            "Content-Type": "application/json-rpc",
        }

        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            hosts = await self._rpc(
                client,
                url,
                headers,
                "host.get",
                {
                    "output": ["hostid", "host", "name", "status"],
                    "selectInterfaces": [
                        "interfaceid",
                        "ip",
                        "type",
                        "available",
                        "main",
                    ],
                },
            )
            if not isinstance(hosts, list):
                raise ValueError("Zabbix host.get result must be a list")

            host_ids = [
                str(host["hostid"])
                for host in hosts
                if isinstance(host, dict) and host.get("hostid") is not None
            ]
            items: list[Any] = []
            if host_ids:
                result = await self._rpc(
                    client,
                    url,
                    headers,
                    "item.get",
                    {
                        "hostids": host_ids,
                        "output": [
                            "itemid",
                            "hostid",
                            "key_",
                            "lastvalue",
                            "lastclock",
                        ],
                        "filter": {"status": "0"},
                        "limit": 5000,
                    },
                )
                if not isinstance(result, list):
                    raise ValueError("Zabbix item.get result must be a list")
                items = result

        checked_at = utc_now()
        device_observations: list[DeviceStatusObservation] = []
        for host in hosts:
            if not isinstance(host, dict) or host.get("hostid") is None:
                continue
            if str(host.get("status", "0")) != "0":
                device_observations.append(
                    DeviceStatusObservation(
                        source_device_id=str(host["hostid"]),
                        status="unknown",
                        observed_at=checked_at,
                    )
                )
                continue
            interfaces = host.get("interfaces") or []
            available_values = {
                str(interface.get("available", "0"))
                for interface in interfaces
                if isinstance(interface, dict) and str(interface.get("type")) in {"1", "2"}
            }
            if "1" in available_values:
                status = "online"
            elif "2" in available_values:
                status = "offline"
            else:
                status = "unknown"
            device_observations.append(
                DeviceStatusObservation(
                    source_device_id=str(host["hostid"]),
                    status=status,
                    observed_at=checked_at,
                )
            )

        metrics: list[MetricObservation] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key_", ""))
            if key == "system.cpu.util" or key.startswith("system.cpu.util["):
                metric_name = "cpu_percent"
            elif key == "vm.memory.size[pused]":
                metric_name = "memory_percent"
            else:
                continue

            try:
                value = float(item["lastvalue"])
                timestamp = datetime.fromtimestamp(
                    int(item["lastclock"]), tz=timezone.utc
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(value) or not 0 <= value <= 100:
                continue
            if item.get("hostid") is None or item.get("itemid") is None:
                continue
            metrics.append(
                MetricObservation(
                    source_device_id=str(item["hostid"]),
                    metric_name=metric_name,
                    value=value,
                    recorded_at=timestamp,
                    source_record_id=(
                        f"{item['hostid']}:{item['itemid']}:{item['lastclock']}"
                    ),
                )
            )

        return CollectorResult(
            provider="zabbix",
            checked_at=checked_at,
            service_status="available",
            devices=device_observations,
            metrics=metrics,
        )

    async def _rpc(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        method: str,
        params: dict[str, Any],
    ) -> Any:
        self._request_id += 1
        response = await client.post(
            url,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": self._request_id,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Zabbix JSON-RPC response must be an object")
        if payload.get("error"):
            error = payload["error"]
            message = error.get("message", "Zabbix JSON-RPC request failed")
            data = error.get("data")
            raise ValueError(f"{message}: {data}" if data else message)
        if "result" not in payload:
            raise ValueError("Zabbix JSON-RPC response is missing result")
        return payload["result"]
