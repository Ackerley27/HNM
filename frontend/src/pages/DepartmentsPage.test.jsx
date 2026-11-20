import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DepartmentsPage from "./DepartmentsPage.jsx";
import { api } from "../services/api.js";
import { useAuth } from "../context/AuthContext.jsx";

vi.mock("../services/api.js", () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: vi.fn(),
}));

describe("department analytics page", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { role: "viewer" } });
    api.get.mockImplementation((path) => {
      if (path === "/departments") {
        return Promise.resolve({
          data: [{
            id: "department-1",
            code: "CARD",
            name: "แผนกหัวใจ",
            description: null,
            device_count: 2,
            traffic_bytes_24h: 2048,
            vlans: [],
          }],
        });
      }
      if (path === "/dashboard/overview") {
        return Promise.resolve({ data: { data_mode: "live" } });
      }
      if (path === "/departments/department-1/usage") {
        return Promise.resolve({
          data: {
            department_id: "department-1",
            department_name: "แผนกหัวใจ",
            data_mode: "live",
            period: "day",
            period_count: 30,
            ingress_bytes: 2048,
            egress_bytes: null,
            total_traffic_bytes: 2048,
            flow_bytes: null,
            flow_count: 0,
            points: [],
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
  });

  it("loads department totals and requests usage for the selected department", async () => {
    render(<DepartmentsPage />);

    expect(await screen.findByRole("heading", { name: "แผนกและ VLAN" })).toBeInTheDocument();
    expect(await screen.findByText("แผนกหัวใจ")).toBeInTheDocument();
    expect(screen.getAllByText("2 kB").length).toBeGreaterThan(0);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      "/departments/department-1/usage",
      expect.objectContaining({ params: { period: "day", periods: 30 } }),
    ));
  });
});
