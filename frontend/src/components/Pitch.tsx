import { useEffect, useRef, useState } from "react";
import type { PickedPlayer, Position } from "../api";
import { STATUS_LABELS, money } from "../format";
import { Shirt } from "./Shirt";

const ROW_Y: Record<Position, number> = { GKP: 87, DEF: 63, MID: 38, FWD: 13 }; // % from the top

function positions(players: PickedPlayer[]): Map<number, { x: number; y: number }> {
  const rows = new Map<Position, PickedPlayer[]>();
  for (const p of players) rows.set(p.position, [...(rows.get(p.position) ?? []), p]);
  const out = new Map<number, { x: number; y: number }>();
  for (const [pos, list] of rows) {
    list.forEach((p, i) => out.set(p.player_id, { x: ((i + 0.5) / list.length) * 100, y: ROW_Y[pos] }));
  }
  return out;
}

// The name bar takes the chance-of-playing colour, as on the FPL site.
function nameBar(p: PickedPlayer): string {
  if (p.status === "a") return "bg-white text-raised";
  const chance = p.chance_of_playing_next_round ?? 0;
  if (chance >= 75) return "bg-[#ffe65b] text-raised";
  if (chance >= 50) return "bg-warn text-raised";
  return "bg-[#d81920] text-white";
}

function Card({ p, captain, vice }: { p: PickedPlayer; captain: boolean; vice: boolean }) {
  const points = p.xp * (captain ? 2 : 1);
  return (
    <>
      {(captain || vice) && (
        <span
          className={`absolute left-[3px] top-[3px] grid h-[15px] w-[15px] place-items-center rounded-full text-[9px] font-extrabold lg:h-[18px] lg:w-[18px] lg:text-[10px] ${
            captain ? "bg-white text-raised" : "bg-raised text-white"
          }`}
        >
          {captain ? "C" : "V"}
        </span>
      )}
      <span className="num absolute right-[3px] top-[3px] rounded bg-accent px-1 text-[10px] font-bold leading-[14px] text-accent-ink lg:text-[11px] lg:leading-4">
        {points.toFixed(1)}
      </span>
      <span className="absolute inset-x-0 top-[6%] flex justify-center">
        <Shirt team={p.team_short_name} size={44} className="h-auto w-[64%] drop-shadow" />
      </span>
      <span className="absolute inset-x-[2px] bottom-[2px] flex flex-col overflow-hidden rounded-[3px] font-bold">
        <span
          className={`truncate px-[3px] py-[2px] text-center text-[10px] leading-[13px] lg:text-xs lg:leading-4 ${nameBar(p)}`}
        >
          {p.web_name}
        </span>
        <span className="truncate bg-raised px-[3px] py-px text-center text-[9px] font-medium leading-3 text-white lg:text-[11px] lg:leading-[15px]">
          {p.fixtures[0] ?? "No game"}
        </span>
      </span>
    </>
  );
}

/** The XI on an FPL-style pitch. Players in both XIs slide to their new places when the XI changes. */
export function Pitch({
  lineup,
  captainId,
  viceId,
}: {
  lineup: PickedPlayer[];
  captainId: number;
  viceId: number;
}) {
  const pos = positions(lineup);
  const [picked, setPicked] = useState<{ p: PickedPlayer; left: number; top: number } | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!picked) return;
    const close = (e: PointerEvent) => {
      if (!(e.target as HTMLElement).closest("[data-player-sheet], [data-player]")) setPicked(null);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [picked]);

  function open(p: PickedPlayer, el: HTMLElement) {
    const box = boxRef.current!.getBoundingClientRect();
    const r = el.closest("[data-player]")!.getBoundingClientRect();
    setPicked({
      p,
      left: Math.min(Math.max(8, r.left - box.left + r.width / 2 - 120), box.width - 248),
      top: r.bottom - box.top + 6,
    });
  }

  return (
    <div ref={boxRef} className="pitch relative aspect-[68/98] overflow-hidden rounded-xl sm:aspect-[68/80]"
      style={{ background: "repeating-linear-gradient(180deg, var(--color-pitch-a) 0 10%, var(--color-pitch-b) 10% 20%)" }}>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 68 72" preserveAspectRatio="none" aria-hidden="true">
        <g fill="none" stroke="rgba(255,255,255,.35)" strokeWidth=".4">
          <rect x="2" y="2" width="64" height="68" />
          <path d="M2 36h64" />
          <circle cx="34" cy="36" r="7" />
          <rect x="18" y="2" width="32" height="12" />
          <rect x="18" y="58" width="32" height="12" />
          <rect x="27" y="2" width="14" height="5" />
          <rect x="27" y="65" width="14" height="5" />
        </g>
      </svg>
      {lineup.map((p, i) => {
        const at = pos.get(p.player_id)!;
        return (
          <button
            key={p.player_id}
            type="button"
            data-player
            className="player"
            style={{ left: `${at.x}%`, top: `${at.y}%`, animationDelay: `${i * 28}ms` }}
            aria-label={`${p.web_name}, ${p.team_short_name}, ${p.xp.toFixed(1)} expected points${p.player_id === captainId ? ", captain" : ""}`}
            onClick={(e) => open(p, e.currentTarget)}
          >
            <Card p={p} captain={p.player_id === captainId} vice={p.player_id === viceId} />
          </button>
        );
      })}
      {picked && (
        <div
          data-player-sheet
          role="dialog"
          aria-label={picked.p.web_name}
          className="absolute z-10 w-60 rounded-[14px] bg-raised p-3 text-sm shadow-[0_12px_28px_rgba(0,0,0,.45)]"
          style={{ left: picked.left, top: picked.top }}
        >
          <div className="mb-2 flex items-center gap-2">
            <Shirt team={picked.p.team_short_name} size={28} />
            <div>
              <strong>{picked.p.web_name}</strong>
              <span className="block text-xs text-faint">
                {picked.p.team_short_name} · {picked.p.position} · {money(picked.p.price)}
              </span>
            </div>
          </div>
          <dl className="space-y-1 text-xs">
            <div className="flex justify-between gap-2"><dt className="text-faint">Next fixture</dt><dd>{picked.p.fixtures.join(", ") || "No game"}</dd></div>
            <div className="flex justify-between gap-2"><dt className="text-faint">Expected points</dt><dd className="num">{picked.p.xp.toFixed(1)}</dd></div>
            <div className="flex justify-between gap-2"><dt className="text-faint">Owned by</dt><dd className="num">{picked.p.selected_by_percent.toFixed(1)}%</dd></div>
            {picked.p.status !== "a" && (
              <div className="flex justify-between gap-2"><dt className="text-faint">{STATUS_LABELS[picked.p.status] ?? "Status"}</dt><dd className="text-right">{picked.p.news}</dd></div>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}

/** The bench in substitution order, goalkeeper first. */
export function Bench({ players }: { players: PickedPlayer[] }) {
  return (
    <div className="mt-3 grid grid-cols-2 gap-2 @[34rem]:grid-cols-4" aria-label="Bench">
      {players.map((p) => (
        <div key={p.player_id} className="flex min-w-0 items-center gap-1.5 rounded-xl bg-raised p-2">
          <Shirt team={p.team_short_name} size={22} className="flex-none" />
          <span className="truncate text-xs text-muted">{p.web_name}</span>
          <span className="num ml-auto text-xs text-faint">{p.xp.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}
