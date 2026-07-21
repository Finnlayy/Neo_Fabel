import {useMemo, useState} from "react";
import {
  parseLiveSymbols,
  type AmountUnit,
  type CapAmount,
  type LiveStartConfig,
  type PositionSizingMode,
} from "../api/loops";

type Props = {
  de?: boolean;
  onCancel: () => void;
  onConfirm: (config: LiveStartConfig) => void;
};

const DEFAULT_CAPITAL = "10";
const DEFAULT_SIZE = "10";
const DEFAULT_TRADES = "2";
const DEFAULT_LOSS = "5";
const DEFAULT_CONF = "60";
const DEFAULT_SYMBOLS = "XRPUSD, ADAUSD";
const DEFAULT_MANUAL = "5";

const SIZING_OPTIONS: {value: PositionSizingMode; de: string; en: string}[] = [
  {value: "half_kelly", de: "Half Kelly", en: "Half Kelly"},
  {value: "full_kelly", de: "Full Kelly", en: "Full Kelly"},
  {value: "ai_chronos", de: "AI / Chronos", en: "AI / Chronos"},
  {value: "manual", de: "Manuell", en: "Manual"},
];

const UNIT_OPTIONS: {value: AmountUnit; label: string}[] = [
  {value: "eur", label: "€"},
  {value: "usd", label: "$"},
  {value: "pct", label: "% cap"},
];

