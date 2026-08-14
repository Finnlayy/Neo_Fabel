import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/agency", () => ({
  fetchAgencyRoster: vi.fn(async () => ({
    agency: "Neo Fabel Agency",
    paper_only: true,
    summary: {
      headcount: 2,
      avg_confidence: 0.55,
      avg_level: 1.5,
      total_experience: 12,
    },
    agents: [
      {
        id: "chronos",
        name: "Chronos K-Line Agent",
        code_name: "chronos",
        profession: "K-Line Language Scientist",
        archetype: "KLine Linguist",
        agenda: "Tokenize markets.",
        lifetask: "Teach the language of markets.",
        level: 2,
        experience_title: "Apprentice",
        experience: 12,
        experience_to_next: 50,
        confidence: 0.62,
        accuracy: 0.7,
        current_streak: 2,
        badges: [],
        drill_type: "kline_language",
        status: "ACTIVE",
      },
      {
        id: "orchestrator",
        name: "Master Orchestrator",
        code_name: "orchestrator",
        profession: "Agency Director",
        archetype: "Diplomat",
        agenda: "Align the swarm.",
        lifetask: "Keep the agency paper-safe.",
        level: 1,
        experience_title: "Novice",
        experience: 0,
        experience_to_next: 10,
        confidence: 0.5,
        accuracy: 0,
        current_streak: 0,
        badges: [],
        drill_type: "orchestration_teamwork",
        status: "ACTIVE",
      },
    ],
  })),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => ({ ready: true, uid: "test-user" }),
}));

vi.mock("../../auth/AuthPanel", () => ({
  default: () => null,
}));

import AgencyPage from "./AgencyPage";

describe("AgencyPage", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders agency job cards with level and life task", async () => {
    render(<AgencyPage language="en" />);
    await waitFor(() => {
      expect(screen.getByTestId("agency-title").textContent).toContain("Neo Fabel Agency");
    });
    expect(screen.getByTestId("agency-card-chronos")).toBeTruthy();
    expect(screen.getByText(/Teach the language of markets/i)).toBeTruthy();
    expect(screen.getByText(/K-Line Language Scientist/i)).toBeTruthy();
  });
});
