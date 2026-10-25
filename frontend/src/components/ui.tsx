import type { ReactNode } from "react";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">{label}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
    >
      {message}
    </div>
  );
}

export function Select<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <label className="flex flex-col text-xs text-slate-500 dark:text-slate-400">
      {label}
      <select
        value={String(value)}
        aria-label={label || undefined}
        onChange={(e) => {
          const picked = options.find((o) => String(o.value) === e.target.value);
          if (picked) onChange(picked.value);
        }}
        className={`${label ? "mt-1 " : ""}rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100`}
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-end gap-3">{children}</div>;
}

/** FPL's fixture difficulty colours: 1-2 easy (green), 3 neutral, 4-5 hard (red). */
export function fdrClass(difficulty: number): string {
  switch (difficulty) {
    case 1:
      return "bg-emerald-600 text-white";
    case 2:
      return "bg-emerald-200 text-emerald-950 dark:bg-emerald-800 dark:text-emerald-50";
    case 3:
      return "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100";
    case 4:
      return "bg-rose-300 text-rose-950 dark:bg-rose-800 dark:text-rose-50";
    default:
      return "bg-rose-700 text-white";
  }
}

export const POSITION_OPTIONS = [
  { value: "", label: "All positions" },
  { value: "GKP", label: "Goalkeepers" },
  { value: "DEF", label: "Defenders" },
  { value: "MID", label: "Midfielders" },
  { value: "FWD", label: "Forwards" },
];

export const PRICE_OPTIONS = [
  { value: 0, label: "Any price" },
  ...[45, 50, 55, 60, 65, 70, 80, 90, 100].map((v) => ({ value: v, label: `Up to £${(v / 10).toFixed(1)}m` })),
];

export function horizonOptions(max = 8) {
  return Array.from({ length: max }, (_, i) => ({
    value: i + 1,
    label: i === 0 ? "Next gameweek" : `Next ${i + 1} gameweeks`,
  }));
}
