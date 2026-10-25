// Types mirror backend/app/manager/state.py. Money is in tenths of £1m.

export type Source = "api" | "derived" | "user_override";

export interface Sourced<T> {
  value: T;
  source: Source;
  note: string | null;
}

export type Position = "GKP" | "DEF" | "MID" | "FWD";

export interface SquadPlayer {
  player_id: number;
  web_name: string;
  team_id: number;
  team_short_name: string;
  position: Position;
  slot: number;
  is_captain: boolean;
  is_vice_captain: boolean;
  bench_order: number | null;
  now_cost: number;
  purchase_price: Sourced<number | null>;
  selling_price: Sourced<number>;
  status: string;
  chance_of_playing_next_round: number | null;
  news: string;
}

export interface ChipStatus {
  chip: string;
  label: string;
  half: number;
  window_start: number;
  window_end: number;
  state: "available" | "used" | "expired" | "upcoming";
  played_gameweek: number | null;
  usable_from_gameweek: number | null;
  note: string | null;
}

export interface GameweekResult {
  gameweek: number;
  points: number;
  total_points: number;
  overall_rank: number | null;
  bank: number;
  team_value: number;
  transfers: number;
  transfer_cost: number;
  points_on_bench: number;
  chip: string | null;
}

export interface ManagerState {
  team_id: number;
  manager_name: string;
  team_name: string;
  season: string;
  current_gameweek: number;
  planning_gameweek: number | null;
  started_gameweek: number;
  overall_rank: number | null;
  total_points: number | null;
  squad_gameweek: number;
  squad_note: string;
  squad: SquadPlayer[];
  bank: Sourced<number>;
  team_value: Sourced<number>;
  sale_value: Sourced<number>;
  free_transfers: Sourced<number | null>;
  max_free_transfers: number;
  chips: ChipStatus[];
  past_gameweeks: GameweekResult[];
  warnings: string[];
}

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error("Can't reach the server. Is the backend running?");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function getManager(teamId: number): Promise<ManagerState> {
  return request(`/manager/${teamId}`);
}

export function setFreeTransfers(teamId: number, freeTransfers: number | null): Promise<ManagerState> {
  return request(`/manager/${teamId}/state`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ free_transfers: freeTransfers }),
  });
}
