import React from "react";
import type { AcademyStatus, CareerEntry, LeaderboardEntry } from "../../api/academy";

interface AcademyLeaderboardProps {
  leaderboard: LeaderboardEntry[];
  status: AcademyStatus | null;
  careers: CareerEntry[];
}

export function AcademyLeaderboard({ leaderboard, status, careers }: AcademyLeaderboardProps) {
  return (
    <section className="xl:col-span-1 space-y-3">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Leaderboard</h3>
      <ol className="space-y-2">
        {leaderboard.map((row, index) => (
          <li
            key={row.scout_name}
            className="flex items-center justify-between rounded-lg border border-white/5 bg-slate-900/40 px-3 py-2"
          >
            <span>
              <span className="text-slate-600 mr-2">{index + 1}.</span>
              {row.scout_name}
            </span>
            <span className="text-slate-400">
              {(row.accuracy * 100).toFixed(0)}% · {row.experience}xp
            </span>
          </li>
        ))}
      </ol>
      {status?.recent_drills?.length ? (
        <>
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold pt-2">
            Recent cycle drills
          </h3>
          <ul className="space-y-1 max-h-40 overflow-y-auto text-[10px] text-slate-500">
            {status.recent_drills.slice(0, 12).map((drill, index) => (
              <li key={index}>
                {String(drill.scout_name)} · {drill.is_correct ? "OK" : "MISS"} ·{" "}
                {String(drill.drill_type ?? "")}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {careers.length > 0 && (
        <>
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold pt-2">
            Career log
          </h3>
          <ul className="space-y-1 max-h-40 overflow-y-auto text-[10px] text-slate-500">
            {careers.slice(0, 12).map((career) => (
              <li key={career.entry_id}>
                {career.scout_name} · {career.event_type}
                {career.details?.is_correct === true
                  ? " · OK"
                  : career.details?.is_correct === false
                    ? " · MISS"
                    : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
