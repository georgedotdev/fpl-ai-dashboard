import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getExplanation,
  getManager,
  getManualExplanation,
  getManualRecommendations,
  getManualState,
  getRecommendations,
  setFreeTransfers,
  type ManagerState,
  type ManualSquad,
} from "../api";
import { KEYS, forget, load, save } from "../storage";
import { parseTeamId } from "../teamId";
import { FindTeamId } from "./FindTeamId";
import { InstallHint } from "./InstallHint";
import { ManualSquadBuilder } from "./ManualSquadBuilder";
import type { PlanSource } from "./Recommendations";
import { TeamView } from "./TeamView";
import { ErrorBox } from "./ui";

type Mode = "team" | "manual";

function teamFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("team");
}

function setUrlTeam(teamId: number | null) {
  const query = teamId ? `?team=${teamId}` : "";
  window.history.replaceState(null, "", `${window.location.pathname}${query}${window.location.hash}`);
}

function TeamIdMode({ onEnterByHand }: { onEnterByHand: () => void }) {
  // A shared link (?team=) wins; otherwise the team remembered on this device.
  const [input, setInput] = useState(() => teamFromUrl() ?? String(load<number>(KEYS.teamId) ?? ""));
  const [state, setState] = useState<ManagerState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const show = useCallback(async (raw: string) => {
    const teamId = parseTeamId(raw);
    if (teamId === null) {
      setError("That doesn't look like a team ID. Paste the number, or the whole link from your FPL Points page.");
      return;
    }
    setInput(String(teamId));
    setLoading(true);
    setError(null);
    try {
      setState(await getManager(teamId));
      save(KEYS.teamId, teamId);
      setUrlTeam(teamId);
    } catch (e) {
      setState(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = teamFromUrl() ?? load<number>(KEYS.teamId);
    if (initial) void show(String(initial));
  }, [show]);

  const source: PlanSource | null = useMemo(() => {
    if (!state) return null;
    const id = state.team_id;
    return {
      key: `team:${id}:${state.free_transfers.source}:${state.free_transfers.value}`,
      recommendations: (horizon) => getRecommendations(id, horizon),
      explanation: (horizon, rank) => getExplanation(id, horizon, rank),
    };
  }, [state]);

  function switchTeam() {
    forget(KEYS.teamId);
    setUrlTeam(null);
    setState(null);
    setInput("");
  }

  return (
    <>
      {state && source ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="text-slate-500 dark:text-slate-400">
            Team ID <span className="font-medium tabular-nums text-slate-900 dark:text-slate-100">{state.team_id}</span>{" "}
            · remembered on this device
          </span>
          <button onClick={switchTeam} className="text-violet-700 hover:underline dark:text-violet-400">
            Use a different team
          </button>
        </div>
      ) : (
        <>
          <form
            className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              void show(input);
            }}
          >
            <label className="flex-1 sm:max-w-md">
              <span className="text-sm font-medium">Team ID or FPL link</span>
              <input
                inputMode="url"
                autoComplete="off"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="1234567 or https://fantasy.premierleague.com/entry/1234567/…"
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 tabular-nums shadow-sm focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-200 dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-violet-900"
              />
            </label>
            <button
              disabled={loading}
              className="rounded-lg bg-violet-600 px-4 py-2 font-medium text-white shadow-sm hover:bg-violet-700 disabled:opacity-60"
            >
              {loading ? "Loading…" : "Show my team"}
            </button>
          </form>
          <FindTeamId onEnterByHand={onEnterByHand} />
        </>
      )}

      {error && (
        <div className="mb-6">
          <ErrorBox message={error} />
        </div>
      )}

      {state && source && (
        <div className="space-y-4">
          <InstallHint />
          <TeamView
            state={state}
            source={source}
            onSetFreeTransfers={async (value) => {
              try {
                setState(await setFreeTransfers(state.team_id, value));
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          />
        </div>
      )}
    </>
  );
}

function ManualMode() {
  const [squad, setSquad] = useState<ManualSquad | null>(() => load<ManualSquad>(KEYS.manualSquad));
  const [state, setState] = useState<ManagerState | null>(null);
  const [editing, setEditing] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(next: ManualSquad) {
    setSubmitting(true);
    setError(null);
    try {
      setState(await getManualState(next));
      setSquad(next);
      save(KEYS.manualSquad, next);
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const source: PlanSource | null = useMemo(() => {
    if (!squad) return null;
    return {
      key: `manual:${JSON.stringify(squad)}`,
      recommendations: (horizon) => getManualRecommendations(squad, horizon),
      explanation: (horizon, rank) => getManualExplanation(squad, horizon, rank),
    };
  }, [squad]);

  if (editing || !state || !source) {
    return (
      <ManualSquadBuilder
        initial={squad}
        submitting={submitting}
        error={error}
        onSubmit={(next) => void submit(next)}
        onDraftChange={(draft) => save(KEYS.manualSquad, draft)}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="text-slate-500 dark:text-slate-400">Squad entered by hand · saved on this device</span>
        <button onClick={() => setEditing(true)} className="text-violet-700 hover:underline dark:text-violet-400">
          Edit squad
        </button>
      </div>
      {error && <ErrorBox message={error} />}
      <InstallHint />
      <TeamView
        state={state}
        source={source}
        enteredByHand
        onSetFreeTransfers={async (value) => {
          if (value !== null && squad) await submit({ ...squad, free_transfers: value });
        }}
      />
    </div>
  );
}

export function MyTeam() {
  const [mode, setMode] = useState<Mode>(() =>
    teamFromUrl() ? "team" : (load<Mode>(KEYS.mode) ?? "team"),
  );

  function choose(next: Mode) {
    setMode(next);
    save(KEYS.mode, next);
  }

  return (
    <>
      <div className="mb-4 inline-flex rounded-lg border border-slate-200 p-0.5 text-sm dark:border-slate-800" role="tablist">
        {(
          [
            ["team", "Use my team ID"],
            ["manual", "Enter squad by hand"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={mode === id}
            onClick={() => choose(id)}
            className={`rounded-md px-3 py-1.5 font-medium ${
              mode === id
                ? "bg-violet-600 text-white"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "team" ? <TeamIdMode onEnterByHand={() => choose("manual")} /> : <ManualMode />}
    </>
  );
}
