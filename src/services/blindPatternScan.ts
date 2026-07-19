/**
 * Blindfolded candlestick pattern scan.
 * Operates on relative candle geometry only — no symbol, timeframe, or absolute prices.
 * Catalog grounded in daytrading candlestick/indicator pattern literature
 * (Hammer, Engulfing, Stars, Doji variants, Soldiers/Crows, etc.).
 */

export type BlindCandle = {
  /** +1 bullish close, -1 bearish close, 0 doji-like */
  dir: -1 | 0 | 1;
  body: number; // 0..1 of range
  upper: number; // 0..1 of range
  lower: number; // 0..1 of range
};

export type BlindPatternHit = {
  name: string;
  bias: "bullish" | "bearish" | "neutral";
  confidence: number; // 0..100
  kind: "single" | "double" | "triple";
};

export type BlindPatternScanResult = {
  hits: BlindPatternHit[];
  summary: string;
  candleCount: number;
};

/** Build relative candles from a close series (open=prev close). Absolute levels are discarded. */
export function closesToBlindCandles(closes: number[]): BlindCandle[] {
  const clean = closes.filter((n) => Number.isFinite(n) && n > 0);
  if (clean.length < 2) return [];
  const out: BlindCandle[] = [];
  for (let i = 1; i < clean.length; i++) {
    const open = clean[i - 1];
    const close = clean[i];
    const high = Math.max(open, close);
    const low = Math.min(open, close);
    // Expand range slightly so wicks can exist when open≈close
    const pad = Math.max((high - low) * 0.05, Math.abs(close) * 1e-6, 1e-9);
    const hi = high + pad * 0.15;
    const lo = low - pad * 0.15;
    out.push(normalizeOhlc(open, hi, lo, close));
  }
  return out;
}

export function ohlcToBlindCandles(
  bars: Array<{open: number; high: number; low: number; close: number}>,
): BlindCandle[] {
  return bars
    .filter((b) => b.high > 0 && b.low > 0 && b.high >= b.low)
    .map((b) => normalizeOhlc(b.open, b.high, b.low, b.close));
}

