import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Hourglass, RefreshCw } from "lucide-react";
import {
  bsqDecode,
  fetchChronosCharts,
  fetchChronosStatus,
  normalizeChronos,
  predictChronos,
  tokenizeChronos,
  type ChronosChartsResponse,
  type ChronosNormalizeResponse,
  type ChronosPredictResponse,
  type ChronosStatus,
  type ChronosTokenizeResponse,
} from "../../api/chronos";
import { fetchOhlcvCandles, type CandlePoint } from "../../api/ohlcv";
import type { SubAgentState } from "../../types";

const AGENT_STATUSES: SubAgentState["status"][] = [
  "ACTIVE",
  "STANDBY",
  "IDLE",
  "OPTIMIZING",
  "ALERT",
];

const LOOKBACK_PRESETS = [64, 512, 2048] as const;
const INTERVALS = ["1m", "5m", "15m", "30m", "60m", "1d"] as const;
const FEATURE_LABELS = ["open", "high", "low", "close", "volume", "amount"] as const;
const TOKEN_PREVIEW = 32;

type AssetClass = "crypto" | "forex" | "sp500";

type Props = {
  activeSymbol: string;
  language?: "en" | "de";
  subAgents?: SubAgentState[];
  onUpdateAgentStatus?: (id: string, status: SubAgentState["status"]) => void;
  marketLive?: boolean;
};

function clampLookback(n: number): number {
  if (!Number.isFinite(n)) return 64;
  return Math.min(4096, Math.max(2, Math.round(n)));
}

/** Map OHLCV → OHLCVA; amount = volume × typical price (o+h+l+c)/4. */
export function candlesToOhlcva(candles: CandlePoint[]): number[][] {
  return candles.map((c) => {
    const typical = (c.open + c.high + c.low + c.close) / 4;
    const amount = c.volume * typical;
    return [c.open, c.high, c.low, c.close, c.volume, amount];
  });
}

function uniqueCount(ids: number[]): number {
  return new Set(ids).size;
}

function fmt(n: number, digits = 4): string {
  if (!Number.isFinite(n)) return "—";
  return n.toPrecision(digits);
}

