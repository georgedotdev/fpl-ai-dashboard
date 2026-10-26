import { useState, type ReactNode } from "react";
import { getBestXI, getCaptaincy, getFixtures, getPlayers, type ManagerState, type PickedPlayer } from "../api";
import { money } from "../format";
import { useData, useMediaQuery } from "../hooks";
import { Chips } from "./Chips";
import { ExpandRow } from "./ExpandRow";
import { FdrGrid } from "./FixturesView";
import { Bench, Pitch } from "./Pitch";
import { RecentGameweeks } from "./RecentGameweeks";
import { ChipsAdvice, MovesDetail, PlanPicks, usePlans, type PlanSource } from "./Recommendations";
import { Squad } from "./Squad";
import { Summary } from "./Summary";

type Mode = "now" | "plan" | "best";
const MODES: [Mode, string][] = [
  ["now", "Now"],
  ["plan", "After moves"],
  ["best", "Best XI"],
];

interface Shown {
  lineup: PickedPlayer[];
  bench: PickedPlayer[];
  captain: number;
  vice: number;
  xp: number;
  note: string;
}

/** A dashboard panel with its title. */
function Box({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="@container min-w-0 rounded-[18px] bg-surface p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        {aside && <div className="text-xs text-faint">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

function Segmented({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  const index = MODES.findIndex(([m]) => m === mode);
  return (
    <div className="relative grid grid-cols-3 rounded-full bg-raised p-[3px]" role="group" aria-label="Which team">
      <span
        aria-hidden="true"
        className="absolute inset-y-[3px] left-[3px] w-[calc((100%-6px)/3)] rounded-full bg-accent transition-transform duration-300 ease-out-soft"
        style={{ transform: `translateX(${index * 100}%)` }}
      />
      {MODES.map(([id, label]) => (
        <button
          key={id}
          type="button"
          aria-pressed={mode === id}
          onClick={() => onChange(id)}
          className={`relative z-10 h-8 whitespace-nowrap rounded-full px-3 text-sm font-semibold transition-colors ${
            mode === id ? "text-accent-ink" : "text-muted"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** Everything about one manager's situation as a dashboard: the team in the middle, the rest around it. */
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
  const desktop = useMediaQuery("(min-width: 1280px)");
  const tablet = useMediaQuery("(min-width: 768px)");
  const [mode, setMode] = useState<Mode>("now");
  const [allFixtures, setAllFixtures] = useState(false);
  const plans = usePlans(source);
  const best = useData(getBestXI, []);
  const captains = useData(() => getCaptaincy(6), []);
  const fixtures = useData(() => getFixtures(5), []);
  const movers = useData(() => getPlayers({ horizon: 1, sort: "net_transfers_event", limit: 6 }), []);

  const recs = plans.data;
  const first = plans.plan?.gameweeks[0];
  const gws = recs?.gameweeks;
  const chipLabels = Object.fromEntries(state.chips.map((c) => [c.chip, c.label]));
  const chipsLeft = state.chips.filter((c) => c.state === "available").length;

  // The three teams the pitch can show.
  let shown: Shown | null = null;
  if (mode === "now" && recs?.current?.length) {
    const lineup = recs.current.slice(0, 11);
    const captain = recs.current_captain ?? -1;
    const captainXp = lineup.find((p) => p.player_id === captain)?.xp ?? 0;
    shown = {
      lineup,
      bench: recs.current.slice(11),
      captain,
      vice: recs.current_vice_captain ?? -1,
      xp: lineup.reduce((sum, p) => sum + p.xp, 0) + captainXp,
      note: enteredByHand ? "Your squad as entered" : `Your team as picked at the GW${state.squad_gameweek} deadline`,
    };
  } else if (mode === "plan" && first) {
    shown = {
      lineup: first.lineup,
      bench: first.bench,
      captain: first.captain.player_id,
      vice: first.vice_captain.player_id,
      xp: first.expected_points,
      note: first.moves.length ? `After ${first.moves.length} recommended transfer${first.moves.length > 1 ? "s" : ""}` : "No transfers recommended",
    };
  } else if (mode === "best" && best.data) {
    shown = {
      lineup: best.data.lineup,
      bench: best.data.bench,
      captain: best.data.captain.player_id,
      vice: best.data.vice_captain.player_id,
      xp: best.data.expected_points,
      note: `Best possible for ${money(best.data.cost)}, whoever you own`,
    };
  }
  const pitchError = mode === "best" ? best.error : plans.error;

  const gain = plans.plan ? `${plans.plan.gain_vs_no_transfers >= 0 ? "+" : ""}${plans.plan.gain_vs_no_transfers.toFixed(1)} xP` : null;

  // ---- the boxes ------------------------------------------------------------------------
  const pitchBox = (
    <section className="@container rounded-[18px] bg-surface p-4 sm:p-5" aria-label="Team on the pitch">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Segmented mode={mode} onChange={setMode} />
        <div className="text-right">
          <div className="num text-2xl font-semibold leading-7">
            {shown ? shown.xp.toFixed(1) : "–"} <small className="text-sm font-normal text-faint">xP GW{gws?.[0] ?? state.planning_gameweek}</small>
          </div>
          <div className="text-xs text-faint">{shown?.note ?? ""}</div>
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
          {mode === "best" ? "Picking the best XI…" : "Loading your team… (a few seconds)"}
        </div>
      )}
    </section>
  );

  const movesBox = (
    <Box title="Transfers" aside={gain && <span className="text-sm font-bold text-accent">{gain}</span>}>
      <MovesDetail plans={plans} source={source} compact={!tablet} />
    </Box>
  );

  const captainContent = (
    <>
      {first && <PlanPicks gw={first} />}
      <h4 className="mb-1 mt-3 text-xs font-semibold text-muted">Best captains this gameweek, any team</h4>
      {captains.data?.players.map((c, i) => (
        <div key={c.player_id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 py-1.5">
          <span className="min-w-0 truncate">
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
    </>
  );

  const fixturesContent = fixtures.data && (
    <>
      <FdrGrid data={fixtures.data} limit={allFixtures ? undefined : 8} />
      <button type="button" onClick={() => setAllFixtures((a) => !a)} className="mt-1 text-sm font-semibold text-accent hover:underline">
        {allFixtures ? "Show the easiest 8" : "Show all 20 teams"}
      </button>
    </>
  );

  const chipsContent = (
    <>
      <Chips chips={state.chips} />
      {recs && <ChipsAdvice chips={recs.chips} />}
    </>
  );

  const pricesContent = (
    <>
      <p className="mb-1 text-xs text-faint">Net transfers this gameweek: what drives tonight's price changes.</p>
      {movers.data?.players.map((m, i) => (
        <div key={m.player_id} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 py-1.5">
          <span className="min-w-0 truncate">
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
    </>
  );

  const bankContent = <Summary state={state} onSetFreeTransfers={onSetFreeTransfers} canResetFreeTransfers={!enteredByHand} compact />;
  const squadContent = (
    <>
      <p className="mb-2 text-xs text-faint">{state.squad_note}</p>
      <Squad squad={state.squad} />
    </>
  );
  const recent = state.past_gameweeks.length > 0 && <RecentGameweeks gameweeks={state.past_gameweeks} chipLabels={chipLabels} />;

  const header = (
    <div className="min-w-0">
      <h2 className="text-[22px] font-bold leading-7">{state.team_name}</h2>
      <p className="mt-0.5 text-muted">
        {state.total_points != null
          ? `${state.manager_name} · ${state.total_points} pts · overall rank ${state.overall_rank?.toLocaleString("en-GB") ?? "–"}`
          : `Planning for GW${state.planning_gameweek}`}
        {plans.plan && first && <> · captain {first.captain.web_name}</>}
      </p>
    </div>
  );
  const warnings = state.warnings.length > 0 && (
    <ul className="rounded-xl bg-warn/15 p-3 text-sm text-warn">
      {state.warnings.map((w) => (
        <li key={w}>{w}</li>
      ))}
    </ul>
  );

  // ---- desktop: the team in the middle, everything else around it ----------------------
  if (desktop) {
    return (
      <div className="space-y-4">
        {header}
        {warnings}
        <div className="grid grid-cols-[minmax(270px,1fr)_minmax(440px,1.3fr)_minmax(320px,1fr)] items-start gap-4">
          <div className="grid gap-4">
            <Box title="Captain" aside={first && `${first.captain.web_name} · ${(first.captain.xp * 2).toFixed(1)} xP`}>{captainContent}</Box>
            <Box title="Bank and transfers" aside={`${state.free_transfers.value ?? "Unlimited"} free`}>{bankContent}</Box>
            <Box title="Chips" aside={`${chipsLeft} to play`}>{chipsContent}</Box>
          </div>
          <div className="sticky top-4">{pitchBox}</div>
          <div className="grid gap-4">
            {movesBox}
            <Box title="Fixtures" aside={gws && `GW${gws[0]}–${gws[gws.length - 1]}`}>{fixturesContent}</Box>
            <Box title="Price moves">{pricesContent}</Box>
          </div>
        </div>
        <div className="grid grid-cols-[2fr_1fr] items-start gap-4">
          <Box title="Squad and selling prices" aside={`Sells for ${money(state.sale_value.value)}`}>{squadContent}</Box>
          {recent ? <Box title="Recent gameweeks">{recent}</Box> : <div />}
        </div>
      </div>
    );
  }

  // ---- tablet: team and transfers side by side, the rest in two columns ------------------
  if (tablet) {
    return (
      <div className="space-y-4">
        {header}
        {warnings}
        <div className="grid grid-cols-2 items-start gap-4">
          <div className="grid gap-4">
            {pitchBox}
            <Box title="Captain">{captainContent}</Box>
            <Box title="Chips" aside={`${chipsLeft} to play`}>{chipsContent}</Box>
          </div>
          <div className="grid gap-4">
            {movesBox}
            <Box title="Bank and transfers">{bankContent}</Box>
            <Box title="Fixtures">{fixturesContent}</Box>
            <Box title="Price moves">{pricesContent}</Box>
          </div>
        </div>
        <Box title="Squad and selling prices" aside={`Sells for ${money(state.sale_value.value)}`}>{squadContent}</Box>
        {recent && <Box title="Recent gameweeks">{recent}</Box>}
      </div>
    );
  }

  // ---- phone: the team, then the moves, the key numbers, and the rest one tap away -------
  return (
    <div className="space-y-3">
      {header}
      {warnings}
      {pitchBox}
      {movesBox}
      <div className="grid grid-cols-2 gap-2">
        {[
          ["In the bank", money(state.bank.value)],
          ["Free transfers", String(state.free_transfers.value ?? "Unlimited")],
          ["Captain", first ? first.captain.web_name : "–"],
          ["Chips to play", String(chipsLeft)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-surface p-3">
            <div className="text-xs text-faint">{label}</div>
            <div className="num truncate text-lg font-semibold">{value}</div>
          </div>
        ))}
      </div>
      <ExpandRow title="Captain" summary={first ? `${first.captain.web_name} · ${first.captain.fixtures.join(", ") || "no game"}` : "Loading…"} value={first ? (first.captain.xp * 2).toFixed(1) : ""}>
        {captainContent}
      </ExpandRow>
      <ExpandRow title="Fixtures" summary={fixtures.data ? `Easiest: ${fixtures.data.teams.slice(0, 3).map((t) => t.short_name).join(", ")}` : "Loading…"}>
        {fixturesContent}
      </ExpandRow>
      <ExpandRow title="Chips" summary={chipsLeft ? `${chipsLeft} to play in this half` : "None to play right now"}>
        {chipsContent}
      </ExpandRow>
      <ExpandRow title="Price moves" summary={movers.data?.players[0] ? `Most bought: ${movers.data.players[0].web_name}` : "Loading…"}>
        {pricesContent}
      </ExpandRow>
      <ExpandRow
        title="Bank and transfers"
        summary={`${state.free_transfers.value ?? "Unlimited"} free transfers · ${state.free_transfers.source === "user_override" ? "set by you" : state.free_transfers.source === "derived" ? "derived" : "from FPL"}`}
        value={money(state.bank.value)}
      >
        {bankContent}
      </ExpandRow>
      <ExpandRow title="Squad and selling prices" summary={`${state.squad.length} players`} value={money(state.sale_value.value)}>
        {squadContent}
      </ExpandRow>
      {recent && (
        <ExpandRow title="Recent gameweeks" summary={`GW${state.past_gameweeks[state.past_gameweeks.length - 1].gameweek}: ${state.past_gameweeks[state.past_gameweeks.length - 1].points} pts`}>
          {recent}
        </ExpandRow>
      )}
    </div>
  );
}
