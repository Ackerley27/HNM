import { describe, expect, it } from "vitest";
import { formatBandwidth, formatBytes } from "./formatters.js";

describe("dashboard formatters", () => {
  it("keeps unavailable measurements distinct from zero", () => {
    expect(formatBandwidth(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
    expect(formatBandwidth(0)).toContain("bps");
    expect(formatBytes(0)).toContain("B");
  });

  it("formats measured bandwidth and traffic with units", () => {
    expect(formatBandwidth(1_500_000)).toContain("Mbps");
    expect(formatBytes(2_500_000)).toContain("MB");
  });
});
