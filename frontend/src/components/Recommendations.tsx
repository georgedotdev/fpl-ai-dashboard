import { useState } from "react";
import type { ChipAdvice, Explanation, GameweekRecommendation, MovePlan, Recommendations, RecommendedPlan } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { ErrorBox, Select, horizonOptions } from "./ui";

function points(n: number): string {
  return n.toFixed(1);
}

/** Where the plans come from: a team ID, or a squad entered by hand. */
export interface PlanSource {
  key: string; // changes whenever the inputs change, so the plans reload
  recommendations: (horizon: number) => Promise<Recommendations>;
  explanation: (horizon: number, rank: number) => Promise<Explanation>;
}

/** The plans for a source, with the horizon and the selected plan as state. */
export function usePlans(source: PlanSource) {
  const [horizon, setHorizonState] = useState(5);
  const [selected, setSelected] = useState(0);
  const { data, error, loading } = useData(() => source.recommendations(horizon), [source.key, horizon]);
  const setHorizon = (h: number) => {
    setHorizonState(h);
    setSelected(0);
  };
  const plan = data?.plans[Math.min(selected, (data?.plans.length ?? 1) - 1)];
  return { horizon, setHorizon, selected, setSelected, data, error, loading, plan };
}
export type Plans = ReturnType<typeof usePlans>;

