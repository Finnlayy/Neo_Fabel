import React, { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import AuthPanel from "../../auth/AuthPanel";
import RouteList from "./RouteList";
import RouteEditor from "./RouteEditor";
import ActivityLog from "./ActivityLog";
import {
  createSignalRoute,
  fetchSignalRoutes,
  fetchSignalStatus,
  fetchSubmission,
  fetchSubmissions,
  patchSignalRoute,
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
        <RouteList
          routes={routes}
          selectedId={selectedId}
          onSelect={setSelectedId}
          name={name}
          setName={setName}
          strategyId={strategyId}
          setStrategyId={setStrategyId}
          onCreate={onCreate}
        />

        <div className="space-y-6">
          {selected ? (
            <>
              <RouteEditor
                selected={selected}
                reveal={reveal}
                setReveal={setReveal}
                onRotate={onRotate}
                applyPatch={applyPatch}
                setConfirmBypass={setConfirmBypass}
                setConfirmEnable={setConfirmEnable}
              />
            </>
          ) : (
            <p className="text-sm text-slate-500">Select or create a route.</p>
          )}

          <ActivityLog
            submissions={submissions}
            detail={detail}
            setDetail={setDetail}
            onFetchSubmission={fetchSubmission}
          />
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
