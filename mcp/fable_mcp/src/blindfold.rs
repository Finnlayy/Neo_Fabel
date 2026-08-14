//! Scale-free blindfold formatting — indexed prices, temporal offsets, relative volume.

use serde::{Deserialize, Serialize};

/// Raw OHLCV bar (absolute prices allowed at input; output is scale-invariant indexed).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RawBar {
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

/// Blindfolded bar — no symbol, no absolute timestamps, scale-normalized index prices.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BlindfoldedBar {
    pub offset: String,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub rel_volume: f64,
    pub rsi_14: f64,
    pub atr_pct_14: f64,
    pub ema_fast_dist_pct: f64,
    pub ema_slow_dist_pct: f64,
}

/// Scale factor: 100.0 / close_0 — multiplying all raw prices by k cancels in indexed space.
pub fn scale_factor(close_0: f64) -> f64 {
    if close_0.abs() < 1e-12 {
        return 1.0;
    }
    100.0 / close_0
}

pub fn index_price(raw: f64, close_0: f64) -> f64 {
    raw * scale_factor(close_0)
}

/// Relative offset label from bar 0, e.g. `t+0d 0h`, `t+1d 4h`.
pub fn temporal_offset(bar_index: usize, bar_hours: u32) -> String {
    let total_hours = bar_index as u32 * bar_hours;
    let days = total_hours / 24;
    let hours = total_hours % 24;
    format!("t+{days}d {hours}h")
}

/// Volume relative to trailing 20-bar SMA (inclusive of current bar when enough history).
pub fn relative_volume(volumes: &[f64], index: usize) -> f64 {
    if index >= volumes.len() {
        return 1.0;
    }
    let start = index.saturating_sub(19);
    let window = &volumes[start..=index];
    let mean: f64 = window.iter().sum::<f64>() / window.len() as f64;
    if mean.abs() < 1e-12 {
        return 1.0;
    }
    volumes[index] / mean
}

pub fn round_price(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

pub fn round_indicator(v: f64) -> f64 {
    (v * 10.0).round() / 10.0
}

fn ema_series(values: &[f64], period: usize) -> Vec<f64> {
    if values.is_empty() {
        return vec![];
    }
    let k = 2.0 / (period as f64 + 1.0);
    let mut out = vec![values[0]];
    for v in values.iter().skip(1) {
        let prev = *out.last().unwrap();
        out.push(v * k + prev * (1.0 - k));
    }
    out
}

fn rsi_14(closes: &[f64], index: usize) -> f64 {
    if index < 14 || closes.len() <= index {
        return 50.0;
    }
    let mut gains = 0.0;
    let mut losses = 0.0;
    for i in (index - 13)..=index {
        let delta = closes[i] - closes[i - 1];
        if delta >= 0.0 {
            gains += delta;
        } else {
            losses -= delta;
        }
    }
    if losses < 1e-12 {
        return 100.0;
    }
    let rs = gains / losses;
    100.0 - (100.0 / (1.0 + rs))
}

fn atr_pct_14(bars: &[RawBar], index: usize) -> f64 {
    if index == 0 || bars.len() <= index {
        return 0.0;
    }
    let len = 14.min(index + 1);
    let start = index + 1 - len;
    let mut trs = Vec::with_capacity(len);
    for i in start..=index {
        let tr = if i == 0 {
            bars[i].high - bars[i].low
        } else {
            let prev_close = bars[i - 1].close;
            (bars[i].high - bars[i].low)
                .max((bars[i].high - prev_close).abs())
                .max((bars[i].low - prev_close).abs())
        };
        trs.push(tr);
    }
    let atr = trs.iter().sum::<f64>() / trs.len() as f64;
    let close = bars[index].close.max(1e-12);
    (atr / close) * 100.0
}

fn ema_distance_pct(closes: &[f64], index: usize, period: usize) -> f64 {
    if closes.is_empty() || index >= closes.len() {
        return 0.0;
    }
    let ema = ema_series(closes, period);
    let close = closes[index].max(1e-12);
    ((closes[index] - ema[index]) / close) * 100.0
}

/// Transform raw OHLCV series into blindfolded bars (closed candles only at index t).
pub fn blindfold_bars(raw: &[RawBar], bar_hours: u32) -> Vec<BlindfoldedBar> {
    if raw.is_empty() {
        return vec![];
    }
    let close_0 = raw[0].close;
    let volumes: Vec<f64> = raw.iter().map(|b| b.volume).collect();
    let closes: Vec<f64> = raw.iter().map(|b| b.close).collect();

    raw.iter()
        .enumerate()
        .map(|(i, bar)| BlindfoldedBar {
            offset: temporal_offset(i, bar_hours),
            open: round_price(index_price(bar.open, close_0)),
            high: round_price(index_price(bar.high, close_0)),
            low: round_price(index_price(bar.low, close_0)),
            close: round_price(index_price(bar.close, close_0)),
            rel_volume: round_indicator(relative_volume(&volumes, i)),
            rsi_14: round_indicator(rsi_14(&closes, i)),
            atr_pct_14: round_indicator(atr_pct_14(raw, i)),
            ema_fast_dist_pct: round_indicator(ema_distance_pct(&closes, i, 8)),
            ema_slow_dist_pct: round_indicator(ema_distance_pct(&closes, i, 21)),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scale_invariance_indexed_prices() {
        let base = vec![
            RawBar {
                open: 100.0,
                high: 105.0,
                low: 98.0,
                close: 102.0,
                volume: 1000.0,
            },
            RawBar {
                open: 102.0,
                high: 108.0,
                low: 101.0,
                close: 106.0,
                volume: 1200.0,
            },
        ];
        let k = 3.7;
        let scaled: Vec<RawBar> = base
            .iter()
            .map(|b| RawBar {
                open: b.open * k,
                high: b.high * k,
                low: b.low * k,
                close: b.close * k,
                volume: b.volume,
            })
            .collect();

        let bf = blindfold_bars(&base, 4);
        let sf = blindfold_bars(&scaled, 4);
        assert_eq!(bf.len(), sf.len());
        for (a, b) in bf.iter().zip(sf.iter()) {
            assert_eq!(a.open, b.open);
            assert_eq!(a.high, b.high);
            assert_eq!(a.low, b.low);
            assert_eq!(a.close, b.close);
            assert_eq!(a.rsi_14, b.rsi_14);
            assert_eq!(a.atr_pct_14, b.atr_pct_14);
        }
    }

    #[test]
    fn precision_formatting() {
        let bars = vec![RawBar {
            open: 123.4567,
            high: 127.8912,
            low: 122.3344,
            close: 125.6789,
            volume: 500.0,
        }];
        let out = blindfold_bars(&bars, 4);
        assert_eq!(out[0].open, 98.23);
        assert!(out[0].rsi_14.fract().abs() < 1e-9 || (out[0].rsi_14 * 10.0).fract().abs() < 1e-9);
    }
}
