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

// --- Stage 2: dashboard views and recommendations ------------------------------------

export interface PlayerSummary {
  player_id: number;
  web_name: string;
  team_id: number;
  team_short_name: string;
  position: Position;
  now_cost: number;
  cost_change_event: number;
  cost_change_start: number;
  net_transfers_event: number;
  form: number;
  total_points: number;
  selected_by_percent: number;
  status: string;
  chance_of_playing_next_round: number | null;
  news: string;
  ep_next: number | null;
  xp_next: number;
  xp_horizon: number;
  xp_per_million: number;
  upcoming: string[];
}

export interface PlayersResponse {
  model: string;
  gameweeks: number[];
  players: PlayerSummary[];
}

export interface TeamFixtureCell {
  gameweek: number;
  opponent: string;
  home: boolean;
  difficulty: number;
}

export interface TeamTicker {
  team_id: number;
  name: string;
  short_name: string;
  gameweeks: TeamFixtureCell[][];
  fixture_count: number;
  average_difficulty: number | null;
}

export interface FixturesResponse {
  gameweeks: number[];
  teams: TeamTicker[];
}

export interface PlayerFacts {
  player_id: number;
  web_name: string;
  team_short_name: string;
  position: Position;
  price: number;
  xp: number[];
  xp_total: number;
  availability: number[];
  status: string;
  news: string;
  fixtures: string[][];
}

export interface MovePlan {
  player_out: PlayerFacts;
  player_in: PlayerFacts;
  xp_gain: number;
}

export interface PickedPlayer {
  player_id: number;
  web_name: string;
  position: Position;
  team_short_name: string;
  xp: number;
  fixtures: string[];
  price: number;
  status: string;
  chance_of_playing_next_round: number | null;
  news: string;
  selected_by_percent: number;
}

export interface GameweekRecommendation {
  gameweek: number;
  free_transfers: number | null;
  hits: number;
  hit_points: number;
  chip: string | null;
  moves: MovePlan[];
  captain: PickedPlayer;
  vice_captain: PickedPlayer;
  lineup: PickedPlayer[];
  bench: PickedPlayer[];
  expected_points: number;
  bank: number;
}

export interface ChipAdvice {
  chip: string;
  label: string;
  half: number;
  window_start: number;
  window_end: number;
  play_in_gameweek: number | null;
  expected_gain: number | null;
  opportunity_cost: number;
  advice: string;
}

export interface RecommendedPlan {
  rank: number;
  headline: string;
  expected_points: number;
  gain_vs_no_transfers: number;
  gameweeks: GameweekRecommendation[];
}

export interface Recommendations {
  team_id: number;
  model: string;
  gameweeks: number[];
  decay: number;
  bank: Sourced<number>;
  free_transfers: Sourced<number | null>;
  squad_gameweek: number;
  no_transfers_expected_points: number;
  plans: RecommendedPlan[];
  chips: ChipAdvice[];
  notes: string[];
}

function query(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export interface Explanation {
  plan_rank: number;
  text: string;
  source: "local_model" | "template";
  model: string | null;
  note: string | null;
  facts: Record<string, unknown>;
}

export function getExplanation(teamId: number, horizon: number, plan: number): Promise<Explanation> {
  return request(`/recommendations/${teamId}/explanation${query({ horizon, plan })}`);
}

export function getRecommendations(teamId: number, horizon: number): Promise<Recommendations> {
  return request(`/recommendations/${teamId}${query({ horizon })}`);
}

export function getPlayers(params: {
  horizon: number;
  position?: string;
  max_price?: number;
  sort?: string;
  limit?: number;
}): Promise<PlayersResponse> {
  return request(`/players${query(params)}`);
}

export function getCaptaincy(limit = 10): Promise<PlayersResponse> {
  return request(`/captaincy${query({ limit })}`);
}

export function getBestPicks(params: { horizon: number; position?: string; max_price?: number; limit?: number }): Promise<PlayersResponse> {
  return request(`/picks/best-by-fixtures${query(params)}`);
}

export function getFixtures(horizon: number): Promise<FixturesResponse> {
  return request(`/fdr${query({ horizon })}`);
}

// --- squads entered by hand, and this season's rules ------------------------------------

export interface ManualSquad {
  player_ids: number[];
  bank: number; // tenths of £1m
  free_transfers: number;
  chips_available: string[]; // "<chip>-<half>" keys from Rules.chips
}

export interface ChipRule {
  key: string;
  chip: string;
  label: string;
  half: number;
  window_start: number;
  window_end: number;
  open_now: boolean;
}

export interface Rules {
  season: string;
  planning_gameweek: number | null;
  planning_deadline: string | null;
  squad_size: number;
  positions: Record<Position, number>;
  max_per_club: number;
  max_free_transfers: number;
  chips: ChipRule[];
}

export function getRules(): Promise<Rules> {
  return request("/rules");
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function getManualState(squad: ManualSquad): Promise<ManagerState> {
  return post("/manual/state", squad);
}

export function getManualRecommendations(squad: ManualSquad, horizon: number): Promise<Recommendations> {
  return post(`/manual/recommendations${query({ horizon })}`, squad);
}

export function getManualExplanation(squad: ManualSquad, horizon: number, plan: number): Promise<Explanation> {
  return post(`/manual/recommendations/explanation${query({ horizon, plan })}`, squad);
}

// --- best XI for the next gameweek ------------------------------------------------------

export interface BestXI {
  model: string;
  gameweek: number;
  budget: number;
  cost: number;
  expected_points: number;
  lineup: PickedPlayer[];
  bench: PickedPlayer[];
  captain: PickedPlayer;
  vice_captain: PickedPlayer;
}

export function getBestXI(): Promise<BestXI> {
  return request("/best-xi");
}