export default function ChronosPage({
  activeSymbol,
  language = "en",
  subAgents,
  onUpdateAgentStatus,
  marketLive = false,
}: Props) {
  const de = language === "de";
  const chronosAgent = subAgents?.find((a) => a.id === "chronos");
  const agentStatus = chronosAgent?.status ?? "STANDBY";

  const [status, setStatus] = useState<ChronosStatus | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"idle" | "load" | "normalize" | "tokenize" | "charts" | "predict">("idle");

  const [lookback, setLookback] = useState(64);
  const [eps, setEps] = useState(1e-6);
  const [clipVal, setClipVal] = useState(5);
  const [symbol, setSymbol] = useState(activeSymbol);
  const [interval, setInterval] = useState<(typeof INTERVALS)[number]>("5m");
  const [assetClass, setAssetClass] = useState<AssetClass>("crypto");

  const [bars, setBars] = useState<number[][] | null>(null);
  const [barsSource, setBarsSource] = useState("");
  const [normalizeResult, setNormalizeResult] = useState<ChronosNormalizeResponse | null>(null);
  const [tokenizeResult, setTokenizeResult] = useState<ChronosTokenizeResponse | null>(null);
  const [showAllTokens, setShowAllTokens] = useState(false);

  const [bsqS1, setBsqS1] = useState(0);
  const [bsqS2, setBsqS2] = useState(0);
  const [bsqZ, setBsqZ] = useState<number[] | null>(null);
  const [bsqBusy, setBsqBusy] = useState(false);
  const [charts, setCharts] = useState<ChronosChartsResponse | null>(null);
  const [predictResult, setPredictResult] = useState<ChronosPredictResponse | null>(null);
  const [predLen, setPredLen] = useState(32);
  const [temperature, setTemperature] = useState(1.0);
  const [topP, setTopP] = useState(0.9);
  const [monteCarlo, setMonteCarlo] = useState(true);
  const [mcSamples, setMcSamples] = useState(30);
  const [includeVolumePlot, setIncludeVolumePlot] = useState(true);

  useEffect(() => {
    setSymbol(activeSymbol);
  }, [activeSymbol]);

  const reloadStatus = useCallback(async () => {
    setStatusBusy(true);
    setError("");
    try {
      setStatus(await fetchChronosStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStatusBusy(false);
    }
  }, []);

  useEffect(() => {
    void reloadStatus();
  }, [reloadStatus]);

  const windowBody = useMemo(() => {
    if (!bars?.length) return null;
    return { bars, eps, clip_val: clipVal };
  }, [bars, eps, clipVal]);

  const loadBars = async () => {
    setBusy("load");
    setError("");
    setNormalizeResult(null);
    setTokenizeResult(null);
    setCharts(null);
    setPredictResult(null);
    try {
      const n = clampLookback(lookback);
      setLookback(n);
      const { candles, source } = await fetchOhlcvCandles({
        symbol,
        timeframe: interval,
        assetClass,
      });
      if (candles.length < 2) {
        throw new Error(
          de
            ? "Zu wenige OHLCV-Bars geladen (mindestens 2)."
            : "Too few OHLCV bars loaded (need at least 2).",
        );
      }
      const sliced = candles.slice(-n);
      const mapped = candlesToOhlcva(sliced);
      setBars(mapped);
      setBarsSource(source);
    } catch (err) {
      setBars(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runNormalize = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback-Bars laden." : "Load lookback bars first.");
      return;
    }
    setBusy("normalize");
    setError("");
    try {
      const res = await normalizeChronos(windowBody);
      setNormalizeResult(res);
      setTokenizeResult(null);
      try {
        setCharts(await fetchChronosCharts({ ...windowBody, include_tokens: false }));
      } catch {
        /* charts optional if matplotlib missing */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runTokenize = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback-Bars laden." : "Load lookback bars first.");
      return;
    }
    setBusy("tokenize");
    setError("");
    try {
      const res = await tokenizeChronos(windowBody);
      setTokenizeResult(res);
      setNormalizeResult({
        paper_only: res.paper_only,
        lookback: res.lookback,
        feature_order: res.feature_order,
        mean: res.mean,
        std: res.std,
        x_norm: res.x_norm,
      });
      setShowAllTokens(false);
      try {
        setCharts(await fetchChronosCharts({ ...windowBody, include_tokens: true }));
      } catch {
        /* charts optional if matplotlib missing */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runCharts = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback-Bars laden." : "Load lookback bars first.");
      return;
    }
    setBusy("charts");
    setError("");
    try {
      setCharts(
        await fetchChronosCharts({
          ...windowBody,
          include_tokens: true,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runPredict = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback-Bars laden." : "Load lookback bars first.");
      return;
    }
    setBusy("predict");
    setError("");
    try {
      const res = await predictChronos({
        ...windowBody,
        pred_len: Math.min(512, Math.max(1, Math.round(predLen))),
        T: temperature,
        top_p: topP,
        sample_count: monteCarlo ? 1 : 1,
        include_volume: includeVolumePlot,
        monte_carlo: monteCarlo,
        mc_samples: Math.min(64, Math.max(2, Math.round(mcSamples))),
      });
      setPredictResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const chartEntries = useMemo(() => {
    if (!charts?.charts) return [];
    const labels: Record<string, { en: string; de: string }> = {
      ohlc: { en: "OHLC lookback", de: "OHLC-Lookback" },
      zscore: { en: "Causal Z-score", de: "Kausaler Z-Score" },
      tokens: { en: "Coarse / fine tokens", de: "Coarse-/Fine-Token" },
      token_hist: { en: "Token histograms", de: "Token-Histogramme" },
    };
    return (["ohlc", "zscore", "tokens", "token_hist"] as const)
      .filter((key) => charts.charts[key])
      .map((key) => ({
        key,
        src: charts.charts[key] as string,
        label: de ? labels[key].de : labels[key].en,
      }));
  }, [charts, de]);

  const predictionChartEntries = useMemo(() => {
    if (!predictResult?.charts) return [];
    const labels: Record<string, { en: string; de: string }> = {
      prediction: {
        en: "Ground Truth (blue) / Prediction (red)",
        de: "Ground Truth (blau) / Prediction (rot)",
      },
      prediction_wo_vol: {
        en: "Close only (wo volume)",
        de: "Nur Close (ohne Volumen)",
      },
      monte_carlo: {
        en: "Monte Carlo mean + uncertainty band",
        de: "Monte-Carlo-Mittel + Unsicherheitsband",
      },
    };
    const keys = includeVolumePlot
      ? (["prediction", "monte_carlo"] as const)
      : (["prediction_wo_vol", "monte_carlo"] as const);
    return keys
      .filter((key) => predictResult.charts?.[key])
      .map((key) => ({
        key,
        src: predictResult.charts![key] as string,
        label: de ? labels[key].de : labels[key].en,
      }));
  }, [predictResult, includeVolumePlot, de]);

  const runBsqDecode = async () => {
    setBsqBusy(true);
    setError("");
    try {
      const res = await bsqDecode(
        Math.min(1023, Math.max(0, Math.round(bsqS1))),
        Math.min(1023, Math.max(0, Math.round(bsqS2))),
      );
      setBsqZ(res.z);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBsqBusy(false);
    }
  };

  const meanStd = normalizeResult ?? tokenizeResult;
  const s1Preview = tokenizeResult
    ? showAllTokens
      ? tokenizeResult.s1_ids
      : tokenizeResult.s1_ids.slice(-TOKEN_PREVIEW)
    : [];
  const s2Preview = tokenizeResult
    ? showAllTokens
      ? tokenizeResult.s2_ids
      : tokenizeResult.s2_ids.slice(-TOKEN_PREVIEW)
    : [];

  const inputCls =
    "bg-slate-950 border border-white/10 rounded px-2 py-1.5 text-slate-200 text-xs font-mono w-full";
  const labelCls = "text-[8px] text-slate-500 uppercase tracking-widest block mb-1";

  return (
    <div role="tabpanel" aria-labelledby="tab-chronos" className="space-y-4 max-w-[1200px] mx-auto">
      {/* A. Header strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 border border-white/5 rounded-xl p-3 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Hourglass className="w-4 h-4 text-cyan-400" aria-hidden />
            <div>
              <div className="text-[8px] text-slate-500 uppercase tracking-widest">
                {de ? "Agent" : "Agent"}
              </div>
              <div className="text-white font-bold mt-0.5">Chronos</div>
            </div>
          </div>
          <span className="text-[9px] px-2 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-300">
            {de ? "Phase" : "Phase"} {status?.phase ?? 1}
          </span>
          <span
            data-testid="chronos-paper-only"
            className="text-[9px] px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 text-amber-300 font-bold"
          >
            PAPER ONLY
          </span>
          <span
            className={`text-[9px] px-2 py-1 rounded border ${
              status?.matplotlib_available
                ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-300"
                : "border-slate-500/30 bg-slate-500/10 text-slate-400"
            }`}
          >
            {status?.matplotlib_available
              ? de
                ? "matplotlib an"
                : "matplotlib on"
              : de
                ? "matplotlib aus"
                : "matplotlib off"}
          </span>
          <div className="text-[10px] text-slate-400">
            <span className="text-slate-500">{de ? "Encoder" : "Encoder"}:</span>{" "}
            <span className="text-cyan-300">{status?.encoder ?? "—"}</span>
            <span className="mx-2 text-slate-600">·</span>
            <span className="text-slate-500">latent:</span>{" "}
            <span className="text-slate-200">{status?.latent_dim ?? "—"}</span>
            <span className="mx-2 text-slate-600">·</span>
            <span className="text-slate-500">vocab:</span>{" "}
            <span className="text-slate-200">
              {status?.vocab
                ? `${status.vocab.coarse}/${status.vocab.fine}`
                : "—"}
            </span>
          </div>
          <span className="text-[9px] text-slate-500">
            {marketLive ? "LIVE" : de ? "CACHE" : "CACHE"} · {symbol}/USD
          </span>
        </div>
        <button
          type="button"
          onClick={() => void reloadStatus()}
          disabled={statusBusy}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${statusBusy ? "animate-spin" : ""}`} />
          {de ? "Status aktualisieren" : "Refresh status"}
        </button>
      </div>

      {error ? (
        <div
          role="alert"
          className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-lg px-3 py-2"
        >
          {error}
        </div>
      ) : null}

      {/* B. Agent controls */}
      <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-4">
        <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
          {de ? "Agent-Steuerung" : "Agent controls"}
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <span className={labelCls}>{de ? "Agent-Status" : "Agent status"}</span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Chronos agent status">
              {AGENT_STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={!onUpdateAgentStatus}
                  onClick={() => onUpdateAgentStatus?.("chronos", s)}
                  className={`px-2 py-1 rounded text-[9px] font-semibold cursor-pointer border transition-all ${
                    agentStatus === s
                      ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-300"
                      : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className={labelCls}>{de ? "Lookback-Länge" : "Lookback length"}</span>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {LOOKBACK_PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setLookback(p)}
                  className={`px-2 py-1 rounded text-[9px] font-semibold cursor-pointer border ${
                    lookback === p
                      ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-300"
                      : "bg-white/5 border-white/10 text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            <input
              type="number"
              min={2}
              max={4096}
              value={lookback}
              onChange={(e) => setLookback(clampLookback(Number(e.target.value)))}
              className={inputCls}
              aria-label={de ? "Lookback" : "Lookback"}
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={labelCls} htmlFor="chronos-eps">
                eps
              </label>
              <input
                id="chronos-eps"
                type="number"
                step="1e-7"
                min={1e-12}
                max={1e-2}
                value={eps}
                onChange={(e) => setEps(Number(e.target.value) || 1e-6)}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls} htmlFor="chronos-clip">
                clip_val
              </label>
              <input
                id="chronos-clip"
                type="number"
                step="0.5"
                min={0.1}
                max={20}
                value={clipVal}
                onChange={(e) => setClipVal(Number(e.target.value) || 5)}
                className={inputCls}
              />
            </div>
          </div>

          <div>
            <label className={labelCls} htmlFor="chronos-symbol">
              {de ? "Symbol" : "Symbol"}
            </label>
            <input
              id="chronos-symbol"
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls} htmlFor="chronos-interval">
              {de ? "Intervall" : "Interval"}
            </label>
            <select
              id="chronos-interval"
              value={interval}
              onChange={(e) => setInterval(e.target.value as (typeof INTERVALS)[number])}
              className={inputCls}
            >
              {INTERVALS.map((iv) => (
                <option key={iv} value={iv}>
                  {iv}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelCls} htmlFor="chronos-asset">
              {de ? "Asset-Klasse" : "Asset class"}
            </label>
            <select
              id="chronos-asset"
              value={assetClass}
              onChange={(e) => setAssetClass(e.target.value as AssetClass)}
              className={inputCls}
            >
              <option value="crypto">crypto</option>
              <option value="forex">forex</option>
              <option value="sp500">sp500</option>
            </select>
          </div>
        </div>

        <p className="text-[10px] text-slate-500 border border-white/5 rounded-lg px-3 py-2 bg-slate-900/40">
          {de
            ? "Kontextfrei: Modellmerkmale ignorieren absolute Preise / Asset-ID. Chronos führt niemals automatisch Trades aus."
            : "Context-free: model features ignore absolute prices / asset ID. Chronos never auto-executes trades."}
        </p>
      </section>

      {/* C. Actions */}
      <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs">
        <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold mb-3">
          {de ? "Aktionen" : "Actions"}
        </h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void loadBars()}
            disabled={busy !== "idle"}
            className="px-4 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer disabled:opacity-50"
          >
            {busy === "load"
              ? de
                ? "Lade…"
                : "Loading…"
              : de
                ? "Lookback laden"
                : "Load lookback"}
          </button>
          <button
            type="button"
            onClick={() => void runNormalize()}
            disabled={busy !== "idle" || !bars}
            className="px-4 py-2 rounded-lg border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 cursor-pointer disabled:opacity-50"
          >
            {busy === "normalize" ? (de ? "Normalisiere…" : "Normalizing…") : de ? "Normalisieren" : "Normalize"}
          </button>
          <button
            type="button"
            onClick={() => void runTokenize()}
            disabled={busy !== "idle" || !bars}
            className="px-4 py-2 rounded-lg border border-cyan-500/40 bg-cyan-500/15 text-cyan-200 font-bold hover:bg-cyan-500/25 cursor-pointer disabled:opacity-50"
          >
            {busy === "tokenize" ? (de ? "Tokenisiere…" : "Tokenizing…") : de ? "Tokenisieren" : "Tokenize"}
          </button>
          <button
            type="button"
            onClick={() => void runCharts()}
            disabled={busy !== "idle" || !bars}
            className="px-4 py-2 rounded-lg border border-white/15 text-slate-200 hover:bg-white/5 cursor-pointer disabled:opacity-50"
          >
            {busy === "charts"
              ? de
                ? "Charts…"
                : "Charts…"
              : de
                ? "matplotlib-Charts"
                : "matplotlib charts"}
          </button>
          <button
            type="button"
            onClick={() => void runPredict()}
            disabled={busy !== "idle" || !bars}
            data-testid="chronos-predict"
            className="px-4 py-2 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-200 font-bold hover:bg-rose-500/20 cursor-pointer disabled:opacity-50"
          >
            {busy === "predict"
              ? de
                ? "Prognose…"
                : "Predicting…"
              : de
                ? "Prognose (GT/Pred)"
                : "Predict (GT / Pred)"}
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div>
            <label className={labelCls} htmlFor="chronos-pred-len">
              pred_len
            </label>
            <input
              id="chronos-pred-len"
              type="number"
              min={1}
              max={512}
              value={predLen}
              onChange={(e) => setPredLen(Number(e.target.value))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="chronos-T">
              T
            </label>
            <input
              id="chronos-T"
              type="number"
              min={0.1}
              max={5}
              step={0.1}
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="chronos-top-p">
              top_p
            </label>
            <input
              id="chronos-top-p"
              type="number"
              min={0.05}
              max={1}
              step={0.05}
              value={topP}
              onChange={(e) => setTopP(Number(e.target.value))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="chronos-mc-n">
              MC samples
            </label>
            <input
              id="chronos-mc-n"
              type="number"
              min={2}
              max={64}
              value={mcSamples}
              onChange={(e) => setMcSamples(Number(e.target.value))}
              className={inputCls}
              disabled={!monteCarlo}
            />
          </div>
          <label className="flex items-end gap-2 text-[10px] text-slate-300 pb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={monteCarlo}
              onChange={(e) => setMonteCarlo(e.target.checked)}
              className="accent-rose-400"
            />
            Monte Carlo
          </label>
          <label className="flex items-end gap-2 text-[10px] text-slate-300 pb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeVolumePlot}
              onChange={(e) => setIncludeVolumePlot(e.target.checked)}
              className="accent-cyan-400"
            />
            {de ? "Volumen-Plot" : "Volume plot"}
          </label>
        </div>

        {bars ? (
          <p className="mt-3 text-[10px] text-slate-500">
            {de ? "Geladen" : "Loaded"}: {bars.length} bars
            {barsSource ? ` · ${barsSource}` : ""}
          </p>
        ) : null}
      </section>

      {/* Kronos-style prediction charts */}
      {predictionChartEntries.length > 0 ? (
        <section
          data-testid="chronos-prediction-charts"
          className="bg-slate-950/60 border border-rose-500/15 rounded-xl p-4 font-mono text-xs space-y-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[10px] text-rose-300/90 uppercase tracking-widest font-bold">
              {de ? "Prognose-Charts (matplotlib)" : "Prediction charts (matplotlib)"}
            </h2>
            <span className="text-[9px] text-slate-500">
              L={predictResult?.lookback} · pred={predictResult?.pred_len}
              {predictResult?.sample_count ? ` · paths=${predictResult.sample_count}` : ""}
            </span>
          </div>
          <p className="text-[10px] text-slate-500">
            {de
              ? "Blau = Ground Truth (Historie), Rot = Prediction — wie Kronos prediction_example.py. OHLCVA als Tabellenzeilen (DataFrame-Spalten)."
              : "Blue = Ground Truth (history), Red = Prediction — Kronos prediction_example.py style. OHLCVA rows match DataFrame columns."}
          </p>
          <div className="grid grid-cols-1 gap-4">
            {predictionChartEntries.map((entry) => (
              <figure key={entry.key} className="space-y-2">
                <figcaption className="text-[9px] text-rose-300/90 uppercase tracking-widest">
                  {entry.label}
                </figcaption>
                <img
                  src={entry.src}
                  alt={entry.label}
                  className="w-full rounded-lg border border-white/5 bg-[#090d16]"
                />
              </figure>
            ))}
          </div>
          {predictResult?.pred?.length ? (
            <p className="text-[10px] text-slate-400" data-testid="chronos-pred-len">
              pred rows: {predictResult.pred.length} · close[0]={predictResult.pred[0].close.toPrecision(6)}
            </p>
          ) : null}
          {predictResult?.chart_error ? (
            <p className="text-rose-300 text-[10px]">{predictResult.chart_error}</p>
          ) : null}
        </section>
      ) : null}

      {/* Charts (matplotlib PNG) */}
      {chartEntries.length > 0 ? (
        <section
          data-testid="chronos-charts"
          className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-4"
        >
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
              {de ? "matplotlib-Charts" : "matplotlib charts"}
            </h2>
            <span className="text-[9px] text-slate-500">
              {charts?.renderer ?? "matplotlib"} · L={charts?.lookback}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4">
            {chartEntries.map((entry) => (
              <figure key={entry.key} className="space-y-2">
                <figcaption className="text-[9px] text-cyan-300/90 uppercase tracking-widest">
                  {entry.label}
                </figcaption>
                <img
                  src={entry.src}
                  alt={entry.label}
                  className="w-full rounded-lg border border-white/5 bg-[#090d16]"
                />
              </figure>
            ))}
          </div>
        </section>
      ) : null}

      {/* D. Results */}
      <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-4">
        <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
          {de ? "Ergebnisse" : "Results"}
        </h2>

        {!meanStd && !tokenizeResult ? (
          <p className="text-slate-500 text-[11px]">
            {de
              ? "Noch keine Ergebnisse — Lookback laden, dann Normalisieren oder Tokenisieren."
              : "No results yet — load lookback, then Normalize or Tokenize."}
          </p>
        ) : null}

        {meanStd ? (
          <div>
            <div className="text-[9px] text-slate-500 uppercase mb-2">
              {de ? "Lookback" : "Lookback"}:{" "}
              <span className="text-slate-200">{meanStd.lookback}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="text-[8px] text-slate-500 uppercase tracking-wider border-b border-white/5">
                    <th className="py-1 pr-3 font-normal">{de ? "Merkmal" : "Feature"}</th>
                    <th className="py-1 pr-3 font-normal">μ</th>
                    <th className="py-1 font-normal">σ</th>
                  </tr>
                </thead>
                <tbody>
                  {(meanStd.feature_order?.length ? meanStd.feature_order : FEATURE_LABELS).map(
                    (name, i) => (
                      <tr key={name} className="border-b border-white/[0.03] text-[11px]">
                        <td className="py-1 pr-3 text-cyan-300/90">{name}</td>
                        <td className="py-1 pr-3 text-slate-300 tabular-nums">{fmt(meanStd.mean[i])}</td>
                        <td className="py-1 text-slate-300 tabular-nums">{fmt(meanStd.std[i])}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {tokenizeResult ? (
          <div className="space-y-3 border-t border-white/5 pt-4">
            <div className="flex flex-wrap gap-4 text-[10px] text-slate-400">
              <span>
                s1 unique:{" "}
                <span className="text-cyan-300" data-testid="chronos-s1-len">
                  {tokenizeResult.s1_ids.length}
                </span>{" "}
                ids · {uniqueCount(tokenizeResult.s1_ids)} distinct
              </span>
              <span>
                s2 unique: {tokenizeResult.s2_ids.length} ids ·{" "}
                {uniqueCount(tokenizeResult.s2_ids)} distinct
              </span>
              <span>
                entropy_mean:{" "}
                <span className="text-slate-200">{fmt(tokenizeResult.entropy_mean, 5)}</span>
              </span>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[8px] text-slate-500 uppercase tracking-widest">
                  {showAllTokens
                    ? de
                      ? "Alle Token-IDs"
                      : "All token ids"
                    : de
                      ? `Letzte ${TOKEN_PREVIEW} Token`
                      : `Last ${TOKEN_PREVIEW} tokens`}
                </span>
                {tokenizeResult.s1_ids.length > TOKEN_PREVIEW ? (
                  <button
                    type="button"
                    onClick={() => setShowAllTokens((v) => !v)}
                    className="text-[9px] text-cyan-400 hover:text-cyan-300 cursor-pointer"
                  >
                    {showAllTokens
                      ? de
                        ? `Nur letzte ${TOKEN_PREVIEW}`
                        : `Show last ${TOKEN_PREVIEW}`
                      : de
                        ? "Alle anzeigen"
                        : "Show all"}
                  </button>
                ) : null}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-x-auto max-h-40 overflow-y-auto">
                  s1: [{s1Preview.join(", ")}]
                </pre>
                <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-x-auto max-h-40 overflow-y-auto">
                  s2: [{s2Preview.join(", ")}]
                </pre>
              </div>
            </div>
          </div>
        ) : null}

        {/* Optional BSQ playground */}
        <div className="border-t border-white/5 pt-4 space-y-2">
          <h3 className="text-[9px] text-slate-500 uppercase tracking-widest">
            {de ? "BSQ-Spielplatz (Decode)" : "BSQ playground (decode)"}
          </h3>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className={labelCls} htmlFor="bsq-s1">
                s1_id
              </label>
              <input
                id="bsq-s1"
                type="number"
                min={0}
                max={1023}
                value={bsqS1}
                onChange={(e) => setBsqS1(Number(e.target.value))}
                className={`${inputCls} w-24`}
              />
            </div>
            <div>
              <label className={labelCls} htmlFor="bsq-s2">
                s2_id
              </label>
              <input
                id="bsq-s2"
                type="number"
                min={0}
                max={1023}
                value={bsqS2}
                onChange={(e) => setBsqS2(Number(e.target.value))}
                className={`${inputCls} w-24`}
              />
            </div>
            <button
              type="button"
              onClick={() => void runBsqDecode()}
              disabled={bsqBusy}
              className="px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:text-white cursor-pointer disabled:opacity-50"
            >
              {bsqBusy ? "…" : de ? "Decodieren" : "Decode"}
            </button>
          </div>
          {bsqZ ? (
            <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-x-auto">
              z[{bsqZ.length}]: [{bsqZ.map((v) => fmt(v, 3)).join(", ")}]
            </pre>
          ) : null}
        </div>
      </section>
    </div>
  );
}
