import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Brain,
  ChevronRight,
  FlaskConical,
  Hourglass,
  LineChart,
  RefreshCw,
  Settings2,
  Sparkles,
} from "lucide-react";
import {
  bsqDecode,
  fetchChronosBacktest,
  fetchChronosCharts,
  fetchChronosIndicators,
  fetchChronosStatus,
  normalizeChronos,
  predictChronos,
  tokenizeChronos,
  type ChronosBacktestResponse,
  type ChronosChartsResponse,
  type ChronosIndicatorsResponse,
  type ChronosNormalizeResponse,
  type ChronosPredictResponse,
  type ChronosStatus,
  type ChronosTokenizeResponse,
} from "../../api/chronos";
import { fetchOhlcvCandles, type CandlePoint } from "../../api/ohlcv";
import type { SubAgentState } from "../../types";
import ChronosVisualizations from "./ChronosVisualizations";

const AGENT_STATUSES: SubAgentState["status"][] = ["ACTIVE", "STANDBY", "IDLE", "OPTIMIZING", "ALERT"];
const LOOKBACK_PRESETS = [64, 512, 2048] as const;
const INTERVALS = ["1m", "5m", "15m", "30m", "60m", "1d"] as const;
const FEATURE_LABELS = ["open", "high", "low", "close", "volume", "amount"] as const;
const TOKEN_PREVIEW = 32;

type AssetClass = "crypto" | "forex" | "sp500";
type TabId = "overview" | "pipeline" | "forecast" | "advanced";

type Props = {
  activeSymbol: string;
  language?: "en" | "de";
  subAgents?: SubAgentState[];
  onUpdateAgentStatus?: (id: string, status: SubAgentState["status"]) => void;
  onUpdateAgentLastAction?: (id: string, lastAction: string) => void;
  marketLive?: boolean;
  rnaPattern?: { bias: "bullish" | "bearish" | "neutral"; confidence: number } | null;
};

const TABS: { id: TabId; icon: React.ComponentType<{ className?: string }>; en: string; de: string }[] = [
  { id: "overview", icon: Activity, en: "Overview", de: "Übersicht" },
  { id: "pipeline", icon: Settings2, en: "Pipeline", de: "Pipeline" },
  { id: "forecast", icon: LineChart, en: "Forecast", de: "Prognose" },
  { id: "advanced", icon: FlaskConical, en: "Advanced", de: "Erweitert" },
];

