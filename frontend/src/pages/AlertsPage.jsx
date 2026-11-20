import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Bell, Check, RefreshCw, Save, TriangleAlert } from "lucide-react";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { formatDateTime } from "../utils/formatters.js";

const statusLabels = {
  open: "เปิด",
  acknowledged: "รับทราบแล้ว",
  resolved: "แก้ไขแล้ว",
};

const severityLabels = {
  critical: "วิกฤต",
  warning: "เฝ้าระวัง",
  info: "ข้อมูล",
};

function AlertsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [thresholds, setThresholds] = useState(null);
  const [dataMode, setDataMode] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [busyAlertId, setBusyAlertId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    const params = {
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(severityFilter ? { severity: severityFilter } : {}),
    };
    try {
      const [alertResponse, thresholdResponse, overviewResponse] = await Promise.all([
        api.get("/alerts", { params, signal }),
        api.get("/alerts/thresholds", { signal }),
        api.get("/dashboard/overview", { signal }),
      ]);
      setAlerts(alertResponse.data);
      setThresholds(thresholdResponse.data);
      setDataMode(overviewResponse.data.data_mode);
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setError(
          requestError?.response
            ? "โหลดข้อมูลการแจ้งเตือนไม่สำเร็จ กรุณาลองอีกครั้ง"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, [severityFilter, statusFilter]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refreshKey]);

  async function updateStatus(alert, nextStatus) {
    setBusyAlertId(alert.id);
    setError("");
    setNotice("");
    try {
      await api.patch(`/alerts/${alert.id}/status`, { status: nextStatus });
      setNotice(nextStatus === "acknowledged" ? "บันทึกการรับทราบแล้ว" : "บันทึกการแก้ไขแล้ว");
      setRefreshKey((key) => key + 1);
    } catch {
      setError("เปลี่ยนสถานะการแจ้งเตือนไม่สำเร็จ กรุณาตรวจสอบสิทธิ์และลองอีกครั้ง");
    } finally {
      setBusyAlertId(null);
    }
  }

  async function saveThresholds(event) {
    event.preventDefault();
    if (!thresholds) return;
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await api.put("/alerts/thresholds", {
        ...thresholds,
        high_bandwidth_bps: Number(thresholds.high_bandwidth_bps),
        unusual_traffic_min_bps: Number(thresholds.unusual_traffic_min_bps),
        unusual_traffic_multiplier: Number(thresholds.unusual_traffic_multiplier),
      });
      setThresholds(response.data);
      setNotice("บันทึกเกณฑ์การแจ้งเตือนแล้ว");
    } catch {
      setError("บันทึกเกณฑ์ไม่สำเร็จ ตรวจสอบค่าที่กรอกและสิทธิ์ผู้ใช้งาน");
    } finally {
      setIsSaving(false);
    }
  }

  function changeThreshold(field, value) {
    setThresholds((current) => current && ({ ...current, [field]: value }));
  }

  const activeCount = alerts.filter((alert) => alert.status !== "resolved").length;
  const isDemo = dataMode === "demo";

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ศูนย์แจ้งเตือน</div>
          <h1>การแจ้งเตือนเครือข่าย</h1>
          <p>ตรวจสอบเหตุการณ์ รับทราบ และติดตามการแก้ไขตามสิทธิ์ผู้ใช้งาน</p>
        </div>
        <div className="heading-actions">
          {dataMode && (
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
        <Bell size={16} />
        <span>
          {isDemo
            ? "DEMO DATA — การแจ้งเตือนจำลอง ไม่ใช่เหตุการณ์จากเครือข่ายจริง"
            : "แสดงเฉพาะเหตุการณ์ที่ได้รับจากข้อมูลจริงหรือผู้ดูแลระบบบันทึก"}
        </span>
      </div>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} /><span>{error}</span>
          <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>ลองอีกครั้ง</button>
        </div>
      )}
      {notice && <div className="success-notice" role="status"><Check size={16} />{notice}</div>}

      <section className="panel alert-toolbar">
        <div className="alert-count-summary">
          <span className="alert-summary-icon"><Bell size={19} /></span>
          <div><strong>{activeCount.toLocaleString("th-TH")}</strong><span>รายการที่ยังไม่แก้ไขในผลลัพธ์</span></div>
        </div>
        <div className="analytics-filters alert-filters">
          <label>
            <span>สถานะ</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">ทุกสถานะ</option>
              <option value="open">เปิด</option>
              <option value="acknowledged">รับทราบแล้ว</option>
              <option value="resolved">แก้ไขแล้ว</option>
            </select>
          </label>
          <label>
            <span>ระดับความรุนแรง</span>
            <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
              <option value="">ทุกระดับ</option>
              <option value="critical">วิกฤต</option>
              <option value="warning">เฝ้าระวัง</option>
              <option value="info">ข้อมูล</option>
            </select>
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <div className="panel-title-row"><TriangleAlert size={17} /><h2>ประวัติการแจ้งเตือน</h2></div>
            <p>เรียงตามเวลาที่ตรวจพบล่าสุด</p>
          </div>
          <span className="chart-unit">{alerts.length.toLocaleString("th-TH")} รายการ</span>
        </div>
        {isLoading && !alerts.length ? (
          <div className="analytics-empty">กำลังโหลดประวัติการแจ้งเตือน...</div>
        ) : alerts.length ? (
          <div className="data-table-wrap">
            <table className="data-table alert-table">
              <thead>
                <tr><th>เหตุการณ์</th><th>ระดับ</th><th>สถานะ</th><th>เวลาที่ตรวจพบ</th>{isAdmin && <th>การดำเนินการ</th>}</tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>
                      <strong>{alert.title}</strong>
                      <span className="table-secondary">{alert.description || "ไม่มีรายละเอียดเพิ่มเติม"}</span>
                    </td>
                    <td><span className={`alert-pill severity-text-${alert.severity}`}>{severityLabels[alert.severity] || alert.severity}</span></td>
                    <td><span className={`alert-pill status-${alert.status}`}>{statusLabels[alert.status] || alert.status}</span></td>
                    <td>{formatDateTime(alert.detected_at)}</td>
                    {isAdmin && (
                      <td>
                        <div className="alert-actions">
                          {alert.status === "open" && (
                            <button type="button" className="secondary-button" disabled={busyAlertId === alert.id} onClick={() => updateStatus(alert, "acknowledged")}>
                              รับทราบ
                            </button>
                          )}
                          {alert.status !== "resolved" && (
                            <button type="button" className="primary-button" disabled={busyAlertId === alert.id} onClick={() => updateStatus(alert, "resolved")}>
                              แก้ไขแล้ว
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="analytics-empty">ไม่พบการแจ้งเตือนตามตัวกรองที่เลือก</div>
        )}
      </section>

      <section className="panel threshold-panel">
        <div className="panel-heading">
          <div>
            <div className="panel-title-row"><Bell size={17} /><h2>เกณฑ์การแจ้งเตือน</h2></div>
            <p>เงื่อนไขตรวจสอบข้อมูลเครือข่ายจากแหล่งตรวจวัด</p>
          </div>
          {!isAdmin && <span className="chart-unit">แก้ไขได้เฉพาะผู้ดูแลระบบ</span>}
        </div>
        {thresholds ? (
          <form className="threshold-form" onSubmit={saveThresholds}>
            <label>
              <span>แบนด์วิดท์สูง (bps)</span>
              <input
                type="number"
                min="1000000"
                max="1000000000000"
                step="1000000"
                value={thresholds.high_bandwidth_bps}
                onChange={(event) => changeThreshold("high_bandwidth_bps", event.target.value)}
                disabled={!isAdmin}
                required
              />
            </label>
            <label>
              <span>ตัวคูณการใช้งานผิดปกติ</span>
              <input
                type="number"
                min="1.5"
                max="20"
                step="0.5"
                value={thresholds.unusual_traffic_multiplier}
                onChange={(event) => changeThreshold("unusual_traffic_multiplier", event.target.value)}
                disabled={!isAdmin}
                required
              />
            </label>
            <label>
              <span>อัตราขั้นต่ำสำหรับตรวจจับ (bps)</span>
              <input
                type="number"
                min="100000"
                max="1000000000000"
                step="100000"
                value={thresholds.unusual_traffic_min_bps}
                onChange={(event) => changeThreshold("unusual_traffic_min_bps", event.target.value)}
                disabled={!isAdmin}
                required
              />
            </label>
            <label className="threshold-toggle">
              <input
                type="checkbox"
                checked={thresholds.offline_detection_enabled}
                onChange={(event) => changeThreshold("offline_detection_enabled", event.target.checked)}
                disabled={!isAdmin}
              />
              <span>เปิดการตรวจจับอุปกรณ์ออฟไลน์</span>
            </label>
            {isAdmin && (
              <button type="submit" className="primary-button threshold-save" disabled={isSaving}>
                <Save size={15} />{isSaving ? "กำลังบันทึก..." : "บันทึกเกณฑ์"}
              </button>
            )}
          </form>
        ) : (
          <div className="analytics-empty">
            {isLoading ? "กำลังโหลดเกณฑ์การแจ้งเตือน..." : "ไม่สามารถโหลดเกณฑ์การแจ้งเตือนได้"}
          </div>
        )}
        <p className="threshold-note">การตรวจจับรูปแบบผิดปกติเปรียบเทียบค่าเฉลี่ยของอุปกรณ์กับข้อมูลย้อนหลัง 24 ชั่วโมง และจะไม่ทำงานหากไม่มีตัวอย่างเพียงพอ</p>
      </section>
    </div>
  );
}

export default AlertsPage;