function normalizeOhlc(open: number, high: number, low: number, close: number): BlindCandle {
  const range = Math.max(high - low, 1e-12);
  const bodyTop = Math.max(open, close);
  const bodyBot = Math.min(open, close);
  const body = Math.abs(close - open) / range;
  const upper = (high - bodyTop) / range;
  const lower = (bodyBot - low) / range;
  const dir: -1 | 0 | 1 =
    body < 0.08 ? 0 : close > open ? 1 : close < open ? -1 : 0;
  return {
    dir,
    body: clamp01(body),
    upper: clamp01(upper),
    lower: clamp01(lower),
  };
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

function isHammer(c: BlindCandle): boolean {
  return c.lower >= 2 * Math.max(c.body, 0.05) && c.upper <= 0.25 && c.body <= 0.4;
}

function isInvertedHammer(c: BlindCandle): boolean {
  return c.upper >= 2 * Math.max(c.body, 0.05) && c.lower <= 0.25 && c.body <= 0.4;
}

function isShootingStar(c: BlindCandle): boolean {
  return isInvertedHammer(c) && c.dir <= 0;
}

function isHangingMan(c: BlindCandle): boolean {
  return isHammer(c) && c.dir <= 0;
}

function isDragonflyDoji(c: BlindCandle): boolean {
  return c.body <= 0.08 && c.lower >= 0.55 && c.upper <= 0.12;
}

function isGravestoneDoji(c: BlindCandle): boolean {
  return c.body <= 0.08 && c.upper >= 0.55 && c.lower <= 0.12;
}

function isDoji(c: BlindCandle): boolean {
  return c.body <= 0.1 && !isDragonflyDoji(c) && !isGravestoneDoji(c);
}

function isMarubozu(c: BlindCandle): boolean {
  return c.body >= 0.75 && c.upper <= 0.12 && c.lower <= 0.12 && c.dir !== 0;
}

function bullishEngulfing(a: BlindCandle, b: BlindCandle): boolean {
  // Relative geometry only: prior bearish, strong bullish follow-through that dominates prior body share.
  return a.dir < 0 && b.dir > 0 && b.body >= 0.4 && b.body >= a.body * 0.85;
}

function bearishEngulfing(a: BlindCandle, b: BlindCandle): boolean {
  return a.dir > 0 && b.dir < 0 && b.body >= 0.4 && b.body >= a.body * 0.85;
}

function piercingLine(a: BlindCandle, b: BlindCandle): boolean {
  // Relative: prior bearish, next bullish with larger body recovering past midpoint proxy
  return a.dir < 0 && b.dir > 0 && b.body >= 0.35 && b.body > a.body * 0.55 && b.lower <= 0.35;
}

function darkCloudCover(a: BlindCandle, b: BlindCandle): boolean {
  return a.dir > 0 && b.dir < 0 && b.body >= 0.35 && b.body > a.body * 0.55 && b.upper <= 0.35;
}

function harami(a: BlindCandle, b: BlindCandle): boolean {
  return a.body >= 0.4 && b.body > 0.05 && b.body < a.body * 0.55 && a.dir !== 0 && b.dir !== a.dir;
}

function insideBar(a: BlindCandle, b: BlindCandle): boolean {
  // Relative range proxy: smaller body+wicks than prior
  const rangeA = 1;
  const rangeB = b.body + b.upper + b.lower;
  return rangeB < rangeA * 0.75 && b.body < a.body;
}

function morningStar(a: BlindCandle, b: BlindCandle, c: BlindCandle): boolean {
  return a.dir < 0 && a.body >= 0.35 && b.body <= 0.3 && c.dir > 0 && c.body >= 0.35;
}

function eveningStar(a: BlindCandle, b: BlindCandle, c: BlindCandle): boolean {
  return a.dir > 0 && a.body >= 0.35 && b.body <= 0.3 && c.dir < 0 && c.body >= 0.35;
}

function threeWhiteSoldiers(a: BlindCandle, b: BlindCandle, c: BlindCandle): boolean {
  return (
    a.dir > 0 &&
    b.dir > 0 &&
    c.dir > 0 &&
    a.body >= 0.35 &&
    b.body >= 0.35 &&
    c.body >= 0.35 &&
    a.upper <= 0.3 &&
    b.upper <= 0.3 &&
    c.upper <= 0.3
  );
}

function threeBlackCrows(a: BlindCandle, b: BlindCandle, c: BlindCandle): boolean {
  return (
    a.dir < 0 &&
    b.dir < 0 &&
    c.dir < 0 &&
    a.body >= 0.35 &&
    b.body >= 0.35 &&
    c.body >= 0.35 &&
    a.lower <= 0.3 &&
    b.lower <= 0.3 &&
    c.lower <= 0.3
  );
}

/** Scan the last few relative candles for catalog patterns. */
export function scanBlindPatterns(candles: BlindCandle[]): BlindPatternScanResult {
  if (candles.length < 1) {
    return {
      hits: [],
      summary: "Blind pattern scan idle — need candle geometry.",
      candleCount: 0,
    };
  }

  const hits: BlindPatternHit[] = [];
  const n = candles.length;
  const c0 = candles[n - 1];
  const c1 = n >= 2 ? candles[n - 2] : null;
  const c2 = n >= 3 ? candles[n - 3] : null;

  // Singles (latest bar)
  if (isDragonflyDoji(c0)) hits.push({name: "Dragonfly Doji", bias: "bullish", confidence: 78, kind: "single"});
  else if (isGravestoneDoji(c0)) hits.push({name: "Gravestone Doji", bias: "bearish", confidence: 78, kind: "single"});
  else if (isDoji(c0)) hits.push({name: "Doji", bias: "neutral", confidence: 55, kind: "single"});

  if (isHammer(c0) && !isHangingMan(c0)) hits.push({name: "Hammer", bias: "bullish", confidence: 68, kind: "single"});
  if (isHangingMan(c0)) hits.push({name: "Hanging Man", bias: "bearish", confidence: 64, kind: "single"});
  if (isInvertedHammer(c0) && !isShootingStar(c0)) {
    hits.push({name: "Inverted Hammer", bias: "bullish", confidence: 62, kind: "single"});
  }
  if (isShootingStar(c0)) hits.push({name: "Shooting Star", bias: "bearish", confidence: 66, kind: "single"});
  if (isMarubozu(c0)) {
    hits.push({
      name: c0.dir > 0 ? "Bullish Marubozu" : "Bearish Marubozu",
      bias: c0.dir > 0 ? "bullish" : "bearish",
      confidence: 70,
      kind: "single",
    });
  }

  // Doubles
  if (c1) {
    if (bullishEngulfing(c1, c0)) hits.push({name: "Bullish Engulfing", bias: "bullish", confidence: 76, kind: "double"});
    if (bearishEngulfing(c1, c0)) hits.push({name: "Bearish Engulfing", bias: "bearish", confidence: 76, kind: "double"});
    if (piercingLine(c1, c0)) hits.push({name: "Piercing Line", bias: "bullish", confidence: 70, kind: "double"});
    if (darkCloudCover(c1, c0)) hits.push({name: "Dark Cloud Cover", bias: "bearish", confidence: 70, kind: "double"});
    if (harami(c1, c0)) {
      hits.push({
        name: c0.dir > 0 ? "Bullish Harami" : c0.dir < 0 ? "Bearish Harami" : "Harami",
        bias: c0.dir > 0 ? "bullish" : c0.dir < 0 ? "bearish" : "neutral",
        confidence: 63,
        kind: "double",
      });
    }
    if (insideBar(c1, c0)) hits.push({name: "Inside Bar", bias: "neutral", confidence: 58, kind: "double"});
  }

  // Triples
  if (c1 && c2) {
    if (morningStar(c2, c1, c0)) hits.push({name: "Morning Star", bias: "bullish", confidence: 80, kind: "triple"});
    if (eveningStar(c2, c1, c0)) hits.push({name: "Evening Star", bias: "bearish", confidence: 80, kind: "triple"});
    if (threeWhiteSoldiers(c2, c1, c0)) {
      hits.push({name: "Three White Soldiers", bias: "bullish", confidence: 82, kind: "triple"});
    }
    if (threeBlackCrows(c2, c1, c0)) {
      hits.push({name: "Three Black Crows", bias: "bearish", confidence: 82, kind: "triple"});
    }
  }

  // Deduplicate by name, keep highest confidence
  const byName = new Map<string, BlindPatternHit>();
  for (const hit of hits) {
    const prev = byName.get(hit.name);
    if (!prev || hit.confidence > prev.confidence) byName.set(hit.name, hit);
  }
  const unique = [...byName.values()].sort((a, b) => b.confidence - a.confidence);

  if (unique.length === 0) {
    return {
      hits: [],
      summary: `Blind pattern scan · ${candles.length} relative candles · no catalog match (geometry only).`,
      candleCount: candles.length,
    };
  }

  const top = unique.slice(0, 3);
  const summary = `Blind pattern scan · ${top
    .map((h) => `${h.name} (${h.bias}, ${h.confidence}%)`)
    .join(" · ")} · no symbol/TF/price context.`;

  return {hits: unique, summary, candleCount: candles.length};
}

/** Pattern-mode vision prompt: ignore labels, prices, timeframes. */
export const BLIND_PATTERN_VISION_PROMPT = `You are a BLINDFolded candlestick pattern analyst.

STRICT RULES:
- Ignore and do NOT mention: ticker/symbol names, exchange labels, timeframes, axis numbers, dollar/price levels, volume numbers, or indicators' numeric values.
- Focus ONLY on candle geometry and classic catalog patterns.
- Catalog to consider: Hammer, Inverted Hammer, Hanging Man, Shooting Star, Dragonfly Doji, Gravestone Doji, Doji, Bullish/Bearish Engulfing, Piercing Line, Dark Cloud Cover, Harami, Inside Bar, Morning Star, Evening Star, Three White Soldiers, Three Black Crows, Marubozu, Flags/Pennants/Wedges as pure shape if visible.
- Output: (1) pattern name(s), (2) bias bullish/bearish/neutral, (3) confidence 0-100, (4) one sentence on geometry confluence. No prices. No symbol. No timeframe.`;
