/** Tenths of £1m (FPL's unit) to "£8.5m". */
export function money(tenths: number): string {
  return `£${(tenths / 10).toFixed(1)}m`;
}

export function rank(n: number | null): string {
  return n == null ? "–" : n.toLocaleString("en-GB");
}

export const STATUS_LABELS: Record<string, string> = {
  a: "Available",
  d: "Doubtful",
  i: "Injured",
  s: "Suspended",
  u: "Unavailable",
  n: "Not in squad",
};
