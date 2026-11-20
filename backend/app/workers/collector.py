import asyncio
import ipaddress
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.collectors.demo import collect_demo_sample
from app.collectors.flow import NetFlowRecord, NetFlowV5Protocol
from app.collectors.ntopng import NtopngCollector
from app.collectors.snmpv3 import Snmpv3Collector
from app.collectors.syslog import SyslogEvent, SyslogProtocol
from app.collectors.zabbix import ZabbixCollector
from app.core.config import Settings
from app.models import (
    DeviceMetric,
    FlowRecord,
    MonitoredHost,
    MonitoringSetting,
    NetworkDevice,
    NetworkLog,
    TrafficRecord,
)
from app.schemas.monitoring import CollectorResult
from app.services.alerts import evaluate_live_alerts

logger = logging.getLogger(__name__)
IngestEvent = NetFlowRecord | SyslogEvent


def persist_collector_result(db: Session, result: CollectorResult) -> None:
    setting = db.scalar(
        select(MonitoringSetting).where(
            MonitoringSetting.provider == result.provider,
            MonitoringSetting.setting_key == "collector",
        )
    )
    if setting is None:
        setting = MonitoringSetting(provider=result.provider, setting_key="collector")
        db.add(setting)
    setting.setting_value = (
        {"message": result.message} if result.message else {}
    )
    setting.enabled = result.configured
    setting.service_status = result.service_status
    setting.last_checked_at = result.checked_at

    if result.service_status == "unavailable":
        devices = db.scalars(
            select(NetworkDevice).where(
                NetworkDevice.source == result.provider,
                NetworkDevice.monitoring_enabled.is_(True),
            )
        ).all()
        for device in devices:
            device.status = "unavailable"

    for observation in result.devices:
        statement = select(NetworkDevice).where(NetworkDevice.monitoring_enabled.is_(True))
        if observation.source_device_id is not None:
            statement = statement.where(
                NetworkDevice.source == result.provider,
                NetworkDevice.source_device_id == observation.source_device_id,
            )
        else:
            statement = statement.where(
                NetworkDevice.ip_address == str(observation.ip_address)
            )
        device = db.scalar(statement)
        if device is None:
            continue
        device.status = observation.status
        if observation.status == "online":
            device.last_seen_at = observation.observed_at

    for metric in result.metrics:
        device = db.scalar(
            select(NetworkDevice).where(
                NetworkDevice.source == result.provider,
                NetworkDevice.source_device_id == metric.source_device_id,
                NetworkDevice.monitoring_enabled.is_(True),
            )
        )
        if device is None:
            continue
        exists = db.scalar(
            select(DeviceMetric.id).where(
                DeviceMetric.source == result.provider,
                DeviceMetric.source_record_id == metric.source_record_id,
            )
        )
        if exists is None:
            db.add(
                DeviceMetric(
                    device_id=device.id,
                    metric_name=metric.metric_name,
                    value=metric.value,
                    unit=metric.unit,
                    recorded_at=metric.recorded_at,
                    source=result.provider,
                    source_record_id=metric.source_record_id,
                )
            )

    for traffic in result.traffic:
        exists = db.scalar(
            select(TrafficRecord.id).where(
                TrafficRecord.source == result.provider,
                TrafficRecord.source_record_id == traffic.source_record_id,
            )
        )
        if exists is None:
            db.add(
                TrafficRecord(
                    interval_start=traffic.interval_start,
                    interval_end=traffic.interval_end,
                    direction=traffic.direction,
                    bytes_transferred=traffic.bytes_transferred,
                    bit_rate_bps=traffic.bit_rate_bps,
                    source=result.provider,
                    source_record_id=traffic.source_record_id,
                )
            )

    for host_observation in result.hosts:
        host = db.scalar(
            select(MonitoredHost).where(
                MonitoredHost.source == result.provider,
                MonitoredHost.source_host_id == host_observation.source_host_id,
            )
        )
        if host is None:
            db.add(
                MonitoredHost(
                    ip_address=str(host_observation.ip_address),
                    hostname=host_observation.hostname,
                    source=result.provider,
                    source_host_id=host_observation.source_host_id,
                    first_seen_at=host_observation.first_seen_at,
                    last_seen_at=host_observation.last_seen_at,
                )
            )
        else:
            host.ip_address = str(host_observation.ip_address)
            host.hostname = host_observation.hostname
            host.last_seen_at = host_observation.last_seen_at

    db.commit()


