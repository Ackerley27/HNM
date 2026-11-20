import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import utc_now
from app.models import (
    Department,
    DeviceMetric,
    FlowRecord,
    MonitoredHost,
    MonitoringSetting,
    NetworkAlert,
    NetworkDevice,
    NetworkInterface,
    NetworkLog,
    TrafficRecord,
    Vlan,
)

DEMO_DEPARTMENTS = (
    ("demo-emergency", "แผนกฉุกเฉิน", 10),
    ("demo-outpatient", "แผนกผู้ป่วยนอก", 20),
    ("demo-laboratory", "ห้องปฏิบัติการ", 30),
    ("demo-pharmacy", "แผนกเภสัชกรรม", 40),
)


def collect_demo_sample(db: Session, now: datetime | None = None) -> None:
    now = now or utc_now()
    departments: dict[str, Department] = {}
    vlans: dict[str, Vlan] = {}
    for code, name, vlan_number in DEMO_DEPARTMENTS:
        department = db.scalar(select(Department).where(Department.code == code))
        if department is None:
            department = Department(code=code, name=name, description="ข้อมูลสาธิตเท่านั้น")
            db.add(department)
            db.flush()
        departments[code] = department

        vlan = db.scalar(select(Vlan).where(Vlan.vlan_number == vlan_number))
        if vlan is None:
            vlan = Vlan(
                department_id=department.id,
                vlan_number=vlan_number,
                name=f"DEMO-{vlan_number}",
            )
            db.add(vlan)
            db.flush()
        vlans[code] = vlan

    device_specs = (
        ("demo-router-main", "เราเตอร์หลัก (สาธิต)", "192.0.2.1", "router", "demo-emergency", "online"),
        ("demo-firewall-edge", "ไฟร์วอลล์ขอบเครือข่าย (สาธิต)", "192.0.2.2", "firewall", "demo-outpatient", "online"),
        ("demo-switch-er", "สวิตช์ฉุกเฉิน (สาธิต)", "192.0.2.10", "switch", "demo-emergency", "online"),
        ("demo-switch-opd", "สวิตช์ผู้ป่วยนอก (สาธิต)", "192.0.2.20", "switch", "demo-outpatient", "online"),
        ("demo-switch-lab", "สวิตช์ห้องปฏิบัติการ (สาธิต)", "192.0.2.30", "switch", "demo-laboratory", "offline"),
        ("demo-ap-lab", "จุดเชื่อมต่อห้องปฏิบัติการ (สาธิต)", "192.0.2.31", "access_point", "demo-laboratory", "online"),
        ("demo-switch-pharmacy", "สวิตช์เภสัชกรรม (สาธิต)", "192.0.2.40", "switch", "demo-pharmacy", "online"),
        ("demo-ap-pharmacy", "จุดเชื่อมต่อเภสัชกรรม (สาธิต)", "192.0.2.41", "access_point", "demo-pharmacy", "online"),
    )
    devices: list[NetworkDevice] = []
    for source_id, name, ip_address, device_type, department_code, status in device_specs:
        device = db.scalar(
            select(NetworkDevice).where(
                NetworkDevice.source == "demo",
                NetworkDevice.source_device_id == source_id,
            )
        )
        if device is None:
            device = NetworkDevice(
                name=name,
                hostname=source_id,
                ip_address=ip_address,
                device_type=device_type,
                status=status,
                source="demo",
                source_device_id=source_id,
                department_id=departments[department_code].id,
                vlan_id=vlans[department_code].id,
                last_seen_at=now if status == "online" else None,
            )
            db.add(device)
            db.flush()
            db.add(
                NetworkInterface(
                    device_id=device.id,
                    if_index=1,
                    name="uplink-1",
                    description="Demo interface; no hardware is contacted",
                    oper_state="up" if status == "online" else "down",
                    last_seen_at=now if status == "online" else None,
                )
            )
        else:
            device.status = status
            if status == "online":
                device.last_seen_at = now
            interface = db.scalar(
                select(NetworkInterface).where(
                    NetworkInterface.device_id == device.id,
                    NetworkInterface.if_index == 1,
                )
            )
            if interface is not None:
                interface.oper_state = "up" if status == "online" else "down"
                if status == "online":
                    interface.last_seen_at = now
        devices.append(device)

    hosts_by_department: dict[str, MonitoredHost] = {}
    for index, (department_code, ip_address) in enumerate(
        zip(
            ("demo-emergency", "demo-outpatient", "demo-laboratory", "demo-pharmacy"),
            ("192.0.2.101", "192.0.2.102", "192.0.2.103", "192.0.2.104"),
        ),
        start=1,
    ):
        source_host_id = f"demo-host-{index}"
        host = db.scalar(
            select(MonitoredHost).where(
                MonitoredHost.source == "demo",
                MonitoredHost.source_host_id == source_host_id,
            )
        )
        if host is None:
            host = MonitoredHost(
                ip_address=ip_address,
                hostname=f"demo-host-{index}.example.invalid",
                source="demo",
                source_host_id=source_host_id,
                department_id=departments[department_code].id,
                vlan_id=vlans[department_code].id,
                first_seen_at=now - timedelta(days=7),
                last_seen_at=now,
            )
            db.add(host)
            db.flush()
        else:
            host.last_seen_at = now
        hosts_by_department[department_code] = host

    has_demo_traffic = db.scalar(
        select(TrafficRecord.id).where(TrafficRecord.source == "demo").limit(1)
    )
    if has_demo_traffic is None:
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        for hours_ago in reversed(range(1, 24)):
            interval_start = current_hour - timedelta(hours=hours_ago)
            for device_index, device in enumerate(devices):
                generator = random.Random(
                    int(interval_start.timestamp()) + device_index * 7919
                )
                for direction, low_rate, high_rate in (
                    ("ingress", 2_000_000, 32_000_000),
                    ("egress", 500_000, 8_000_000),
                ):
                    rate = generator.randint(low_rate, high_rate)
                    source_record_id = (
                        f"hourly-{device.source_device_id}-"
                        f"{int(interval_start.timestamp())}-{direction}"
                    )
                    if db.scalar(
                        select(TrafficRecord.id).where(
                            TrafficRecord.source == "demo",
                            TrafficRecord.source_record_id == source_record_id,
                        )
                    ):
                        continue
                    db.add(
                        TrafficRecord(
                            interval_start=interval_start,
                            interval_end=interval_start + timedelta(hours=1),
                            department_id=device.department_id,
                            device_id=device.id,
                            direction=direction,
                            bytes_transferred=rate * 3600 // 8,
                            bit_rate_bps=rate,
                            source="demo",
                            source_record_id=source_record_id,
                        )
                    )

    slot = int(now.timestamp()) // 60
    for device_index, device in enumerate(devices):
        generator = random.Random(slot + device_index * 104729)
        for direction, low_rate, high_rate in (
            ("ingress", 2_000_000, 32_000_000),
            ("egress", 500_000, 8_000_000),
        ):
            rate = generator.randint(low_rate, high_rate)
            source_record_id = (
                f"sample-{slot}-{device.source_device_id}-{direction}"
            )
            if db.scalar(
                select(TrafficRecord.id).where(
                    TrafficRecord.source == "demo",
                    TrafficRecord.source_record_id == source_record_id,
                )
            ):
                continue
            db.add(
                TrafficRecord(
                    interval_start=now - timedelta(seconds=60),
                    interval_end=now,
                    department_id=device.department_id,
                    device_id=device.id,
                    direction=direction,
                    bytes_transferred=rate * 60 // 8,
                    bit_rate_bps=rate,
                    source="demo",
                    source_record_id=source_record_id,
                )
            )

        if slot % 5 == 0:
            for metric_name, value in (
                ("cpu_percent", generator.uniform(8, 76)),
                ("memory_percent", generator.uniform(21, 83)),
            ):
                source_record_id = (
                    f"metric-{slot}-{device.source_device_id}-{metric_name}"
                )
                if db.scalar(
                    select(DeviceMetric.id).where(
                        DeviceMetric.source == "demo",
                        DeviceMetric.source_record_id == source_record_id,
                    )
                ):
                    continue
                db.add(
                    DeviceMetric(
                        device_id=device.id,
                        metric_name=metric_name,
                        value=round(value, 2),
                        unit="percent",
                        recorded_at=now,
                        source="demo",
                        source_record_id=source_record_id,
                    )
                )

    has_demo_flows = db.scalar(
        select(FlowRecord.id).where(FlowRecord.source == "demo").limit(1)
    )
    if has_demo_flows is None:
        department_codes = [item[0] for item in DEMO_DEPARTMENTS]
        for index in range(12):
            department_code = department_codes[index % len(department_codes)]
            host = hosts_by_department[department_code]
            db.add(
                FlowRecord(
                    flow_start=now - timedelta(minutes=5 + index * 3),
                    flow_end=now - timedelta(minutes=4 + index * 3),
                    department_id=host.department_id,
                    source_host_id=host.id,
                    source_ip=host.ip_address,
                    destination_ip=f"198.51.100.{10 + index}",
                    source_port=40000 + index,
                    destination_port=(443 if index % 2 == 0 else 53),
                    protocol="TCP" if index % 2 == 0 else "UDP",
                    application_name="HTTPS" if index % 2 == 0 else "DNS",
                    bytes_transferred=generator_bytes(index),
                    packets=20 + index * 7,
                    source="demo",
                    source_record_id=f"demo-flow-{index}",
                )
            )

    offline_device = next(device for device in devices if device.status == "offline")
    if not db.scalar(
        select(NetworkAlert.id).where(NetworkAlert.alert_type == "demo_device_offline")
    ):
        db.add(
            NetworkAlert(
                department_id=offline_device.department_id,
                device_id=offline_device.id,
                alert_type="demo_device_offline",
                severity="warning",
                status="open",
                title="อุปกรณ์สาธิตออฟไลน์",
                description="เหตุการณ์จำลองสำหรับ DEMO DATA เท่านั้น",
                detected_at=now - timedelta(minutes=12),
            )
        )

    if not db.scalar(
        select(NetworkLog.id).where(NetworkLog.source_event_id == "demo-startup-event")
    ):
        db.add(
            NetworkLog(
                source="demo",
                event_type="demo.monitoring.started",
                severity="info",
                summary="เริ่มการเก็บข้อมูลสาธิต (ไม่มีการเชื่อมต่ออุปกรณ์จริง)",
                source_event_id="demo-startup-event",
                occurred_at=now,
                received_at=now,
            )
        )

    setting = db.scalar(
        select(MonitoringSetting).where(
            MonitoringSetting.provider == "demo",
            MonitoringSetting.setting_key == "collector",
        )
    )
    if setting is None:
        setting = MonitoringSetting(provider="demo", setting_key="collector")
        db.add(setting)
    setting.setting_value = {"mode": "demo", "label": "DEMO DATA"}
    setting.enabled = True
    setting.service_status = "available"
    setting.last_checked_at = now
    db.commit()


def generator_bytes(seed: int) -> int:
    return 40_000 + seed * 12_345
