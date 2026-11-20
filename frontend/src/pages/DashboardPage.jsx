import { useMemo } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Building2,
  CheckCircle2,
  Clock3,
  Database,
  HardDrive,
  Network,
  RefreshCw,
  TriangleAlert,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useDashboardData } from "../hooks/useDashboardData.js";
import { formatBandwidth, formatBytes, formatDateTime, formatTime } from "../utils/formatters.js";

const stateColors = {
  online: "#278466",
  offline: "#d2635d",
  unknown: "#a6afbd",
  unavailable: "#e5aa4e",
};

const stateLabels = {
  online: "ออนไลน์",
  offline: "ออฟไลน์",
  unknown: "ไม่ทราบสถานะ",
  unavailable: "แหล่งข้อมูลไม่พร้อม",
};

const severityLabels = {
  critical: "วิกฤต",
  warning: "เฝ้าระวัง",
  info: "ข้อมูล",
};

function MetricCard({ title, value, caption, icon: Icon, tone }) {
  const formattedValue = typeof value === "number"
    ? new Intl.NumberFormat("th-TH").format(value)
    : value;
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-card-top">
        <span className="metric-label">{title}</span>
        <span className="metric-icon"><Icon size={19} strokeWidth={1.9} /></span>
      </div>
      <div className="metric-value">{formattedValue}</div>
      <div className="metric-caption">{caption}</div>
    </article>
  );
}

function MetricSkeleton() {
  return (
    <div className="metric-grid" aria-label="กำลังโหลดข้อมูล">
      {Array.from({ length: 6 }, (_, index) => (
        <div className="metric-card skeleton-card" key={index}>
          <div className="skeleton-line skeleton-short" />
          <div className="skeleton-line skeleton-number" />
          <div className="skeleton-line skeleton-caption" />
        </div>
      ))}
    </div>
  );
}

function EmptyChart({ icon: Icon = Database, title, detail }) {
  return (
    <div className="empty-chart">
      <span className="empty-chart-icon"><Icon size={21} /></span>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function TrafficTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.map((entry) => (
        <div className="tooltip-row" key={entry.dataKey}>
          <span className="tooltip-dot" style={{ backgroundColor: entry.color }} />
          <span>{entry.name}</span>
          <b>{entry.value == null ? "—" : `${entry.value.toLocaleString("th-TH", { maximumFractionDigits: 2 })} Mbps`}</b>
        </div>
      ))}
    </div>
  );
}

