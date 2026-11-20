import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Database,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../services/api.js";
import { formatBandwidth, formatBytes, formatTime } from "../utils/formatters.js";

const EMPTY_BREAKDOWN = [];

function TrafficPage() {
  const [hours, setHours] = useState(24);
  const [departmentId, setDepartmentId] = useState("");
  const [startDateTime, setStartDateTime] = useState("");
  const [endDateTime, setEndDateTime] = useState("");
  const [data, setData] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    const params = {
      hours,
      ...(departmentId ? { department_id: departmentId } : {}),
      ...(startDateTime ? { start: new Date(startDateTime).toISOString() } : {}),
      ...(endDateTime ? { end: new Date(endDateTime).toISOString() } : {}),
    };
    try {
      const [
        summary,
        history,
        topHosts,
        protocols,
        applications,
        departmentOptions,
      ] = await Promise.all([
        api.get("/traffic/summary", { params, signal }),
        api.get("/traffic/history", { params, signal }),
        api.get("/traffic/top-hosts", { params, signal }),
        api.get("/traffic/protocols", { params, signal }),
        api.get("/traffic/applications", { params, signal }),
        api.get("/traffic/departments", { params: { hours: 168 }, signal }),
      ]);
      setData({
        summary: summary.data,
        history: history.data,
        topHosts: topHosts.data,
        protocols: protocols.data,
        applications: applications.data,
      });
      setDepartments(departmentOptions.data);
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setError(
          requestError?.response
            ? "โหลดข้อมูลการจราจรไม่สำเร็จ กรุณาลองอีกครั้ง"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, [departmentId, endDateTime, hours, startDateTime]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refreshKey]);

  const chartData = useMemo(
    () =>
      (data?.history.points || []).map((point) => ({
        ...point,
        label: formatTime(point.time),
        download_mbps: point.download_bps === null ? null : point.download_bps / 1_000_000,
        upload_mbps: point.upload_bps === null ? null : point.upload_bps / 1_000_000,
      })),
    [data?.history.points],
  );
  const protocols = data?.protocols || EMPTY_BREAKDOWN;
  const applications = data?.applications || EMPTY_BREAKDOWN;
  const hasBandwidth = chartData.some(
    (point) => point.download_bps !== null || point.upload_bps !== null,
  );
  const isDemo = data?.summary.data_mode === "demo";

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">วิเคราะห์การจราจร</div>
          <h1>วิเคราะห์การใช้งานเครือข่าย</h1>
          <p>ตรวจสอบปริมาณข้อมูล อัตรารับส่ง และข้อมูลเมตาการเชื่อมต่อ</p>
        </div>
        <div className="heading-actions">
          {data && (
            <span className={`source-badge ${isDemo ? "source-demo" : "source-active"}`}>
              <span className="source-dot" />
              {isDemo ? "ข้อมูลสาธิต (DEMO DATA)" : "ข้อมูลจากแหล่งตรวจวัด"}
            </span>
          )}
          <button
            className="refresh-button"
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
            disabled={isLoading}
          >
            <RefreshCw size={16} className={isLoading ? "spin" : ""} />
            <span>รีเฟรช</span>
          </button>
        </div>
      </div>

      <div className={`data-notice ${isDemo ? "data-notice-demo" : ""}`}>
        <Database size={16} />
        <span>
          {isDemo
            ? "DEMO DATA — ข้อมูลจำลองเพื่อการสาธิต ไม่ใช่ข้อมูลจากเครือข่ายจริง"
            : "แสดงเฉพาะข้อมูลเมตาที่ API ได้รับ ไม่มีการเติมข้อมูลจำลอง"}
        </span>
      </div>

      <section className="panel analytics-filters" aria-label="ตัวกรองข้อมูล">
        <label>
          <span>ช่วงเวลา</span>
          <select
            value={hours}
            onChange={(event) => setHours(Number(event.target.value))}
          >
            <option value={1}>1 ชั่วโมง</option>
            <option value={6}>6 ชั่วโมง</option>
            <option value={24}>24 ชั่วโมง</option>
            <option value={72}>3 วัน</option>
            <option value={168}>7 วัน</option>
          </select>
        </label>
        <label>
          <span>แผนก</span>
          <select
            value={departmentId}
            onChange={(event) => setDepartmentId(event.target.value)}
          >
            <option value="">ทุกแผนก</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>ตั้งแต่วันที่และเวลา</span>
          <input
            type="datetime-local"
            value={startDateTime}
            onChange={(event) => setStartDateTime(event.target.value)}
          />
        </label>
        <label>
          <span>ถึงวันที่และเวลา</span>
          <input
            type="datetime-local"
            value={endDateTime}
            onChange={(event) => setEndDateTime(event.target.value)}
          />
        </label>
      </section>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} />
          <span>{error}</span>
          <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>
            ลองอีกครั้ง
          </button>
        </div>
      )}

      <section className="metric-grid analytics-metrics">
        <article className="metric-card tone-blue">
          <div className="metric-card-top">
            <span className="metric-label">ปริมาณข้อมูลรวม</span>
            <span className="metric-icon"><Database size={19} /></span>
          </div>
          <div className="metric-value">{formatBytes(data?.summary.total_bytes)}</div>
          <div className="metric-caption">จากระเบียนในช่วงเวลาที่เลือก</div>
        </article>
        <article className="metric-card tone-blue">
          <div className="metric-card-top">
            <span className="metric-label">ดาวน์โหลดในช่วงที่เลือก</span>
            <span className="metric-icon"><ArrowDownToLine size={19} /></span>
          </div>
          <div className="metric-value">{formatBytes(data?.summary.download_bytes)}</div>
          <div className="metric-caption">ผลรวมระเบียนขาเข้า</div>
        </article>
        <article className="metric-card tone-violet">
          <div className="metric-card-top">
            <span className="metric-label">อัปโหลดในช่วงที่เลือก</span>
            <span className="metric-icon"><ArrowUpFromLine size={19} /></span>
          </div>
          <div className="metric-value">{formatBytes(data?.summary.upload_bytes)}</div>
          <div className="metric-caption">ผลรวมระเบียนขาออก</div>
        </article>
        <article className="metric-card tone-green">
          <div className="metric-card-top">
            <span className="metric-label">ดาวน์โหลดขณะนี้</span>
            <span className="metric-icon"><Activity size={19} /></span>
          </div>
          <div className="metric-value">{formatBandwidth(data?.summary.current_download_bps)}</div>
          <div className="metric-caption">ค่าเฉลี่ยตัวอย่างใน 5 นาทีล่าสุด</div>
        </article>
        <article className="metric-card tone-violet">
          <div className="metric-card-top">
            <span className="metric-label">อัปโหลดขณะนี้</span>
            <span className="metric-icon"><ArrowUpFromLine size={19} /></span>
          </div>
          <div className="metric-value">{formatBandwidth(data?.summary.current_upload_bps)}</div>
          <div className="metric-caption">ค่าเฉลี่ยตัวอย่างใน 5 นาทีล่าสุด</div>
        </article>
        <article className="metric-card tone-amber">
          <div className="metric-card-top">
            <span className="metric-label">ปริมาณข้อมูลจากโฟลว์</span>
            <span className="metric-icon"><Database size={19} /></span>
          </div>
          <div className="metric-value">{formatBytes(data?.summary.flow_bytes)}</div>
          <div className="metric-caption">
            {data?.summary.flow_count == null
              ? "จำนวนโฟลว์ —"
              : `${data.summary.flow_count.toLocaleString("th-TH")} โฟลว์`}
          </div>
        </article>
      </section>

      {isLoading && !data ? (
        <div className="panel analytics-empty">กำลังโหลดข้อมูลการจราจร...</div>
      ) : (
        <>
          <section className="panel analytics-chart-panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><Activity size={17} /><h2>อัตรารับส่งข้อมูลตามเวลา</h2></div>
                <p>แสดงค่าเฉลี่ยแยกตามอุปกรณ์และอินเทอร์เฟซ</p>
              </div>
              <span className="chart-unit">Mbps</span>
            </div>
            {hasBandwidth ? (
              <div className="analytics-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 12, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 11 }} minTickGap={35} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 11 }} />
                    <Tooltip formatter={(value, name) => [`${Number(value).toLocaleString("th-TH")} Mbps`, name]} />
                    <Area type="monotone" dataKey="download_mbps" name="ดาวน์โหลด" stroke="#278466" fill="#278466" fillOpacity={0.12} strokeWidth={2} connectNulls={false} />
                    <Area type="monotone" dataKey="upload_mbps" name="อัปโหลด" stroke="#7187d8" fill="#7187d8" fillOpacity={0.1} strokeWidth={2} connectNulls={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty-chart">
                <span className="empty-chart-icon"><Activity size={21} /></span>
                <strong>{chartData.length ? "ไม่มีข้อมูลอัตราความเร็ว" : "ยังไม่มีข้อมูลการจราจร"}</strong>
                <span>กราฟจะแสดงเมื่อแหล่งตรวจวัดส่งข้อมูลอัตรารับและส่ง</span>
              </div>
            )}
          </section>

          <div className="analytics-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><Database size={17} /><h2>โปรโตคอล</h2></div>
                  <p>จำแนกตามปริมาณข้อมูลในช่วงที่เลือก</p>
                </div>
              </div>
              {protocols.length ? (
                <div className="analytics-bar-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={protocols} layout="vertical" margin={{ top: 8, right: 16, left: 10, bottom: 0 }}>
                      <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="name" width={76} tickLine={false} axisLine={false} tick={{ fill: "#626e7e", fontSize: 11 }} />
                      <Tooltip formatter={(value) => [formatBytes(value), "ปริมาณข้อมูล"]} />
                      <Bar dataKey="bytes_transferred" fill="#438d78" radius={[0, 5, 5, 0]} barSize={18} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="analytics-empty">ไม่มีข้อมูลโปรโตคอลในช่วงเวลานี้</div>
              )}
            </section>

            <section className="panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-title-row"><Activity size={17} /><h2>แอปพลิเคชัน</h2></div>
                  <p>แสดงเมื่อแหล่งข้อมูลรองรับการจำแนกแอปพลิเคชัน</p>
                </div>
              </div>
              {applications.length ? (
                <div className="breakdown-list">
                  {applications.map((application) => (
                    <div className="breakdown-row" key={application.name}>
                      <div><strong>{application.name}</strong><span>{application.percent}%</span></div>
                      <div className="breakdown-track"><span style={{ width: `${application.percent}%` }} /></div>
                      <small>{formatBytes(application.bytes_transferred)} · {application.flow_count.toLocaleString("th-TH")} โฟลว์</small>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="analytics-empty">แหล่งตรวจวัดยังไม่มีข้อมูลแอปพลิเคชัน</div>
              )}
            </section>
          </div>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><Database size={17} /><h2>โฮสต์ที่มีปริมาณข้อมูลสูง</h2></div>
                <p>แสดงเฉพาะ IP และชื่อโฮสต์จากข้อมูลเมตาโฟลว์</p>
              </div>
            </div>
            {data?.topHosts.length ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead><tr><th>IP Address</th><th>ชื่อโฮสต์</th><th>ปริมาณข้อมูล</th><th>โฟลว์</th></tr></thead>
                  <tbody>
                    {data.topHosts.map((host) => (
                      <tr key={host.ip_address}>
                        <td className="table-mono">{host.ip_address}</td>
                        <td>{host.hostname || "ไม่ทราบชื่อ"}</td>
                        <td>{formatBytes(host.bytes_transferred)}</td>
                        <td>{host.flow_count.toLocaleString("th-TH")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="analytics-empty">ไม่มีข้อมูลโฮสต์ในช่วงเวลาที่เลือก</div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default TrafficPage;
