import React from "react";
import type { SignalRoute } from "./types";

interface RouteListProps {
  routes: SignalRoute[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  name: string;
  setName: (name: string) => void;
  strategyId: string;
  setStrategyId: (strategyId: string) => void;
  onCreate: () => void;
}

export default function RouteList({
  routes,
  selectedId,
  onSelect,
  name,
  setName,
  strategyId,
  setStrategyId,
  onCreate,
}: RouteListProps) {
  return (
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
              onClick={() => onSelect(route.id)}
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
  );
}
