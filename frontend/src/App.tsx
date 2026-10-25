import { useCallback, useEffect, useState } from "react";
import { getManager, setFreeTransfers, type ManagerState } from "./api";
import { Card } from "./components/Card";
import { Chips } from "./components/Chips";
import { RecentGameweeks } from "./components/RecentGameweeks";
import { Squad } from "./components/Squad";
import { Summary } from "./components/Summary";
import { rank } from "./format";

function teamIdFromUrl(): string {
  return new URLSearchParams(window.location.search).get("team") ?? "";
}

export default function App() {
  const [input, setInput] = useState(teamIdFromUrl);
  const [state, setState] = useState<ManagerState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (raw: string) => {
    const teamId = Number(raw.trim());
    if (!Number.isInteger(teamId) || teamId < 1) {
      setError("Team IDs are whole numbers, e.g. 1234567.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setState(await getManager(teamId));
      // Keep the team in the URL so the page can be refreshed or shared.
      window.history.replaceState(null, "", `?team=${teamId}`);
    } catch (e) {
      setState(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const fromUrl = teamIdFromUrl();
    if (fromUrl) void load(fromUrl);
  }, [load]);

  async function overrideFreeTransfers(value: number | null) {
    if (!state) return;
    try {
      setState(await setFreeTransfers(state.team_id, value));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const chipLabels = Object.fromEntries((state?.chips ?? []).map((c) => [c.chip, c.label]));

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">FPL Assistant</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Your squad, bank, free transfers and chips from your FPL team ID. No login, no password.
        </p>
      </header>

      <form
        className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          void load(input);
        }}
      >
        <label className="flex-1 sm:max-w-xs">
          <span className="text-sm font-medium">Team ID</span>
          <input
            inputMode="numeric"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. 1234567"
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 tabular-nums shadow-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-200 dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-violet-900"
          />
        </label>
        <button
          disabled={loading}
          className="rounded-lg bg-violet-600 px-4 py-2 font-medium text-white shadow-sm hover:bg-violet-700 disabled:opacity-60"
        >
          {loading ? "Loading…" : "Show my team"}
        </button>
        <p className="text-xs text-slate-500 dark:text-slate-400 sm:ml-2 sm:self-center">
          Find it in the address of your FPL Points page: …/entry/<strong>1234567</strong>/event/…
        </p>
      </form>

      {error && (
        <div role="alert" className="mb-6 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {state && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <div>
              <h2 className="text-xl font-semibold">{state.team_name}</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {state.manager_name} · {state.total_points ?? 0} pts · overall rank {rank(state.overall_rank)}
              </p>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {state.planning_gameweek ? `Planning for GW${state.planning_gameweek}` : "Season over"} · season{" "}
              {state.season}
            </p>
          </div>

          {state.warnings.length > 0 && (
            <ul className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
              {state.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}

          <Summary state={state} onSetFreeTransfers={overrideFreeTransfers} />

          <Card title="Squad" aside={<span className="text-xs text-slate-500 dark:text-slate-400">GW{state.squad_gameweek}</span>}>
            <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">{state.squad_note}</p>
            <Squad squad={state.squad} />
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Chips">
              <Chips chips={state.chips} />
            </Card>
            <Card title="Recent gameweeks">
              <RecentGameweeks gameweeks={state.past_gameweeks} chipLabels={chipLabels} />
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
