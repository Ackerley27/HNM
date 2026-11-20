import csv
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database.session import get_db
from app.models import Department, FlowRecord, NetworkDevice, TrafficRecord, User
from app.schemas.reports import DepartmentReportRow, NetworkReport
from app.services.traffic import MonitoringMode, source_filter

router = APIRouter(prefix="/reports", tags=["reports"])
ReportPeriod = Literal["daily", "monthly"]


@router.get("/daily", response_model=NetworkReport)
def get_daily_report(
    request: Request,
    report_date: date | None = Query(default=None, alias="date"),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NetworkReport:
    now = datetime.now(timezone.utc)
    selected_date = report_date or now.date()
    start = datetime.combine(selected_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return _build_report(
        db,
        request.app.state.settings.monitoring_mode,
        start,
        end,
    )


@router.get("/monthly", response_model=NetworkReport)
def get_monthly_report(
    request: Request,
    year: int | None = Query(default=None, ge=2000, le=9998),
    month: int | None = Query(default=None, ge=1, le=12),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NetworkReport:
    if (year is None) != (month is None):
        raise HTTPException(
            status_code=422,
            detail="year and month must be provided together",
        )
    now = datetime.now(timezone.utc)
    selected_year = year or now.year
    selected_month = month or now.month
    start = datetime(selected_year, selected_month, 1, tzinfo=timezone.utc)
    end = (
        datetime(selected_year + 1, 1, 1, tzinfo=timezone.utc)
        if selected_month == 12
        else datetime(selected_year, selected_month + 1, 1, tzinfo=timezone.utc)
    )
    return _build_report(
        db,
        request.app.state.settings.monitoring_mode,
        start,
        end,
    )


@router.get("/export")
def export_report(
    request: Request,
    period: ReportPeriod = "daily",
    report_date: date | None = Query(default=None, alias="date"),
    year: int | None = Query(default=None, ge=2000, le=9998),
    month: int | None = Query(default=None, ge=1, le=12),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if period == "daily":
        if year is not None or month is not None:
            raise HTTPException(
                status_code=422,
                detail="year and month apply only to monthly exports",
            )
        now = datetime.now(timezone.utc)
        selected_date = report_date or now.date()
        start = datetime.combine(selected_date, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        filename = f"network-report-{selected_date.isoformat()}.csv"
    else:
        if report_date is not None:
            raise HTTPException(
                status_code=422,
                detail="date applies only to daily exports",
            )
        if (year is None) != (month is None):
            raise HTTPException(
                status_code=422,
                detail="year and month must be provided together",
            )
        now = datetime.now(timezone.utc)
        selected_year = year or now.year
        selected_month = month or now.month
        start = datetime(selected_year, selected_month, 1, tzinfo=timezone.utc)
        end = (
            datetime(selected_year + 1, 1, 1, tzinfo=timezone.utc)
            if selected_month == 12
            else datetime(selected_year, selected_month + 1, 1, tzinfo=timezone.utc)
        )
        filename = f"network-report-{selected_year}-{selected_month:02d}.csv"

    report = _build_report(
        db,
        request.app.state.settings.monitoring_mode,
        start,
        end,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ช่วงเวลาเริ่มต้น UTC",
            "ช่วงเวลาสิ้นสุด UTC",
            "โหมดข้อมูล",
            "ประเภท",
            "รายการ",
            "ไบต์",
            "จำนวน",
        ]
    )
    base = [report.period_start.isoformat(), report.period_end.isoformat(), report.data_mode]
    writer.writerow(base + ["traffic", "total", _csv_value(report.traffic_bytes), ""])
    writer.writerow(base + ["traffic", "ingress", _csv_value(report.download_bytes), ""])
    writer.writerow(base + ["traffic", "egress", _csv_value(report.upload_bytes), ""])
    writer.writerow(base + ["flows", "total", _csv_value(report.flow_bytes), report.flow_count])
    for label, count in (
        ("devices_total", report.total_devices),
        ("devices_online", report.online_devices),
        ("devices_offline", report.offline_devices),
        ("devices_unknown", report.unknown_devices),
        ("devices_unavailable", report.unavailable_devices),
    ):
        writer.writerow(base + ["device_status", label, "", count])
    for department in report.department_usage:
        writer.writerow(
            base
            + [
                "department",
                department.department_name,
                department.bytes_transferred,
                "",
            ]
        )
    content = "\ufeff" + output.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_report(
    db: Session,
    mode: MonitoringMode,
    start: datetime,
    end: datetime,
) -> NetworkReport:
    traffic_rows = db.execute(
        select(
            TrafficRecord.direction,
            func.sum(TrafficRecord.bytes_transferred),
            func.count(TrafficRecord.id),
        )
        .where(
            TrafficRecord.interval_start >= start,
            TrafficRecord.interval_start < end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(TrafficRecord.direction)
    ).all()
    traffic_by_direction = {
        direction: (int(byte_count or 0), count)
        for direction, byte_count, count in traffic_rows
    }
    traffic_count = sum(count for _bytes, count in traffic_by_direction.values())

    flow_bytes, flow_count = db.execute(
        select(func.sum(FlowRecord.bytes_transferred), func.count(FlowRecord.id)).where(
            FlowRecord.flow_start >= start,
            FlowRecord.flow_start < end,
            source_filter(FlowRecord.source, mode),
        )
    ).one()
    device_counts = dict(
        db.execute(
            select(NetworkDevice.status, func.count(NetworkDevice.id))
            .where(source_filter(NetworkDevice.source, mode))
            .group_by(NetworkDevice.status)
        ).all()
    )
    department_rows = db.execute(
        select(
            Department.id,
            Department.name,
            func.sum(TrafficRecord.bytes_transferred),
        )
        .select_from(TrafficRecord)
        .join(Department, Department.id == TrafficRecord.department_id)
        .where(
            TrafficRecord.interval_start >= start,
            TrafficRecord.interval_start < end,
            source_filter(TrafficRecord.source, mode),
        )
        .group_by(Department.id, Department.name)
        .order_by(desc(func.sum(TrafficRecord.bytes_transferred)))
    ).all()
    ingress = traffic_by_direction.get("ingress")
    egress = traffic_by_direction.get("egress")
    return NetworkReport(
        data_mode=mode,
        period_start=start,
        period_end=end,
        traffic_bytes=(
            sum(value for value, _count in traffic_by_direction.values())
            if traffic_count
            else None
        ),
        download_bytes=ingress[0] if ingress else None,
        upload_bytes=egress[0] if egress else None,
        flow_bytes=int(flow_bytes) if flow_count else None,
        flow_count=flow_count,
        total_devices=sum(device_counts.values()),
        online_devices=device_counts.get("online", 0),
        offline_devices=device_counts.get("offline", 0),
        unknown_devices=device_counts.get("unknown", 0),
        unavailable_devices=device_counts.get("unavailable", 0),
        department_usage=[
            DepartmentReportRow(
                department_id=department_id,
                department_name=name,
                bytes_transferred=int(byte_count or 0),
            )
            for department_id, name, byte_count in department_rows
        ],
    )


def _csv_value(value: int | None) -> int | str:
    return value if value is not None else ""
