const pad = (n: number) => String(n).padStart(2, "0");

/** 2026-11-09 (local date) */
export function fmtDate(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(d.getTime())) return value;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** 2026-11-09 14:32 (local time) */
export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${fmtDate(value)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const utcLabel = (value: string): string => `${new Date(value).toISOString().replace("T", " ").slice(0, 19)} UTC`;

export const shortHash = (hash: string | null | undefined, length = 10): string => (hash ? hash.slice(0, length) : "-");

export const titleCase = (value: string): string =>
  value
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

export function daysFromToday(value: string | null | undefined): number | null {
  if (!value) return null;
  const target = new Date(`${value.slice(0, 10)}T12:00:00`).getTime();
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  return Math.round((target - today.getTime()) / 86_400_000);
}

export const fileSize = (bytes: number): string => (bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`);

/** Risk priority number and level, the same rule as backend/app/services/risk.py. */
export function riskOf(
  severity: number | null,
  probability: number | null,
  detectability: number | null,
  highFrom = 12,
  mediumFrom = 6,
): { rpn: number; level: "low" | "medium" | "high" } | null {
  if (!severity || !probability || !detectability) return null;
  const rpn = severity * probability * detectability;
  return { rpn, level: rpn >= highFrom ? "high" : rpn >= mediumFrom ? "medium" : "low" };
}
