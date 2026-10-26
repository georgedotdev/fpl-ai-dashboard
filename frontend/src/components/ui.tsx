import type { ReactNode } from "react";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="py-6 text-center text-sm text-faint">{label}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-xl bg-negative/15 p-3 text-sm text-negative">
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
    <label className="flex flex-col text-xs text-faint">
      {label}
      <select
        value={String(value)}
        aria-label={label || undefined}
        onChange={(e) => {
          const picked = options.find((o) => String(o.value) === e.target.value);
          if (picked) onChange(picked.value);
        }}
        className={`${label ? "mt-1 " : ""}h-9 rounded-full border-0 bg-raised px-3 text-sm text-ink focus:ring-2 focus:ring-accent`}
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

/** FPL's own fixture difficulty colours, 1 (easy) to 5 (hard). */
export function fdrClass(difficulty: number): string {
  switch (difficulty) {
    case 1:
      return "bg-d1 text-d1-ink";
    case 2:
      return "bg-d2 text-d2-ink";
    case 3:
      return "bg-d3 text-d3-ink";
    case 4:
      return "bg-d4 text-d4-ink";
    default:
      return "bg-d5 text-d5-ink";
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
