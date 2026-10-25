import type { ChipStatus } from "../api";

const STATE_STYLES: Record<ChipStatus["state"], string> = {
  available: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  upcoming: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
  used: "border-slate-200 bg-white text-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-500",
  expired: "border-slate-200 bg-white text-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-500",
};

function detail(chip: ChipStatus): string {
  switch (chip.state) {
    case "used":
      return `Played GW${chip.played_gameweek}`;
    case "expired":
      return `Expired after GW${chip.window_end}`;
    case "upcoming":
      return `From GW${chip.usable_from_gameweek}`;
    case "available":
      return chip.usable_from_gameweek && chip.note
        ? `From GW${chip.usable_from_gameweek}`
        : `Until GW${chip.window_end}`;
  }
}

export function Chips({ chips }: { chips: ChipStatus[] }) {
  const halves = [...new Set(chips.map((c) => c.half))].sort();
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {halves.map((half) => {
        const inHalf = chips.filter((c) => c.half === half);
        return (
          <div key={half}>
            <h3 className="mb-2 text-xs font-medium text-slate-500 dark:text-slate-400">
              {half === 1 ? "First" : "Second"} half · GW{Math.min(...inHalf.map((c) => c.window_start))}–
              {Math.max(...inHalf.map((c) => c.window_end))}
            </h3>
            <ul className="grid grid-cols-2 gap-2">
              {inHalf.map((chip) => (
                <li
                  key={chip.chip}
                  title={chip.note ?? undefined}
                  className={`rounded-lg border px-3 py-2 ${STATE_STYLES[chip.state]}`}
                >
                  <div className={`text-sm font-medium ${chip.state === "used" || chip.state === "expired" ? "line-through" : ""}`}>
                    {chip.label}
                  </div>
                  <div className="text-xs opacity-80">{detail(chip)}</div>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
