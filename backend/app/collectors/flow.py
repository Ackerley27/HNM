import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import logging
import socket
import struct
from typing import Any

logger = logging.getLogger(__name__)
NETFLOW_V5_HEADER_SIZE = 24
NETFLOW_V5_RECORD_SIZE = 48
NETFLOW_V5_MAX_RECORDS = 30


@dataclass(frozen=True)
class NetFlowRecord:
    exporter_ip: str
    source_record_id: str
    flow_start: datetime
    flow_end: datetime
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    protocol: str
    bytes_transferred: int
    packets: int


def parse_netflow_v5(payload: bytes, exporter_ip: str) -> list[NetFlowRecord]:
    if len(payload) < NETFLOW_V5_HEADER_SIZE or len(payload) > 1500:
        raise ValueError("Invalid NetFlow v5 datagram size")
    (
        version,
        count,
        system_uptime_ms,
        unix_seconds,
        _,
        sequence,
        _,
        _,
        _,
    ) = struct.unpack_from("!HHIIIIBBH", payload)
    if version != 5 or not 1 <= count <= NETFLOW_V5_MAX_RECORDS:
        raise ValueError("Unsupported NetFlow datagram version or record count")
    expected_size = NETFLOW_V5_HEADER_SIZE + count * NETFLOW_V5_RECORD_SIZE
    if len(payload) != expected_size:
        raise ValueError("NetFlow v5 datagram length does not match its record count")

    exporter = str(ipaddress.ip_address(exporter_ip))
    records: list[NetFlowRecord] = []
    for index in range(count):
        offset = NETFLOW_V5_HEADER_SIZE + index * NETFLOW_V5_RECORD_SIZE
        source_address, destination_address = struct.unpack_from(
            "!II", payload, offset
        )
        packets, octets, first_uptime_ms, last_uptime_ms = struct.unpack_from(
            "!IIII", payload, offset + 16
        )
        source_port, destination_port = struct.unpack_from(
            "!HH", payload, offset + 32
        )
        protocol_number = payload[offset + 38]

        flow_end_epoch = unix_seconds - max(system_uptime_ms - last_uptime_ms, 0) / 1000
        flow_start_epoch = unix_seconds - max(system_uptime_ms - first_uptime_ms, 0) / 1000
        flow_end = datetime.fromtimestamp(flow_end_epoch, timezone.utc)
        flow_start = min(datetime.fromtimestamp(flow_start_epoch, timezone.utc), flow_end)
        protocol = {
            1: "ICMP",
            6: "TCP",
            17: "UDP",
        }.get(protocol_number, f"IP-{protocol_number}")

        records.append(
            NetFlowRecord(
                exporter_ip=exporter,
                source_record_id=f"{exporter}:{sequence}:{unix_seconds}:{index}",
                flow_start=flow_start,
                flow_end=flow_end,
                source_ip=socket.inet_ntoa(struct.pack("!I", source_address)),
                destination_ip=socket.inet_ntoa(struct.pack("!I", destination_address)),
                source_port=source_port,
                destination_port=destination_port,
                protocol=protocol,
                bytes_transferred=octets,
                packets=packets,
            )
        )
    return records


class NetFlowV5Protocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        queue: asyncio.Queue[Any],
        allowed_exporters: set[str],
    ) -> None:
        self.queue = queue
        self.allowed_exporters = allowed_exporters
        self._rejected_exporters = 0
        self._dropped_records = 0

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        exporter = str(ipaddress.ip_address(addr[0]))
        if exporter not in self.allowed_exporters:
            self._rejected_exporters += 1
            if self._rejected_exporters == 1 or self._rejected_exporters % 100 == 0:
                logger.warning(
                    "Dropped NetFlow datagrams from unapproved exporters (count=%s)",
                    self._rejected_exporters,
                )
            return
        try:
            records = parse_netflow_v5(data, exporter)
        except (ValueError, OSError, OverflowError, struct.error):
            logger.warning("Dropped invalid NetFlow v5 datagram from %s", exporter)
            return
        for record in records:
            try:
                self.queue.put_nowait(record)
            except asyncio.QueueFull:
                self._dropped_records += 1
                if self._dropped_records == 1 or self._dropped_records % 100 == 0:
                    logger.warning(
                        "NetFlow ingestion queue is full (dropped=%s)",
                        self._dropped_records,
                    )
