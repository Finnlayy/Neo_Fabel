import { apiRequest } from "./client";

export type AgencyAgentCard = {
  id: string;
  name: string;
  code_name: string;
  profession: string;
  archetype: string;
  agenda: string;
  lifetask: string;
  level: number;
  experience_title: string;
  experience: number;
  experience_to_next: number | null;
  confidence: number;
  accuracy: number;
  current_streak: number;
  badges: Array<{ name: string; description: string; icon: string }>;
  drill_type: string;
  status: string;
};

export type AgencyRosterResponse = {
  agency: string;
  paper_only: boolean;
  summary: {
    headcount: number;
    avg_confidence: number;
    avg_level: number;
    total_experience: number;
    paper_only?: boolean;
  };
  agents: AgencyAgentCard[];
};

export function fetchAgencyRoster(): Promise<AgencyRosterResponse> {
  return apiRequest<AgencyRosterResponse>("/api/v1/academy/agency/roster");
}
