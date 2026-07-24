import React from "react";
import type { SignalSubmission } from "./types";

interface ActivityLogProps {
  submissions: SignalSubmission[];
  detail: SignalSubmission | null;
  setDetail: (detail: SignalSubmission | null) => void;
  onFetchSubmission: (id: string) => Promise<SignalSubmission>;
}

export default function ActivityLog({
  submissions,
  detail,
  setDetail,
  onFetchSubmission,
}: ActivityLogProps) {
  return (
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
                onClick={() => void onFetchSubmission(row.id).then(setDetail)}
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
  );
}
