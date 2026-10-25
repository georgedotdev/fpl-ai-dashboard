import { useState } from "react";
import { getBestPicks } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { Card } from "./Card";
import { Availability } from "./PlayersView";
import { ErrorBox, Loading, PRICE_OPTIONS, Select, Toolbar, horizonOptions } from "./ui";

const POSITIONS = [
  { code: "GKP", label: "Goalkeepers" },
  { code: "DEF", label: "Defenders" },
  { code: "MID", label: "Midfielders" },
  { code: "FWD", label: "Forwards" },
];

function PositionList({ position, label, horizon, maxPrice }: { position: string; label: string; horizon: number; maxPrice: number }) {
  const { data, error, loading } = useData(
    () => getBestPicks({ horizon, position, max_price: maxPrice || undefined, limit: 5 }),
    [position, horizon, maxPrice],
  );
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium text-slate-500 dark:text-slate-400">{label}</h3>
      {error && <ErrorBox message={error} />}
      {loading && !data && <Loading />}
      {data && (
        <ol className={`divide-y divide-slate-100 dark:divide-slate-800 ${loading ? "opacity-60" : ""}`}>
          {data.players.map((p) => (
            <li key={p.player_id} className="flex items-center gap-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="font-medium">
                  {p.web_name}
                  <Availability player={p} />
                </div>
                <div className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {p.team_short_name} · {p.upcoming.join(", ")}
                </div>
              </div>
              <div className="text-right text-sm tabular-nums">
                <div className="font-semibold">{p.xp_horizon.toFixed(1)} xP</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">{money(p.now_cost)}</div>
              </div>
            </li>
          ))}
          {data.players.length === 0 && <li className="py-2 text-sm text-slate-500">Nobody at this price.</li>}
        </ol>
      )}
    </div>
  );
}

export function BestPicksView() {
  const [horizon, setHorizon] = useState(5);
  const [maxPrice, setMaxPrice] = useState(0);
  return (
    <Card title="Best players for the coming fixtures">
      <Toolbar>
        <Select label="Horizon" value={horizon} options={horizonOptions()} onChange={setHorizon} />
        <Select label="Price" value={maxPrice} options={PRICE_OPTIONS} onChange={setMaxPrice} />
      </Toolbar>
      <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
        {POSITIONS.map((p) => (
          <PositionList key={p.code} position={p.code} label={p.label} horizon={horizon} maxPrice={maxPrice} />
        ))}
      </div>
    </Card>
  );
}
