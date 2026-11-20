import { useState } from "react";
import {
  Activity,
  Bell,
  Building2,
  ChartNoAxesCombined,
  ChevronDown,
  FileText,
  Gauge,
  LogOut,
  Menu,
  Router,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const navigation = [
  { to: "/dashboard", label: "ภาพรวม", icon: Gauge },
  { to: "/traffic", label: "วิเคราะห์การจราจร", icon: ChartNoAxesCombined },
  { to: "/departments", label: "แผนก", icon: Building2 },
  { to: "/devices", label: "อุปกรณ์เครือข่าย", icon: Router },
  { to: "/alerts", label: "การแจ้งเตือน", icon: Bell },
  { to: "/reports", label: "รายงาน", icon: FileText },
];

const routeTitles = {
  "/dashboard": "ภาพรวมเครือข่าย",
  "/traffic": "วิเคราะห์การจราจร",
  "/departments": "วิเคราะห์รายแผนก",
  "/devices": "อุปกรณ์เครือข่าย",
  "/alerts": "การแจ้งเตือน",
  "/reports": "รายงาน",
  "/settings": "ตั้งค่าระบบ",
};

export default function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  async function handleLogout() {
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      navigate("/login", {
        replace: true,
        state: {
          message:
            "ออกจากระบบในอุปกรณ์นี้แล้ว แต่ไม่สามารถยืนยันการปิดโทเคนบนเซิร์ฟเวอร์ได้",
        },
      });
    }
  }

  function closeSidebar() {
    setSidebarOpen(false);
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button
          className="mobile-backdrop"
          type="button"
          aria-label="ปิดเมนู"
          onClick={closeSidebar}
        />
      )}
      <aside id="app-sidebar" className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={21} strokeWidth={2.5} /></div>
          <div>
            <div className="brand-name">เครือข่าย<span>สุขภาพ</span></div>
            <div className="brand-caption">ศูนย์ปฏิบัติการเครือข่าย</div>
          </div>
          <button
            className="sidebar-close"
            type="button"
            aria-label="ปิดเมนู"
            onClick={closeSidebar}
          >
            <X size={20} />
          </button>
        </div>

        <div className="sidebar-label">เมนูหลัก</div>
        <nav className="side-nav" aria-label="เมนูหลัก">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              onClick={closeSidebar}
            >
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            onClick={closeSidebar}
          >
            <Settings size={18} strokeWidth={1.8} />
            <span>ตั้งค่าระบบ</span>
          </NavLink>
        </nav>

        <div className="sidebar-spacer" />
        <div className="connection-card">
          <div className="connection-icon"><ShieldCheck size={17} /></div>
          <div>
            <strong>คำนึงถึงความเป็นส่วนตัว</strong>
            <span>ใช้ข้อมูลเมตาเครือข่ายเท่านั้น</span>
          </div>
          <span className="status-dot" />
        </div>
        <div className="sidebar-footer">
          <span>ระบบเฝ้าระวังเครือข่าย</span>
          <span>รุ่นทดลอง 0.1</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="menu-toggle"
              type="button"
              aria-label="เปิดเมนู"
              aria-controls="app-sidebar"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={21} />
            </button>
            <div className="breadcrumb">
              <span>ระบบเครือข่าย</span>
              <span className="breadcrumb-divider">/</span>
              <strong>{routeTitles[location.pathname] || "ภาพรวมเครือข่าย"}</strong>
            </div>
          </div>
          <div className="topbar-right">
            <div className="user-chip">
              <div className="avatar">{(user?.email?.[0] || "ผ").toUpperCase()}</div>
              <div className="user-details">
                <strong>{user?.email}</strong>
                <span>{user?.role === "admin" ? "ผู้ดูแลระบบ" : "ผู้เข้าชม"}</span>
              </div>
              <ChevronDown size={15} className="user-chevron" />
            </div>
            <button className="logout-button" type="button" onClick={handleLogout} title="ออกจากระบบ">
              <LogOut size={17} />
              <span>ออกจากระบบ</span>
            </button>
          </div>
        </header>
        <main className="page-content"><Outlet /></main>
      </div>
    </div>
  );
}
