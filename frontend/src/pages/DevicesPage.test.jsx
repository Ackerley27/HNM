import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DevicesPage from "./DevicesPage.jsx";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";

vi.mock("../services/api.js", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: vi.fn(),
}));

const device = {
  id: "device-1",
  name: "Core switch",
  hostname: "core.example.invalid",
  ip_address: "192.0.2.10",
  device_type: "switch",
  department_id: null,
  department_name: null,
  vlan_id: null,
  vlan_number: null,
  status: "online",
  source: "demo",
  monitoring_enabled: true,
  last_seen_at: "2026-11-20T03:00:00Z",
  cpu_percent: null,
  memory_percent: null,
};

describe("device inventory page", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { role: "admin" } });
    api.get.mockImplementation((path) => {
      if (path === "/devices") return Promise.resolve({ data: [device] });
      if (path === "/departments") return Promise.resolve({ data: [] });
      if (path === "/dashboard/overview") {
        return Promise.resolve({ data: { data_mode: "demo" } });
      }
      if (path.endsWith("/history")) {
        return Promise.resolve({
          data: { metrics: [], traffic: [], window_hours: 24 },
        });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it("labels demo inventory and loads API-backed device history", async () => {
    const user = userEvent.setup();
    render(<DevicesPage />);

    expect(await screen.findByText("Core switch")).toBeInTheDocument();
    expect(screen.getByText(/DEMO DATA — อุปกรณ์ตัวอย่าง/)).toBeInTheDocument();
    expect(screen.getAllByText("ออนไลน์").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "ประวัติ" }));
    expect(await screen.findByText("ประวัติของ Core switch")).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      "/devices/device-1/history",
      { params: { hours: 24 } },
    ));
  });

  it("lets administrators submit a device record without treating it as measured", async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { ...device, status: "unknown" } });
    render(<DevicesPage />);

    await user.click(await screen.findByRole("button", { name: /เพิ่มอุปกรณ์/ }));
    await user.type(screen.getByLabelText("ชื่ออุปกรณ์"), "Ward switch");
    await user.type(screen.getByLabelText("ที่อยู่ IP"), "192.0.2.12");
    await user.click(screen.getByRole("button", { name: "บันทึกข้อมูล" }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      "/devices",
      expect.objectContaining({
        name: "Ward switch",
        ip_address: "192.0.2.12",
      }),
    ));
    expect(api.post.mock.calls[0][1]).not.toHaveProperty("status");
  });
});
