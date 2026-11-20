import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TrafficPage from "./TrafficPage.jsx";
import { api } from "../services/api.js";

vi.mock("../services/api.js", () => ({
  api: { get: vi.fn() },
}));

describe("traffic analytics page", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockImplementation((path) => {
      if (path === "/traffic/summary") {
        return Promise.resolve({
          data: {
            data_mode: "demo",
            download_bytes: 4096,
            upload_bytes: null,
            current_download_bps: 64000,
            current_upload_bps: null,
            flow_count: 0,
            flow_bytes: null,
          },
        });
      }
      if (path === "/traffic/history") {
        return Promise.resolve({
          data: {
            has_data: false,
            points: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it("loads API analytics and explicitly labels simulated data", async () => {
    render(<TrafficPage />);

    expect(await screen.findByRole("heading", { name: "วิเคราะห์การใช้งานเครือข่าย" }))
      .toBeInTheDocument();
    expect(await screen.findByText(/DEMO DATA — ข้อมูลจำลอง/)).toBeInTheDocument();
    expect(screen.getByText("4.1 kB")).toBeInTheDocument();
    expect(screen.getByLabelText("ช่วงเวลา")).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      "/traffic/summary",
      expect.objectContaining({ params: { hours: 24 } }),
    ));
  });
});
