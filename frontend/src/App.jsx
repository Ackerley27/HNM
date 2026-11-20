import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import AppLayout from "./layouts/AppLayout.jsx";
import ComingSoonPage from "./pages/ComingSoonPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";

const DashboardPage = lazy(() => import("./pages/DashboardPage.jsx"));
const TrafficPage = lazy(() => import("./pages/TrafficPage.jsx"));
const AlertsPage = lazy(() => import("./pages/AlertsPage.jsx"));
const DepartmentsPage = lazy(() => import("./pages/DepartmentsPage.jsx"));
const DevicesPage = lazy(() => import("./pages/DevicesPage.jsx"));
const ReportsPage = lazy(() => import("./pages/ReportsPage.jsx"));
const SettingsPage = lazy(() => import("./pages/SettingsPage.jsx"));

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมข้อมูลภาพรวม...</div>}>
                <DashboardPage />
              </Suspense>
            }
          />
          <Route
            path="/traffic"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมข้อมูลการจราจร...</div>}>
                <TrafficPage />
              </Suspense>
            }
          />
          <Route
            path="/departments"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมข้อมูลแผนก...</div>}>
                <DepartmentsPage />
              </Suspense>
            }
          />
          <Route
            path="/devices"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมทะเบียนอุปกรณ์...</div>}>
                <DevicesPage />
              </Suspense>
            }
          />
          <Route
            path="/alerts"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมข้อมูลการแจ้งเตือน...</div>}>
                <AlertsPage />
              </Suspense>
            }
          />
          <Route
            path="/reports"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมรายงาน...</div>}>
                <ReportsPage />
              </Suspense>
            }
          />
          <Route
            path="/settings"
            element={
              <Suspense fallback={<div className="page-loading">กำลังเตรียมการตั้งค่าระบบ...</div>}>
                <SettingsPage />
              </Suspense>
            }
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
