import React, { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import AuthPanel from "../../auth/AuthPanel";
import {
  createSignalRoute,
  fetchSignalRoutes,
  fetchSignalStatus,
  fetchSubmission,
  fetchSubmissions,
  patchSignalRoute,
  pineJsonTemplate,
  rotateMcpCredential,
  rotateTradingViewCredential,
} from "./api";
import SignalSafetyHeader from "./SignalSafetyHeader";
import type { CredentialReveal, SignalAutomationStatus, SignalRoute, SignalSubmission } from "./types";

export default function SignalRoutesPage() {
  const auth = useAuth();
  const [status, setStatus] = useState<SignalAutomationStatus | null>(null);
  const [routes, setRoutes] = useState<SignalRoute[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submissions, setSubmissions] = useState<SignalSubmission[]>([]);
  const [detail, setDetail] = useState<SignalSubmission | null>(null);
  const [reveal, setReveal] = useState<CredentialReveal | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [confirmBypass, setConfirmBypass] = useState(false);
  const [confirmEnable, setConfirmEnable] = useState(false);
  const [name, setName] = useState("Paper TV Route");
  const [strategyId, setStrategyId] = useState("BPRC_PRO");

  const selected = routes.find((r) => r.id === selectedId) ?? null;

  const reload = useCallback(async () => {
    setError("");
    try {
      const [st, rt, sub] = await Promise.all([
        fetchSignalStatus(),
        fetchSignalRoutes(),
        fetchSubmissions(selectedId ? { route_id: selectedId } : undefined),
      ]);
      setStatus(st);
      setRoutes(rt);
      setSubmissions(sub);
      if (!selectedId && rt[0]) setSelectedId(rt[0].id);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.message || "Failed to load signal routes");
      if (apiErr.code === "auth_unconfigured" || apiErr.code === "session_expired") {
        setError(apiErr.code === "auth_unconfigured" ? "Firebase auth is not configured." : "Session expired. Sign in again.");
      }
    }
  }, [selectedId]);

  useEffect(() => {
    if (!auth.ready || !auth.uid) return;
    void reload();
    const id = window.setInterval(() => void reload(), 15000);
    return () => window.clearInterval(id);
  }, [auth.ready, auth.uid, reload]);

  async function onCreate() {
    try {
      const route = await createSignalRoute({ name, strategy_id: strategyId, pair_allowlist: "BTCUSD,ETHUSD" });
      setMessage(`Created route ${route.name} (disabled, advisory).`);
      setSelectedId(route.id);
      await reload();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  async function onRotate(kind: "tv" | "mcp") {
    if (!selected) return;
    try {
      const cred =
        kind === "tv"
          ? await rotateTradingViewCredential(selected.id)
          : await rotateMcpCredential(selected.id);
      setReveal(cred);
      setMessage("Credential shown once — copy now. It will not be stored in the browser.");
      await reload();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  async function applyPatch(body: Record<string, unknown>) {
    if (!selected) return;
    try {
      const updated = await patchSignalRoute(selected.id, {
        expected_version: selected.version,
        ...body,
      });
      setMessage(`Route saved (v${updated.version}).`);
      setConfirmBypass(false);
      setConfirmEnable(false);
      await reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.code === "route_version_conflict" ? "Route changed elsewhere — reloaded." : apiErr.message);
      await reload();
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6 text-slate-900 shadow-sm">
      <SignalSafetyHeader status={status} />

      <div className="mb-4">
        <AuthPanel />
      </div>

      {!auth.uid && (
        <p className="mb-4 text-sm text-slate-600">Sign in with Firebase to manage signal routes.</p>
      )}

      <div className="sr-only" aria-live="polite">
        {message}
      </div>
      {error && (
        <p className="mb-3 rounded border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="mb-3 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {message}
        </p>
      )}

      {auth.uid && <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside>
          <h3 className="text-sm font-semibold mb-2">Routes</h3>
          <ul className="space-y-2 mb-4" role="listbox" aria-label="Signal routes">
            {routes.map((route) => (
              <li key={route.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={route.id === selectedId}
                  className={`w-full min-h-11 rounded border px-3 py-2 text-left text-sm ${
                    route.id === selectedId ? "border-slate-900 bg-slate-50" : "border-slate-200"
                  }`}
                  onClick={() => setSelectedId(route.id)}
                >
                  <div className="font-medium">{route.name}</div>
                  <div className="text-xs text-slate-500">
                    {route.enabled ? "enabled" : "disabled"} · {route.mode}
                  </div>
                </button>
              </li>
            ))}
            {routes.length === 0 && <li className="text-sm text-slate-500">No routes yet.</li>}
          </ul>
          <div className="space-y-2 border-t border-slate-200 pt-3">
            <label className="block text-xs font-medium">
              Name
              <input className="mt-1 w-full min-h-11 rounded border px-3" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="block text-xs font-medium">
              Strategy ID
              <input
                className="mt-1 w-full min-h-11 rounded border px-3"
                value={strategyId}
                onChange={(e) => setStrategyId(e.target.value)}
              />
            </label>
            <button type="button" className="min-h-11 w-full rounded bg-slate-900 text-white text-sm font-semibold" onClick={() => void onCreate()}>
              Create advisory route
            </button>
          </div>
        </aside>

        <div className="space-y-6">
          {selected ? (
            <>
              <div>
                <h3 className="text-sm font-semibold mb-2">Route editor</h3>
                <p className="text-xs text-slate-500 mb-3">
                  Execution target is permanently <code className="font-mono">kraken_paper</code>. Version {selected.version}.
                </p>
                <fieldset className="mb-4">
                  <legend className="text-sm font-medium mb-2">Review mode</legend>
                  <div className="space-y-3" role="radiogroup" aria-label="Review mode">
                    <label className="flex gap-3 items-start min-h-11 cursor-pointer">
                      <input
                        type="radio"
                        name="mode"
                        checked={selected.mode === "bypass_ai"}
                        onChange={() => setConfirmBypass(true)}
                      />
                      <span>
                        <span className="font-medium">Bypass (AI off)</span>
                        <span className="block text-xs text-slate-600">
                          Skips AI review only. Authentication, validation, replay protection, deterministic guardrails,
                          paper-only routing, and audit remain enforced.
                        </span>
                      </span>
                    </label>
                    <label className="flex gap-3 items-start min-h-11 cursor-pointer">
                      <input
                        type="radio"
                        name="mode"
                        checked={selected.mode === "advisory"}
                        onChange={() => void applyPatch({ mode: "advisory" })}
                      />
                      <span>
                        <span className="font-medium">Advisory (AI gate)</span>
                        <span className="block text-xs text-slate-600">
                          AI must approve the canonical signal. Reject, abstain, timeout, or service failure blocks the
                          paper order.
                        </span>
                      </span>
                    </label>
                  </div>
                </fieldset>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="min-h-11 rounded border border-slate-300 px-4 text-sm font-semibold"
                    onClick={() => (selected.enabled ? void applyPatch({ enabled: false }) : setConfirmEnable(true))}
                  >
                    {selected.enabled ? "Disable route" : "Enable route"}
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold mb-2">Credentials & setup</h3>
                <div className="flex flex-wrap gap-2 mb-3">
                  <button type="button" className="min-h-11 rounded bg-slate-900 px-4 text-sm text-white" onClick={() => void onRotate("tv")}>
                    Rotate TradingView secret
                  </button>
                  <button type="button" className="min-h-11 rounded border px-4 text-sm" onClick={() => void onRotate("mcp")}>
                    Rotate MCP bearer
                  </button>
                  {reveal && (
                    <button type="button" className="min-h-11 rounded border px-4 text-sm" onClick={() => setReveal(null)}>
                      Dismiss secret
                    </button>
                  )}
                </div>
                {reveal && (
                  <div className="mb-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm" aria-live="assertive">
                    <p className="font-semibold">One-time credential ({reveal.kind})</p>
                    <code className="mt-2 block break-all font-mono text-xs">{reveal.plaintext}</code>
                    <button
                      type="button"
                      className="mt-2 min-h-11 rounded border px-3 text-xs font-semibold"
                      onClick={() => void navigator.clipboard.writeText(reveal.plaintext)}
                    >
                      Copy
                    </button>
                  </div>
                )}
                <p className="text-xs font-mono text-slate-700 mb-2">Webhook: {selected.webhook_url_path}</p>
                <pre className="overflow-x-auto rounded bg-slate-950 text-slate-100 p-3 text-[11px] leading-relaxed">
                  {pineJsonTemplate(reveal?.kind === "tradingview_secret" ? reveal.plaintext : "tvsec_YOUR_SECRET")}
                </pre>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Select or create a route.</p>
          )}

          <div>
            <h3 className="text-sm font-semibold mb-2">Activity</h3>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-2 pr-2">Time</th>
                    <th className="py-2 pr-2">Source</th>
                    <th className="py-2 pr-2">Pair</th>
                    <th className="py-2 pr-2">Mode</th>
                    <th className="py-2 pr-2">AI</th>
                    <th className="py-2 pr-2">Status</th>
                    <th className="py-2">Request</th>
                  </tr>
                </thead>
                <tbody>
                  {submissions.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-slate-100 cursor-pointer hover:bg-slate-50"
                      onClick={() => void fetchSubmission(row.id).then(setDetail)}
                    >
                      <td className="py-2 pr-2 font-mono">{new Date(row.created_at).toLocaleString()}</td>
                      <td className="py-2 pr-2">{row.source}</td>
                      <td className="py-2 pr-2">
                        {row.side} {row.volume} {row.pair}
                      </td>
                      <td className="py-2 pr-2">{row.mode_snapshot}</td>
                      <td className="py-2 pr-2">{row.advisory_decision ?? "—"}</td>
                      <td className="py-2 pr-2">{row.status}</td>
                      <td className="py-2 font-mono">{row.request_id.slice(0, 8)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="md:hidden space-y-2">
              {submissions.map((row) => (
                <article key={row.id} className="rounded border border-slate-200 p-3 text-xs">
                  <p>
                    <span className="text-slate-500">Time:</span> {new Date(row.created_at).toLocaleString()}
                  </p>
                  <p>
                    <span className="text-slate-500">Order:</span> {row.side} {row.volume} {row.pair}
                  </p>
                  <p>
                    <span className="text-slate-500">Status:</span> {row.status}
                  </p>
                </article>
              ))}
            </div>
            {detail && (
              <div className="mt-3 rounded border border-slate-200 p-3 text-xs">
                <h4 className="font-semibold mb-2">Event detail</h4>
                <p>Status timeline ends at: {detail.status}</p>
                <p>Reason: {detail.reason_code ?? "—"}</p>
                <p>Paper intent: {detail.paper_intent_id ?? "—"}</p>
                <p className="font-mono mt-2">signal_id={detail.signal_id}</p>
                <button type="button" className="mt-2 min-h-11 rounded border px-3" onClick={() => setDetail(null)}>
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      </div>}

      {(confirmBypass || confirmEnable) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl">
            <h3 className="text-base font-semibold">
              {confirmBypass ? "Switch to Bypass (AI off)?" : "Enable this route?"}
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              {confirmBypass
                ? "Bypass skips AI review only. All other controls stay enforced."
                : "Enabling is ineffective while the global signal gate is off."}
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="min-h-11 rounded border px-4 text-sm"
                onClick={() => {
                  setConfirmBypass(false);
                  setConfirmEnable(false);
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="min-h-11 rounded bg-slate-900 px-4 text-sm text-white"
                onClick={() =>
                  void applyPatch(confirmBypass ? { mode: "bypass_ai" } : { enabled: true })
                }
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
