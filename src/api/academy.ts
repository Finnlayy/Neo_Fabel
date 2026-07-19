import { apiRequest } from "./client";

export type AcademyAgent = {
  scout_id: string;
  name: string;
  archetype: string;
  total_calls: number;
  correct_calls: number;
  accuracy: number;
  current_streak: number;
  experience_level: string;
  badges: Array<{ name: string; description: string; icon: string }>;
};

export type AcademyStatus = {
  is_running: boolean;
  enabled: boolean;
  env_enabled?: boolean;
  session_enabled?: boolean;
  auto_start_enabled: boolean;
  night_mode?: boolean;
  is_night_time: boolean;
  last_run_time: string | null;
  cycles_completed: number;
  next_interval_seconds: number;
  last_skip_reason: string | null;
  last_error: string | null;
  hint?: string | null;
  recent_drills: Array<Record<string, unknown>>;
  diversity: {
    agreement_rate: number;
    total_evaluations: number;
    status: string;
  };
  agents: string[];
  paper_only: boolean;
};

export type SyntheticDrill = {
  drill_id: string;
  drill_type: string;
  scout_target: string;
  scenario_data: Record<string, unknown>;
  expected_outcome: string;
  difficulty: number;
};

export type DrillResult = {
  result_id: string;
  drill_id: string;
  scout_name: string;
  scout_decision: string;
  is_correct: boolean;
  confidence: number;
  feedback_notes: string;
};

export type LeaderboardEntry = {
  scout_name: string;
  archetype: string;
  accuracy: number;
  experience: number;
  top_badge: { name: string; description: string; icon: string } | null;
};

export function fetchAcademyStatus(): Promise<AcademyStatus> {
  return apiRequest<AcademyStatus>("/api/v1/academy/status");
}

export function fetchAcademyAgents(): Promise<{ agents: AcademyAgent[] }> {
  return apiRequest<{ agents: AcademyAgent[] }>("/api/v1/academy/agents/registry");
}

export function fetchAcademyLeaderboard(): Promise<{ leaderboard: LeaderboardEntry[] }> {
  return apiRequest<{ leaderboard: LeaderboardEntry[] }>("/api/v1/academy/agents/leaderboard");
}

export function startTraining(): Promise<{
  started: boolean;
  reason: string | null;
  hint?: string;
  error?: string;
  session_enabled?: boolean;
  night_mode?: boolean;
  is_night_time?: boolean;
}> {
  return apiRequest("/api/v1/academy/train/start", { method: "POST" });
}

export function stopTraining(): Promise<{ stopped: boolean }> {
  return apiRequest("/api/v1/academy/train/stop", { method: "POST" });
}

export function runTrainingCycle(): Promise<{ ok: boolean; status: AcademyStatus }> {
  return apiRequest("/api/v1/academy/train/cycle", { method: "POST" });
}

export function fetchAvailableDrills(
  scoutName: string,
  count = 3,
): Promise<{ drills: SyntheticDrill[] }> {
  const q = new URLSearchParams({ scout_name: scoutName, count: String(count) });
  return apiRequest(`/api/v1/academy/drills/available?${q}`);
}

export function evaluateDrill(body: {
  drill: SyntheticDrill;
  scout_decision: string;
  confidence?: number;
}): Promise<DrillResult> {
  return apiRequest("/api/v1/academy/drill/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchCurriculum(scoutName: string): Promise<{
  curriculum: Array<{
    scout_name: string;
    curriculum_level: string;
    completed_drills: number;
    required_drills: number;
    passed_drills: number;
    average_confidence: number;
  }>;
}> {
  return apiRequest(`/api/v1/academy/curriculum/${encodeURIComponent(scoutName)}`);
}

export function fetchAbTests(): Promise<{ ab_tests: Array<Record<string, unknown>> }> {
  return apiRequest("/api/v1/academy/ab-tests");
}

export type CareerEntry = {
  entry_id: string;
  scout_name: string;
  event_type: string;
  timestamp: string;
  details: Record<string, unknown>;
};

export function fetchRecentCareers(limit = 20): Promise<{ career: CareerEntry[]; count: number }> {
  const q = new URLSearchParams({ limit: String(limit) });
  return apiRequest(`/api/v1/academy/agents/careers/recent?${q}`);
}
