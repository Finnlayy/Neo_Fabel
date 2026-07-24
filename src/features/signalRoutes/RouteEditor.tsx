import React from "react";
import { pineJsonTemplate } from "./api";
import type { CredentialReveal, SignalRoute } from "./types";

interface RouteEditorProps {
  selected: SignalRoute;
  reveal: CredentialReveal | null;
  setReveal: (reveal: CredentialReveal | null) => void;
  onRotate: (kind: "tv" | "mcp") => void;
  applyPatch: (body: Record<string, unknown>) => void;
  setConfirmBypass: (confirm: boolean) => void;
  setConfirmEnable: (confirm: boolean) => void;
}

export default function RouteEditor({
  selected,
  reveal,
  setReveal,
  onRotate,
  applyPatch,
  setConfirmBypass,
  setConfirmEnable,
}: RouteEditorProps) {
  return (
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
  );
}
