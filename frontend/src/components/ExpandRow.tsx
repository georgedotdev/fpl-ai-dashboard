import { useId, useState, type ReactNode } from "react";

/** A home-page row: one line of summary that expands in place to the full detail. */
export function ExpandRow({
  title,
  summary,
  value,
  valueTone = "ink",
  defaultOpen = false,
  children,
}: {
  title: string;
  summary?: ReactNode;
  value?: ReactNode;
  valueTone?: "ink" | "accent";
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section className="overflow-hidden rounded-[18px] bg-surface">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="grid min-h-16 w-full grid-cols-[1fr_auto_20px] items-center gap-3 px-5 py-4 text-left transition-colors hover:bg-raised"
      >
        <span className="min-w-0">
          <span className="block font-semibold">{title}</span>
          {summary && <span className="block truncate text-[13px] text-muted">{summary}</span>}
        </span>
        <span className={`num text-right text-base font-semibold ${valueTone === "accent" ? "text-accent" : "text-ink"}`}>
          {value}
        </span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          aria-hidden="true"
          className={`text-faint transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        >
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" fill="none" />
        </svg>
      </button>
      <div id={id} className={`expand ${open ? "open" : ""}`}>
        <div>
          <div className="reveal px-5 pb-5">{children}</div>
        </div>
      </div>
    </section>
  );
}
