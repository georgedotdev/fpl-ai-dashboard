import { getCaptaincy } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { Card } from "./Card";
import { Availability } from "./PlayersView";
import { ErrorBox, Loading } from "./ui";

export function CaptaincyView() {
  const { data, error, loading } = useData(() => getCaptaincy(10), []);

  return (
    <Card title={data ? `Best captains for GW${data.gameweeks[0]}` : "Best captains"}>
      {error && <ErrorBox message={error} />}
      {loading && <Loading />}
      {data && (
        <>
          <ol className="grid gap-2 sm:grid-cols-2">
            {data.players.map((p, i) => (
              <li key={p.player_id} className="flex items-center gap-3 rounded-lg border border-line p-3">
                <span className="w-6 text-center text-lg font-bold text-faint">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {p.web_name}
                    <Availability player={p} />
                  </div>
                  <div className="text-xs text-faint">
                    {p.team_short_name} · {money(p.now_cost)} · {p.upcoming.join(", ") || "no fixture"} · {p.selected_by_percent.toFixed(1)}%
                    owned
                  </div>
                </div>
                <div className="text-right tabular-nums">
                  <div className="text-lg font-semibold">{(p.xp_next * 2).toFixed(1)}</div>
                  <div className="text-[11px] text-faint">as captain</div>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-xs text-faint">
            Expected points for the next gameweek, doubled for the armband, from the "{data.model}" predictor. Your own best
            captain is in your recommendations.
          </p>
        </>
      )}
    </Card>
  );
}
