import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)
PRI_PATTERN = re.compile(rb"^<(\d{1,3})>")
SYSLOG_SEVERITIES = ("critical", "critical", "critical", "critical", "warning", "info", "info", "info")


@dataclass(frozen=True)
class SyslogEvent:
    exporter_ip: str
    source_event_id: str
    event_type: str
    severity: str
    summary: str
    occurred_at: datetime
    received_at: datetime


def parse_syslog_metadata(
    payload: bytes,
    exporter_ip: str,
    received_at: datetime | None = None,
) -> SyslogEvent:
    if len(payload) > 8192:
        raise ValueError("Syslog datagram exceeds the configured maximum size")
    match = PRI_PATTERN.match(payload[:8])
    if match is None:
        raise ValueError("Syslog datagram is missing a valid priority header")
    priority = int(match.group(1))
    if priority > 191:
        raise ValueError("Syslog priority is out of range")

    received_at = received_at or datetime.now(timezone.utc)
    exporter = str(ipaddress.ip_address(exporter_ip))
    severity_code = priority % 8
    return SyslogEvent(
        exporter_ip=exporter,
        source_event_id=f"{exporter}:{priority}:{int(received_at.timestamp())}",
        event_type=f"syslog.severity.{severity_code}",
        severity=SYSLOG_SEVERITIES[severity_code],
        summary="Syslog event received; message content omitted",
        occurred_at=received_at,
        received_at=received_at,
    )


class SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        queue: asyncio.Queue[Any],
        allowed_exporters: set[str],
    ) -> None:
        self.queue = queue
        self.allowed_exporters = allowed_exporters
        self._rejected_exporters = 0
        self._dropped_events = 0

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        exporter = str(ipaddress.ip_address(addr[0]))
        if exporter not in self.allowed_exporters:
            self._rejected_exporters += 1
            if self._rejected_exporters == 1 or self._rejected_exporters % 100 == 0:
                logger.warning(
                    "Dropped syslog datagrams from unapproved exporters (count=%s)",
                    self._rejected_exporters,
                )
            return
        try:
            event = parse_syslog_metadata(data, exporter)
        except ValueError:
            logger.warning("Dropped invalid syslog datagram from %s", exporter)
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped_events += 1
            if self._dropped_events == 1 or self._dropped_events % 100 == 0:
                logger.warning(
                    "Syslog ingestion queue is full (dropped=%s)",
                    self._dropped_events,
                )
