import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  BarChart3,
  CalendarDays,
  Database,
  Download,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../services/api.js";
import { formatBytes, formatDateTime } from "../utils/formatters.js";

const DEVICE_STATES = [
  { key: "online_devices", label: "ออนไลน์", tone: "online" },
  { key: "offline_devices", label: "ออฟไลน์", tone: "offline" },
  { key: "unknown_devices", label: "ไม่ทราบสถานะ", tone: "unknown" },
  { key: "unavailable_devices", label: "แหล่งข้อมูลไม่พร้อม", tone: "unavailable" },
];

function ReportsPage() {
  const [period, setPeriod] = useState("daily");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const params = period === "daily"
    ? { date }
    : {
      year: Number(month.slice(0, 4)),
      month: Number(month.slice(5, 7)),
    };

  const loadReport = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    try {
      const response = await api.get(`/reports/${period}`, { params, signal });
      setReport(response.data);
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setReport(null);
        setError(
          requestError?.response
            ? "โหลดรายงานไม่สำเร็จ กรุณาตรวจสอบช่วงเวลาที่เลือก"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, [period, date, month, refreshKey]);

  useEffect(() => {
    const controller = new AbortController();
    loadReport(controller.signal);
    return () => controller.abort();
  }, [loadReport]);

  async function exportCsv() {
    setIsExporting(true);
    setError("");
    try {
      const response = await api.get("/reports/export", {
        params: { period, ...params },
        responseType: "blob",
      });
      const objectUrl = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = period === "daily"
        ? `network-report-${date}.csv`
        : `network-report-${month}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch {
      setError("ส่งออกรายงาน CSV ไม่สำเร็จ กรุณาลองอีกครั้ง");
    } finally {
      setIsExporting(false);
    }
  }

  const isDemo = report?.data_mode === "demo";
  const departmentRows = (report?.department_usage || []).map((department) => ({
    ...department,
    name: department.department_name,
  }));
  const statusTotal = DEVICE_STATES.reduce(
    (total, state) => total + (report?.[state.key] || 0),
    0,
  );
  const windowLabel = report
    ? `${formatDateTime(report.period_start)} – ${formatDateTime(report.period_end)}`
    : "ช่วงเวลารายงานอ้างอิง UTC";

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">สรุปและส่งออกข้อมูล</div>
          <h1>รายงานเครือข่าย</h1>
          <p>สรุปปริมาณการจราจร สถานะอุปกรณ์ และการใช้งานแยกตามแผนก</p>
        </div>
        <div className="heading-actions">
          {report && (
            <span className={`source-badge ${isDemo ? "source-demo" : "source-active"}`}>
              <span className="source-dot" />
              {isDemo ? "ข้อมูลสาธิต (DEMO DATA)" : "ข้อมูลจริง (LIVE)"}
            </span>
          )}
          <button type="button" className="refresh-button" onClick={() => setRefreshKey((key) => key + 1)} disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? "spin" : ""} /><span>รีเฟรช</span>
          </button>
        </div>
      </div>

      <div className={`data-notice ${isDemo ? "data-notice-demo" : ""}`}>
        <Database size={16} />
        <span>
          {isDemo
            ? "DEMO DATA — รายงานนี้สรุปข้อมูลจำลอง ไม่ใช่การใช้งานเครือข่ายจริง"
            : "รายงานใช้เฉพาะระเบียนที่มีอยู่จริงในโหมดปัจจุบัน ค่าว่างหมายถึงไม่มีข้อมูล"}
        </span>
      </div>

      <section className="panel report-filters" aria-label="ตัวกรองรายงาน">
        <label>
          <span>ประเภทรายงาน</span>
          <select value={period} onChange={(event) => setPeriod(event.target.value)}>
            <option value="daily">รายวัน</option>
            <option value="monthly">รายเดือน</option>
          </select>
        </label>
        {period === "daily" ? (
          <label>
            <span>วันที่ (UTC)</span>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </label>
        ) : (
          <label>
            <span>เดือน (UTC)</span>
            <input type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
          </label>
        )}
        <button type="button" className="primary-button report-export-button" onClick={exportCsv} disabled={!report || isLoading || isExporting}>
          <Download size={15} />{isExporting ? "กำลังส่งออก..." : "ส่งออก CSV"}
        </button>
      </section>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} /><span>{error}</span>
          <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>ลองอีกครั้ง</button>
        </div>
      )}

      <div className="report-period-caption">
        <CalendarDays size={15} /><span>{windowLabel}</span>
        {report && <span className="report-period-zone">ขอบเขตข้อมูล: UTC</span>}
      </div>

      {isLoading && !report ? (
        <div className="panel analytics-empty">กำลังสร้างรายงานจากข้อมูลที่จัดเก็บ...</div>
      ) : report ? (
        <>
          <section className="metric-grid analytics-metrics report-metrics">
            <article className="metric-card tone-blue">
              <div className="metric-card-top"><span className="metric-label">ปริมาณข้อมูลรวม</span><span className="metric-icon"><Database size={19} /></span></div>
              <div className="metric-value">{formatBytes(report.traffic_bytes)}</div>
              <div className="metric-caption">จากระเบียน traffic ในช่วงรายงาน</div>
            </article>
            <article className="metric-card tone-green">
              <div className="metric-card-top"><span className="metric-label">ข้อมูลขาเข้า</span><span className="metric-icon"><ArrowDownToLine size={19} /></span></div>
              <div className="metric-value">{formatBytes(report.download_bytes)}</div>
              <div className="metric-caption">ผลรวมระเบียน ingress</div>
            </article>
            <article className="metric-card tone-violet">
              <div className="metric-card-top"><span className="metric-label">ข้อมูลขาออก</span><span className="metric-icon"><ArrowUpFromLine size={19} /></span></div>
              <div className="metric-value">{formatBytes(report.upload_bytes)}</div>
              <div className="metric-caption">ผลรวมระเบียน egress</div>
            </article>
            <article className="metric-card tone-amber">
              <div className="metric-card-top"><span className="metric-label">ปริมาณข้อมูลจาก Flow</span><span className="metric-icon"><BarChart3 size={19} /></span></div>
              <div className="metric-value">{formatBytes(report.flow_bytes)}</div>
              <div className="metric-caption">{report.flow_count.toLocaleString("th-TH")} รายการข้อมูล Flow</div>
            </article>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><BarChart3 size={17} /><h2>การใช้งานตามแผนก</h2></div>
                <p>ยอดรวม traffic ตามแผนกในช่วงรายงานที่เลือก</p>
              </div>
            </div>
            {departmentRows.length ? (
              <div className="report-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={departmentRows} margin={{ top: 12, right: 12, left: 8, bottom: 4 }}>
                    <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "#718091", fontSize: 10 }} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 10 }} tickFormatter={formatBytes} />
                    <Tooltip formatter={(value) => [formatBytes(value), "ปริมาณข้อมูล"]} />
                    <Bar dataKey="bytes_transferred" name="ปริมาณข้อมูล" fill="#438d78" radius={[5, 5, 0, 0]} barSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="analytics-empty">ไม่มีข้อมูลการใช้งานตามแผนกในช่วงเวลานี้</div>
            )}
            {departmentRows.length > 0 && (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead><tr><th>แผนก</th><th>ปริมาณข้อมูล</th></tr></thead>
                  <tbody>{departmentRows.map((department) => (
                    <tr key={department.department_id}><td>{department.department_name}</td><td>{formatBytes(department.bytes_transferred)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><BarChart3 size={17} /><h2>สถานะอุปกรณ์</h2></div>
                <p>จำนวนสถานะปัจจุบัน ณ เวลาที่เรียกรายงาน ไม่ใช่ประวัติสถานะย้อนหลัง</p>
              </div>
              <span className="chart-unit">{statusTotal.toLocaleString("th-TH")} อุปกรณ์</span>
            </div>
            {report.total_devices ? (
              <div className="report-device-status">
                {DEVICE_STATES.map((state) => (
                  <div className="report-state-row" key={state.key}>
                    <div className="report-state-label"><span className={`report-state-dot state-dot-${state.tone}`} /><span>{state.label}</span><strong>{report[state.key].toLocaleString("th-TH")}</strong></div>
                    <div className="report-state-track"><span className={`state-bar-${state.tone}`} style={{ width: `${(report[state.key] / report.total_devices) * 100}%` }} /></div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="analytics-empty">ไม่มีอุปกรณ์ในทะเบียนของโหมดข้อมูลนี้</div>
            )}
          </section>
        </>
      ) : (
        <div className="panel analytics-empty">ไม่พบข้อมูลรายงาน</div>
      )}
    </div>
  );
}

export default ReportsPage;
