import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { CredentialReveal, SignalRoute } from "./types";

const advisoryRoute: SignalRoute = {
  id: "route-1",
  public_route_key: "pub_abc",
  name: "Paper TV Route",
  strategy_id: "BPRC_PRO",
  mode: "advisory",
  enabled: false,
  execution_target: "kraken_paper",
  pair_allowlist: "ADAUSD,XRPUSD",
  max_volume: "100",
  max_notional: null,
  allowed_order_types: "market",
  max_event_age_seconds: 120,
  max_rate_per_minute: 10,
  max_backlog: 50,
  policy_version: "v1",
  version: 1,
  created_at: "2026-07-21T00:00:00Z",
  updated_at: "2026-07-21T00:00:00Z",
  webhook_url_path: "/api/v1/webhooks/tradingview/pub_abc",
  has_tradingview_credential: false,
  has_mcp_credential: false,
};

const fetchSignalStatus = vi.fn();
const fetchSignalRoutes = vi.fn();
const fetchSubmissions = vi.fn();
const fetchSubmission = vi.fn();
const createSignalRoute = vi.fn();
const patchSignalRoute = vi.fn();
const rotateTradingViewCredential = vi.fn();
const rotateMcpCredential = vi.fn();
const pineJsonTemplate = vi.fn((secret: string) =>
  JSON.stringify({ schema_version: 1, credential: secret, pair: "ADAUSD" }),
);

vi.mock("./api", () => ({
  fetchSignalStatus: (...args: unknown[]) => fetchSignalStatus(...args),
  fetchSignalRoutes: (...args: unknown[]) => fetchSignalRoutes(...args),
  fetchSubmissions: (...args: unknown[]) => fetchSubmissions(...args),
  fetchSubmission: (...args: unknown[]) => fetchSubmission(...args),
  createSignalRoute: (...args: unknown[]) => createSignalRoute(...args),
  patchSignalRoute: (...args: unknown[]) => patchSignalRoute(...args),
  rotateTradingViewCredential: (...args: unknown[]) => rotateTradingViewCredential(...args),
  rotateMcpCredential: (...args: unknown[]) => rotateMcpCredential(...args),
  pineJsonTemplate: (...args: unknown[]) => pineJsonTemplate(...(args as [string])),
  fetchEngineStatus: vi.fn(async () => ({ enabled: false, dry_run: true, started: false })),
  fetchEngineDryRuns: vi.fn(async () => []),
}));

vi.mock("../../auth/AuthProvider", () => ({
  useAuth: () => ({ ready: true, uid: "test-admin" }),
}));

vi.mock("../../auth/AuthPanel", () => ({
  default: () => null,
}));

vi.mock("./FableEnginePanel", () => ({
  default: () => null,
}));

import SignalRoutesPage from "./SignalRoutesPage";

function mockLoadedRoute(route: SignalRoute = advisoryRoute) {
  fetchSignalStatus.mockResolvedValue({
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
  });
  fetchSignalRoutes.mockResolvedValue([route]);
  fetchSubmissions.mockResolvedValue([]);
}

