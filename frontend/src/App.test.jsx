import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { api, setAccessToken } from "./services/api.js";

vi.mock("./services/api.js", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
  setAccessToken: vi.fn(),
}));

function renderApp(initialPath = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("application authentication flow", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated visitors to the Thai login page", async () => {
    renderApp();
    expect(await screen.findByRole("heading", { name: "ยินดีต้อนรับ" })).toBeInTheDocument();
    expect(screen.getByLabelText("อีเมลผู้ใช้งาน")).toBeInTheDocument();
  });

  it("logs in through the API and opens the protected dashboard", async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValueOnce({ data: { access_token: "test-token" } });
    api.get.mockImplementation(async (path) => {
      if (path === "/auth/me") {
        return {
          data: {
            id: "c4c9a9e3-1b0d-4c93-b4dc-2a1591285038",
            email: "it.admin@hospital.org",
            role: "admin",
          },
        };
      }
      if (path === "/dashboard/overview") {
        return {
          data: {
            generated_at: "2026-11-20T03:00:00Z",
            data_mode: "demo",
            total_devices: 0,
            online_devices: 0,
            offline_devices: 0,
            unknown_devices: 0,
            unavailable_devices: 0,
            download_bps: null,
            upload_bps: null,
            traffic_bytes_24h: null,
            availability_percent: null,
            department_usage: [],
            recent_alerts: [],
            monitoring_services: [],
          },
        };
      }
      if (path.startsWith("/dashboard/traffic")) {
        return { data: { window_hours: 24, has_data: false, points: [] } };
      }
      return {
        data: { total: 0, online: 0, offline: 0, unknown: 0, unavailable: 0 },
      };
    });

    renderApp("/login");
    await user.type(screen.getByLabelText("อีเมลผู้ใช้งาน"), "it.admin@hospital.org");
    await user.type(screen.getByLabelText("รหัสผ่าน"), "secure-password");
    await user.click(screen.getByRole("button", { name: "เข้าสู่ระบบ" }));

    expect(await screen.findByRole(
      "heading",
      { name: "ภาพรวมเครือข่าย" },
      { timeout: 5000 },
    )).toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith("/auth/login", {
      email: "it.admin@hospital.org",
      password: "secure-password",
    });
    expect(setAccessToken).toHaveBeenCalledWith("test-token");
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/dashboard/overview", expect.any(Object)));
    expect(screen.getByText(/DEMO DATA — ข้อมูลจำลองเพื่อการสาธิต/)).toBeInTheDocument();
  });
});
