import { useMemo, useRef, useState } from "react";
import { getPlayers, getRules, type ManualSquad, type PlayerSummary, type Position } from "../api";
import { money } from "../format";
import { useData } from "../hooks";
import { Card } from "./Card";
import { ErrorBox, Loading } from "./ui";

const POSITIONS: { code: Position; label: string }[] = [
  { code: "GKP", label: "Goalkeepers" },
  { code: "DEF", label: "Defenders" },
  { code: "MID", label: "Midfielders" },
  { code: "FWD", label: "Forwards" },
];

/** Pick your 15 players, bank, free transfers and chips: no team ID needed. */
export function ManualSquadBuilder({
  initial,
  submitting,
  error,
  onSubmit,
  onDraftChange,
}: {
  initial: ManualSquad | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (squad: ManualSquad) => void;
  onDraftChange: (squad: ManualSquad) => void;
}) {
  const rules = useData(getRules, []);
  const players = useData(() => getPlayers({ horizon: 1, limit: 1000, sort: "selected_by_percent" }), []);

  const [picked, setPicked] = useState<number[]>(initial?.player_ids ?? []);
  const [bankText, setBankText] = useState(initial ? (initial.bank / 10).toFixed(1) : "0.0");
  const [freeTransfers, setFreeTransfers] = useState(initial?.free_transfers ?? 1);
  const [chips, setChips] = useState<string[] | null>(initial?.chips_available ?? null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Position | "">("");
  const searchRef = useRef<HTMLInputElement>(null);

  const byId = useMemo(
    () => new Map((players.data?.players ?? []).map((p) => [p.player_id, p])),
    [players.data],
  );
  const openChips = (rules.data?.chips ?? []).filter((c) => c.open_now);
  const chipsHeld = chips ?? openChips.map((c) => c.key); // default: you still have them all
  const bank = Math.round(Number(bankText) * 10);
  const bankValid = Number.isFinite(bank) && bank >= 0;

  if (rules.error || players.error) return <ErrorBox message={(rules.error ?? players.error)!} />;
  if (!rules.data || !players.data) return <Loading label="Loading players…" />;
  const r = rules.data;

  const pickedPlayers = picked.map((id) => byId.get(id)).filter((p): p is PlayerSummary => !!p);
  const count = (pos: Position) => pickedPlayers.filter((p) => p.position === pos).length;
  const fromClub = (team: number) => pickedPlayers.filter((p) => p.team_id === team).length;

  function draft(next: Partial<ManualSquad>): ManualSquad {
    return {
      player_ids: picked,
      bank: bankValid ? bank : 0,
      free_transfers: freeTransfers,
      chips_available: chipsHeld,
      ...next,
    };
  }

  function update(next: Partial<ManualSquad>) {
    onDraftChange(draft(next));
  }

  function whyNot(p: PlayerSummary): string | null {
    if (picked.includes(p.player_id)) return "Picked";
    if (count(p.position) >= r.positions[p.position]) return `${p.position} full`;
    if (fromClub(p.team_id) >= r.max_per_club) return `${r.max_per_club} from ${p.team_short_name}`;
    return null;
  }

  function add(id: number) {
    const next = [...picked, id];
    setPicked(next);
    update({ player_ids: next });
  }

  function remove(id: number) {
    const next = picked.filter((x) => x !== id);
    setPicked(next);
    update({ player_ids: next });
  }

  const needle = search.trim().toLowerCase();
  const matches = players.data.players
    .filter((p) => (!filter || p.position === filter) && (!needle || p.web_name.toLowerCase().includes(needle) || p.team_short_name.toLowerCase() === needle))
    .slice(0, 40);
  const complete = picked.length === r.squad_size;

  return (
    <Card title="Enter your squad">
      <p className="mb-4 text-sm text-muted">
        No team ID needed: pick your {r.squad_size} players and tell us your bank, free transfers and chips. It's saved on
        this device, so next time you only change what's different.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          {POSITIONS.map(({ code, label }) => (
            <div key={code}>
              <div className="mb-1 flex items-baseline justify-between">
                <h3 className="text-xs font-medium text-faint">{label}</h3>
                <button
                  onClick={() => {
                    // On a phone the search sits below the squad: take the user to it.
                    setFilter(code);
                    searchRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                    searchRef.current?.focus({ preventScroll: true });
                  }}
                  className={`text-xs tabular-nums ${count(code) === r.positions[code] ? "text-accent" : "text-accent hover:underline"}`}
                >
                  {count(code)}/{r.positions[code]}
                  {count(code) < r.positions[code] ? " · add" : ""}
                </button>
              </div>
              <ul className="flex flex-wrap gap-1.5">
                {pickedPlayers
                  .filter((p) => p.position === code)
                  .map((p) => (
                    <li key={p.player_id} className="flex items-center gap-1 rounded-full border border-line py-0.5 pl-2.5 pr-1 text-sm">
                      {p.web_name}
                      <span className="text-xs text-faint">{p.team_short_name}</span>
                      <button
                        onClick={() => remove(p.player_id)}
                        aria-label={`Remove ${p.web_name}`}
                        className="ml-0.5 rounded-full px-1.5 text-faint hover:bg-raised-2"
                      >
                        ×
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          ))}

          <div className="grid grid-cols-2 gap-3 border-t border-line pt-4">
            <label className="text-xs text-faint">
              Money in the bank (£m)
              <input
                inputMode="decimal"
                value={bankText}
                onChange={(e) => {
                  setBankText(e.target.value);
                  const tenths = Math.round(Number(e.target.value) * 10);
                  if (Number.isFinite(tenths) && tenths >= 0) update({ bank: tenths });
                }}
                className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm tabular-nums text-ink"
              />
            </label>
            <label className="text-xs text-faint">
              Free transfers for GW{r.planning_gameweek}
              <select
                value={freeTransfers}
                onChange={(e) => {
                  setFreeTransfers(Number(e.target.value));
                  update({ free_transfers: Number(e.target.value) });
                }}
                className="mt-1 w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
              >
                {Array.from({ length: r.max_free_transfers + 1 }, (_, n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {openChips.length > 0 && (
            <fieldset>
              <legend className="text-xs text-faint">Chips you still have</legend>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                {openChips.map((c) => (
                  <label key={c.key} className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={chipsHeld.includes(c.key)}
                      onChange={(e) => {
                        const next = e.target.checked ? [...chipsHeld, c.key] : chipsHeld.filter((k) => k !== c.key);
                        setChips(next);
                        update({ chips_available: next });
                      }}
                    />
                    {c.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {error && <ErrorBox message={error} />}
          <button
            disabled={!complete || !bankValid || submitting}
            onClick={() => onSubmit(draft({}))}
            className="w-full rounded-lg bg-accent px-4 py-2.5 font-medium text-accent-ink hover:brightness-110 disabled:opacity-50"
          >
            {submitting
              ? "Loading…"
              : complete
                ? "Show my recommendations"
                : `Pick ${r.squad_size - picked.length} more player${r.squad_size - picked.length === 1 ? "" : "s"}`}
          </button>
        </div>

        <div>
          <div className="mb-2 flex gap-2">
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search players or a team (e.g. ARS)"
              aria-label="Search players"
              className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink"
            />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as Position | "")}
              aria-label="Position"
              className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm text-ink"
            >
              <option value="">All</option>
              {POSITIONS.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.code}
                </option>
              ))}
            </select>
          </div>
          <ul className="max-h-[28rem] divide-y divide-line overflow-y-auto rounded-lg border border-line">
            {matches.map((p) => {
              const blocked = whyNot(p);
              return (
                <li key={p.player_id} className="flex items-center gap-3 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{p.web_name}</div>
                    <div className="text-xs text-faint">
                      {p.team_short_name} · {p.position} · {money(p.now_cost)}
                    </div>
                  </div>
                  <button
                    disabled={!!blocked}
                    onClick={() => add(p.player_id)}
                    className="shrink-0 rounded-md border border-accent px-2.5 py-1 text-xs font-medium text-accent hover:brightness-110 disabled:border-line disabled:text-faint"
                  >
                    {blocked ?? "Add"}
                  </button>
                </li>
              );
            })}
            {matches.length === 0 && <li className="px-3 py-2 text-sm text-faint">No players match.</li>}
          </ul>
          <p className="mt-1 text-xs text-faint">Most-owned players first.</p>
        </div>
      </div>
    </Card>
  );
}
