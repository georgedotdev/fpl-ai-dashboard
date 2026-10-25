import { useState } from "react";
import { getPlayers, type PlayerSummary } from "../api";
import { STATUS_LABELS, money } from "../format";
import { useData } from "../hooks";
import { Card } from "./Card";
import { ErrorBox, Loading, POSITION_OPTIONS, PRICE_OPTIONS, Select, Toolbar, horizonOptions } from "./ui";

const SORTS = [
  { value: "xp_horizon", label: "Expected points (horizon)" },
  { value: "xp_next", label: "Expected points (next GW)" },
  { value: "xp_per_million", label: "Value (xP per £m)" },
  { value: "form", label: "Form" },
  { value: "total_points", label: "Total points" },
  { value: "now_cost", label: "Price" },
  { value: "cost_change_event", label: "Price change this GW" },
  { value: "net_transfers_event", label: "Net transfers this GW" },
  { value: "selected_by_percent", label: "Ownership" },
];

export function PriceChange({ change }: { change: number }) {
  if (change === 0) return <span className="text-slate-400">–</span>;
  return (
    <span className={change > 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}>
      {change > 0 ? "▲" : "▼"}
      {(Math.abs(change) / 10).toFixed(1)}
    </span>
  );
}

export function Availability({ player }: { player: PlayerSummary }) {
  if (player.status === "a") return null;
  return (
    <span
      title={player.news}
      className="ml-1 rounded bg-amber-100 px-1 text-[10px] font-medium text-amber-900 dark:bg-amber-950 dark:text-amber-300"
    >
      {STATUS_LABELS[player.status] ?? player.status}
      {player.chance_of_playing_next_round != null ? ` ${player.chance_of_playing_next_round}%` : ""}
    </span>
  );
}

export function PlayersView() {
  const [horizon, setHorizon] = useState(5);
  const [position, setPosition] = useState("");
  const [maxPrice, setMaxPrice] = useState(0);
  const [sort, setSort] = useState("xp_horizon");
  const { data, error, loading } = useData(
    () => getPlayers({ horizon, position, max_price: maxPrice || undefined, sort, limit: 100 }),
    [horizon, position, maxPrice, sort],
  );

  return (
    <Card title="Players">
      <Toolbar>
        <Select label="Position" value={position} options={POSITION_OPTIONS} onChange={setPosition} />
        <Select label="Price" value={maxPrice} options={PRICE_OPTIONS} onChange={setMaxPrice} />
        <Select label="Sort by" value={sort} options={SORTS} onChange={setSort} />
        <Select label="Horizon" value={horizon} options={horizonOptions()} onChange={setHorizon} />
      </Toolbar>
      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && (
        <div className={`-mx-4 overflow-x-auto px-4 ${loading ? "opacity-60" : ""}`}>
          <table className="w-full min-w-[46rem] text-sm tabular-nums">
            <thead>
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                <th className="py-1.5 font-medium">Player</th>
                <th className="py-1.5 text-right font-medium">Price</th>
                <th className="py-1.5 text-right font-medium" title="Change since this gameweek's deadline / since the season started">
                  Δ GW / season
                </th>
                <th className="py-1.5 text-right font-medium">Form</th>
                <th className="py-1.5 text-right font-medium">Owned</th>
                <th className="py-1.5 text-right font-medium" title="Our expected points for the next gameweek">
                  xP next
                </th>
                <th className="py-1.5 text-right font-medium" title={`Our expected points over GW${data.gameweeks[0]}–${data.gameweeks.at(-1)}`}>
                  xP {data.gameweeks.length} GW
                </th>
                <th className="py-1.5 pl-4 font-medium">Fixtures</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.players.map((p) => (
                <tr key={p.player_id}>
                  <td className="py-1.5">
                    <span className="font-medium">{p.web_name}</span>
                    <Availability player={p} />
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {p.team_short_name} · {p.position}
                    </div>
                  </td>
                  <td className="py-1.5 text-right">{money(p.now_cost)}</td>
                  <td className="py-1.5 text-right text-xs">
                    <PriceChange change={p.cost_change_event} /> / <PriceChange change={p.cost_change_start} />
                  </td>
                  <td className="py-1.5 text-right">{p.form.toFixed(1)}</td>
                  <td className="py-1.5 text-right">{p.selected_by_percent.toFixed(1)}%</td>
                  <td className="py-1.5 text-right">{p.xp_next.toFixed(1)}</td>
                  <td className="py-1.5 text-right font-semibold">{p.xp_horizon.toFixed(1)}</td>
                  <td className="py-1.5 pl-4 text-xs text-slate-500 dark:text-slate-400">{p.upcoming.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            xP comes from the "{data.model}" predictor. Top 100 shown.
          </p>
        </div>
      )}
    </Card>
  );
}
