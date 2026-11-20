import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ReportsPage from "./ReportsPage.jsx";
import { api } from "../services/api.js";

vi.mock("../services/api.js", () => ({
  api: { get: vi.fn() },
}));

const report = {
  data_mode: "demo",
  period_start: "2026-11-20T00:00:00Z",
  period_end: "2026-11-21T00:00:00Z",
  traffic_bytes: 1200,
  download_bytes: 800,
  upload_bytes: 400,
  flow_bytes: 300,
  flow_count: 2,
  total_devices: 2,
  online_devices: 1,
  offline_devices: 1,
  unknown_devices: 0,
  unavailable_devices: 0,
  department_usage: [],
};

describe("network reports page", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((path) => {
      if (path === "/reports/export") {
        return Promise.resolve({ data: new Blob(["report"]) });
      }
      return Promise.resolve({ data: report });
    });
  });

  it("shows a clear demo label and requests a CSV export", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<ReportsPage />);

    expect(await screen.findByRole("heading", { name: "รายงานเครือข่าย" })).toBeInTheDocument();
    expect(await screen.findByText(/DEMO DATA — รายงานนี้สรุปข้อมูลจำลอง/)).toBeInTheDocument();
    expect(screen.getByText("1.2 kB")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "ส่งออก CSV" }));

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      "/reports/export",
      expect.objectContaining({
        params: expect.objectContaining({ period: "daily" }),
        responseType: "blob",
      }),
    ));
    expect(createObjectURL).toHaveBeenCalled();
  });
});
