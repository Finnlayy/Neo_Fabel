import React from "react";
import type { LeaderboardEntry, AcademyStatus } from "../../api/academy";

interface AcademyLeaderboardProps {
  leaderboard: LeaderboardEntry[];
  status: AcademyStatus | null;
}

export function AcademyLeaderboard({ leaderboard, status }: AcademyLeaderboardProps) {
  return (
    <section className="xl:col-span-1 space-y-3">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-bold">Leaderboard</h3>
      <ol className="space-y-2">
        {leaderboard.map((row, i) => (
          <li
            key={row.scout_name}
            className="flex items-center justify-between rounded-lg border border-white/5 bg-slate-900/40 px-3 py-2"
          >
            <span>
              <span className="text-slate-600 mr-2">{i + 1}.</span>
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
          <ul className="space-y-1 max-h-48 overflow-y-auto text-[10px] text-slate-500">
            {status.recent_drills.slice(0, 12).map((d, i) => (
              <li key={i}>
                {String(d.scout_name)} · {d.is_correct ? "OK" : "MISS"} ·{" "}
                {String(d.drill_type ?? "")}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
