import asyncio
import ipaddress
from datetime import datetime, timezone
import json
import struct

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.collectors.demo import collect_demo_sample
from app.collectors.flow import NetFlowRecord, NetFlowV5Protocol, parse_netflow_v5
from app.collectors.ntopng import NtopngCollector
from app.collectors.snmpv3 import Snmpv3Collector
from app.collectors.syslog import parse_syslog_metadata
from app.collectors.zabbix import ZabbixCollector
from app.core.config import Settings
from app.database.base import Base
from app.models import (
    DeviceMetric,
    FlowRecord,
    MonitoredHost,
    NetworkAlert,
    NetworkDevice,
    NetworkLog,
    TrafficRecord,
)
from app.schemas.monitoring import (
    CollectorResult,
    DeviceStatusObservation,
    MetricObservation,
    TrafficObservation,
)
from app.workers.collector import (
    _collect_safely,
    _persist_ingest_event,
    persist_collector_result,
)


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite+pysqlite://",
        "jwt_secret_key": "test-only-secret-key-at-least-32-characters",
    }
    values.update(overrides)
    return Settings(**values)


def test_demo_collector_generates_labeled_idempotent_records():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    with Session(engine) as db:
        collect_demo_sample(db, now)
        collect_demo_sample(db, now)

        assert db.scalar(select(func.count()).select_from(NetworkDevice)) == 8
        assert db.scalar(select(func.count()).select_from(MonitoredHost)) == 4
        assert db.scalar(select(func.count()).select_from(TrafficRecord)) == 384
        assert db.scalar(select(func.count()).select_from(FlowRecord)) == 12
        assert db.scalar(select(func.count()).select_from(DeviceMetric)) == 16
        assert db.scalar(select(func.count()).select_from(NetworkAlert)) == 1
        assert db.scalar(
            select(NetworkDevice.source).limit(1)
        ) == "demo"

    engine.dispose()


def test_zabbix_collector_uses_read_only_methods_and_normalizes_measurements():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        if payload["method"] == "host.get":
            result = [
                {
                    "hostid": "101",
                    "status": "0",
                    "interfaces": [{"type": "2", "available": "1"}],
                }
            ]
        elif payload["method"] == "item.get":
            result = [
                {
                    "hostid": "101",
                    "itemid": "501",
                    "key_": "system.cpu.util[,idle]",
                    "lastvalue": "20.5",
                    "lastclock": "1767225600",
                },
                {
                    "hostid": "101",
                    "itemid": "502",
                    "key_": "vm.memory.size[pused]",
                    "lastvalue": "45",
                    "lastclock": "1767225600",
                },
            ]
        else:
            raise AssertionError(f"Unexpected Zabbix method: {payload['method']}")
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "result": result, "id": payload["id"]},
        )

    settings = build_settings(
        zabbix_api_url="https://zabbix.example.invalid",
        zabbix_api_token="read-only-token",
    )
    result = asyncio.run(
        ZabbixCollector(settings, transport=httpx.MockTransport(handler)).collect()
    )

    assert result.service_status == "available"
    assert result.devices[0].status == "online"
    assert {metric.metric_name for metric in result.metrics} == {
        "cpu_percent",
        "memory_percent",
    }
    assert [json.loads(request.content)["method"] for request in requests] == [
        "host.get",
        "item.get",
    ]
    assert all(request.headers["Authorization"] == "Bearer read-only-token" for request in requests)
    assert all(request.url.path == "/api_jsonrpc.php" for request in requests)


