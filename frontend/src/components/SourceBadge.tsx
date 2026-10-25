import type { Source } from "../api";

const STYLES: Record<Source, { label: string; className: string }> = {
  api: { label: "From FPL", className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
  derived: { label: "Derived", className: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300" },
  user_override: { label: "Set by you", className: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300" },
};

/** Says where a number came from, so derived estimates are never mistaken for FPL's own figures. */
export function SourceBadge({ source, note }: { source: Source; note?: string | null }) {
  const style = STYLES[source];
  return (
    <span
      title={note ?? undefined}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${style.className}`}
    >
      {style.label}
    </span>
  );
}
