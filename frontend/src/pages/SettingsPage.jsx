import { useEffect, useState } from "react";
import axios from "axios";
import {
  Database,
  RefreshCw,
  Server,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { api } from "../services/api.js";

function SettingsPage() {
  const [overview, setOverview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError("");
    api.get("/dashboard/overview", { signal: controller.signal })
      .then((response) => setOverview(response.data))
      .catch((requestError) => {
        if (!axios.isCancel(requestError)) {
          setError("โหลดสถานะการตั้งค่าการตรวจวัดไม่สำเร็จ");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const isDemo = overview?.data_mode === "demo";
  const services = overview?.monitoring_services || [];

  return (
    <div className="dashboard-page analytics-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">การกำหนดค่าระบบ</div>
          <h1>ตั้งค่าระบบและแหล่งตรวจวัด</h1>
          <p>ดูโหมดข้อมูลและสถานะแหล่งตรวจวัดโดยไม่เผยข้อมูลรับรอง</p>
        </div>
        <button
          type="button"
          className="refresh-button"
          onClick={() => setRefreshKey((key) => key + 1)}
          disabled={isLoading}
        >
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />
          <span>รีเฟรช</span>
        </button>
      </div>

      {error && (
        <div className="dashboard-error" role="alert">
          <TriangleAlert size={18} /><span>{error}</span>
        </div>
      )}

      {isLoading && !overview ? (
        <div className="panel analytics-empty">กำลังโหลดสถานะการตรวจวัด...</div>
      ) : (
        <>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><Database size={17} /><h2>โหมดข้อมูล</h2></div>
                <p>โหมดนี้กำหนดที่ระบบเซิร์ฟเวอร์ แก้ไขผ่านสภาพแวดล้อมเท่านั้น</p>
              </div>
              {overview && (
                <span className={`source-badge ${isDemo ? "source-demo" : "source-active"}`}>
                  <span className="source-dot" />
                  {isDemo ? "DEMO DATA" : "LIVE"}
                </span>
              )}
            </div>
            <div className="settings-mode-copy">
              {isDemo
                ? "โหมดสาธิตสร้างข้อมูลจำลองเพื่อทดสอบหน้าใช้งาน ข้อมูลเหล่านี้จะไม่แสดงว่าส่งมาจากอุปกรณ์จริง"
                : "โหมดจริงใช้เฉพาะข้อมูลที่ได้รับจากแหล่งตรวจวัดที่อนุญาตและบันทึกไว้ ไม่เติมค่าจำลอง"}
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><Server size={17} /><h2>แหล่งตรวจวัด</h2></div>
                <p>สถานะการเชื่อมต่อไม่แสดง URL หรือข้อมูลรับรอง</p>
              </div>
            </div>
            {services.length ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead><tr><th>แหล่งข้อมูล</th><th>สถานะ</th><th>ตรวจสอบล่าสุด</th></tr></thead>
                  <tbody>
                    {services.map((service) => (
                      <tr key={service.name}>
                        <td>{service.name}</td>
                        <td>
                          <span className={`device-status status-${service.status === "connected" ? "online" : service.status === "unavailable" ? "unavailable" : "unknown"}`}>
                            {service.status === "connected" ? "เชื่อมต่อ" : service.status === "unavailable" ? "ไม่พร้อมใช้งาน" : "ไม่ทราบสถานะ"}
                          </span>
                        </td>
                        <td>{service.last_checked_at || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="analytics-empty">
                {isDemo ? "โหมดสาธิตไม่ได้อ้างอิงการเชื่อมต่อภายนอก" : "ไม่มีแหล่งตรวจวัดที่ตรวจพบ หรือแหล่งข้อมูลไม่พร้อมใช้งาน"}
              </div>
            )}
          </section>

          <section className="panel settings-security-panel">
            <div className="panel-heading">
              <div>
                <div className="panel-title-row"><ShieldCheck size={17} /><h2>นโยบายการเข้าถึง</h2></div>
                <p>การเปลี่ยนบัญชีสิทธิ์และข้อมูลรับรองทำผ่านกระบวนการบริหารระบบ</p>
              </div>
            </div>
            <ul className="settings-list">
              <li>บทบาทผู้ดูแลระบบเท่านั้นที่จัดการบัญชี อุปกรณ์ แผนก และเกณฑ์การแจ้งเตือน</li>
              <li>ระบบใช้การตรวจสอบ JWT และบันทึกการกระทำผู้ดูแลระบบ</li>
              <li>ข้อมูลรับรอง Zabbix ntopng และ SNMP เก็บเฉพาะฝั่งเซิร์ฟเวอร์</li>
              <li>ไม่มีการดึงเนื้อหาแพ็กเก็ต รหัสผ่าน หรือเนื้อหาการท่องเว็บ</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

export default SettingsPage;
