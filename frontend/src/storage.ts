/**
 * Remembered settings on this device only (the team ID, a hand-entered squad, dismissed hints).
 * Storage can be unavailable (private browsing, blocked site data), so every access is
 * guarded and the app works without it.
 */
export const KEYS = {
  teamId: "fpl.teamId",
  manualSquad: "fpl.manualSquad",
  mode: "fpl.mode",
  installHintDismissed: "fpl.installHintDismissed",
} as const;

export function load<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw == null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

export function save(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Not remembered; the app still works.
  }
}

export function forget(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Nothing to do.
  }
}
