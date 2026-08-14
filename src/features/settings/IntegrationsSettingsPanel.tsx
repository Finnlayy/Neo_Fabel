import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, EyeOff, KeyRound, Trash2, Save, Plus } from "lucide-react";
import {
  deleteIntegration,
  deletePassword,
  fetchIntegrations,
  fetchPasswords,
  revealIntegration,
  revealPassword,
  upsertIntegration,
  upsertPassword,
  type IntegrationItem,
  type PasswordItem,
} from "./integrationsApi";
import { ApiError } from "../../api/client";

type Props = {
  language: "en" | "de";
};

function groupItems(items: IntegrationItem[]): Record<string, IntegrationItem[]> {
  const out: Record<string, IntegrationItem[]> = {};
  for (const item of items) {
    (out[item.group] ??= []).push(item);
  }
  return out;
}

export default function IntegrationsSettingsPanel({ language }: Props) {
  const de = language === "de";
  const [items, setItems] = useState<IntegrationItem[]>([]);
  const [passwords, setPasswords] = useState<PasswordItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pwLabel, setPwLabel] = useState("");
  const [pwUser, setPwUser] = useState("");
  const [pwSecret, setPwSecret] = useState("");
  const [pwNotes, setPwNotes] = useState("");
  const [pwReveal, setPwReveal] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const [integ, pw] = await Promise.all([fetchIntegrations(), fetchPasswords()]);
      setItems(integ.items);
      setPasswords(pw.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const groups = useMemo(() => groupItems(items), [items]);

  async function saveKey(key: string) {
    setBusy(key);
    setError(null);
    try {
      const value = drafts[key]?.trim() ?? "";
      if (!value) {
        await deleteIntegration(key);
      } else {
        await upsertIntegration(key, value);
      }
      setDrafts((d) => {
        const next = { ...d };
        delete next[key];
        return next;
      });
      setRevealed((r) => {
        const next = { ...r };
        delete next[key];
        return next;
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function revealKey(key: string) {
    setBusy(`reveal:${key}`);
    setError(null);
    try {
      const res = await revealIntegration(key);
      setRevealed((r) => ({ ...r, [key]: res.value }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function savePassword() {
    setBusy("password-new");
    setError(null);
    try {
      await upsertPassword({
        label: pwLabel,
        username: pwUser || null,
        secret: pwSecret,
        notes: pwNotes || null,
      });
      setPwLabel("");
      setPwUser("");
      setPwSecret("");
      setPwNotes("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function revealPw(id: string) {
    setBusy(`pw:${id}`);
    setError(null);
    try {
      const res = await revealPassword(id);
      setPwReveal((r) => ({ ...r, [id]: res.secret }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function removePw(id: string) {
    setBusy(`del:${id}`);
    setError(null);
    try {
      await deletePassword(id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/30 border border-emerald-500/20 p-4 rounded-lg space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-emerald-400 font-bold uppercase tracking-wider text-[10px] flex items-center gap-1.5">
            <KeyRound className="w-3.5 h-3.5" />
            {de ? "API-Keys & Integrationen" : "API keys & integrations"}
          </span>
          <span className="text-emerald-500/60 text-[8px] uppercase">
            {de ? "Server-Vault (nicht Browser)" : "Server vault (not browser)"}
          </span>
        </div>
        <p className="text-[10px] text-slate-500 leading-relaxed">
          {de
            ? "Keys werden auf dem API-Server gespeichert und sofort in die Laufzeitumgebung geladen. Speichern erfordert frische Anmeldung (Admin)."
            : "Keys are stored on the API server and applied to the runtime env. Saving requires recent admin sign-in."}
        </p>
        {error && (
          <p className="text-[10px] text-rose-400 border border-rose-500/30 bg-rose-500/10 px-2 py-1.5 rounded">
            {error}
          </p>
        )}
        <div className="max-h-64 overflow-y-auto space-y-3 pr-1">
          {Object.entries(groups).map(([group, groupItems]) => (
            <div key={group} className="space-y-2">
              <div className="text-[9px] uppercase tracking-widest text-slate-500">{group}</div>
              {(groupItems as IntegrationItem[]).map((item) => (
                <div key={item.key} className="border border-white/10 rounded bg-black/20 p-2 space-y-1.5">
                  <div className="flex justify-between gap-2 items-center">
                    <span className="text-[10px] text-slate-200 font-semibold">{item.label}</span>
                    <span
                      className={`text-[8px] uppercase px-1.5 py-0.5 rounded border ${
                        item.configured
                          ? "border-emerald-500/40 text-emerald-400"
                          : "border-slate-600 text-slate-500"
                      }`}
                    >
                      {item.configured ? (item.source === "vault" ? "vault" : "env") : de ? "leer" : "empty"}
                    </span>
                  </div>
                  <div className="text-[9px] font-mono text-slate-500">{item.key}</div>
                  <input
                    type="password"
                    autoComplete="off"
                    placeholder={item.masked ?? (de ? "neuen Wert einfügen…" : "paste new value…")}
                    value={drafts[item.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [item.key]: e.target.value }))}
                    className="w-full bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-[10px] text-slate-200 outline-none focus:border-emerald-500/40"
                  />
                  {revealed[item.key] && (
                    <div className="text-[9px] font-mono text-amber-300/90 break-all bg-amber-500/5 border border-amber-500/20 px-2 py-1 rounded">
                      {revealed[item.key]}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy === item.key}
                      onClick={() => void saveKey(item.key)}
                      className="flex items-center gap-1 px-2 py-1 rounded border border-emerald-500/30 text-emerald-400 text-[9px] uppercase hover:bg-emerald-500/10 cursor-pointer disabled:opacity-40"
                    >
                      <Save className="w-3 h-3" />
                      {de ? "Speichern" : "Save"}
                    </button>
                    {item.configured && (
                      <button
                        type="button"
                        disabled={busy === `reveal:${item.key}`}
                        onClick={() =>
                          revealed[item.key]
                            ? setRevealed((r) => {
                                const n = { ...r };
                                delete n[item.key];
                                return n;
                              })
                            : void revealKey(item.key)
                        }
                        className="flex items-center gap-1 px-2 py-1 rounded border border-white/15 text-slate-400 text-[9px] uppercase hover:bg-white/5 cursor-pointer"
                      >
                        {revealed[item.key] ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                        {revealed[item.key] ? (de ? "Verbergen" : "Hide") : de ? "Zeigen" : "Reveal"}
                      </button>
                    )}
                    {item.configured && (
                      <button
                        type="button"
                        disabled={busy === item.key}
                        onClick={() => {
                          setBusy(item.key);
                          setError(null);
                          void deleteIntegration(item.key)
                            .then(() => load())
                            .catch((err) =>
                              setError(err instanceof ApiError ? err.message : String(err)),
                            )
                            .finally(() => setBusy(null));
                        }}
                        className="flex items-center gap-1 px-2 py-1 rounded border border-rose-500/30 text-rose-400 text-[9px] uppercase hover:bg-rose-500/10 cursor-pointer ml-auto"
                      >
                        <Trash2 className="w-3 h-3" />
                        {de ? "Löschen" : "Clear"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-900/30 border border-violet-500/20 p-4 rounded-lg space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-violet-400 font-bold uppercase tracking-wider text-[10px]">
            {de ? "Passwort-Tresor" : "Password vault"}
          </span>
          <span className="text-violet-500/60 text-[8px]">{passwords.length} entries</span>
        </div>
        <div className="grid grid-cols-1 gap-2">
          <input
            value={pwLabel}
            onChange={(e) => setPwLabel(e.target.value)}
            placeholder={de ? "Label (z.B. Kraken Login)" : "Label (e.g. Kraken login)"}
            className="bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-[10px] text-slate-200"
          />
          <input
            value={pwUser}
            onChange={(e) => setPwUser(e.target.value)}
            placeholder={de ? "Benutzername (optional)" : "Username (optional)"}
            className="bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-[10px] text-slate-200"
          />
          <input
            type="password"
            value={pwSecret}
            onChange={(e) => setPwSecret(e.target.value)}
            placeholder={de ? "Passwort / Secret" : "Password / secret"}
            className="bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-[10px] text-slate-200"
          />
          <input
            value={pwNotes}
            onChange={(e) => setPwNotes(e.target.value)}
            placeholder={de ? "Notiz (optional)" : "Notes (optional)"}
            className="bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-[10px] text-slate-200"
          />
          <button
            type="button"
            disabled={!pwLabel.trim() || !pwSecret.trim() || busy === "password-new"}
            onClick={() => void savePassword()}
            className="flex items-center justify-center gap-1 py-2 rounded border border-violet-500/40 text-violet-300 text-[9px] uppercase hover:bg-violet-500/10 cursor-pointer disabled:opacity-40"
          >
            <Plus className="w-3 h-3" />
            {de ? "Passwort speichern" : "Save password"}
          </button>
        </div>
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {passwords.map((pw) => (
            <div key={pw.id} className="border border-white/10 rounded p-2 space-y-1 bg-black/20">
              <div className="flex justify-between text-[10px]">
                <span className="text-slate-200 font-semibold">{pw.label}</span>
                <span className="text-slate-500 font-mono">{pw.masked}</span>
              </div>
              {pw.username && <div className="text-[9px] text-slate-500">user: {pw.username}</div>}
              {pwReveal[pw.id] && (
                <div className="text-[9px] font-mono text-amber-300 break-all">{pwReveal[pw.id]}</div>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() =>
                    pwReveal[pw.id]
                      ? setPwReveal((r) => {
                          const n = { ...r };
                          delete n[pw.id];
                          return n;
                        })
                      : void revealPw(pw.id)
                  }
                  className="text-[9px] uppercase text-slate-400 border border-white/15 px-2 py-1 rounded cursor-pointer"
                >
                  {pwReveal[pw.id] ? (de ? "Verbergen" : "Hide") : de ? "Zeigen" : "Reveal"}
                </button>
                <button
                  type="button"
                  onClick={() => void removePw(pw.id)}
                  className="text-[9px] uppercase text-rose-400 border border-rose-500/30 px-2 py-1 rounded cursor-pointer ml-auto"
                >
                  {de ? "Löschen" : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
