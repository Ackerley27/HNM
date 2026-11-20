import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "./AlertsPage.jsx";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";

vi.mock("../services/api.js", () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: vi.fn(),
}));

describe("alert management page", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { role: "admin" } });
    api.get.mockImplementation((path) => {
      if (path === "/alerts") {
        return Promise.resolve({
          data: [{
            id: "alert-1",
            title: "อุปกรณ์ออฟไลน์",
            description: "ตรวจพบอุปกรณ์ที่ไม่ตอบสนอง",
            severity: "critical",
            status: "open",
            detected_at: "2026-11-20T03:00:00Z",
          }],
        });
      }
      if (path === "/alerts/thresholds") {
        return Promise.resolve({
          data: {
            high_bandwidth_bps: 500000000,
            unusual_traffic_multiplier: 3,
            unusual_traffic_min_bps: 5000000,
            offline_detection_enabled: true,
          },
        });
      }
      return Promise.resolve({ data: { data_mode: "live" } });
    });
    api.patch.mockResolvedValue({ data: { status: "acknowledged" } });
  });

  it("shows alerts and lets administrators acknowledge them", async () => {
    const user = userEvent.setup();
    render(<AlertsPage />);

    expect(await screen.findByText("อุปกรณ์ออฟไลน์")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "รับทราบ" }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
      "/alerts/alert-1/status",
      { status: "acknowledged" },
    ));
    expect(await screen.findByText("บันทึกการรับทราบแล้ว")).toBeInTheDocument();
  });

  it("does not display default thresholds when the API cannot provide them", async () => {
    api.get.mockImplementation((path) => {
      if (path === "/alerts/thresholds") {
        return Promise.reject(new Error("API unavailable"));
      }
      if (path === "/alerts") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: { data_mode: "live" } });
    });

    render(<AlertsPage />);

    expect(await screen.findByText("ไม่สามารถโหลดเกณฑ์การแจ้งเตือนได้")).toBeInTheDocument();
    expect(screen.queryByLabelText("แบนด์วิดท์สูง (bps)")).not.toBeInTheDocument();
  });
});
