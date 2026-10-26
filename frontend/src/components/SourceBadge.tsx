import type { Source } from "../api";

const STYLES: Record<Source, { label: string; className: string }> = {
  api: { label: "From FPL", className: "bg-raised text-muted" },
  derived: { label: "Derived", className: "bg-warn/20 text-warn" },
  user_override: { label: "Set by you", className: "bg-raised text-accent" },
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