def test_ntopng_uses_counter_deltas_and_validates_host_metadata():
    interface_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal interface_calls
        if request.url.path.endswith("/interface/data.lua"):
            interface_calls += 1
            download = 1000 if interface_calls == 1 else 1750
            upload = 2000 if interface_calls == 1 else 2300
            return httpx.Response(
                200,
                json={
                    "rc": 0,
                    "rsp": {
                        "bytes_download": download,
                        "bytes_upload": upload,
                        "throughput": {
                            "download": {"bps": 8000},
                            "upload": {"bps": 3000},
                        },
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "rc": 0,
                "rsp": {
                    "data": [
                        {
                            "ip": "192.0.2.20",
                            "vlan": 30,
                            "name": "lab-host",
                            "first_seen": 1767225600,
                            "last_seen": 1767225660,
                        },
                        {"ip": "not-an-ip"},
                    ]
                },
            },
        )

    settings = build_settings(
        ntopng_api_url="https://ntopng.example.invalid",
        ntopng_username="collector",
        ntopng_password="server-only-password",
        ntopng_interface_id=3,
    )
    collector = NtopngCollector(settings, transport=httpx.MockTransport(handler))

    first = asyncio.run(collector.collect())
    second = asyncio.run(collector.collect())

    assert first.service_status == "available"
    assert first.traffic == []
    assert len(first.hosts) == 1
    assert first.hosts[0].source_host_id == "3:192.0.2.20@30"
    assert len(second.traffic) == 2
    traffic_by_direction = {sample.direction: sample for sample in second.traffic}
    assert traffic_by_direction["ingress"].bytes_transferred == 750
    assert traffic_by_direction["egress"].bytes_transferred == 300
    assert traffic_by_direction["ingress"].bit_rate_bps == 8000


def test_snmpv3_collector_reports_per_target_health_without_exposing_secrets():
    settings = build_settings(
        snmpv3_targets=json.dumps(
            [
                {
                    "ip_address": "192.0.2.10",
                    "username": "monitor",
                    "auth_key": "auth-secret-123",
                    "privacy_key": "privacy-secret-456",
                },
                {
                    "ip_address": "192.0.2.11",
                    "username": "monitor",
                    "auth_key": "auth-secret-123",
                    "privacy_key": "privacy-secret-456",
                },
            ]
        )
    )

    async def probe(target):
        assert target.auth_protocol == "SHA256"
        assert target.privacy_protocol == "AES128"
        if str(target.ip_address) == "192.0.2.11":
            raise TimeoutError("target did not answer")

    result = asyncio.run(Snmpv3Collector(settings, probe=probe).collect())

    assert result.service_status == "available"
    assert [item.status for item in result.devices] == ["online", "unavailable"]
    assert "auth-secret" not in repr(settings.snmpv3_targets)


def test_live_results_update_only_registered_devices_and_mark_stale_sources_unavailable():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    observed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with Session(engine) as db:
        zabbix_device = NetworkDevice(
            name="Zabbix switch",
            ip_address="192.0.2.10",
            device_type="switch",
            status="unknown",
            source="zabbix",
            source_device_id="101",
        )
        manual_device = NetworkDevice(
            name="Manual router",
            ip_address="192.0.2.11",
            device_type="router",
            status="online",
            source="manual",
        )
        db.add_all([zabbix_device, manual_device])
        db.commit()
        zabbix_device_id = zabbix_device.id

        result = CollectorResult(
            provider="zabbix",
            checked_at=observed_at,
            service_status="available",
            devices=[
                DeviceStatusObservation(
                    source_device_id="101",
                    status="online",
                    observed_at=observed_at,
                ),
                DeviceStatusObservation(
                    source_device_id="unregistered-host",
                    status="offline",
                    observed_at=observed_at,
                ),
            ],
            metrics=[
                MetricObservation(
                    source_device_id="101",
                    metric_name="cpu_percent",
                    value=35.5,
                    recorded_at=observed_at,
                    source_record_id="101:501:1",
                )
            ],
            traffic=[
                TrafficObservation(
                    direction="ingress",
                    interval_start=observed_at,
                    interval_end=observed_at,
                    bytes_transferred=500,
                    bit_rate_bps=4000,
                    source_record_id="zabbix:sample:1",
                )
            ],
        )
        persist_collector_result(db, result)

        assert db.get(NetworkDevice, zabbix_device_id).status == "online"
        assert db.scalar(select(func.count()).select_from(NetworkDevice)) == 2
        assert db.scalar(select(func.count()).select_from(DeviceMetric)) == 1
        assert db.scalar(select(func.count()).select_from(TrafficRecord)) == 1

        persist_collector_result(
            db,
            CollectorResult(
                provider="zabbix",
                checked_at=observed_at,
                service_status="unavailable",
            ),
        )
        assert db.get(NetworkDevice, zabbix_device_id).status == "unavailable"
        assert db.scalar(
            select(NetworkDevice.status).where(NetworkDevice.source == "manual")
        ) == "online"

    engine.dispose()


def test_netflow_v5_parser_extracts_only_flow_metadata_and_allowlists_exporter():
    header = struct.pack(
        "!HHIIIIBBH",
        5,
        1,
        100_000,
        1_767_225_700,
        0,
        42,
        0,
        0,
        0,
    )
    record = struct.pack(
        "!IIIHHIIIIHHBBBBHHBBH",
        int(ipaddress.IPv4Address("192.0.2.50")),
        int(ipaddress.IPv4Address("198.51.100.20")),
        0,
        1,
        2,
        25,
        1500,
        90_000,
        95_000,
        12345,
        443,
        0,
        0,
        6,
        0,
        0,
        0,
        24,
        24,
        0,
    )
    payload = header + record
    records = parse_netflow_v5(payload, "192.0.2.1")
    queue = asyncio.Queue()
    receiver = NetFlowV5Protocol(queue, {"192.0.2.1"})
    receiver.datagram_received(payload, ("192.0.2.1", 2055))
    rejected = NetFlowV5Protocol(queue, {"192.0.2.2"})
    rejected.datagram_received(payload, ("192.0.2.1", 2055))

    assert len(records) == 1
    assert records[0].protocol == "TCP"
    assert records[0].source_ip == "192.0.2.50"
    assert records[0].destination_port == 443
    assert records[0].bytes_transferred == 1500
    assert queue.qsize() == 1


def test_syslog_parser_discards_message_content():
    event = parse_syslog_metadata(
        b"<34>1 2026-01-01T00:00:00Z host app 7 ID47 - private text",
        "192.0.2.5",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert event.severity == "critical"
    assert event.event_type == "syslog.severity.2"
    assert "private text" not in event.summary
    assert event.exporter_ip == "192.0.2.5"


def test_flow_and_syslog_persistence_stores_metadata_only_and_deduplicates():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    flow = NetFlowRecord(
        exporter_ip="192.0.2.1",
        source_record_id="192.0.2.1:42:0",
        flow_start=timestamp,
        flow_end=timestamp,
        source_ip="192.0.2.50",
        destination_ip="198.51.100.20",
        source_port=12345,
        destination_port=443,
        protocol="TCP",
        bytes_transferred=1500,
        packets=25,
    )
    event = parse_syslog_metadata(
        b"<34>1 2026-01-01T00:00:00Z host app 7 ID47 - sensitive body",
        "192.0.2.1",
        timestamp,
    )

    _persist_ingest_event(factory, flow)
    _persist_ingest_event(factory, flow)
    _persist_ingest_event(factory, event)
    _persist_ingest_event(factory, event)

    with Session(engine) as db:
        stored_flow = db.scalar(select(FlowRecord))
        stored_log = db.scalar(select(NetworkLog))
        assert db.scalar(select(func.count()).select_from(FlowRecord)) == 1
        assert db.scalar(select(func.count()).select_from(NetworkLog)) == 1
        assert stored_flow is not None and stored_flow.bytes_transferred == 1500
        assert stored_log is not None
        assert "sensitive body" not in stored_log.summary

    engine.dispose()


def test_live_udp_collectors_require_exporter_allowlists():
    with pytest.raises(ValueError, match="NETFLOW_ALLOWED_EXPORTERS"):
        build_settings(netflow_v5_enabled=True)
    with pytest.raises(ValueError, match="SYSLOG_ALLOWED_EXPORTERS"):
        build_settings(syslog_enabled=True)


def test_invalid_snmp_configuration_does_not_log_credentials(caplog):
    settings = build_settings(
        snmpv3_targets=json.dumps(
            [
                {
                    "ip_address": "192.0.2.10",
                    "auth_key": "do-not-log-this-auth-key",
                    "privacy_key": "do-not-log-this-privacy-key",
                }
            ]
        )
    )
    result = asyncio.run(
        _collect_safely(
            Snmpv3Collector(settings).collect,
            "snmpv3",
        )
    )

    assert result.service_status == "unavailable"
    assert "do-not-log-this-auth-key" not in caplog.text
    assert "do-not-log-this-privacy-key" not in caplog.text
