import type { Position, SquadPlayer } from "../api";
import { STATUS_LABELS, money } from "../format";

const POSITION_ORDER: Position[] = ["GKP", "DEF", "MID", "FWD"];

const STATUS_STYLES: Record<string, string> = {
  d: "bg-warn/20 text-warn",
  i: "bg-negative/20 text-negative",
  s: "bg-negative/20 text-negative",
  u: "bg-raised-2 text-muted",
  n: "bg-raised-2 text-muted",
};

function Availability({ player }: { player: SquadPlayer }) {
  if (player.status === "a") return null;
  const chance = player.chance_of_playing_next_round;
  return (
    <span
      title={player.news || undefined}
      className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${STATUS_STYLES[player.status] ?? STATUS_STYLES.u}`}
    >
      {STATUS_LABELS[player.status] ?? player.status}
      {chance != null ? ` · ${chance}%` : ""}
    </span>
  );
}

function PlayerRow({ player }: { player: SquadPlayer }) {
  const sell = player.selling_price;
  const changed = sell.value !== player.now_cost;
  return (
    <li className="flex items-center gap-3 py-2">
      <span className="w-9 shrink-0 text-xs font-medium text-faint">{player.position}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="truncate font-medium">{player.web_name}</span>
          {player.is_captain && (
            <span className="rounded-full bg-white px-1.5 text-[11px] font-bold text-raised">
              C
            </span>
          )}
          {player.is_vice_captain && (
            <span className="rounded-full border border-line px-1.5 text-[11px] font-bold text-muted">
              V
            </span>
          )}
          <Availability player={player} />
        </div>
        <div className="text-xs text-faint">
          {player.team_short_name}
          {player.news && player.status !== "a" ? ` · ${player.news}` : ""}
        </div>
      </div>
      <div className="shrink-0 text-right tabular-nums">
        <div className="text-sm font-medium">{money(player.now_cost)}</div>
        <div
          className={`text-xs ${changed ? "text-warn" : "text-faint"}`}
          title={[sell.note, player.purchase_price.note].filter(Boolean).join(" ")}
        >
          sells ~{money(sell.value)}
        </div>
      </div>
    </li>
  );
}

export function Squad({ squad }: { squad: SquadPlayer[] }) {
  const starters = squad
    .filter((p) => p.bench_order == null)
    .sort((a, b) => POSITION_ORDER.indexOf(a.position) - POSITION_ORDER.indexOf(b.position) || a.slot - b.slot);
  const bench = squad.filter((p) => p.bench_order != null).sort((a, b) => a.bench_order! - b.bench_order!);

  return (
    <div className="grid gap-x-8 lg:grid-cols-[2fr_1fr]">
      <div>
        <h3 className="text-xs font-medium text-faint">Starting XI</h3>
        <ul className="divide-y divide-line">
          {starters.map((p) => (
            <PlayerRow key={p.player_id} player={p} />
          ))}
        </ul>
      </div>
      <div className="mt-4 lg:mt-0">
        <h3 className="text-xs font-medium text-faint">Bench (substitution order)</h3>
        <ul className="divide-y divide-line">
          {bench.map((p) => (
            <PlayerRow key={p.player_id} player={p} />
          ))}
        </ul>
        <p className="mt-3 text-xs text-faint">
          "Sells ~" is our estimate: FPL only shows exact selling prices when you're logged in. It's your purchase
          price plus half of any rise, rounded down. Price falls are passed on in full.
        </p>
      </div>
    </div>
  );
}
