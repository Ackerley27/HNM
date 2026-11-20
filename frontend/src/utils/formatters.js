export function formatBandwidth(bitsPerSecond) {
  if (bitsPerSecond === null || bitsPerSecond === undefined) return "—";
  const units = [
    { limit: 1_000_000_000, suffix: "Gbps" },
    { limit: 1_000_000, suffix: "Mbps" },
    { limit: 1_000, suffix: "Kbps" },
  ];
  const unit = units.find(({ limit }) => bitsPerSecond >= limit);
  if (!unit) return `${new Intl.NumberFormat("th-TH").format(bitsPerSecond)} bps`;
  return `${new Intl.NumberFormat("th-TH", { maximumFractionDigits: 1 }).format(
    bitsPerSecond / unit.limit,
  )} ${unit.suffix}`;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1000) return `${new Intl.NumberFormat("th-TH").format(bytes)} B`;
  const units = ["kB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = -1;
  do {
    value /= 1000;
    unitIndex += 1;
  } while (value >= 1000 && unitIndex < units.length - 1);
  return `${new Intl.NumberFormat("th-TH", { maximumFractionDigits: 1 }).format(
    value,
  )} ${units[unitIndex]}`;
}

export function formatDateTime(value) {
  if (!value) return "ไม่พบข้อมูลเวลา";
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatTime(value) {
  return new Intl.DateTimeFormat("th-TH", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
