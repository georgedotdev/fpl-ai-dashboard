import { useState } from "react";
import { getExplanation, getRecommendations, type ChipAdvice, type GameweekRecommendation, type MovePlan, type RecommendedPlan } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { Card } from "./Card";
import { ErrorBox, Loading, Select, horizonOptions } from "./ui";

function points(n: number): string {
  return n.toFixed(1);
}

function Move({ move, gameweeks }: { move: MovePlan; gameweeks: number[] }) {
  const { player_out: out, player_in: inn } = move;
  return (
    <li className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-medium">
          <span className="text-red-700 dark:text-red-400">{out.web_name}</span>
          <span className="mx-1.5 text-slate-400">→</span>
          <span className="text-emerald-700 dark:text-emerald-400">{inn.web_name}</span>
          <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">{inn.position}</span>
        </p>
        <span className="text-sm font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
          +{points(move.xp_gain)} xP
        </span>
      </div>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[22rem] text-xs tabular-nums">
          <thead>
            <tr className="text-slate-500 dark:text-slate-400">
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
            {[
              { p: out, label: `sell ~${money(out.price)}` },
              { p: inn, label: `buy ${money(inn.price)}` },
            ].map(({ p, label }) => (
              <tr key={p.player_id}>
                <td className="py-0.5 pr-2 text-left">
                  {p.web_name} <span className="text-slate-500 dark:text-slate-400">· {label}</span>
                </td>
                {p.xp.map((v, i) => (
                  <td key={i} className="py-0.5 text-right" title={p.fixtures[i].join(", ") || "No fixture"}>
                    {p.fixtures[i].length === 0 ? "–" : points(v)}
                  </td>
                ))}
                <td className="py-0.5 text-right font-medium">{points(p.xp_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {out.status !== "a" && out.news && (
        <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
          {out.web_name}: {out.news}
        </p>
      )}
    </li>
  );
}

function ChipBadge({ label }: { label: string }) {
  return (
    <span className="rounded bg-violet-100 px-1.5 py-0.5 text-xs font-semibold text-violet-800 dark:bg-violet-950 dark:text-violet-300">
      {label}
    </span>
  );
}

function FirstGameweek({ gw, gameweeks }: { gw: GameweekRecommendation; gameweeks: number[] }) {
  return (
    <div className="space-y-3">
      {gw.chip && (
        <p className="text-sm">
          <ChipBadge label={gw.chip} /> <span className="ml-1">Play it this gameweek.</span>
        </p>
      )}
      {gw.moves.length > 0 ? (
        <ul className="space-y-2">
          {gw.moves.map((m) => (
            <Move key={m.player_in.player_id} move={m} gameweeks={gameweeks} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-600 dark:text-slate-300">No transfer is worth more than keeping it for later.</p>
      )}
      <div className="grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Captain</div>
          <div className="font-medium">
            {gw.captain.web_name}{" "}
            <span className="tabular-nums text-slate-500 dark:text-slate-400">({points(gw.captain.xp)} xP)</span>
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Vice-captain</div>
          <div className="font-medium">{gw.vice_captain.web_name}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Bench order</div>
          <div className="font-medium">{gw.bench.map((p) => p.web_name).join(", ")}</div>
        </div>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        GW{gw.gameweek}: {gw.hits > 0 ? `${gw.hits} hit${gw.hits > 1 ? "s" : ""} (−${gw.hit_points}), ` : "no hits, "}
        {money(gw.bank)} left in the bank, {points(gw.expected_points)} expected points from the XI and captain.
      </p>
    </div>
  );
}

function LaterGameweeks({ plan }: { plan: RecommendedPlan }) {
  const later = plan.gameweeks.slice(1);
  if (later.length === 0) return null;
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-violet-700 hover:underline dark:text-violet-400">The rest of the plan</summary>
      <ul className="mt-2 space-y-1">
        {later.map((gw) => (
          <li key={gw.gameweek} className="tabular-nums">
            <span className="font-medium">GW{gw.gameweek}</span>
            <span className="text-slate-500 dark:text-slate-400"> · {gw.free_transfers ?? "∞"} FT · </span>
            {gw.moves.length ? gw.moves.map((m) => `${m.player_out.web_name} → ${m.player_in.web_name}`).join(", ") : "roll"}
            {gw.hits > 0 && <span className="text-red-600 dark:text-red-400"> (−{gw.hit_points})</span>}
            {gw.chip && (
              <>
                {" "}
                <ChipBadge label={gw.chip} />
              </>
            )}
            <span className="text-slate-500 dark:text-slate-400"> · C {gw.captain.web_name}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Later moves are provisional: re-check after each deadline, when the predictions update.
      </p>
    </details>
  );
}

function Why({ teamId, horizon, rank }: { teamId: number; horizon: number; rank: number }) {
  const { data, error, loading } = useData(() => getExplanation(teamId, horizon, rank), [teamId, horizon, rank]);
  return (
    <div className="mb-3 rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800/60">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Why</span>
        {data && (
          <span
            className="text-[11px] text-slate-500 dark:text-slate-400"
            title="Written only from the plan's facts; every number is checked against them before it's shown."
          >
            {data.source === "local_model" ? `Written by a local model (${data.model})` : "Written from the plan's facts"}
          </span>
        )}
      </div>
      {loading && <p className="text-slate-500 dark:text-slate-400">Writing the explanation…</p>}
      {error && <p className="text-red-700 dark:text-red-400">{error}</p>}
      {data && !loading && (
        <>
          <p className="leading-relaxed">{data.text}</p>
          {data.note && <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">{data.note}</p>}
        </>
      )}
    </div>
  );
}

function ChipsAdvice({ chips }: { chips: ChipAdvice[] }) {
  if (chips.length === 0) return null;
  const play = (c: ChipAdvice) => c.play_in_gameweek != null;
  return (
    <div className="mt-4 border-t border-slate-100 pt-3 dark:border-slate-800">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Chips</h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {chips.map((c) => (
          <li
            key={`${c.chip}-${c.half}`}
            className={`rounded-lg border p-2.5 text-sm ${
              play(c)
                ? "border-violet-400 bg-violet-50 dark:border-violet-700 dark:bg-violet-950"
                : "border-slate-200 dark:border-slate-800"
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">{c.label}</span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {c.half === 1 ? "1st" : "2nd"} half · GW{c.window_start}–{c.window_end}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">{c.advice}</p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        A chip is only played when it beats what saving it is likely to be worth, a hand-set estimate that shrinks to zero
        as its window closes. Chips are usually best saved for double or blank gameweeks.
      </p>
    </div>
  );
}

export function RecommendationsPanel({ teamId, refreshKey }: { teamId: number; refreshKey: string }) {
  const [horizon, setHorizon] = useState(5);
  const [selected, setSelected] = useState(0);
  const { data, error, loading } = useData(() => getRecommendations(teamId, horizon), [teamId, horizon, refreshKey]);
  const plan = data?.plans[selected];

  return (
    <Card
      title="Recommended moves"
      aside={
        <Select
          label=""
          value={horizon}
          options={horizonOptions()}
          onChange={(h) => {
            setHorizon(h);
            setSelected(0);
          }}
        />
      }
    >
      {loading && <Loading label="Planning your transfers… (a few seconds)" />}
      {error && <ErrorBox message={error} />}
      {data && !loading && (
        <div>
          <div className="mb-3 flex flex-wrap gap-2" role="tablist">
            {data.plans.map((p, i) => (
              <button
                key={p.rank}
                role="tab"
                aria-selected={i === selected}
                onClick={() => setSelected(i)}
                className={`rounded-lg border px-3 py-2 text-left text-sm ${
                  i === selected
                    ? "border-violet-500 bg-violet-50 dark:bg-violet-950"
                    : "border-slate-200 hover:border-slate-400 dark:border-slate-800"
                }`}
              >
                <div className="text-xs text-slate-500 dark:text-slate-400">{i === 0 ? "Best plan" : `Alternative ${i}`}</div>
                <div className="font-medium tabular-nums">
                  {p.gain_vs_no_transfers >= 0 ? "+" : ""}
                  {points(p.gain_vs_no_transfers)} xP vs no transfers
                </div>
              </button>
            ))}
          </div>
          {plan && (
            <>
              <h3 className="mb-2 font-semibold">{plan.headline}</h3>
              <Why teamId={teamId} horizon={horizon} rank={plan.rank} />
              <FirstGameweek gw={plan.gameweeks[0]} gameweeks={data.gameweeks} />
              <LaterGameweeks plan={plan} />
            </>
          )}
          <ChipsAdvice chips={data.chips} />
          <ul className="mt-4 space-y-0.5 border-t border-slate-100 pt-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <li>
              Plans are ranked by expected points over GW{data.gameweeks[0]}–{data.gameweeks[data.gameweeks.length - 1]}, with
              nearer gameweeks counting more, so a plan with slightly more raw points can rank lower.
            </li>
            {data.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
