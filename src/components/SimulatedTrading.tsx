import {FormEvent, useMemo, useState} from "react";
import {AlertTriangle, CheckCircle2, Play, ShieldCheck} from "lucide-react";
import {TickerData, Trade} from "../types";
import {ApiError, apiRequest} from "../api/client";

interface SimulatedTradingProps {
  tickers: TickerData[];
  onExecuteTrade: (trade: Omit<Trade, "id" | "time" | "pnl" | "status">) => void;
  isComplianceActive: boolean;
  tradingExchange: string;
}

type PaperOrderResponse = {result: Record<string, unknown>};

export default function SimulatedTrading({
  tickers,
  onExecuteTrade,
  isComplianceActive: _isComplianceActive,
  tradingExchange,
}: SimulatedTradingProps) {
  const [selectedAsset, setSelectedAsset] = useState(tickers[0]?.symbol ?? "BTC");
  const [tradeType, setTradeType] = useState<"BUY" | "SELL">("BUY");
  const [amount, setAmount] = useState("0.001");
  const [status, setStatus] = useState<"idle" | "submitting" | "accepted" | "error">("idle");
  const [message, setMessage] = useState("");

  const activeTicker = useMemo(
    () => tickers.find((ticker) => ticker.symbol === selectedAsset),
    [selectedAsset, tickers],
  );
  const activePrice = activeTicker?.price ?? 0;
  const canSubmit = status !== "submitting" && Boolean(activeTicker) && Number(amount) > 0;

  const handleOrderSubmission = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;

    setStatus("submitting");
    setMessage("Submitting a paper order through FastAPI...");
    try {
      const body = await apiRequest<PaperOrderResponse & {status?: string}>("/api/v1/trade/execute", {
        method: "POST",
        body: JSON.stringify({
          pair: `${selectedAsset}USD`,
          side: tradeType.toLowerCase(),
          volume: amount,
          order_type: "market",
          idempotency_key: crypto.randomUUID(),
        }),
      });
      const source =
        typeof body.result?.source === "string" ? String(body.result.source) : "paper";
      setStatus("accepted");
      setMessage(`Paper order accepted (${source}).`);
      onExecuteTrade({asset: selectedAsset, type: tradeType, price: activePrice, amount: Number(amount)});
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof ApiError ? `${error.code}: ${error.message}` : "Paper execution unavailable.");
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
      <div className="bg-slate-900/40 border border-amber-500/20 rounded-xl p-5">
        <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
          <div className="flex items-center gap-2 text-white font-bold uppercase tracking-wider text-[11px]">
            <ShieldCheck className="w-4 h-4 text-amber-400" />
            Paper execution
          </div>
          <span className="text-[9px] text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded uppercase">
            PAPER ONLY
          </span>
        </div>

        <form onSubmit={handleOrderSubmission} className="space-y-4">
          <label className="block text-[10px] text-slate-400 uppercase">
            Asset
            <select
              data-trace-id="ORDER-ASSET"
              value={selectedAsset}
              onChange={(event) => setSelectedAsset(event.target.value)}
              className="mt-1 w-full bg-slate-950 border border-white/5 rounded-sm px-2.5 py-1.5 text-slate-200"
            >
              {tickers.map((ticker) => <option key={ticker.symbol} value={ticker.symbol}>{ticker.symbol}</option>)}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <button data-trace-id="ORDER-BUY" type="button" onClick={() => setTradeType("BUY")} className={`py-2 rounded-sm ${tradeType === "BUY" ? "bg-emerald-500/20 text-emerald-300" : "bg-white/5 text-slate-400"}`}>BUY</button>
            <button data-trace-id="ORDER-SELL" type="button" onClick={() => setTradeType("SELL")} className={`py-2 rounded-sm ${tradeType === "SELL" ? "bg-rose-500/20 text-rose-300" : "bg-white/5 text-slate-400"}`}>SELL</button>
          </div>

          <label className="block text-[10px] text-slate-400 uppercase">
            Volume
            <input data-trace-id="ORDER-VOLUME" type="number" min="0.00000001" step="0.00000001" value={amount} onChange={(event) => setAmount(event.target.value)} className="mt-1 w-full bg-slate-950 border border-white/5 rounded-sm px-2.5 py-1.5 text-slate-200" />
          </label>

          <div className="text-slate-400 border border-white/5 bg-slate-950/60 rounded-sm p-3">
            <div className="flex justify-between"><span>Source</span><span className="text-slate-200">API paper router (CLI or local ledger)</span></div>
            <div className="flex justify-between mt-1"><span>Last known price</span><span className="text-slate-200">{activePrice ? `$${activePrice.toLocaleString()}` : "Unavailable"}</span></div>
          </div>

          <button data-trace-id="ORDER-SUBMIT" type="submit" disabled={!canSubmit} className="w-full bg-white/5 hover:bg-white/10 disabled:opacity-40 border border-amber-500/20 text-white rounded-sm py-2.5 text-[10px] font-bold tracking-widest uppercase flex items-center justify-center gap-2">
            <Play className="w-3.5 h-3.5 text-amber-400" />
            {status === "submitting" ? "SUBMITTING..." : "SUBMIT PAPER ORDER"}
          </button>
        </form>

        {message && <div className={`mt-4 p-3 rounded border flex items-center gap-2 ${status === "error" ? "border-rose-500/30 text-rose-300" : status === "accepted" ? "border-emerald-500/30 text-emerald-300" : "border-amber-500/30 text-amber-300"}`}>
          {status === "error" ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
          <span>{message}</span>
        </div>}
      </div>

      <div className="bg-slate-900/40 border border-white/5 rounded-xl p-5">
        <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-4">
          <span className="text-white font-bold uppercase tracking-wider text-[11px]">Order book</span>
          <span className="text-[9px] text-slate-500 uppercase">Backend data required</span>
        </div>
        <div className="h-52 flex items-center justify-center text-center text-slate-500 border border-dashed border-white/10 rounded">
          No order-book snapshot is available. The UI will not display fabricated depth data.
        </div>
      </div>
    </div>
  );
}