function DashboardPage() {
  const { data, isLoading, error, reload } = useDashboardData();

  const trafficPoints = useMemo(
    () =>
      (data?.traffic.points || []).map((point) => ({
        ...point,
        label: formatTime(point.time),
        download_mbps: point.download_bps === null ? null : point.download_bps / 1_000_000,
        upload_mbps: point.upload_bps === null ? null : point.upload_bps / 1_000_000,
      })),
    [data?.traffic.points],
  );

  const overview = data?.overview;
  const isDemoMode = overview?.data_mode === "demo";
  const status = data?.deviceStatus;
  const statusData = status
    ? ["online", "offline", "unknown", "unavailable"]
        .map((key) => ({
          key,
          name: stateLabels[key],
          value: status[key],
          color: stateColors[key],
        }))
        .filter((entry) => entry.value > 0)
    : [];
  const departmentData = (overview?.department_usage || []).map((department) => ({
    ...department,
    usage_mb: department.bytes_transferred / 1_000_000,
  }));
  const hasBandwidthData = trafficPoints.some(
    (point) => point.download_bps !== null || point.upload_bps !== null,
  );
  const hasAvailableSource = overview?.monitoring_services.some(
    (service) => service.status === "available",
  );
  const sourceText = isDemoMode
    ? "ข้อมูลสาธิต (DEMO DATA)"
    : hasAvailableSource
      ? "มีแหล่งตรวจวัดพร้อมใช้งาน"
      : "ยังไม่มีแหล่งตรวจวัดที่พร้อมใช้งาน";

  return (
    <div className="dashboard-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ศูนย์ปฏิบัติการเครือข่าย</div>
          <h1>ภาพรวมเครือข่าย</h1>
          <p>ติดตามสถานะและปริมาณการใช้งานเครือข่ายของโรงพยาบาล</p>
        </div>
        <div className="heading-actions">
          <span className={`source-badge ${isDemoMode ? "source-demo" : hasAvailableSource ? "source-active" : "source-idle"}`}>
            <span className="source-dot" />
            {sourceText}
          </span>
          <button className="refresh-button" type="button" onClick={reload} disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? "spin" : ""} />
            <span>รีเฟรช</span>
          </button>
        </div>
      </div>

      <div className={`data-notice ${isDemoMode ? "data-notice-demo" : ""}`}>
        <Database size={16} />
        <span>
          {isDemoMode
            ? "DEMO DATA — ข้อมูลจำลองเพื่อการสาธิต ไม่ใช่ข้อมูลจากเครือข่ายจริง"
            : "แสดงเฉพาะข้อมูลที่ได้รับจาก API ไม่มีการเติมข้อมูลจำลอง"}
        </span>
        {overview?.generated_at && (
          <span className="data-updated"><Clock3 size={14} /> อัปเดต {formatDateTime(overview.generated_at)}</span>
        )}
      </div>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} />
          <span>{error}</span>
          <button type="button" onClick={reload}>ลองอีกครั้ง</button>
        </div>
      )}

      {isLoading && !data ? (
        <MetricSkeleton />
      ) : (
        <>
          <section className="metric-grid" aria-label="สรุปสถานะเครือข่าย">
            <MetricCard
              title="อุปกรณ์ทั้งหมด"
              value={overview?.total_devices ?? "—"}
              caption="อุปกรณ์ในทะเบียนระบบ"
              icon={Network}
              tone="navy"
            />
            <MetricCard
              title="ออนไลน์"
              value={overview?.online_devices ?? "—"}
              caption="สถานะที่ยืนยันว่าออนไลน์"
              icon={Wifi}
              tone="green"
            />
            <MetricCard
              title="ออฟไลน์"
              value={overview?.offline_devices ?? "—"}
              caption="อุปกรณ์ที่ตรวจพบว่าออฟไลน์"
              icon={WifiOff}
              tone="red"
            />
            <MetricCard
              title="ดาวน์โหลดขณะนี้"
              value={formatBandwidth(overview?.download_bps)}
              caption="ตัวอย่างข้อมูลใน 5 นาทีล่าสุด"
              icon={ArrowDownToLine}
              tone="blue"
            />
            <MetricCard
              title="อัปโหลดขณะนี้"
              value={formatBandwidth(overview?.upload_bps)}
              caption="ตัวอย่างข้อมูลใน 5 นาทีล่าสุด"
              icon={ArrowUpFromLine}
              tone="violet"
            />
            <MetricCard
              title="ปริมาณข้อมูล 24 ชม."
              value={formatBytes(overview?.traffic_bytes_24h)}
              caption="รวมจากระเบียนการจราจร"
              icon={HardDrive}
              tone="amber"
            />
          </section>

          <div className="dashboard-main-grid">
            <section className="panel traffic-panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><Activity size={17} /><h2>ปริมาณการใช้งานเครือข่าย</h2></div>
                  <p>อัตรารับและส่งข้อมูลใน 24 ชั่วโมงล่าสุด</p>
                </div>
                <span className="chart-unit">Mbps</span>
              </div>
              {hasBandwidthData ? (
                <div className="traffic-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trafficPoints} margin={{ top: 10, right: 12, left: -12, bottom: 0 }}>
                      <defs>
                        <linearGradient id="downloadFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#2b8a70" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#2b8a70" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="uploadFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#7187d8" stopOpacity={0.16} />
                          <stop offset="95%" stopColor="#7187d8" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 11 }} minTickGap={35} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 11 }} tickFormatter={(value) => `${value}`} />
                      <Tooltip content={<TrafficTooltip />} />
                      <Area type="monotone" dataKey="download_mbps" name="ดาวน์โหลด" stroke="#278466" fill="url(#downloadFill)" strokeWidth={2.2} connectNulls={false} />
                      <Area type="monotone" dataKey="upload_mbps" name="อัปโหลด" stroke="#7187d8" fill="url(#uploadFill)" strokeWidth={2} connectNulls={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChart
                  icon={Activity}
                  title={trafficPoints.length ? "ไม่มีข้อมูลอัตราความเร็ว" : "ยังไม่มีข้อมูลการจราจร"}
                  detail="กราฟจะแสดงเมื่อ API ได้รับข้อมูลอัตรารับและส่งจากแหล่งตรวจวัด"
                />
              )}
              <div className="chart-legend">
                <span><i className="legend-dot legend-download" /> ดาวน์โหลด</span>
                <span><i className="legend-dot legend-upload" /> อัปโหลด</span>
              </div>
            </section>

            <section className="panel availability-panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><CheckCircle2 size={17} /><h2>สถานะอุปกรณ์</h2></div>
                  <p>ข้อมูลจากทะเบียนเครือข่าย</p>
                </div>
              </div>
              <div className="availability-score">
                <strong>
                  {overview?.availability_percent == null
                    ? "—"
                    : `${overview.availability_percent.toLocaleString("th-TH", { maximumFractionDigits: 1 })}%`}
                </strong>
                <span>ความพร้อมใช้งานของอุปกรณ์ที่ทราบสถานะ</span>
              </div>
              {statusData.length ? (
                <>
                  <div className="status-donut">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={statusData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={64} paddingAngle={3} stroke="none">
                          {statusData.map((entry) => <Cell key={entry.key} fill={entry.color} />)}
                        </Pie>
                        <Tooltip formatter={(value, name) => [`${value} เครื่อง`, name]} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="status-legend">
                    {statusData.map((entry) => (
                      <div className="status-legend-item" key={entry.key}>
                        <span className="legend-dot" style={{ backgroundColor: entry.color }} />
                        <span>{entry.name}</span>
                        <strong>{entry.value}</strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyChart
                  icon={Network}
                  title="ยังไม่มีอุปกรณ์ในระบบ"
                  detail="สถานะจะแสดงเมื่อมีการลงทะเบียนอุปกรณ์"
                />
              )}
            </section>

            <section className="panel department-panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><Building2 size={17} /><h2>การใช้งานตามแผนก</h2></div>
                  <p>ปริมาณข้อมูลสะสมใน 24 ชั่วโมงล่าสุด</p>
                </div>
                <span className="chart-unit">8 อันดับ</span>
              </div>
              {departmentData.length ? (
                <div className="department-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={departmentData} layout="vertical" margin={{ top: 0, right: 18, left: 4, bottom: 0 }}>
                      <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" horizontal={false} />
                      <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 11 }} tickFormatter={(value) => `${value} MB`} />
                      <YAxis type="category" dataKey="name" width={104} tickLine={false} axisLine={false} tick={{ fill: "#626e7e", fontSize: 11 }} />
                      <Tooltip formatter={(_, __, item) => [formatBytes(item.payload.bytes_transferred), "ปริมาณข้อมูล"]} />
                      <Bar dataKey="usage_mb" fill="#438d78" radius={[0, 5, 5, 0]} barSize={17} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyChart
                  icon={Building2}
                  title="ยังไม่มีข้อมูลแยกตามแผนก"
                  detail="ข้อมูลจะแสดงเมื่อมีการระบุแผนกในระเบียนเครือข่าย"
                />
              )}
            </section>

            <section className="panel alerts-panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><TriangleAlert size={17} /><h2>การแจ้งเตือนล่าสุด</h2></div>
                  <p>เหตุการณ์จากระบบเฝ้าระวัง</p>
                </div>
                <span className="alert-count">{overview?.recent_alerts.length || 0}</span>
              </div>
              {overview?.recent_alerts.length ? (
                <div className="alert-list">
                  {overview.recent_alerts.map((alert) => (
                    <article className="alert-row" key={alert.id}>
                      <span className={`alert-severity severity-${alert.severity}`} />
                      <div className="alert-content">
                        <div className="alert-title-row">
                          <strong>{alert.title}</strong>
                          <span className={`severity-label severity-text-${alert.severity}`}>
                            {severityLabels[alert.severity] || alert.severity}
                          </span>
                        </div>
                        <span className="alert-description">{alert.description || "ไม่มีรายละเอียดเพิ่มเติม"}</span>
                        <time>{formatDateTime(alert.detected_at)}</time>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyChart
                  icon={CheckCircle2}
                  title="ไม่มีการแจ้งเตือน"
                  detail="ยังไม่มีเหตุการณ์ที่บันทึกในระบบ"
                />
              )}
            </section>
          </div>
          <div className="dashboard-footnote">
            <span><span className="footnote-dot" />{sourceText}</span>
            <span>ข้อมูลที่ไม่มีในแหล่งตรวจวัดจะแสดงเป็น “—”</span>
          </div>
        </>
      )}
    </div>
  );
}

export default DashboardPage;
