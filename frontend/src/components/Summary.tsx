import { useState } from "react";
import type { ManagerState, Sourced } from "../api";
import { money } from "../format";
import { SourceBadge } from "./SourceBadge";

function Stat({ label, value, sourced }: { label: string; value: string; sourced: Sourced<unknown> }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
        <SourceBadge source={sourced.source} note={sourced.note} />
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sourced.note && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{sourced.note}</p>}
    </div>
  );
}

function FreeTransfers({
  state,
  maxBanked,
  onSave,
}: {
  state: ManagerState;
  maxBanked: number;
  onSave: (value: number | null) => Promise<void>;
}) {
  const ft = state.free_transfers;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(ft.value ?? 1);
  const [saving, setSaving] = useState(false);

  async function save(value: number | null) {
    setSaving(true);
    try {
      await onSave(value);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Free transfers{state.planning_gameweek ? ` for GW${state.planning_gameweek}` : ""}
        </span>
        <SourceBadge source={ft.source} note={ft.note} />
      </div>
      {editing ? (
        <form
          className="mt-1 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void save(draft);
          }}
        >
          <input
            type="number"
            min={0}
            max={maxBanked}
            value={draft}
            onChange={(e) => setDraft(Number(e.target.value))}
            className="w-16 rounded-md border border-slate-300 bg-transparent px-2 py-1 text-xl font-semibold tabular-nums dark:border-slate-700"
            aria-label="Your free transfers"
            autoFocus
          />
          <button
            disabled={saving}
            className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            Save
          </button>
          <button type="button" onClick={() => setEditing(false)} className="text-sm text-slate-500 hover:underline">
            Cancel
          </button>
        </form>
      ) : (
        <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-2xl font-semibold tabular-nums">{ft.value ?? "Unlimited"}</span>
          {state.planning_gameweek && (
            <button
              onClick={() => {
                setDraft(ft.value ?? 1);
                setEditing(true);
              }}
              className="whitespace-nowrap text-sm text-violet-700 hover:underline dark:text-violet-400"
            >
              Not right? Correct it
            </button>
          )}
          {ft.source === "user_override" && (
            <button
              onClick={() => void save(null)}
              disabled={saving}
              className="whitespace-nowrap text-sm text-slate-500 hover:underline"
            >
              Use derived value
            </button>
          )}
        </div>
      )}
      {ft.note && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{ft.note}</p>}
    </div>
  );
}

export function Summary({
  state,
  onSetFreeTransfers,
}: {
  state: ManagerState;
  onSetFreeTransfers: (value: number | null) => Promise<void>;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Money in the bank" value={money(state.bank.value)} sourced={state.bank} />
      <Stat label="Team value" value={money(state.team_value.value)} sourced={state.team_value} />
      <Stat label="Value if you sold everyone" value={money(state.sale_value.value)} sourced={state.sale_value} />
      <FreeTransfers state={state} maxBanked={state.max_free_transfers} onSave={onSetFreeTransfers} />
    </div>
  );
}