function Move({ move, gameweeks }: { move: MovePlan; gameweeks: number[] }) {
  const { player_out: out, player_in: inn } = move;
  const [open, setOpen] = useState(false);
  const max = Math.max(...out.xp, ...inn.xp, 0.1);
  return (
    <li className="rounded-[14px] bg-raised">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-x-3 gap-y-0.5 p-3 text-left"
      >
        <span className="min-w-0 font-semibold">
          <span className="font-medium text-faint line-through">{out.web_name}</span>
          <span className="mx-1.5 text-faint">→</span>
          {inn.web_name}
        </span>
        <span className="num text-sm font-bold text-accent">+{points(move.xp_gain)}</span>
        <span className="text-xs text-faint">
          {inn.position} · {inn.team_short_name} · sell ~{money(out.price)} · buy {money(inn.price)}
        </span>
        <span className="text-xs text-faint">{open ? "Hide" : "GW by GW"}</span>
      </button>
      {out.status !== "a" && out.news && (
        <p className="-mt-1 px-3 pb-2 text-xs text-warn">
          {out.web_name}: {out.news}
        </p>
      )}
      <div className={`expand ${open ? "open" : ""}`}>
        <div>
          <div className="reveal px-3 pb-3">
            <div className="grid grid-cols-5 gap-1.5" aria-hidden="true">
              {gameweeks.map((gw, i) => (
                <div key={gw} className="flex flex-col items-center gap-1 text-[11px] text-faint">
                  <div className="flex h-11 items-end gap-[3px]">
                    <i className="w-2 rounded-t-[3px] bg-line" style={{ height: `${(out.xp[i] / max) * 44}px` }} />
                    <i className="w-2 rounded-t-[3px] bg-accent" style={{ height: `${(inn.xp[i] / max) * 44}px` }} />
                  </div>
                  GW{gw}
                </div>
              ))}
            </div>
            <div className="mt-2 overflow-x-auto">
              <table className="num w-full min-w-[18rem] text-xs">
                <thead>
                  <tr className="text-faint">
                    <th className="py-0.5 text-left font-medium" />
                    {gameweeks.map((gw) => (
                      <th key={gw} className="py-0.5 text-right font-medium">
                        GW{gw}
                      </th>
                    ))}
                    <th className="py-0.5 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {[out, inn].map((p) => (
                    <tr key={p.player_id}>
                      <td className="py-0.5 pr-2 text-left">{p.web_name}</td>
                      {p.xp.map((v, i) => (
                        <td key={i} className="py-0.5 text-right" title={p.fixtures[i].join(", ") || "No fixture"}>
                          {p.fixtures[i].length === 0 ? "–" : points(v)}
                        </td>
                      ))}
                      <td className="py-0.5 text-right font-semibold">{points(p.xp_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}

function ChipBadge({ label }: { label: string }) {
  return <span className="rounded bg-accent px-1.5 py-0.5 text-xs font-bold text-accent-ink">{label}</span>;
}

function LaterGameweeks({ plan }: { plan: RecommendedPlan }) {
  const later = plan.gameweeks.slice(1);
  if (later.length === 0) return null;
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer font-medium text-accent hover:underline">The rest of the plan</summary>
      <ul className="mt-2 space-y-1">
        {later.map((gw) => (
          <li key={gw.gameweek} className="num">
            <span className="font-semibold">GW{gw.gameweek}</span>
            <span className="text-faint"> · {gw.free_transfers ?? "∞"} FT · </span>
            {gw.moves.length ? gw.moves.map((m) => `${m.player_out.web_name} → ${m.player_in.web_name}`).join(", ") : "roll"}
            {gw.hits > 0 && <span className="text-negative"> (−{gw.hit_points})</span>}
            {gw.chip && (
              <>
                {" "}
                <ChipBadge label={gw.chip} />
              </>
            )}
            <span className="text-faint"> · C {gw.captain.web_name}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-faint">Later moves are provisional: re-check after each deadline, when the predictions update.</p>
    </details>
  );
}

function Why({ source, horizon, rank }: { source: PlanSource; horizon: number; rank: number }) {
  const { data, error, loading } = useData(() => source.explanation(horizon, rank), [source.key, horizon, rank]);
  return (
    <div className="mb-3 rounded-[14px] bg-raised p-3 text-sm">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-muted">Why</span>
        {data && (
          <span className="text-[11px] text-faint" title="Written only from the plan's facts; every number is checked against them before it's shown.">
            {data.source === "local_model" ? `Written by a local model (${data.model})` : "Written from the plan's facts"}
          </span>
        )}
      </div>
      {loading && <p className="text-faint">Writing the explanation…</p>}
      {error && <p className="text-negative">{error}</p>}
      {data && !loading && (
        <>
          <p className="leading-relaxed text-muted">{data.text}</p>
          {data.note && <p className="mt-1 text-xs text-warn">{data.note}</p>}
        </>
      )}
    </div>
  );
}

/** Everything about the recommended moves: plans, horizon, reasons, week-by-week detail. */
export function MovesDetail({ plans, source, compact = false }: { plans: Plans; source: PlanSource; compact?: boolean }) {
  const { data, error, loading, plan, horizon, setHorizon, selected, setSelected } = plans;
  const first: GameweekRecommendation | undefined = plan?.gameweeks[0];
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-2" role="tablist">
          {data?.plans.map((p, i) => (
            <button
              key={p.rank}
              role="tab"
              aria-selected={i === selected}
              onClick={() => setSelected(i)}
              className={`rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                i === selected ? "bg-accent text-accent-ink" : "bg-raised text-muted hover:bg-raised-2"
              }`}
            >
              <span className="block text-xs opacity-80">{i === 0 ? "Best plan" : `Alternative ${i}`}</span>
              <span className="num block font-semibold">
                {p.gain_vs_no_transfers >= 0 ? "+" : ""}
                {points(p.gain_vs_no_transfers)} xP
              </span>
            </button>
          ))}
        </div>
        <Select label="" value={horizon} options={horizonOptions()} onChange={setHorizon} />
      </div>
      {loading && <p className="py-4 text-sm text-faint">Planning your transfers… (a few seconds)</p>}
      {error && <ErrorBox message={error} />}
      {data && plan && first && !loading && (
        <>
          {first.chip && (
            <p className="mb-2 text-sm">
              <ChipBadge label={first.chip} /> <span className="ml-1">Play it this gameweek.</span>
            </p>
          )}
          {first.moves.length > 0 ? (
            <ul className="space-y-2">
              {first.moves.map((m) => (
                <Move key={m.player_in.player_id} move={m} gameweeks={data.gameweeks} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No transfer is worth more than keeping it for later.</p>
          )}
          <p className="mt-3 text-xs text-faint">
            GW{first.gameweek}: {first.hits > 0 ? `${first.hits} hit${first.hits > 1 ? "s" : ""} (−${first.hit_points}), ` : "no hits, "}
            {money(first.bank)} left in the bank, {points(first.expected_points)} expected points from the XI and captain.
          </p>
          {compact ? (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-medium text-accent">Why these moves</summary>
              <div className="mt-2">
                <Why source={source} horizon={horizon} rank={plan.rank} />
              </div>
            </details>
          ) : (
            <div className="mt-3">
              <Why source={source} horizon={horizon} rank={plan.rank} />
            </div>
          )}
          <LaterGameweeks plan={plan} />
          {(() => {
            const notes = (
              <ul className="mt-2 space-y-0.5 text-xs text-faint">
                <li>
                  Plans are ranked by expected points over GW{data.gameweeks[0]}–{data.gameweeks[data.gameweeks.length - 1]}, with nearer
                  gameweeks counting more, so a plan with slightly more raw points can rank lower.
                </li>
                {data.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            );
            return compact ? (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer font-medium text-accent">About these numbers</summary>
                {notes}
              </details>
            ) : (
              <div className="mt-2">{notes}</div>
            );
          })()}
        </>
      )}
    </div>
  );
}

/** Captain, vice-captain and bench order for the plan's first gameweek. */
export function PlanPicks({ gw }: { gw: GameweekRecommendation }) {
  return (
    <div className="grid grid-cols-2 gap-2 text-sm @[30rem]:grid-cols-3">
      <div className="rounded-xl bg-raised p-3">
        <div className="text-xs text-faint">Captain</div>
        <div className="font-semibold">
          {gw.captain.web_name} <span className="num font-normal text-faint">({points(gw.captain.xp * 2)} xP)</span>
        </div>
      </div>
      <div className="rounded-xl bg-raised p-3">
        <div className="text-xs text-faint">Vice-captain</div>
        <div className="font-semibold">{gw.vice_captain.web_name}</div>
      </div>
      <div className="col-span-2 rounded-xl bg-raised p-3 @[30rem]:col-span-1">
        <div className="text-xs text-faint">Bench order</div>
        <div className="font-semibold">{gw.bench.map((p) => p.web_name).join(", ")}</div>
      </div>
    </div>
  );
}

export function ChipsAdvice({ chips }: { chips: ChipAdvice[] }) {
  if (chips.length === 0) return null;
  return (
    <div className="mt-3">
      <ul className="grid gap-2 @[34rem]:grid-cols-2">
        {chips.map((c) => (
          <li
            key={`${c.chip}-${c.half}`}
            className={`rounded-xl p-2.5 text-sm ${c.play_in_gameweek != null ? "bg-accent text-accent-ink" : "bg-raised"}`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-semibold">{c.label}</span>
              <span className={`text-xs ${c.play_in_gameweek != null ? "" : "text-faint"}`}>
                {c.half === 1 ? "1st" : "2nd"} half · GW{c.window_start}–{c.window_end}
              </span>
            </div>
            <p className={`mt-0.5 text-xs ${c.play_in_gameweek != null ? "" : "text-muted"}`}>{c.advice}</p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-faint">
        A chip is only played when it beats what saving it is likely to be worth, a hand-set estimate that shrinks to zero as its
        window closes. Chips are usually best saved for double or blank gameweeks.
      </p>
    </div>
  );
}