async def run_collector_worker(
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    zabbix = ZabbixCollector(settings)
    ntopng = NtopngCollector(settings)
    snmpv3 = Snmpv3Collector(settings)
    ingest_queue: asyncio.Queue[IngestEvent] = asyncio.Queue(maxsize=512)
    ingest_task: asyncio.Task[None] | None = None
    transports: list[asyncio.BaseTransport] = []
    try:
        if settings.monitoring_mode == "live":
            ingest_task = asyncio.create_task(
                _run_ingest_queue(ingest_queue, session_factory)
            )
            transports.extend(
                await _start_udp_receivers(settings, session_factory, ingest_queue)
            )
        while True:
            try:
                if settings.monitoring_mode == "demo":
                    await asyncio.to_thread(_collect_demo, session_factory)
                else:
                    results = await asyncio.gather(
                        _collect_safely(zabbix.collect, "zabbix"),
                        _collect_safely(ntopng.collect, "ntopng"),
                        _collect_safely(snmpv3.collect, "snmpv3"),
                    )
                    await asyncio.to_thread(
                        _persist_results, session_factory, results
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Network data collection cycle failed")
            await asyncio.sleep(settings.collector_interval_seconds)
    finally:
        for transport in transports:
            transport.close()
        if ingest_task is not None:
            ingest_task.cancel()
            await asyncio.gather(ingest_task, return_exceptions=True)


async def _start_udp_receivers(
    settings: Settings,
    session_factory: sessionmaker[Session],
    queue: asyncio.Queue[IngestEvent],
) -> list[asyncio.BaseTransport]:
    loop = asyncio.get_running_loop()
    transports: list[asyncio.BaseTransport] = []
    receiver_configs = (
        (
            "netflow_v5",
            settings.netflow_v5_enabled,
            settings.netflow_v5_host,
            settings.netflow_v5_port,
            settings.netflow_allowed_exporters,
            NetFlowV5Protocol,
        ),
        (
            "syslog",
            settings.syslog_enabled,
            settings.syslog_host,
            settings.syslog_port,
            settings.syslog_allowed_exporters,
            SyslogProtocol,
        ),
    )
    for provider, enabled, host, port, exporters, protocol_class in receiver_configs:
        if not enabled:
            await asyncio.to_thread(
                _record_listener_status,
                session_factory,
                provider,
                False,
                "unavailable",
            )
            continue
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda protocol_class=protocol_class, exporters=exporters: protocol_class(
                    queue,
                    {str(ipaddress.ip_address(item)) for item in exporters},
                ),
                local_addr=(host, port),
            )
        except OSError:
            logger.exception("%s UDP listener could not bind to %s:%s", provider, host, port)
            await asyncio.to_thread(
                _record_listener_status,
                session_factory,
                provider,
                True,
                "unavailable",
            )
            continue
        transports.append(transport)
        await asyncio.to_thread(
            _record_listener_status,
            session_factory,
            provider,
            True,
            "available",
        )
    return transports


def _set_listener_status(
    session_factory: sessionmaker[Session],
    provider: str,
    enabled: bool,
    status: str,
) -> None:
    with session_factory() as db:
        setting = db.scalar(
            select(MonitoringSetting).where(
                MonitoringSetting.provider == provider,
                MonitoringSetting.setting_key == "collector",
            )
        )
        if setting is None:
            setting = MonitoringSetting(provider=provider, setting_key="collector")
            db.add(setting)
        setting.setting_value = {}
        setting.enabled = enabled
        setting.service_status = status
        setting.last_checked_at = datetime.now(timezone.utc)
        db.commit()


def _record_listener_status(
    session_factory: sessionmaker[Session],
    provider: str,
    enabled: bool,
    status: str,
) -> None:
    try:
        _set_listener_status(session_factory, provider, enabled, status)
    except Exception:
        logger.exception("Could not persist %s listener health", provider)


async def _run_ingest_queue(
    queue: asyncio.Queue[IngestEvent],
    session_factory: sessionmaker[Session],
) -> None:
    while True:
        event = await queue.get()
        try:
            await asyncio.to_thread(_persist_ingest_event, session_factory, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Metadata ingestion persistence failed")
        finally:
            queue.task_done()


def _persist_ingest_event(
    session_factory: sessionmaker[Session],
    event: IngestEvent,
) -> None:
    with session_factory() as db:
        if isinstance(event, NetFlowRecord):
            exists = db.scalar(
                select(FlowRecord.id).where(
                    FlowRecord.source == "netflow_v5",
                    FlowRecord.source_record_id == event.source_record_id,
                )
            )
            if exists is not None:
                return
            hosts = db.scalars(
                select(MonitoredHost).where(
                    MonitoredHost.ip_address.in_(
                        [event.source_ip, event.destination_ip]
                    )
                )
            ).all()
            hosts_by_ip = {host.ip_address: host for host in hosts}
            source_host = hosts_by_ip.get(event.source_ip)
            destination_host = hosts_by_ip.get(event.destination_ip)
            department_id = (
                source_host.department_id
                if source_host is not None
                else destination_host.department_id
                if destination_host is not None
                else None
            )
            db.add(
                FlowRecord(
                    flow_start=event.flow_start,
                    flow_end=event.flow_end,
                    department_id=department_id,
                    source_host_id=source_host.id if source_host else None,
                    destination_host_id=(
                        destination_host.id if destination_host else None
                    ),
                    source_ip=event.source_ip,
                    destination_ip=event.destination_ip,
                    source_port=event.source_port,
                    destination_port=event.destination_port,
                    protocol=event.protocol,
                    bytes_transferred=event.bytes_transferred,
                    packets=event.packets,
                    source="netflow_v5",
                    source_record_id=event.source_record_id,
                )
            )
        else:
            exists = db.scalar(
                select(NetworkLog.id).where(
                    NetworkLog.source == "syslog",
                    NetworkLog.source_event_id == event.source_event_id,
                )
            )
            if exists is not None:
                return
            device = db.scalar(
                select(NetworkDevice).where(
                    NetworkDevice.ip_address == event.exporter_ip
                )
            )
            db.add(
                NetworkLog(
                    device_id=device.id if device else None,
                    source="syslog",
                    event_type=event.event_type,
                    severity=event.severity,
                    summary=event.summary,
                    source_event_id=event.source_event_id,
                    occurred_at=event.occurred_at,
                    received_at=event.received_at,
                )
            )
        db.commit()


async def _collect_safely(
    collect: Callable[[], Awaitable[CollectorResult]],
    provider: Literal["zabbix", "ntopng", "snmpv3"],
) -> CollectorResult:
    try:
        return await collect()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.error(
            "%s collection failed (%s)",
            provider,
            type(error).__name__,
        )
        return CollectorResult(
            provider=provider,
            checked_at=datetime.now(timezone.utc),
            service_status="unavailable",
            message="Collection failed; check the server-side collector log",
        )


def _collect_demo(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        collect_demo_sample(db)


def _persist_results(
    session_factory: sessionmaker[Session], results: list[CollectorResult]
) -> None:
    with session_factory() as db:
        for result in results:
            persist_collector_result(db, result)
        evaluate_live_alerts(db)
