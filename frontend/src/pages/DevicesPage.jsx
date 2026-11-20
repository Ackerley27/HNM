import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  Clock3,
  Database,
  Pencil,
  Plus,
  RefreshCw,
  Router,
  Search,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { formatBandwidth, formatBytes, formatDateTime } from "../utils/formatters.js";

const DEVICE_TYPES = {
  router: "เราเตอร์",
  switch: "สวิตช์",
  firewall: "ไฟร์วอลล์",
  access_point: "จุดเชื่อมต่อ",
};

const DEVICE_STATUS = {
  online: "ออนไลน์",
  offline: "ออฟไลน์",
  unknown: "ไม่ทราบสถานะ",
  unavailable: "แหล่งข้อมูลไม่พร้อม",
};

const EMPTY_FORM = {
  name: "",
  hostname: "",
  ip_address: "",
  device_type: "switch",
  department_id: "",
  vlan_id: "",
  monitoring_enabled: true,
};

function DevicesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [devices, setDevices] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [dataMode, setDataMode] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [historyDevice, setHistoryDevice] = useState(null);
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState("");

  const load = useCallback(async (signal) => {
    setIsLoading(true);
    setError("");
    const params = {
      ...(search.trim() ? { search: search.trim() } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(typeFilter ? { device_type: typeFilter } : {}),
    };
    try {
      const [deviceResponse, departmentResponse, overviewResponse] = await Promise.all([
        api.get("/devices", { params, signal }),
        api.get("/departments", { signal }),
        api.get("/dashboard/overview", { signal }),
      ]);
      setDevices(deviceResponse.data);
      setDepartments(departmentResponse.data);
      setDataMode(overviewResponse.data.data_mode);
    } catch (requestError) {
      if (!axios.isCancel(requestError)) {
        setError(
          requestError?.response
            ? "โหลดทะเบียนอุปกรณ์ไม่สำเร็จ กรุณาลองอีกครั้ง"
            : "ไม่สามารถเชื่อมต่อ API ได้ ตรวจสอบสถานะเซิร์ฟเวอร์",
        );
      }
    } finally {
      if (!signal.aborted) setIsLoading(false);
    }
  }, [search, statusFilter, typeFilter]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, refreshKey]);

  function openCreateForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError("");
    setIsFormOpen(true);
  }

  function openEditForm(device) {
    setEditingId(device.id);
    setForm({
      name: device.name,
      hostname: device.hostname || "",
      ip_address: device.ip_address,
      device_type: device.device_type,
      department_id: device.department_id || "",
      vlan_id: device.vlan_id || "",
      monitoring_enabled: device.monitoring_enabled,
    });
    setFormError("");
    setIsFormOpen(true);
  }

  async function saveDevice(event) {
    event.preventDefault();
    setIsSaving(true);
    setFormError("");
    const payload = {
      ...form,
      hostname: form.hostname.trim() || null,
      department_id: form.department_id || null,
      vlan_id: form.vlan_id || null,
    };
    try {
      if (editingId) {
        await api.put(`/devices/${editingId}`, payload);
      } else {
        await api.post("/devices", payload);
      }
      setIsFormOpen(false);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setFormError(
        requestError?.response?.status === 409
          ? "IP Address นี้มีอยู่ในทะเบียนแล้ว"
          : requestError?.response?.status === 403
            ? "ต้องใช้สิทธิ์ผู้ดูแลระบบเพื่อจัดการอุปกรณ์"
            : "บันทึกอุปกรณ์ไม่สำเร็จ ตรวจสอบข้อมูลและลองอีกครั้ง",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function removeDevice(device) {
    if (!window.confirm(`ยืนยันการลบ ${device.name} ออกจากทะเบียนหรือไม่?`)) return;
    setError("");
    try {
      await api.delete(`/devices/${device.id}`);
      setRefreshKey((key) => key + 1);
    } catch {
      setError("ลบอุปกรณ์ไม่สำเร็จ กรุณาตรวจสอบสิทธิ์และลองอีกครั้ง");
    }
  }

  async function showHistory(device) {
    setHistoryDevice(device);
    setHistory(null);
    setHistoryError("");
    try {
      const response = await api.get(`/devices/${device.id}/history`, {
        params: { hours: 24 },
      });
      setHistory(response.data);
    } catch {
      setHistoryError("โหลดประวัติอุปกรณ์ไม่สำเร็จ");
    }
  }

  const selectedDepartment = departments.find(
    (department) => department.id === form.department_id,
  );
  const isDemo = dataMode === "demo";

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ทะเบียนเครือข่าย</div>
          <h1>อุปกรณ์เครือข่าย</h1>
          <p>ดูสถานะอุปกรณ์และข้อมูลเมตาที่ได้รับจากแหล่งตรวจวัด</p>
        </div>
        <div className="heading-actions">
          {dataMode && (
            <span className={`source-badge ${isDemo ? "source-demo" : "source-active"}`}>
              <span className="source-dot" />
              {isDemo ? "ข้อมูลสาธิต (DEMO DATA)" : "ข้อมูลจริง (LIVE)"}
            </span>
          )}
          {isAdmin && (
            <button type="button" className="primary-button" onClick={openCreateForm}>
              <Plus size={15} />เพิ่มอุปกรณ์
            </button>
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
            ? "DEMO DATA — อุปกรณ์ตัวอย่างไม่เชื่อมต่อกับฮาร์ดแวร์จริง"
            : "การเพิ่มหรือแก้ไขเป็นการจัดการทะเบียนเท่านั้น ไม่เปลี่ยนการตั้งค่าอุปกรณ์"}
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
            <div>
              <div className="panel-title-row"><Router size={17} /><h2>{editingId ? "แก้ไขข้อมูลอุปกรณ์" : "ลงทะเบียนอุปกรณ์"}</h2></div>
              <p>ข้อมูลนี้ใช้จัดหมวดหมู่การตรวจวัดเท่านั้น</p>
            </div>
            <button className="icon-button" type="button" aria-label="ปิดแบบฟอร์ม" onClick={() => setIsFormOpen(false)}>
              <X size={17} />
            </button>
          </div>
          {formError && <div className="dashboard-error" role="alert">{formError}</div>}
          <form className="device-form" onSubmit={saveDevice}>
            <label>
              <span>ชื่ออุปกรณ์</span>
              <input required minLength="2" maxLength="120" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label>
              <span>ที่อยู่ IP</span>
              <input required type="text" inputMode="decimal" value={form.ip_address} onChange={(event) => setForm({ ...form, ip_address: event.target.value })} placeholder="192.0.2.10" />
            </label>
            <label>
              <span>ชื่อโฮสต์ (ถ้ามี)</span>
              <input maxLength="253" value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} />
            </label>
            <label>
              <span>ประเภทอุปกรณ์</span>
              <select value={form.device_type} onChange={(event) => setForm({ ...form, device_type: event.target.value })}>
                {Object.entries(DEVICE_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              <span>แผนก</span>
              <select value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value, vlan_id: "" })}>
                <option value="">ไม่ระบุ</option>
                {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
              </select>
            </label>
            <label>
              <span>VLAN</span>
              <select value={form.vlan_id} onChange={(event) => setForm({ ...form, vlan_id: event.target.value })} disabled={!selectedDepartment?.vlans.length}>
                <option value="">ไม่ระบุ</option>
                {(selectedDepartment?.vlans || []).map((vlan) => (
                  <option key={vlan.id} value={vlan.id}>{vlan.vlan_number} · {vlan.name}</option>
                ))}
              </select>
            </label>
            <label className="device-monitor-toggle">
              <input type="checkbox" checked={form.monitoring_enabled} onChange={(event) => setForm({ ...form, monitoring_enabled: event.target.checked })} />
              <span>เปิดใช้งานการตรวจวัด</span>
            </label>
            <div className="device-form-actions">
              <button type="button" className="secondary-button" onClick={() => setIsFormOpen(false)}>ยกเลิก</button>
              <button type="submit" className="primary-button" disabled={isSaving}>
                {isSaving ? "กำลังบันทึก..." : "บันทึกข้อมูล"}
              </button>
            </div>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="device-filter-row">
          <label className="device-search">
            <Search size={16} />
            <input aria-label="ค้นหาอุปกรณ์" placeholder="ค้นหาชื่อ โฮสต์ หรือ IP" value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <label>
            <span className="sr-only">กรองประเภทอุปกรณ์</span>
            <select aria-label="กรองประเภทอุปกรณ์" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
              <option value="">ทุกประเภท</option>
              {Object.entries(DEVICE_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>
            <span className="sr-only">กรองสถานะ</span>
            <select aria-label="กรองสถานะ" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">ทุกสถานะ</option>
              {Object.entries(DEVICE_STATUS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </div>
        {isLoading && !devices.length ? (
          <div className="analytics-empty">กำลังโหลดทะเบียนอุปกรณ์...</div>
        ) : devices.length ? (
          <div className="data-table-wrap">
            <table className="data-table device-table">
              <thead>
                <tr><th>อุปกรณ์</th><th>ที่อยู่ IP</th><th>ประเภท</th><th>แผนก / VLAN</th><th>สถานะ</th><th>CPU / หน่วยความจำ</th><th>ตรวจพบล่าสุด</th>{isAdmin && <th>จัดการ</th>}</tr>
              </thead>
              <tbody>
                {devices.map((device) => (
                  <tr key={device.id}>
                    <td><strong>{device.name}</strong><span className="table-secondary">{device.hostname || "ไม่ทราบชื่อโฮสต์"}</span></td>
                    <td className="table-mono">{device.ip_address}</td>
                    <td>{DEVICE_TYPES[device.device_type]}</td>
                    <td>{device.department_name || "ไม่ระบุ"}{device.vlan_number && <span className="table-secondary">VLAN {device.vlan_number}</span>}</td>
                    <td><span className={`device-status status-${device.status}`}>{DEVICE_STATUS[device.status]}</span></td>
                    <td>CPU {device.cpu_percent == null ? "—" : `${device.cpu_percent}%`}<span className="table-secondary">หน่วยความจำ {device.memory_percent == null ? "—" : `${device.memory_percent}%`}</span></td>
                    <td>{device.last_seen_at ? formatDateTime(device.last_seen_at) : "—"}</td>
                    <td>
                      <div className="table-actions">
                        <button className="secondary-button" type="button" onClick={() => showHistory(device)}>ประวัติ</button>
                        {isAdmin && (
                          <>
                            <button className="icon-button" type="button" aria-label={`แก้ไข ${device.name}`} onClick={() => openEditForm(device)}><Pencil size={15} /></button>
                            <button className="icon-button icon-danger" type="button" aria-label={`ลบ ${device.name}`} onClick={() => removeDevice(device)}><Trash2 size={15} /></button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="analytics-empty">ไม่พบอุปกรณ์ตามตัวกรองที่เลือก</div>
        )}
      </section>

      {historyDevice && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-title-row"><Clock3 size={17} /><h2>ประวัติของ {historyDevice.name}</h2></div>
              <p>ข้อมูลเมตาย้อนหลัง 24 ชั่วโมงจากแหล่งตรวจวัดที่เลือก</p>
            </div>
            <button className="icon-button" type="button" aria-label="ปิดประวัติ" onClick={() => { setHistoryDevice(null); setHistory(null); }}>
              <X size={17} />
            </button>
          </div>
          {historyError ? (
            <div className="dashboard-error" role="alert">{historyError}</div>
          ) : !history ? (
            <div className="analytics-empty">กำลังโหลดประวัติ...</div>
          ) : (
            <div className="device-history-grid">
              <div>
                <h3>CPU / Memory</h3>
                {history.metrics.length ? (
                  <div className="data-table-wrap">
                    <table className="data-table">
                      <thead><tr><th>ตัวชี้วัด</th><th>ค่า</th><th>เวลา</th></tr></thead>
                      <tbody>{history.metrics.map((metric, index) => (
                        <tr key={`${metric.metric_name}-${metric.recorded_at}-${index}`}>
                          <td>{metric.metric_name === "cpu_percent" ? "CPU" : "หน่วยความจำ"}</td>
                          <td>{metric.value} {metric.unit}</td>
                          <td>{formatDateTime(metric.recorded_at)}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                ) : <div className="analytics-empty">ไม่มีข้อมูลตัวชี้วัดจากแหล่งตรวจวัด</div>}
              </div>
              <div>
                <h3>ปริมาณการจราจร</h3>
                {history.traffic.length ? (
                  <div className="data-table-wrap">
                    <table className="data-table">
                      <thead><tr><th>ทิศทาง</th><th>ปริมาณ</th><th>อัตรา</th><th>เวลา</th></tr></thead>
                      <tbody>{history.traffic.map((record, index) => (
                        <tr key={`${record.interval_start}-${index}`}>
                          <td>{record.direction === "ingress" ? "ขาเข้า" : "ขาออก"}</td>
                          <td>{formatBytes(record.bytes_transferred)}</td>
                          <td>{formatBandwidth(record.bit_rate_bps)}</td>
                          <td>{formatDateTime(record.interval_start)}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                ) : <div className="analytics-empty">ไม่มีข้อมูลการจราจร</div>}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export default DevicesPage;
