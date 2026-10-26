import { useState } from "react";
import { getBestXI, getCaptaincy, getFixtures, getPlayers, type ManagerState, type PickedPlayer } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { Chips } from "./Chips";
import { ExpandRow } from "./ExpandRow";
import { FdrGrid } from "./FixturesView";
import { Bench, Pitch } from "./Pitch";
import { RecentGameweeks } from "./RecentGameweeks";
import { ChipsAdvice, MovesDetail, PlanPicks, usePlans, type PlanSource } from "./Recommendations";
import { Squad } from "./Squad";
import { Summary } from "./Summary";

type Mode = "mine" | "best";

function Segmented({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="relative inline-flex rounded-full bg-raised p-[3px]" role="group" aria-label="Which team">
      <span
        aria-hidden="true"
        className="absolute inset-y-[3px] w-[calc(50%-3px)] rounded-full bg-accent transition-transform duration-300 ease-out-soft"
        style={{ transform: mode === "best" ? "translateX(100%)" : "translateX(0)" }}
      />
      {(
        [
          ["mine", "Your XI"],
          ["best", "Best XI"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={mode === id}
          onClick={() => onChange(id)}
          className={`relative z-10 h-8 w-24 rounded-full font-semibold transition-colors ${mode === id ? "text-accent-ink" : "text-muted"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** Everything about one manager's situation: the pitch first, then every part one tap away. */
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
  const [mode, setMode] = useState<Mode>("mine");
  const plans = usePlans(source);
  const best = useData(getBestXI, []);
  const captains = useData(() => getCaptaincy(6), []);
  const fixtures = useData(() => getFixtures(5), []);
  const movers = useData(() => getPlayers({ horizon: 1, sort: "net_transfers_event", limit: 6 }), []);

  const first = plans.plan?.gameweeks[0];
  const shown: { lineup: PickedPlayer[]; bench: PickedPlayer[]; captain: number; vice: number; xp: number } | null =
    mode === "best"
      ? best.data && {
          lineup: best.data.lineup,
          bench: best.data.bench,
          captain: best.data.captain.player_id,
          vice: best.data.vice_captain.player_id,
          xp: best.data.expected_points,
        }
      : first
        ? { lineup: first.lineup, bench: first.bench, captain: first.captain.player_id, vice: first.vice_captain.player_id, xp: first.expected_points }
        : null;
  const pitchError = mode === "best" ? best.error : plans.error;
  const chipLabels = Object.fromEntries(state.chips.map((c) => [c.chip, c.label]));
  const chipsLeft = state.chips.filter((c) => c.state === "available").length;
  const gws = plans.data?.gameweeks;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[22px] font-bold leading-7">{state.team_name}</h2>
        <p className="mt-0.5 text-muted">
          {plans.plan && gws ? (
            <>
              {plans.plan.headline}: <b className="font-semibold text-accent">{plans.plan.gain_vs_no_transfers >= 0 ? "+" : ""}{plans.plan.gain_vs_no_transfers.toFixed(1)} xP</b> over
              GW{gws[0]}–{gws[gws.length - 1]}.{first && ` Captain ${first.captain.web_name}.`}
            </>
          ) : state.total_points != null ? (
            `${state.manager_name} · ${state.total_points} pts · overall rank ${state.overall_rank?.toLocaleString("en-GB") ?? "–"}`
          ) : (
            `Planning for GW${state.planning_gameweek}`
          )}
        </p>
      </div>

      {state.warnings.length > 0 && (
        <ul className="rounded-xl bg-warn/15 p-3 text-sm text-warn">
          {state.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <div className="grid items-start gap-3.5 lg:grid-cols-[7fr_5fr]">
        <section className="rounded-[18px] bg-surface p-5 lg:sticky lg:top-4" aria-label="Team on the pitch">
          <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
            <Segmented mode={mode} onChange={setMode} />
            <div className="text-right">
              <div className="num text-2xl font-semibold leading-7">
                {shown ? shown.xp.toFixed(1) : "–"} <small className="text-sm font-normal text-faint">xP</small>
              </div>
              <div className="text-xs text-faint">
                {mode === "best"
                  ? best.data
                    ? `Best possible for ${money(best.data.cost)} · GW${best.data.gameweek}`
                    : "Best possible XI"
                  : first
                    ? `After your moves${best.data ? ` · best possible ${best.data.expected_points.toFixed(1)}` : ""}`
                    : "Your XI"}
              </div>
            </div>
          </div>
          {shown ? (
            <>
              <Pitch lineup={shown.lineup} captainId={shown.captain} viceId={shown.vice} />
              <Bench players={shown.bench} />
            </>
          ) : pitchError ? (
            <p className="rounded-xl bg-negative/15 p-3 text-sm text-negative">{pitchError}</p>
          ) : (
            <div className="grid aspect-[68/98] place-items-center rounded-xl bg-raised text-sm text-faint sm:aspect-[68/80]">
              {mode === "best" ? "Picking the best XI…" : "Planning your XI… (a few seconds)"}
            </div>
          )}
          {mode === "best" && (
            <p className="mt-3 text-xs text-faint">
              The strongest squad for the next gameweek from every player, within the £100m budget and the squad rules: a Free Hit
              team, whatever you own.
            </p>
          )}
        </section>

        <div className="grid gap-3.5">
          <ExpandRow
            title="Your moves"
            summary={plans.plan ? plans.plan.headline : plans.loading ? "Planning…" : "No plan yet"}
            value={plans.plan ? `${plans.plan.gain_vs_no_transfers >= 0 ? "+" : ""}${plans.plan.gain_vs_no_transfers.toFixed(1)}` : ""}
            valueTone="accent"
          >
            <MovesDetail plans={plans} source={source} />
          </ExpandRow>

          <ExpandRow
            title="Captain"
            summary={first ? `${first.captain.web_name} · ${first.captain.fixtures.join(", ") || "no game"}` : "Planning…"}
            value={first ? (first.captain.xp * 2).toFixed(1) : ""}
          >
            {first && <PlanPicks gw={first} />}
            <h3 className="mb-1 mt-4 text-xs font-semibold text-muted">Best captains this gameweek, any team</h3>
            <div className="grid gap-0.5">
              {captains.data?.players.map((c, i) => (
                <div key={c.player_id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 py-2">
                  <span>
                    {c.web_name} <small className="text-xs text-faint">{c.team_short_name} · {c.upcoming[0] ?? "no game"}</small>
                  </span>
                  <span className="num">{(c.xp_next * 2).toFixed(1)}</span>
                  <span className="col-span-2 h-0.5 overflow-hidden rounded bg-raised-2">
                    <i
                      className={`block h-full ${i === 0 ? "bg-accent" : "bg-faint"}`}
                      style={{ width: `${(c.xp_next / (captains.data?.players[0].xp_next || 1)) * 100}%` }}
                    />
                  </span>
                </div>
              ))}
            </div>
          </ExpandRow>

          <ExpandRow
            title="Fixtures"
            summary={fixtures.data ? `Easiest runs: ${fixtures.data.teams.slice(0, 3).map((t) => t.short_name).join(", ")}` : "Loading…"}
            value={fixtures.data ? `${fixtures.data.gameweeks.length} GWs` : ""}
          >
            {fixtures.data && <FdrGrid data={fixtures.data} />}
          </ExpandRow>

          <ExpandRow
            title="Chips"
            summary={chipsLeft ? `${chipsLeft} to play in this half` : "None to play right now"}
            value={`${chipsLeft} left`}
          >
            <Chips chips={state.chips} />
            {plans.data && <ChipsAdvice chips={plans.data.chips} />}
          </ExpandRow>

          <ExpandRow
            title="Price moves"
            summary={movers.data?.players[0] ? `Most bought: ${movers.data.players[0].web_name}` : "Loading…"}
            value={movers.data ? movers.data.players.length : ""}
          >
            <p className="mb-1 text-xs text-faint">Net transfers this gameweek: what drives tonight's price changes.</p>
            {movers.data?.players.map((m, i) => (
              <div key={m.player_id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 py-2">
                <span>
                  {m.web_name} <small className="text-xs text-faint">{m.team_short_name} · {money(m.now_cost)}</small>
                </span>
                <span className="num">
                  {m.net_transfers_event > 0 ? "+" : "−"}
                  {Math.abs(m.net_transfers_event).toLocaleString("en-GB")}
                </span>
                <span className="col-span-2 h-0.5 overflow-hidden rounded bg-raised-2">
                  <i
                    className={`block h-full ${i === 0 ? "bg-accent" : "bg-faint"}`}
                    style={{ width: `${(Math.abs(m.net_transfers_event) / Math.abs(movers.data!.players[0].net_transfers_event || 1)) * 100}%` }}
                  />
                </span>
              </div>
            ))}
          </ExpandRow>

          <ExpandRow
            title="Bank and transfers"
            summary={`${state.free_transfers.value ?? "Unlimited"} free transfers · ${state.free_transfers.source === "derived" ? "derived" : state.free_transfers.source === "user_override" ? "set by you" : "from FPL"}`}
            value={money(state.bank.value)}
          >
            <Summary state={state} onSetFreeTransfers={onSetFreeTransfers} canResetFreeTransfers={!enteredByHand} />
          </ExpandRow>

          <ExpandRow title="Squad and selling prices" summary={`${state.squad.length} players · GW${state.squad_gameweek} squad`} value={money(state.sale_value.value)}>
            <p className="mb-2 text-xs text-faint">{state.squad_note}</p>
            <Squad squad={state.squad} />
          </ExpandRow>

          {state.past_gameweeks.length > 0 && (
            <ExpandRow
              title="Recent gameweeks"
              summary={`GW${state.past_gameweeks[state.past_gameweeks.length - 1].gameweek}: ${state.past_gameweeks[state.past_gameweeks.length - 1].points} pts`}
              value={state.total_points != null ? `${state.total_points} pts` : ""}
            >
              <RecentGameweeks gameweeks={state.past_gameweeks} chipLabels={chipLabels} />
            </ExpandRow>
          )}
        </div>
      </div>
    </div>
  );
}
