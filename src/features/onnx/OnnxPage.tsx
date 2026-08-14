import React, { useCallback, useEffect, useState } from "react";
import { Cpu, Network, RefreshCw } from "lucide-react";
import NeuralTracker from "../../components/NeuralTracker";
import {
  fetchOnnxGraph,
  fetchOnnxModels,
  fetchOnnxStatus,
  netronEmbedUrl,
  setOnnxActive,
  uploadOnnxModel,
  type OnnxGraphSummary,
  type OnnxModelMeta,
  type OnnxStatus,
} from "../../api/onnx";

type Props = {
  currentPrice: number;
  activeSymbol: string;
  marketLive?: boolean;
  language?: "en" | "de";
};

type Panel = "tracker" | "graph";

export default function OnnxPage({
  currentPrice,
  activeSymbol,
  marketLive = false,
  language = "en",
}: Props) {
  const de = language === "de";
  const [panel, setPanel] = useState<Panel>("tracker");
  const [status, setStatus] = useState<OnnxStatus | null>(null);
  const [models, setModels] = useState<OnnxModelMeta[]>([]);
  const [selectedModel, setSelectedModel] = useState("model4");
  const [graphSummary, setGraphSummary] = useState<OnnxGraphSummary | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [st, list] = await Promise.all([fetchOnnxStatus(), fetchOnnxModels()]);
      setStatus(st);
      setModels(list.models);
      setSelectedModel((prev) => {
        if (st.active_model_id && list.models.some((m) => m.id === st.active_model_id)) {
          return st.active_model_id;
        }
        if (list.models.length && !list.models.some((m) => m.id === prev)) {
          return list.models[0].id;
        }
        return prev;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const selectedMeta = models.find((m) => m.id === selectedModel);
  const metaRevision = `${selectedMeta?.checksum ?? ""}:${selectedMeta?.file_mtime ?? ""}:${selectedMeta?.version ?? ""}`;

  useEffect(() => {
    if (panel !== "graph" || !status?.runtime_available) {
      setGraphSummary(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const g = await fetchOnnxGraph(selectedModel);
        if (!cancelled) setGraphSummary(g);
      } catch {
        if (!cancelled) setGraphSummary(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [panel, selectedModel, status?.runtime_available, metaRevision]);

  const modeBadge = status?.runtime_available
    ? de
      ? "Echtes ONNX-Runtime"
      : "Live ONNX runtime"
    : de
      ? "Simulierte Inferenz (Fallback)"
      : "Simulated inference (fallback)";

  const graphSrc = netronEmbedUrl(
    selectedModel,
    selectedMeta?.checksum ?? selectedMeta?.file_mtime ?? selectedMeta?.trained_at ?? selectedMeta?.test_mae,
  );

  const onSetActive = async () => {
    setBusy(true);
    setError("");
    try {
      await setOnnxActive(selectedModel);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onUpload = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const res = await uploadOnnxModel({ file, makeActive: true });
      await reload();
      if (res.meta?.id) setSelectedModel(res.meta.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="tabpanel" aria-labelledby="tab-onnx" className="space-y-4 max-w-[1200px] mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 border border-white/5 rounded-xl p-3 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Aktives Paar" : "Active pair"}
            </div>
            <div className="text-white font-bold mt-0.5">{activeSymbol}/USD</div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Live-Preis" : "Live price"}
            </div>
            <div className="text-lime-300 font-bold mt-0.5 tabular-nums">
              {Number.isFinite(currentPrice) ? currentPrice.toFixed(2) : "—"}
              <span className="ml-2 text-[9px] text-slate-500">
                {marketLive ? (de ? "LIVE" : "LIVE") : de ? "CACHE" : "CACHE"}
              </span>
            </div>
          </div>
          <div>
            <div className="text-[8px] text-slate-500 uppercase tracking-widest">
              {de ? "Aktives Modell" : "Active model"}
            </div>
            <div className="text-slate-200 font-bold mt-0.5">{status?.active_model_id ?? "—"}</div>
          </div>
          <span
            className={`text-[9px] px-2 py-1 rounded border ${
              status?.runtime_available
                ? "border-lime-500/30 bg-lime-500/10 text-lime-300"
                : "border-amber-500/30 bg-amber-500/10 text-amber-300"
            }`}
          >
            {modeBadge}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void reload()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} />
          {de ? "Aktualisieren" : "Refresh"}
        </button>
      </div>

      {error ? (
        <div className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-lg px-3 py-2">
          {error}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setPanel("tracker")}
          className={`px-4 py-2 rounded-lg text-xs font-bold font-mono flex items-center gap-1.5 cursor-pointer ${
            panel === "tracker"
              ? "bg-lime-500/15 border border-lime-500/30 text-lime-300"
              : "border border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          {de ? "LSTM-Kern" : "LSTM core"}
        </button>
        <button
          type="button"
          onClick={() => setPanel("graph")}
          className={`px-4 py-2 rounded-lg text-xs font-bold font-mono flex items-center gap-1.5 cursor-pointer ${
            panel === "graph"
              ? "bg-lime-500/15 border border-lime-500/30 text-lime-300"
              : "border border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Network className="w-3.5 h-3.5" />
          {de ? "Modell-Graph (Netron)" : "Model graph (Netron)"}
        </button>
      </div>

      {panel === "tracker" ? (
        <NeuralTracker
          currentPrice={currentPrice}
          symbol={activeSymbol}
          preferLiveRuntime={Boolean(status?.runtime_available)}
        />
      ) : (
        <div className="space-y-3 bg-slate-900/40 border border-white/5 rounded-xl p-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">
              {de ? "Modell" : "Model"}
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-slate-950 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
            >
              {(models.length ? models : [{ id: "model4", filename: "model4.onnx" }]).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.filename ?? `${m.id}.onnx`}
                  {status?.active_model_id === m.id ? " ★" : ""}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void onSetActive()}
              disabled={busy || !status?.runtime_available}
              className="px-3 py-2 rounded-lg border border-lime-500/30 text-[10px] font-mono text-lime-300 hover:bg-lime-500/10 cursor-pointer disabled:opacity-40"
            >
              {de ? "Als aktiv setzen" : "Set active"}
            </button>
            <label className="px-3 py-2 rounded-lg border border-white/15 text-[10px] font-mono text-slate-300 hover:bg-white/5 cursor-pointer disabled:opacity-40">
              <input
                type="file"
                accept=".onnx,application/octet-stream"
                className="hidden"
                disabled={busy || !status?.runtime_available}
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  e.target.value = "";
                  void onUpload(f);
                }}
              />
              {de ? "ONNX hochladen" : "Upload ONNX"}
            </label>
            {!status?.netron_available ? (
              <span className="text-[10px] text-amber-300 font-mono">
                {de
                  ? "Netron optional: pip install '.[onnx]' — Datei-API bleibt aktiv"
                  : "Netron optional: pip install '.[onnx]' — file API still works"}
              </span>
            ) : null}
          </div>
          <p className="text-[10px] font-mono text-slate-500 leading-relaxed max-w-3xl">
            {de
              ? "Alle Modelle teilen dieselbe Netron-Topologie: Flatten → Gemm. Nach dem Training ändern sich Checksum / Weight-Fingerprint — nicht die Knotenstruktur."
              : "All models share the same Netron topology: Flatten → Gemm. After training, checksum / weight fingerprint change — not the node graph."}
          </p>
          {selectedMeta ? (
            <p className="text-[10px] font-mono text-slate-400 break-all">
              {selectedMeta.architecture ?? "flatten_gemm_proxy"} · v={selectedMeta.version ?? "—"} · MAE=
              {selectedMeta.test_mae ?? "—"} · {selectedMeta.target_formula ?? selectedMeta.target ?? "—"}
              {selectedMeta.checksum ? ` · sha256=${selectedMeta.checksum.slice(0, 16)}…` : ""}
            </p>
          ) : null}
          {graphSummary ? (
            <p className="text-[10px] font-mono text-lime-300/90 break-all">
              {de ? "Gewichte" : "Weights"}: fp={graphSummary.weight_fingerprint || "—"} · ops=
              {graphSummary.ops.join("→")} · nodes={graphSummary.node_count}
              {graphSummary.initializers[0]
                ? ` · ${graphSummary.initializers[0].name} L2=${graphSummary.initializers[0].l2.toFixed(4)}`
                : ""}
            </p>
          ) : null}
          {status?.netron_available && graphSrc ? (
            <iframe
              key={graphSrc}
              title="ONNX graph (Netron)"
              className="w-full h-[520px] rounded-lg border border-white/10 bg-black"
              src={graphSrc}
            />
          ) : (
            <div className="rounded-lg border border-dashed border-white/15 p-6 text-sm text-slate-400 font-mono space-y-2">
              <p>
                {de
                  ? "Netron-Viewer nicht eingebettet. Modelldatei herunterladen und in Netron öffnen:"
                  : "Netron viewer not embedded. Download the model and open it in Netron:"}
              </p>
              <a
                className="text-lime-300 underline"
                href={`/api/v1/onnx/models/${encodeURIComponent(selectedModel)}/file`}
              >
                /api/v1/onnx/models/{selectedModel}/file
              </a>
              <p>
                <a
                  className="text-sky-300 underline"
                  href="https://netron.app"
                  target="_blank"
                  rel="noreferrer"
                >
                  netron.app
                </a>
              </p>
            </div>
          )}
          {models.length ? (
            <ul className="text-[10px] font-mono text-slate-500 space-y-1">
              {models.map((m) => (
                <li key={m.id}>
                  {m.id}
                  {status?.active_model_id === m.id ? " ★" : ""}: MAE={m.test_mae ?? "—"} ·{" "}
                  {m.target_formula ?? m.target ?? "—"} · {m.version ?? m.source ?? "local"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  );
}