const DEP_LABELS: Record<string, { en: string; de: string }> = {
  numpy: { en: "NumPy", de: "NumPy" },
  pandas: { en: "Pandas", de: "Pandas" },
  matplotlib: { en: "Matplotlib", de: "Matplotlib" },
  torch: { en: "PyTorch", de: "PyTorch" },
  vectorbt: { en: "vectorbt", de: "vectorbt" },
  pinets_cli: { en: "PineTS", de: "PineTS" },
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
  language = "de",
  subAgents,
  onUpdateAgentStatus,
  onUpdateAgentLastAction,
  marketLive = false,
  rnaPattern = null,
}: Props) {
  const de = language === "de";
  const chronosAgent = subAgents?.find((a) => a.id === "chronos");
  const agentStatus = chronosAgent?.status ?? "STANDBY";

  const [tab, setTab] = useState<TabId>("overview");
  const [status, setStatus] = useState<ChronosStatus | null>(null);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<
    "idle" | "load" | "normalize" | "tokenize" | "charts" | "predict" | "indicators" | "backtest"
  >("idle");

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
  const [indicators, setIndicators] = useState<ChronosIndicatorsResponse | null>(null);
  const [backtest, setBacktest] = useState<ChronosBacktestResponse | null>(null);
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
      const next = await fetchChronosStatus();
      setStatus(next);
      if (next.pipeline_status && onUpdateAgentLastAction && !bars?.length) {
        onUpdateAgentLastAction("chronos", next.pipeline_status);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setStatusBusy(false);
    }
  }, [bars?.length, onUpdateAgentLastAction]);

  useEffect(() => {
    void reloadStatus();
  }, [reloadStatus]);

  const windowBody = useMemo(() => {
    if (!bars?.length) return null;
    return { bars, eps, clip_val: clipVal };
  }, [bars, eps, clipVal]);

  const runSideAnalysis = async (body: { bars: number[][]; eps: number; clip_val: number }) => {
    const tasks: Promise<void>[] = [];
    if (status?.indicators_available) {
      tasks.push(
        fetchChronosIndicators(body).then((res) => {
          setIndicators(res);
        }),
      );
    }
    if (status?.vectorbt_available) {
      tasks.push(
        fetchChronosBacktest(body).then((res) => {
          setBacktest(res);
        }),
      );
    }
    if (tasks.length) {
      setBusy((b) => (b === "idle" ? "indicators" : b));
      try {
        await Promise.allSettled(tasks);
      } finally {
        setBusy((b) => (b === "indicators" ? "idle" : b));
      }
    }
  };

  const loadBars = async () => {
    setBusy("load");
    setError("");
    setNormalizeResult(null);
    setTokenizeResult(null);
    setCharts(null);
    setPredictResult(null);
    setIndicators(null);
    setBacktest(null);
    try {
      const n = clampLookback(lookback);
      setLookback(n);
      const { candles, source } = await fetchOhlcvCandles({ symbol, timeframe: interval, assetClass });
      if (candles.length < 2) {
        throw new Error(de ? "Zu wenige OHLCV-Bars (min. 2)." : "Too few OHLCV bars (need at least 2).");
      }
      const mapped = candlesToOhlcva(candles.slice(-n));
      setBars(mapped);
      setBarsSource(source);
      onUpdateAgentLastAction?.(
        "chronos",
        de
          ? `${mapped.length} Bars · ${symbol}/USD ${interval} geladen`
          : `${mapped.length} bars · ${symbol}/USD ${interval} loaded`,
      );
      onUpdateAgentStatus?.("chronos", "ACTIVE");
      const body = { bars: mapped, eps, clip_val: clipVal };
      void runSideAnalysis(body);
      setTab("overview");
    } catch (err) {
      setBars(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runNormalize = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback laden." : "Load lookback first.");
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
        /* optional */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runTokenize = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback laden." : "Load lookback first.");
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
        /* optional */
      }
      onUpdateAgentLastAction?.(
        "chronos",
        de
          ? `Tokenized ${res.lookback} · vocab ${res.vocab.coarse}/${res.vocab.fine}`
          : `Tokenized ${res.lookback} · vocab ${res.vocab.coarse}/${res.vocab.fine}`,
      );
      onUpdateAgentStatus?.("chronos", "ACTIVE");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runCharts = async () => {
    if (!windowBody) return;
    setBusy("charts");
    setError("");
    try {
      setCharts(await fetchChronosCharts({ ...windowBody, include_tokens: true }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

  const runPredict = async () => {
    if (!windowBody) {
      setError(de ? "Zuerst Lookback laden." : "Load lookback first.");
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
        sample_count: 1,
        include_volume: includeVolumePlot,
        monte_carlo: monteCarlo,
        mc_samples: Math.min(64, Math.max(2, Math.round(mcSamples))),
        pattern_bias: rnaPattern?.bias,
        pattern_confidence: rnaPattern?.confidence,
      });
      setPredictResult(res);
      setTab("forecast");
      onUpdateAgentLastAction?.(
        "chronos",
        de ? `Prognose pred_len=${res.pred?.length ?? predLen}` : `Forecast pred_len=${res.pred?.length ?? predLen}`,
      );
      onUpdateAgentStatus?.("chronos", "ACTIVE");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("idle");
    }
  };

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
      prediction: { en: "Ground Truth / Prediction", de: "Ground Truth / Prediction" },
      prediction_wo_vol: { en: "Close only", de: "Nur Close" },
      monte_carlo: { en: "Monte Carlo band", de: "Monte-Carlo-Band" },
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

  const pipelineStep = !bars ? 0 : tokenizeResult ? 3 : normalizeResult ? 2 : 1;
  const inputCls =
    "bg-slate-950 border border-white/10 rounded-lg px-2.5 py-2 text-slate-200 text-xs font-mono w-full focus:border-cyan-500/40 outline-none";
  const labelCls = "text-[8px] text-slate-500 uppercase tracking-widest block mb-1.5";

  return (
    <div role="tabpanel" aria-labelledby="tab-chronos" className="space-y-4 max-w-[1280px] mx-auto pb-8">
      {/* Header */}
      <header className="bg-gradient-to-br from-slate-950/90 to-slate-900/40 border border-white/5 rounded-2xl p-4 font-mono">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="space-y-3 min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 mr-2">
                <Hourglass className="w-5 h-5 text-cyan-400 shrink-0" aria-hidden />
                <div>
                  <div className="text-[8px] text-slate-500 uppercase tracking-widest">Chronos</div>
                  <div className="text-white font-bold text-sm">{de ? "Kline-Sprache" : "Kline language"}</div>
                </div>
              </div>
              <Badge tone="cyan">{de ? "Phase" : "Phase"} {status?.phase ?? 1}</Badge>
              <Badge tone="amber" testId="chronos-paper-only">PAPER ONLY</Badge>
              {status?.deps?.research_ready ? (
                <Badge tone="emerald">{de ? "Research bereit" : "Research ready"}</Badge>
              ) : null}
              <Badge tone="slate">{marketLive ? "LIVE" : "CACHE"} · {symbol}/USD</Badge>
            </div>
            {status?.pipeline_status ? (
              <p
                data-testid="chronos-pipeline-status"
                className="text-[10px] text-violet-200/90 bg-violet-500/5 border border-violet-500/20 rounded-lg px-3 py-2 line-clamp-2"
              >
                {status.pipeline_status}
              </p>
            ) : null}
            {status?.deps ? (
              <div className="flex flex-wrap gap-1.5" data-testid="chronos-deps">
                {(Object.keys(DEP_LABELS) as (keyof typeof DEP_LABELS)[]).map((key) => {
                  const on = Boolean(status.deps?.[key]);
                  return (
                    <span
                      key={key}
                      className={`text-[8px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wide ${
                        on
                          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                          : "border-slate-600/40 bg-slate-800/40 text-slate-500"
                      }`}
                    >
                      {de ? DEP_LABELS[key].de : DEP_LABELS[key].en}
                    </span>
                  );
                })}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => void reloadStatus()}
            disabled={statusBusy}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-slate-300 hover:text-white hover:border-white/20 cursor-pointer shrink-0 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${statusBusy ? "animate-spin" : ""}`} />
            {de ? "Aktualisieren" : "Refresh"}
          </button>
        </div>
      </header>

      {error ? (
        <div role="alert" className="text-xs font-mono text-rose-300 border border-rose-500/30 bg-rose-500/10 rounded-xl px-4 py-3">
          {error}
        </div>
      ) : null}

      {/* Tab navigation */}
      <nav
        className="flex flex-wrap gap-1 bg-slate-950/60 border border-white/5 rounded-xl p-1"
        aria-label={de ? "Chronos-Bereiche" : "Chronos sections"}
      >
        {TABS.map(({ id, icon: Icon, en, de: deLabel }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-mono font-semibold cursor-pointer transition-all ${
              tab === id
                ? "bg-cyan-500/15 text-cyan-200 border border-cyan-500/30"
                : "text-slate-500 hover:text-slate-300 border border-transparent"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {de ? deLabel : en}
          </button>
        ))}
      </nav>

      {/* ── Overview ── */}
      {tab === "overview" ? (
        <div className="space-y-4">
          <section className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <MetricCard
              icon={Brain}
              label={de ? "Encoder" : "Encoder"}
              value={status?.encoder ?? "—"}
            />
            <MetricCard
              icon={Sparkles}
              label="Latent"
              value={status?.latent_dim != null ? String(status.latent_dim) : "—"}
            />
            <MetricCard
              icon={BarChart3}
              label="Vocab"
              value={status?.vocab ? `${status.vocab.coarse}/${status.vocab.fine}` : "—"}
            />
            <MetricCard
              icon={Activity}
              label={de ? "Lookback" : "Lookback"}
              value={bars ? String(bars.length) : "—"}
              highlight={Boolean(bars)}
            />
          </section>

          <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4">
            <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold mb-3 font-mono">
              {de ? "Datenvisualisierung" : "Data visualization"}
            </h2>
            <ChronosVisualizations
              bars={bars}
              indicators={indicators}
              backtest={backtest}
              s1Ids={tokenizeResult?.s1_ids}
              s2Ids={tokenizeResult?.s2_ids}
              language={language}
            />
          </section>

          <QuickLoadPanel
            de={de}
            symbol={symbol}
            setSymbol={setSymbol}
            interval={interval}
            setInterval={setInterval}
            assetClass={assetClass}
            setAssetClass={setAssetClass}
            lookback={lookback}
            setLookback={setLookback}
            busy={busy}
            bars={bars}
            barsSource={barsSource}
            onLoad={() => void loadBars()}
            inputCls={inputCls}
            labelCls={labelCls}
          />
        </div>
      ) : null}

      {/* ── Pipeline ── */}
      {tab === "pipeline" ? (
        <div className="space-y-4">
          <PipelineSteps de={de} step={pipelineStep} />

          <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-4">
            <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
              {de ? "Datenquelle & Parameter" : "Data source & parameters"}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <Field label={de ? "Symbol" : "Symbol"} id="chronos-symbol">
                <input
                  id="chronos-symbol"
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  className={inputCls}
                />
              </Field>
              <Field label={de ? "Intervall" : "Interval"} id="chronos-interval">
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
              </Field>
              <Field label={de ? "Asset-Klasse" : "Asset class"} id="chronos-asset">
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
              </Field>
              <Field label={de ? "Lookback" : "Lookback"} id="chronos-lookback">
                <div className="flex gap-1 mb-1.5">
                  {LOOKBACK_PRESETS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setLookback(p)}
                      className={`px-2 py-0.5 rounded text-[9px] border cursor-pointer ${
                        lookback === p
                          ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-300"
                          : "border-white/10 text-slate-500"
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                <input
                  id="chronos-lookback"
                  type="number"
                  min={2}
                  max={4096}
                  value={lookback}
                  onChange={(e) => setLookback(clampLookback(Number(e.target.value)))}
                  className={inputCls}
                />
              </Field>
              <Field label="eps" id="chronos-eps">
                <input
                  id="chronos-eps"
                  type="number"
                  step="1e-7"
                  value={eps}
                  onChange={(e) => setEps(Number(e.target.value) || 1e-6)}
                  className={inputCls}
                />
              </Field>
              <Field label="clip_val" id="chronos-clip">
                <input
                  id="chronos-clip"
                  type="number"
                  step="0.5"
                  value={clipVal}
                  onChange={(e) => setClipVal(Number(e.target.value) || 5)}
                  className={inputCls}
                />
              </Field>
            </div>

            <div className="flex flex-wrap gap-2 pt-2 border-t border-white/5">
              <ActionBtn onClick={() => void loadBars()} disabled={busy !== "idle"} primary>
                {busy === "load" ? "…" : de ? "1 · Lookback laden" : "1 · Load lookback"}
              </ActionBtn>
              <ActionBtn onClick={() => void runNormalize()} disabled={busy !== "idle" || !bars}>
                {busy === "normalize" ? "…" : de ? "2 · Normalisieren" : "2 · Normalize"}
              </ActionBtn>
              <ActionBtn onClick={() => void runTokenize()} disabled={busy !== "idle" || !bars} accent>
                {busy === "tokenize" ? "…" : de ? "3 · Tokenisieren" : "3 · Tokenize"}
              </ActionBtn>
              <ActionBtn onClick={() => void runCharts()} disabled={busy !== "idle" || !bars}>
                {busy === "charts" ? "…" : de ? "matplotlib-Charts" : "matplotlib charts"}
              </ActionBtn>
            </div>
            {bars ? (
              <p className="text-[10px] text-slate-500">
                {de ? "Geladen" : "Loaded"}: {bars.length} bars{barsSource ? ` · ${barsSource}` : ""}
              </p>
            ) : null}
          </section>

          {meanStd ? (
            <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs">
              <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold mb-3">
                {de ? "Normalisierung μ / σ" : "Normalization μ / σ"}
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[8px] text-slate-500 uppercase border-b border-white/5">
                      <th className="py-1.5 pr-4">{de ? "Merkmal" : "Feature"}</th>
                      <th className="py-1.5 pr-4">μ</th>
                      <th className="py-1.5">σ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(meanStd.feature_order?.length ? meanStd.feature_order : FEATURE_LABELS).map((name, i) => (
                      <tr key={name} className="border-b border-white/[0.03]">
                        <td className="py-1.5 pr-4 text-cyan-300/90">{name}</td>
                        <td className="py-1.5 pr-4 tabular-nums text-slate-300">{fmt(meanStd.mean[i])}</td>
                        <td className="py-1.5 tabular-nums text-slate-300">{fmt(meanStd.std[i])}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {chartEntries.length > 0 ? (
            <MatplotlibGallery
              de={de}
              title={de ? "Substrat-Charts" : "Substrate charts"}
              entries={chartEntries}
              meta={`L=${charts?.lookback}`}
              testId="chronos-charts"
            />
          ) : null}
        </div>
      ) : null}

      {/* ── Forecast ── */}
      {tab === "forecast" ? (
        <div className="space-y-4">
          <section className="bg-slate-950/60 border border-rose-500/10 rounded-xl p-4 font-mono text-xs space-y-4">
            <h2 className="text-[10px] text-rose-300/90 uppercase tracking-widest font-bold">
              {de ? "Kronos-Stil Prognose" : "Kronos-style forecast"}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <Field label="pred_len" id="chronos-pred-len">
                <input
                  id="chronos-pred-len"
                  type="number"
                  min={1}
                  max={512}
                  value={predLen}
                  onChange={(e) => setPredLen(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
              <Field label="T" id="chronos-T">
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
              </Field>
              <Field label="top_p" id="chronos-top-p">
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
              </Field>
              <Field label="MC samples" id="chronos-mc-n">
                <input
                  id="chronos-mc-n"
                  type="number"
                  min={2}
                  max={64}
                  value={mcSamples}
                  disabled={!monteCarlo}
                  onChange={(e) => setMcSamples(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
              <label className="flex items-end gap-2 text-[10px] text-slate-300 pb-2 cursor-pointer col-span-1">
                <input type="checkbox" checked={monteCarlo} onChange={(e) => setMonteCarlo(e.target.checked)} className="accent-rose-400" />
                Monte Carlo
              </label>
              <label className="flex items-end gap-2 text-[10px] text-slate-300 pb-2 cursor-pointer col-span-1">
                <input
                  type="checkbox"
                  checked={includeVolumePlot}
                  onChange={(e) => setIncludeVolumePlot(e.target.checked)}
                  className="accent-cyan-400"
                />
                {de ? "Volumen" : "Volume"}
              </label>
            </div>
            <button
              type="button"
              onClick={() => void runPredict()}
              disabled={busy !== "idle" || !bars}
              data-testid="chronos-predict"
              className="px-5 py-2.5 rounded-lg border border-rose-500/40 bg-rose-500/15 text-rose-100 font-bold hover:bg-rose-500/25 cursor-pointer disabled:opacity-50 text-xs"
            >
              {busy === "predict" ? "…" : de ? "Prognose starten" : "Run forecast"}
            </button>
            {!bars ? (
              <p className="text-[10px] text-slate-500">
                {de ? "Zuerst Lookback unter Pipeline laden." : "Load lookback under Pipeline first."}
              </p>
            ) : null}
          </section>

          {predictResult?.pattern_confluence ? (
            <div
              className={`text-xs font-mono border rounded-xl px-4 py-3 ${
                predictResult.pattern_confluence.agreement
                  ? "border-emerald-400/20 bg-emerald-950/30 text-emerald-200"
                  : "border-rose-400/20 bg-rose-950/30 text-rose-200"
              }`}
            >
              <div className="font-semibold mb-1 uppercase tracking-wider text-[10px]">
                Pattern → Chronos {de ? "Konfluenz" : "confluence"}
              </div>
              <div className="text-[10px] text-slate-300">
                {predictResult.pattern_confluence.input_bias} ({predictResult.pattern_confluence.input_confidence.toFixed(0)}%)
                → forecast {predictResult.pattern_confluence.forecast_bias}
                · {predictResult.pattern_confluence.agreement ? (de ? "Übereinstimmung" : "Agreement") : (de ? "Divergenz" : "Divergence")}
              </div>
            </div>
          ) : null}

          {predictionChartEntries.length > 0 ? (
            <MatplotlibGallery
              de={de}
              title={de ? "Prognose-Charts" : "Forecast charts"}
              entries={predictionChartEntries}
              meta={
                predictResult
                  ? `L=${predictResult.lookback} · pred=${predictResult.pred_len}`
                  : undefined
              }
              testId="chronos-prediction-charts"
              accent="rose"
            />
          ) : null}

          {predictResult?.pred?.length ? (
            <p className="text-[10px] text-slate-400 font-mono" data-testid="chronos-pred-len">
              pred rows: {predictResult.pred.length} · close[0]={predictResult.pred[0].close.toPrecision(6)}
            </p>
          ) : null}
          {predictResult?.chart_error ? (
            <p className="text-rose-300 text-[10px] font-mono">{predictResult.chart_error}</p>
          ) : null}
        </div>
      ) : null}

      {/* ── Advanced ── */}
      {tab === "advanced" ? (
        <div className="space-y-4">
          {tokenizeResult ? (
            <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-3">
              <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
                {de ? "Token-Analyse" : "Token analysis"}
              </h2>
              <div className="flex flex-wrap gap-4 text-[10px] text-slate-400">
                <span>
                  s1: <span className="text-cyan-300" data-testid="chronos-s1-len">{tokenizeResult.s1_ids.length}</span> ·{" "}
                  {uniqueCount(tokenizeResult.s1_ids)} distinct
                </span>
                <span>
                  s2: {tokenizeResult.s2_ids.length} · {uniqueCount(tokenizeResult.s2_ids)} distinct
                </span>
                <span>entropy: {fmt(tokenizeResult.entropy_mean, 5)}</span>
              </div>
              <ChronosVisualizations
                bars={bars}
                indicators={indicators}
                backtest={backtest}
                s1Ids={tokenizeResult.s1_ids}
                s2Ids={tokenizeResult.s2_ids}
                language={language}
              />
              <div className="flex items-center justify-between">
                <span className="text-[8px] text-slate-500 uppercase">
                  {showAllTokens ? (de ? "Alle IDs" : "All ids") : `Last ${TOKEN_PREVIEW}`}
                </span>
                {tokenizeResult.s1_ids.length > TOKEN_PREVIEW ? (
                  <button
                    type="button"
                    onClick={() => setShowAllTokens((v) => !v)}
                    className="text-[9px] text-cyan-400 cursor-pointer"
                  >
                    {showAllTokens ? (de ? "Weniger" : "Less") : de ? "Alle anzeigen" : "Show all"}
                  </button>
                ) : null}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-auto max-h-36">
                  s1: [{s1Preview.join(", ")}]
                </pre>
                <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-auto max-h-36">
                  s2: [{s2Preview.join(", ")}]
                </pre>
              </div>
            </section>
          ) : (
            <p className="text-[11px] text-slate-500 font-mono px-1">
              {de ? "Token-Daten erscheinen nach Tokenisierung (Pipeline-Tab)." : "Token data appears after tokenize (Pipeline tab)."}
            </p>
          )}

          <section className="bg-slate-950/60 border border-white/5 rounded-xl p-4 font-mono text-xs space-y-3">
            <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
              BSQ {de ? "Decode-Spielplatz" : "decode playground"}
            </h2>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="s1_id" id="bsq-s1">
                <input
                  id="bsq-s1"
                  type="number"
                  min={0}
                  max={1023}
                  value={bsqS1}
                  onChange={(e) => setBsqS1(Number(e.target.value))}
                  className={`${inputCls} w-24`}
                />
              </Field>
              <Field label="s2_id" id="bsq-s2">
                <input
                  id="bsq-s2"
                  type="number"
                  min={0}
                  max={1023}
                  value={bsqS2}
                  onChange={(e) => setBsqS2(Number(e.target.value))}
                  className={`${inputCls} w-24`}
                />
              </Field>
              <ActionBtn onClick={() => void runBsqDecode()} disabled={bsqBusy}>
                {bsqBusy ? "…" : de ? "Decodieren" : "Decode"}
              </ActionBtn>
            </div>
            {bsqZ ? (
              <pre className="bg-slate-900/60 border border-white/5 rounded-lg p-2 text-[10px] text-slate-300 overflow-x-auto">
                z[{bsqZ.length}]: [{bsqZ.map((v) => fmt(v, 3)).join(", ")}]
              </pre>
            ) : null}
          </section>

          <section className="bg-slate-950/40 border border-white/5 rounded-xl p-4 font-mono text-[10px] text-slate-500 space-y-2">
            <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">
              {de ? "Agent-Status (UI)" : "Agent status (UI)"}
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {AGENT_STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={!onUpdateAgentStatus}
                  onClick={() => onUpdateAgentStatus?.("chronos", s)}
                  className={`px-2 py-1 rounded text-[9px] font-semibold cursor-pointer border ${
                    agentStatus === s
                      ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-300"
                      : "bg-white/5 border-white/10 text-slate-500"
                  } disabled:opacity-40`}
                >
                  {s}
                </button>
              ))}
            </div>
            <p>
              {de
                ? "Kontextfrei — keine Auto-Trades. Chronos lernt selbst (Academy trainiert Chronos nicht)."
                : "Context-free — no auto-trades. Chronos is self-taught (Academy does not train Chronos)."}
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function Badge({
  children,
  tone,
  testId,
}: {
  children: React.ReactNode;
  tone: "cyan" | "amber" | "emerald" | "slate";
  testId?: string;
}) {
  const styles = {
    cyan: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
    amber: "border-amber-500/30 bg-amber-500/10 text-amber-300 font-bold",
    emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    slate: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  };
  return (
    <span data-testid={testId} className={`text-[9px] px-2 py-1 rounded-lg border ${styles[tone]}`}>
      {children}
    </span>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  highlight,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-3 font-mono ${
        highlight ? "border-cyan-500/20 bg-cyan-500/5" : "border-white/5 bg-slate-950/60"
      }`}
    >
      <div className="flex items-center gap-1.5 text-[8px] text-slate-500 uppercase tracking-widest mb-1">
        <Icon className="w-3 h-3" />
        {label}
      </div>
      <div className="text-sm font-bold text-slate-100 truncate">{value}</div>
    </div>
  );
}

function Field({
  label,
  id,
  children,
}: {
  label: string;
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-[8px] text-slate-500 uppercase tracking-widest block mb-1.5" htmlFor={id}>
        {label}
      </label>
      {children}
    </div>
  );
}

function ActionBtn({
  children,
  onClick,
  disabled,
  primary,
  accent,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  accent?: boolean;
}) {
  const cls = accent
    ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-100 font-bold hover:bg-cyan-500/25"
    : primary
      ? "border-white/15 text-slate-200 hover:bg-white/5"
      : "border-white/10 text-slate-400 hover:text-slate-200";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`px-4 py-2 rounded-lg border text-xs cursor-pointer disabled:opacity-50 ${cls}`}
    >
      {children}
    </button>
  );
}

function PipelineSteps({ de, step }: { de: boolean; step: number }) {
  const steps = de
    ? ["Lookback laden", "Normalisieren", "Tokenisieren"]
    : ["Load lookback", "Normalize", "Tokenize"];
  return (
    <div className="flex flex-wrap items-center gap-1 font-mono text-[10px]">
      {steps.map((label, i) => (
        <React.Fragment key={label}>
          <div
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${
              step > i
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                : step === i
                  ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-300"
                  : "border-white/5 bg-slate-950/40 text-slate-500"
            }`}
          >
            <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[9px] font-bold">
              {i + 1}
            </span>
            {label}
          </div>
          {i < steps.length - 1 ? <ChevronRight className="w-3 h-3 text-slate-600" /> : null}
        </React.Fragment>
      ))}
    </div>
  );
}

function QuickLoadPanel({
  de,
  symbol,
  setSymbol,
  interval,
  setInterval,
  assetClass,
  setAssetClass,
  lookback,
  setLookback,
  busy,
  bars,
  barsSource,
  onLoad,
  inputCls,
  labelCls,
}: {
  de: boolean;
  symbol: string;
  setSymbol: (v: string) => void;
  interval: string;
  setInterval: (v: (typeof INTERVALS)[number]) => void;
  assetClass: AssetClass;
  setAssetClass: (v: AssetClass) => void;
  lookback: number;
  setLookback: (v: number) => void;
  busy: string;
  bars: number[][] | null;
  barsSource: string;
  onLoad: () => void;
  inputCls: string;
  labelCls: string;
}) {
  return (
    <section className="bg-slate-950/60 border border-cyan-500/10 rounded-xl p-4 font-mono text-xs">
      <h2 className="text-[10px] text-cyan-300/90 uppercase tracking-widest font-bold mb-3">
        {de ? "Schnellstart" : "Quick start"}
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
        <div>
          <label className={labelCls} htmlFor="qs-symbol">
            Symbol
          </label>
          <input id="qs-symbol" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className={inputCls} />
        </div>
        <div>
          <label className={labelCls} htmlFor="qs-interval">
            Interval
          </label>
          <select
            id="qs-interval"
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
          <label className={labelCls} htmlFor="qs-asset">
            Asset
          </label>
          <select
            id="qs-asset"
            value={assetClass}
            onChange={(e) => setAssetClass(e.target.value as AssetClass)}
            className={inputCls}
          >
            <option value="crypto">crypto</option>
            <option value="forex">forex</option>
            <option value="sp500">sp500</option>
          </select>
        </div>
        <div>
          <label className={labelCls} htmlFor="qs-lookback">
            Lookback
          </label>
          <input
            id="qs-lookback"
            type="number"
            min={2}
            max={4096}
            value={lookback}
            onChange={(e) => setLookback(clampLookback(Number(e.target.value)))}
            className={inputCls}
          />
        </div>
      </div>
      <button
        type="button"
        onClick={onLoad}
        disabled={busy !== "idle"}
        className="px-5 py-2 rounded-lg border border-cyan-500/40 bg-cyan-500/15 text-cyan-100 font-bold hover:bg-cyan-500/25 cursor-pointer disabled:opacity-50"
      >
        {busy === "load" ? "…" : de ? "Lookback laden" : "Load lookback"}
      </button>
      {bars ? (
        <p className="mt-2 text-[10px] text-slate-500">
          {de ? "Geladen" : "Loaded"}: {bars.length} bars{barsSource ? ` · ${barsSource}` : ""}
        </p>
      ) : null}
    </section>
  );
}

function MatplotlibGallery({
  de,
  title,
  entries,
  meta,
  testId,
  accent,
}: {
  de: boolean;
  title: string;
  entries: { key: string; src: string; label: string }[];
  meta?: string;
  testId?: string;
  accent?: "rose" | "cyan";
}) {
  const border = accent === "rose" ? "border-rose-500/15" : "border-white/5";
  const caption = accent === "rose" ? "text-rose-300/90" : "text-cyan-300/90";
  return (
    <section data-testid={testId} className={`bg-slate-950/60 border ${border} rounded-xl p-4 font-mono text-xs space-y-4`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">{title}</h2>
        {meta ? <span className="text-[9px] text-slate-500">{meta}</span> : null}
      </div>
      <div className="grid grid-cols-1 gap-4">
        {entries.map((entry) => (
          <figure key={entry.key} className="space-y-2">
            <figcaption className={`text-[9px] ${caption} uppercase tracking-widest`}>{entry.label}</figcaption>
            <img src={entry.src} alt={entry.label} className="w-full rounded-lg border border-white/5 bg-[#090d16]" />
          </figure>
        ))}
      </div>
    </section>
  );
}
