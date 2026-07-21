//! Prompt snapshot builder — aggregates blindfold bars, patterns, ONNX, RNA, rationale.

use serde::{Deserialize, Serialize};

use crate::blindfold::{blindfold_bars, BlindfoldedBar, RawBar};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PatternHit {
    pub name: String,
    pub bias: String,
    pub confidence: f64,
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct RnaContext {
    pub bias: String,
    pub confidence: f64,
    pub symbol: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct OnnxScore {
    pub direction: String,
    pub confidence: f64,
    pub prediction: f64,
    pub model_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PromptSnapshot {
    pub bars: Vec<BlindfoldedBar>,
    pub patterns: Vec<PatternHit>,
    pub rna: Option<RnaContext>,
    pub onnx: Option<OnnxScore>,
    pub rationale_tail: Vec<String>,
    pub summary: String,
}

pub struct PromptBuilder {
    bar_hours: u32,
}

impl Default for PromptBuilder {
    fn default() -> Self {
        Self { bar_hours: 4 }
    }
}

impl PromptBuilder {
    pub fn new(bar_hours: u32) -> Self {
        Self { bar_hours }
    }

    /// Build a blindfolded prompt snapshot from raw market context (Phase 1).
    pub fn build_prompt_snapshot(
        &self,
        raw_bars: &[RawBar],
        patterns: &[PatternHit],
        rna: Option<RnaContext>,
        onnx: Option<OnnxScore>,
        rationale_tail: &[String],
    ) -> PromptSnapshot {
        let bars = blindfold_bars(raw_bars, self.bar_hours);
        let summary = Self::compose_summary(&bars, patterns, rna.as_ref(), onnx.as_ref());
        PromptSnapshot {
            bars,
            patterns: patterns.to_vec(),
            rna,
            onnx,
            rationale_tail: rationale_tail.to_vec(),
            summary,
        }
    }

    fn compose_summary(
        bars: &[BlindfoldedBar],
        patterns: &[PatternHit],
        rna: Option<&RnaContext>,
        onnx: Option<&OnnxScore>,
    ) -> String {
        let last = bars.last();
        let pat = patterns
            .first()
            .map(|p| format!("{}({:.0}%)", p.name, p.confidence))
            .unwrap_or_else(|| "none".into());
        let rna_s = rna
            .map(|r| format!("{} {:.0}%", r.bias, r.confidence))
            .unwrap_or_else(|| "neutral".into());
        let onnx_s = onnx
            .map(|o| format!("{} {:.0}%", o.direction, o.confidence))
            .unwrap_or_else(|| "off".into());
        let close = last.map(|b| b.close).unwrap_or(0.0);
        format!(
            "blindfold close_idx={close:.2} pattern={pat} rna={rna_s} onnx={onnx_s}"
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::blindfold::RawBar;

    fn sample_bars() -> Vec<RawBar> {
        (0..20)
            .map(|i| {
                let base = 100.0 + i as f64 * 0.5;
                RawBar {
                    open: base,
                    high: base + 1.2,
                    low: base - 0.8,
                    close: base + 0.3,
                    volume: 1000.0 + i as f64 * 10.0,
                }
            })
            .collect()
    }

    #[test]
    fn scale_invariance_snapshot() {
        let builder = PromptBuilder::new(4);
        let raw = sample_bars();
        let k = 2.5;
        let scaled: Vec<RawBar> = raw
            .iter()
            .map(|b| RawBar {
                open: b.open * k,
                high: b.high * k,
                low: b.low * k,
                close: b.close * k,
                volume: b.volume,
            })
            .collect();

        let p1 = builder.build_prompt_snapshot(&raw, &[], None, None, &[]);
        let p2 = builder.build_prompt_snapshot(&scaled, &[], None, None, &[]);
        assert_eq!(p1.bars, p2.bars);
    }

    #[test]
    fn precision_formatting_in_snapshot() {
        let builder = PromptBuilder::default();
        let bars = vec![RawBar {
            open: 50.555,
            high: 51.999,
            low: 49.111,
            close: 51.333,
            volume: 800.0,
        }];
        let snap = builder.build_prompt_snapshot(&bars, &[], None, None, &[]);
        for bar in &snap.bars {
            assert_eq!(bar.open, (bar.open * 100.0).round() / 100.0);
            assert_eq!(bar.rsi_14, (bar.rsi_14 * 10.0).round() / 10.0);
        }
    }
}