function CapRow({
  label,
  value,
  unit,
  onValue,
  onUnit,
}: {
  label: string;
  value: string;
  unit: AmountUnit;
  onValue: (v: string) => void;
  onUnit: (u: AmountUnit) => void;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      <div className="flex gap-2">
        <input
          type="number"
          min={0}
          step={0.01}
          value={value}
          onChange={(e) => onValue(e.target.value)}
          className="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
        />
        <select
          value={unit}
          onChange={(e) => onUnit(e.target.value as AmountUnit)}
          className="bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[11px] text-slate-100"
        >
          {UNIT_OPTIONS.map((u) => (
            <option key={u.value} value={u.value}>
              {u.label}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}

export function LiveStartConfirmModal({de = false, onCancel, onConfirm}: Props) {
  const [capital, setCapital] = useState(DEFAULT_CAPITAL);
  const [sizeVal, setSizeVal] = useState(DEFAULT_SIZE);
  const [sizeUnit, setSizeUnit] = useState<AmountUnit>("eur");
  const [trades, setTrades] = useState(DEFAULT_TRADES);
  const [lossVal, setLossVal] = useState(DEFAULT_LOSS);
  const [lossUnit, setLossUnit] = useState<AmountUnit>("pct");
  const [minConf, setMinConf] = useState(DEFAULT_CONF);
  const [prePost, setPrePost] = useState(true);
  const [humanVerify, setHumanVerify] = useState(true);
  const [symbolsRaw, setSymbolsRaw] = useState(DEFAULT_SYMBOLS);
  const [sizingMode, setSizingMode] = useState<PositionSizingMode>("half_kelly");
  const [manualNotional, setManualNotional] = useState(DEFAULT_MANUAL);
  const [formError, setFormError] = useState("");

  const symbols = useMemo(() => parseLiveSymbols(symbolsRaw), [symbolsRaw]);

  const submit = () => {
    const startCapital = Number(capital);
    const maxTrades = Number.parseInt(trades, 10);
    const sizeNum = Number(sizeVal);
    const lossNum = Number(lossVal);
    const confNum = Number(minConf);
    const manual = Number(manualNotional);

    if (!Number.isFinite(startCapital) || startCapital <= 0) {
      setFormError(de ? "Startkapital muss > 0 sein" : "Starting capital must be > 0");
      return;
    }
    if (!Number.isFinite(sizeNum) || sizeNum <= 0) {
      setFormError(de ? "Max session size muss > 0 sein" : "Max session size must be > 0");
      return;
    }
    if (!Number.isFinite(maxTrades) || maxTrades < 1 || maxTrades > 10) {
      setFormError(de ? "Parallele Trades: 1–10" : "Concurrent trades: 1–10");
      return;
    }
    if (!Number.isFinite(lossNum) || lossNum < 0) {
      setFormError(de ? "Daily loss limit ungültig" : "Invalid daily loss limit");
      return;
    }
    if (!Number.isFinite(confNum) || confNum < 0 || confNum > 100) {
      setFormError(de ? "Min confidence 0–100%" : "Min confidence 0–100%");
      return;
    }
    if (sizingMode === "manual" && (!Number.isFinite(manual) || manual <= 0)) {
      setFormError(de ? "Manuelles Notional (€) muss > 0 sein" : "Manual notional (€) must be > 0");
      return;
    }

    const max_session_size: CapAmount = {value: sizeNum, unit: sizeUnit};
    const daily_loss_limit: CapAmount = {value: lossNum, unit: lossUnit};

    setFormError("");
    onConfirm({
      starting_capital_eur: startCapital,
      max_session_size,
      max_margin_eur: sizeUnit === "eur" ? sizeNum : startCapital,
      max_concurrent_trades: maxTrades,
      daily_loss_limit,
      min_confidence_pct: confNum,
      allow_pre_post_market: prePost,
      human_verification: humanVerify,
      symbols: symbols.length ? symbols : undefined,
      position_sizing_mode: sizingMode,
      manual_notional_eur: sizingMode === "manual" ? manual : undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-950 border border-rose-500/40 rounded-lg p-4 max-w-lg w-full font-mono space-y-3 shadow-xl max-h-[92vh] overflow-y-auto">
        <h3 className="text-sm font-bold text-rose-300 uppercase tracking-widest">
          {de ? "Live-Session starten" : "Start live session"}
        </h3>
        <p className="text-[11px] text-slate-300 leading-relaxed">
          {de
            ? "Risiko-Limits für diese Session. Bei Human-Verify gehen Trade-Vorschläge per Telegram zur Freigabe."
            : "Risk limits for this session. With human verify, trade proposals go to Telegram for approval."}
        </p>

        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            {de ? "Startkapital / Max Capital (€)" : "Starting / max capital (€)"}
          </span>
          <input
            type="number"
            min={0.01}
            step={0.01}
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            className="w-full bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
          />
        </label>

        <CapRow
          label={de ? "Max Session Size" : "Max session size"}
          value={sizeVal}
          unit={sizeUnit}
          onValue={setSizeVal}
          onUnit={setSizeUnit}
        />

        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            {de ? "Max Concurrent Trades (1–10)" : "Max concurrent trades (1–10)"}
          </span>
          <input
            type="number"
            min={1}
            max={10}
            step={1}
            value={trades}
            onChange={(e) => setTrades(e.target.value)}
            className="w-full bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
          />
        </label>

        <CapRow
          label={de ? "Tägliches Loss Limit" : "Daily loss limit"}
          value={lossVal}
          unit={lossUnit}
          onValue={setLossVal}
          onUnit={setLossUnit}
        />

        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            {de ? "Min Confidence (%)" : "Min confidence (%)"}
          </span>
          <input
            type="number"
            min={0}
            max={100}
            step={1}
            value={minConf}
            onChange={(e) => setMinConf(e.target.value)}
            className="w-full bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
          />
        </label>

        <div className="grid grid-cols-1 gap-2">
          <label className="flex items-center justify-between gap-3 rounded border border-white/10 bg-black/20 px-2 py-1.5">
            <span className="text-[11px] text-slate-200">
              {de ? "Pre/Post Market erlauben" : "Allow pre/post market"}
            </span>
            <input type="checkbox" checked={prePost} onChange={(e) => setPrePost(e.target.checked)} />
          </label>
          <label className="flex items-center justify-between gap-3 rounded border border-rose-500/30 bg-rose-500/5 px-2 py-1.5">
            <span className="text-[11px] text-slate-200">
              {de
                ? "Extra Human Verification (Telegram Approve)"
                : "Extra human verification (Telegram approve)"}
            </span>
            <input
              type="checkbox"
              checked={humanVerify}
              onChange={(e) => setHumanVerify(e.target.checked)}
            />
          </label>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-[10px] uppercase tracking-wider text-slate-500">
            {de ? "Position Sizing" : "Position sizing"}
          </legend>
          <div className="grid grid-cols-2 gap-1.5">
            {SIZING_OPTIONS.map((opt) => {
              const selected = sizingMode === opt.value;
              return (
                <label
                  key={opt.value}
                  className={`flex items-center gap-2 rounded border px-2 py-1.5 cursor-pointer ${
                    selected
                      ? "border-rose-500/50 bg-rose-500/10"
                      : "border-white/10 bg-black/20 hover:border-white/25"
                  }`}
                >
                  <input
                    type="radio"
                    name="position_sizing"
                    checked={selected}
                    onChange={() => setSizingMode(opt.value)}
                  />
                  <span className="text-[11px] text-slate-100">{de ? opt.de : opt.en}</span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {sizingMode === "manual" ? (
          <label className="block space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-slate-500">
              {de ? "Manuelles Notional (€ / Trade)" : "Manual notional (€ / trade)"}
            </span>
            <input
              type="number"
              min={0.01}
              step={0.01}
              value={manualNotional}
              onChange={(e) => setManualNotional(e.target.value)}
              className="w-full bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
            />
          </label>
        ) : null}

        <label className="block space-y-1">
          <span className="text-[10px] uppercase tracking-wider text-slate-500">
            {de ? "Symbole (optional)" : "Symbols (optional)"}
          </span>
          <input
            type="text"
            value={symbolsRaw}
            onChange={(e) => setSymbolsRaw(e.target.value)}
            placeholder="XRPUSD, METAUSD, ADAUSD"
            className="w-full bg-black/40 border border-white/15 rounded px-2 py-1.5 text-[12px] text-slate-100"
          />
        </label>

        {formError ? <p className="text-[10px] text-rose-400">{formError}</p> : null}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            className="px-3 py-1.5 text-[10px] border border-white/15 text-slate-300 rounded cursor-pointer"
            onClick={onCancel}
          >
            {de ? "Abbrechen" : "Cancel"}
          </button>
          <button
            type="button"
            className="px-3 py-1.5 text-[10px] bg-rose-500/20 border border-rose-500/40 text-rose-200 rounded cursor-pointer font-bold"
            onClick={submit}
          >
            {de ? "Live starten" : "Start live"}
          </button>
        </div>
      </div>
    </div>
  );
}
