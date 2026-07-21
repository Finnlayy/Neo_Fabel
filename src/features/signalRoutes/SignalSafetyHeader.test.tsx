import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import SignalSafetyHeader from "./SignalSafetyHeader";
import type { SignalAutomationStatus } from "./types";

const baseStatus: SignalAutomationStatus = {
  signal_routes_enabled: false,
  tradingview_ingress_enabled: false,
  mcp_signal_adapter_enabled: false,
  signal_worker_enabled: false,
  signal_execution_enabled: false,
  ai_advisory_enabled: false,
  execution_target: "kraken_paper",
  paper_only: true,
  queue_depth: 0,
  oldest_ready_age_seconds: null,
  worker_heartbeat_ok: false,
  advisory_ready: false,
};

describe("SignalSafetyHeader", () => {
  afterEach(() => cleanup());

  it("shows permanent paper-only copy and no live execution option", () => {
    render(<SignalSafetyHeader status={baseStatus} />);

    expect(screen.getByText(/Paper only/i)).toBeTruthy();
    expect(screen.getByText(/Live Kraken execution is not available on this page/i)).toBeTruthy();
    expect(screen.getByText(/kraken_paper/)).toBeTruthy();
    expect(screen.queryByText(/kraken_live/i)).toBeNull();
    expect(screen.queryByText(/live trading/i)).toBeNull();
  });

  it("renders readiness pills from status without inventing a live target", () => {
    render(
      <SignalSafetyHeader
        status={{
          ...baseStatus,
          signal_routes_enabled: true,
          signal_worker_enabled: true,
          queue_depth: 2,
        }}
      />,
    );

    expect(screen.getByLabelText(/Global gate: ready/i)).toBeTruthy();
    expect(screen.getByLabelText(/Worker: ready/i)).toBeTruthy();
    expect(screen.getByText(/Queue: 2/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/live\s*option/i);
  });
});