describe("SignalRoutesPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  beforeEach(() => {
    mockLoadedRoute();
  });

  it("shows paper-only safety copy and advisory as the loaded default mode", async () => {
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Paper only/i)).toBeTruthy();
    });
    expect(screen.getByText(/Live Kraken execution is not available on this page/i)).toBeTruthy();
    expect(screen.getAllByText(/kraken_paper/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("radio", { name: /live/i })).toBeNull();
    expect(screen.queryByText(/kraken_live/i)).toBeNull();

    const advisory = screen.getByRole("radio", { name: /Advisory \(AI gate\)/i }) as HTMLInputElement;
    const bypass = screen.getByRole("radio", { name: /Bypass \(AI off\)/i }) as HTMLInputElement;
    expect(advisory.checked).toBe(true);
    expect(bypass.checked).toBe(false);
    expect(screen.getByText(/Skips AI review only/i)).toBeTruthy();
  });

  it("creates routes with ADAUSD,XRPUSD allowlist and advisory messaging", async () => {
    createSignalRoute.mockResolvedValue({ ...advisoryRoute, id: "route-new", name: "New Route" });
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Create advisory route/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Create advisory route/i }));

    await waitFor(() => {
      expect(createSignalRoute).toHaveBeenCalledWith({
        name: "Paper TV Route",
        strategy_id: "BPRC_PRO",
        pair_allowlist: "ADAUSD,XRPUSD",
      });
    });
    await waitFor(() => {
      expect(screen.getAllByText(/Created route New Route \(disabled, advisory\)/i).length).toBeGreaterThan(0);
    });
  });

  it("requires confirmation before switching to Bypass and cancels without patching", async () => {
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /Bypass \(AI off\)/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("radio", { name: /Bypass \(AI off\)/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Switch to Bypass \(AI off\)\?/i)).toBeTruthy();
    expect(within(dialog).getByText(/Bypass skips AI review only/i)).toBeTruthy();
    expect(patchSignalRoute).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: /Cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(patchSignalRoute).not.toHaveBeenCalled();
  });

  it("confirms Bypass switch and patches mode to bypass_ai", async () => {
    patchSignalRoute.mockResolvedValue({ ...advisoryRoute, mode: "bypass_ai", version: 2 });
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("radio", { name: /Bypass \(AI off\)/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("radio", { name: /Bypass \(AI off\)/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirm/i }));

    await waitFor(() => {
      expect(patchSignalRoute).toHaveBeenCalledWith("route-1", {
        expected_version: 1,
        mode: "bypass_ai",
      });
    });
  });

  it("reveals a one-time credential then masks it after dismiss", async () => {
    const reveal: CredentialReveal = {
      credential_id: "cred-1",
      kind: "tradingview_secret",
      plaintext: "tvsec_ONE_TIME_SECRET_VALUE",
      display_prefix: "tvsec_ONE",
      activated_at: "2026-07-21T00:00:00Z",
    };
    rotateTradingViewCredential.mockResolvedValue(reveal);
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Rotate TradingView secret/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Rotate TradingView secret/i }));

    expect(await screen.findByText(/One-time credential \(tradingview_secret\)/i)).toBeTruthy();
    expect(screen.getAllByText(/tvsec_ONE_TIME_SECRET_VALUE/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Credential shown once/i).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Dismiss secret/i }));

    await waitFor(() => {
      expect(screen.queryByText(/One-time credential/i)).toBeNull();
      expect(screen.queryByRole("button", { name: /Dismiss secret/i })).toBeNull();
    });
    // Pine template falls back to placeholder; plaintext banner must be gone.
    expect(screen.queryByText(/One-time credential \(tradingview_secret\)/i)).toBeNull();
  });

  it("requires confirmation before enabling a route and cancels without patching", async () => {
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Enable route/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Enable route/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Enable this route\?/i)).toBeTruthy();
    expect(within(dialog).getByText(/global signal gate is off/i)).toBeTruthy();
    expect(patchSignalRoute).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: /Cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(patchSignalRoute).not.toHaveBeenCalled();
  });

  it("confirms Enable route and patches enabled true with expected_version", async () => {
    patchSignalRoute.mockResolvedValue({ ...advisoryRoute, enabled: true, version: 2 });
    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Enable route/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Enable route/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirm/i }));

    await waitFor(() => {
      expect(patchSignalRoute).toHaveBeenCalledWith("route-1", {
        expected_version: 1,
        enabled: true,
      });
    });
  });

  it("surfaces route_version_conflict and reloads routes", async () => {
    patchSignalRoute.mockRejectedValue(
      new ApiError(409, "route_version_conflict", "Version mismatch"),
    );
    const reloaded = { ...advisoryRoute, version: 3, name: "Paper TV Route (reloaded)" };
    fetchSignalRoutes
      .mockResolvedValueOnce([advisoryRoute])
      .mockResolvedValue([reloaded]);

    render(<SignalRoutesPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Enable route/i })).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /Enable route/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirm/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
      expect(screen.getByText(/Route changed elsewhere — reloaded/i)).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(fetchSignalRoutes.mock.calls.length).toBeGreaterThan(1);
  });
});
