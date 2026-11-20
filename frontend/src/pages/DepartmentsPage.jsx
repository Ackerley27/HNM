import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  Building2,
  Database,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { formatBytes, formatTime } from "../utils/formatters.js";

const EMPTY_FORM = { code: "", name: "", description: "" };

function DepartmentsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [departments, setDepartments] = useState([]);
  const [dataMode, setDataMode] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [period, setPeriod] = useState("day");
  const [periods, setPeriods] = useState(30);
  const [usage, setUsage] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUsageLoading, setIsUsageLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    try {
      const [departmentResponse, overviewResponse] = await Promise.all([
        api.get("/departments", { signal }),
        api.get("/dashboard/overview", { signal }),
      ]);
      setDepartments(departmentResponse.data);
      setDataMode(overviewResponse.data.data_mode);
      setSelectedId((current) => current || departmentResponse.data[0]?.id || "");
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setError(
          requestError?.response
            ? "โหลดข้อมูลแผนกไม่สำเร็จ กรุณาลองอีกครั้ง"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refreshKey]);

  useEffect(() => {
    if (!selectedId) {
      setUsage(null);
      return undefined;
    }
    const controller = new AbortController();
    setIsUsageLoading(true);
    api.get(`/departments/${selectedId}/usage`, {
      params: { period, periods },
      signal: controller.signal,
    }).then((response) => {
      setUsage(response.data);
    }).catch((requestError) => {
      if (!axios.isCancel(requestError)) {
        setError("โหลดสถิติแผนกไม่สำเร็จ กรุณาลองอีกครั้ง");
      }
    }).finally(() => {
      if (!controller.signal.aborted) setIsUsageLoading(false);
    });
    return () => controller.abort();
  }, [period, periods, selectedId, refreshKey]);

  const chartData = useMemo(
    () => (usage?.points || []).map((point) => ({
      ...point,
      label: period === "hour"
        ? formatTime(point.period_start)
        : new Intl.DateTimeFormat("th-TH", {
          day: "numeric",
          month: "short",
          ...(period === "month" ? { year: "2-digit" } : {}),
        }).format(new Date(point.period_start)),
    })),
    [period, usage?.points],
  );
  const selectedDepartment = departments.find((department) => department.id === selectedId);
  const isDemo = dataMode === "demo";

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setIsFormOpen(true);
  }

  function startEdit(department) {
    setEditingId(department.id);
    setForm({
      code: department.code,
      name: department.name,
      description: department.description || "",
    });
    setIsFormOpen(true);
  }

  async function saveDepartment(event) {
    event.preventDefault();
    setError("");
    setIsSaving(true);
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim() || null,
    };
    try {
      if (editingId) {
        await api.put(`/departments/${editingId}`, payload);
      } else {
        await api.post("/departments", payload);
      }
      setIsFormOpen(false);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setError(
        requestError?.response?.status === 409
          ? "รหัสแผนกนี้มีอยู่แล้ว หรือแผนกยังถูกใช้งาน"
          : "บันทึกข้อมูลแผนกไม่สำเร็จ กรุณาตรวจสอบข้อมูลและสิทธิ์",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function removeDepartment(department) {
    if (!window.confirm(`ยืนยันการลบแผนก ${department.name} หรือไม่?`)) return;
    setError("");
    try {
      await api.delete(`/departments/${department.id}`);
      if (selectedId === department.id) {
        setSelectedId("");
        setUsage(null);
      }
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setError(
        requestError?.response?.status === 409
          ? "ลบไม่ได้ เนื่องจากยังมีอุปกรณ์หรือข้อมูลเครือข่ายอ้างอิงแผนกนี้"
          : "ลบแผนกไม่สำเร็จ กรุณาลองอีกครั้ง",
      );
    }
  }

  const maxPeriods = { hour: 168, day: 90, month: 24 }[period];
  const totalUsage = departments
    .filter((department) => department.traffic_bytes_24h != null)
    .reduce((sum, department) => sum + department.traffic_bytes_24h, 0);
  const hasDepartmentUsage = departments.some(
    (department) => department.traffic_bytes_24h != null,
  );

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">วิเคราะห์การใช้งาน</div>
          <h1>แผนกและ VLAN</h1>
          <p>เปรียบเทียบปริมาณการใช้งานและดูสถิติรายชั่วโมง รายวัน หรือรายเดือน</p>
        </div>
        <div className="heading-actions">
          {dataMode && (
            <span className={`source-badge ${isDemo ? "source-demo" : "source-active"}`}>
              <span className="source-dot" />
              {isDemo ? "ข้อมูลสาธิต (DEMO DATA)" : "ข้อมูลจริง (LIVE)"}
            </span>
          )}
          {isAdmin && (
            <button type="button" className="primary-button" onClick={startCreate}>
              <Plus size={15} />เพิ่มแผนก
            </button>
          )}
          <button className="refresh-button" type="button" onClick={() => setRefreshKey((key) => key + 1)} disabled={isLoading}>
            <RefreshCw size={16} className={isLoading ? "spin" : ""} /><span>รีเฟรช</span>
          </button>
        </div>
      </div>

      <div className={`data-notice ${isDemo ? "data-notice-demo" : ""}`}>
        <Database size={16} />
        <span>
          {isDemo
            ? "DEMO DATA — สถิติเป็นข้อมูลจำลอง ไม่ใช่การใช้งานจริง"
            : "แสดงยอดใช้งานเฉพาะข้อมูลจากโหมดจริง แผนกที่ไม่มีข้อมูลจะแสดงเป็นไม่พบข้อมูล"}
        </span>
      </div>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} /><span>{error}</span>
          <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>ลองอีกครั้ง</button>
        </div>
      )}

      {isFormOpen && isAdmin && (
        <section className="panel editor-panel">
          <div className="panel-heading">
            <div className="panel-title-row"><Building2 size={17} /><h2>{editingId ? "แก้ไขแผนก" : "เพิ่มแผนก"}</h2></div>
            <button className="icon-button" type="button" aria-label="ปิดแบบฟอร์ม" onClick={() => setIsFormOpen(false)}><X size={17} /></button>
          </div>
          <form className="department-form" onSubmit={saveDepartment}>
            <label><span>รหัสแผนก</span><input required minLength="2" maxLength="32" pattern="[A-Za-z0-9_-]+" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></label>
            <label><span>ชื่อแผนก</span><input required minLength="2" maxLength="120" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label className="department-description"><span>รายละเอียด (ถ้ามี)</span><input maxLength="500" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
            <button className="primary-button" type="submit" disabled={isSaving}><Save size={15} />{isSaving ? "กำลังบันทึก..." : "บันทึกแผนก"}</button>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <div className="panel-title-row"><Building2 size={17} /><h2>เปรียบเทียบการใช้งานใน 24 ชั่วโมง</h2></div>
            <p>ยอดรวมจากระเบียน traffic ในโหมดข้อมูลปัจจุบัน</p>
          </div>
          <span className="chart-unit">รวม {formatBytes(hasDepartmentUsage ? totalUsage : null)}</span>
        </div>
        {departments.some((department) => department.traffic_bytes_24h != null) ? (
          <div className="department-analytics-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={departments.filter((department) => department.traffic_bytes_24h != null)} margin={{ top: 12, right: 12, left: 8, bottom: 4 }}>
                <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "#718091", fontSize: 10 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 10 }} tickFormatter={(value) => formatBytes(value)} />
                <Tooltip formatter={(value) => [formatBytes(value), "ปริมาณข้อมูล"]} />
                <Bar dataKey="traffic_bytes_24h" name="ปริมาณข้อมูล" fill="#438d78" radius={[5, 5, 0, 0]} barSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="analytics-empty">ไม่มีข้อมูลเปรียบเทียบการใช้งานตามแผนก</div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <div className="panel-title-row"><Building2 size={17} /><h2>ทะเบียนแผนก</h2></div>
            <p>เลือกแผนกเพื่อดูแนวโน้มการใช้งานและ VLAN</p>
          </div>
          <span className="chart-unit">{departments.length.toLocaleString("th-TH")} แผนก</span>
        </div>
        {isLoading && !departments.length ? (
          <div className="analytics-empty">กำลังโหลดข้อมูลแผนก...</div>
        ) : departments.length ? (
          <div className="data-table-wrap">
            <table className="data-table department-table">
              <thead><tr><th>แผนก</th><th>รหัส</th><th>อุปกรณ์</th><th>VLAN</th><th>ข้อมูล 24 ชม.</th>{isAdmin && <th>จัดการ</th>}</tr></thead>
              <tbody>
                {departments.map((department) => (
                  <tr key={department.id} className={selectedId === department.id ? "selected-row" : ""}>
                    <td>
                      <button className="department-select-button" type="button" onClick={() => setSelectedId(department.id)}>{department.name}</button>
                      <span className="table-secondary">{department.description || ""}</span>
                    </td>
                    <td className="table-mono">{department.code}</td>
                    <td>{department.device_count.toLocaleString("th-TH")}</td>
                    <td>{department.vlans.length ? department.vlans.map((vlan) => vlan.vlan_number).join(", ") : "—"}</td>
                    <td>{formatBytes(department.traffic_bytes_24h)}</td>
                    {isAdmin && (
                      <td>
                        <div className="table-actions">
                          <button className="icon-button" type="button" aria-label={`แก้ไข ${department.name}`} onClick={() => startEdit(department)}><Pencil size={15} /></button>
                          <button className="icon-button icon-danger" type="button" aria-label={`ลบ ${department.name}`} onClick={() => removeDepartment(department)}><Trash2 size={15} /></button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="analytics-empty">ยังไม่มีแผนกในทะเบียน</div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading department-usage-heading">
          <div>
            <div className="panel-title-row"><Building2 size={17} /><h2>{selectedDepartment ? `สถิติ ${selectedDepartment.name}` : "สถิติรายแผนก"}</h2></div>
            <p>ยอด traffic และ flow แยกกัน ไม่รวมซ้ำเป็นยอดเดียว</p>
          </div>
          <div className="usage-filter-row">
            <label><span>ช่วงข้อมูล</span>
              <select value={period} onChange={(event) => { const next = event.target.value; setPeriod(next); setPeriods(next === "hour" ? 24 : next === "day" ? 30 : 12); }}>
                <option value="hour">รายชั่วโมง</option><option value="day">รายวัน</option><option value="month">รายเดือน</option>
              </select>
            </label>
            <label><span>จำนวนช่วง</span><input type="number" min="1" max={maxPeriods} value={periods} onChange={(event) => setPeriods(Math.min(maxPeriods, Math.max(1, Number(event.target.value) || 1)))} /></label>
          </div>
        </div>
        {isUsageLoading ? (
          <div className="analytics-empty">กำลังโหลดสถิติ...</div>
        ) : chartData.length ? (
          <div className="department-analytics-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 12, right: 12, left: 8, bottom: 4 }}>
                <CartesianGrid stroke="#edf0f3" strokeDasharray="3 5" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#718091", fontSize: 9 }} minTickGap={30} />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "#8a93a1", fontSize: 10 }} tickFormatter={(value) => formatBytes(value)} />
                <Tooltip formatter={(value, name) => [formatBytes(value), name]} />
                <Legend />
                <Bar dataKey="ingress_bytes" name="ขาเข้า" fill="#438d78" barSize={12} />
                <Bar dataKey="egress_bytes" name="ขาออก" fill="#7187d8" barSize={12} />
                <Bar dataKey="flow_bytes" name="Flow metadata" fill="#d2a04b" barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="analytics-empty">ไม่มีข้อมูลการใช้งานในช่วงที่เลือก</div>
        )}
        {usage && (
          <div className="department-usage-summary">
            <span>Traffic {formatBytes(usage.total_traffic_bytes)}</span>
            <span>Flow {formatBytes(usage.flow_bytes)} · {usage.flow_count.toLocaleString("th-TH")} รายการ</span>
          </div>
        )}
      </section>
    </div>
  );
}

export default DepartmentsPage;
