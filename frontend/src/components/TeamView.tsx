import type { ManagerState } from "../api";
import { rank } from "../format";
import { Card } from "./Card";
import { Chips } from "./Chips";
import { RecentGameweeks } from "./RecentGameweeks";
import { RecommendationsPanel, type PlanSource } from "./Recommendations";
import { Squad } from "./Squad";
import { Summary } from "./Summary";

/** Everything about one manager's situation, whether it came from a team ID or was entered by hand. */
export function TeamView({
  state,
  source,
  onSetFreeTransfers,
  enteredByHand = false,
}: {
  state: ManagerState;
  source: PlanSource;
  onSetFreeTransfers: (value: number | null) => Promise<void>;
  enteredByHand?: boolean;
}) {
  const chipLabels = Object.fromEntries(state.chips.map((c) => [c.chip, c.label]));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <div>
          <h2 className="text-xl font-semibold">{state.team_name}</h2>
          {state.total_points != null && (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {state.manager_name} · {state.total_points} pts · overall rank {rank(state.overall_rank)}
            </p>
          )}
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {state.planning_gameweek ? `Planning for GW${state.planning_gameweek}` : "Season over"} · season {state.season}
        </p>
      </div>

      {state.warnings.length > 0 && (
        <ul className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          {state.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <Summary state={state} onSetFreeTransfers={onSetFreeTransfers} canResetFreeTransfers={!enteredByHand} />

      {state.planning_gameweek && <RecommendationsPanel source={source} />}

      <Card title="Squad" aside={<span className="text-xs text-slate-500 dark:text-slate-400">GW{state.squad_gameweek}</span>}>
        <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">{state.squad_note}</p>
        <Squad squad={state.squad} />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Chips">
          <Chips chips={state.chips} />
        </Card>
        {state.past_gameweeks.length > 0 && (
          <Card title="Recent gameweeks">
            <RecentGameweeks gameweeks={state.past_gameweeks} chipLabels={chipLabels} />
          </Card>
        )}
      </div>
    </div>
  );
}
