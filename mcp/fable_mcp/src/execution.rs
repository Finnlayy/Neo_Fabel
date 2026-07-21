//! Next-bar open (t+1) execution engine with friction and SL-priority dual-breach.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PositionSide {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionConfig {
    pub commission_bps: f64,
    pub slippage_bps: f64,
}

impl Default for ExecutionConfig {
    fn default() -> Self {
        Self {
            commission_bps: 5.0,
            slippage_bps: 2.0,
        }
    }
}

impl ExecutionConfig {
    pub fn friction_bps(&self) -> f64 {
        self.commission_bps + self.slippage_bps
    }

    pub fn buy_fill(&self, open: f64) -> f64 {
        open * (1.0 + self.friction_bps() / 10_000.0)
    }

    pub fn sell_fill(&self, open: f64) -> f64 {
        open * (1.0 - self.friction_bps() / 10_000.0)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NextBar {
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingSignal {
    pub side: PositionSide,
    pub volume: f64,
    pub stop_loss: Option<f64>,
    pub take_profit: Option<f64>,
    pub rationale: String,
    #[serde(default = "default_pair")]
    pub pair: String,
}

fn default_pair() -> String {
    std::env::var("FABLE_MCP_DEFAULT_PAIR").unwrap_or_else(|_| "ADAUSD".into())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenPosition {
    pub side: PositionSide,
    pub volume: f64,
    pub entry_price: f64,
    pub stop_loss: Option<f64>,
    pub take_profit: Option<f64>,
    pub rationale: String,
    #[serde(default = "default_pair")]
    pub pair: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FillEvent {
    pub event: String,
    pub side: PositionSide,
    pub price: f64,
    pub volume: f64,
    pub pnl: Option<f64>,
    pub rationale: String,
    #[serde(default = "default_pair")]
    pub pair: String,
}

#[derive(Debug, Default)]
pub struct ExecutionEngine {
    pub config: ExecutionConfig,
    pub balance_usd: f64,
    pending: VecDeque<PendingSignal>,
    pub position: Option<OpenPosition>,
    pub fills: Vec<FillEvent>,
    bar_index: u64,
}

impl ExecutionEngine {
    pub fn new(starting_balance: f64, config: ExecutionConfig) -> Self {
        Self {
            config,
            balance_usd: starting_balance,
            ..Default::default()
        }
    }

    /// Queue a signal at bar t (executes at next bar open).
    pub fn queue_signal(&mut self, signal: PendingSignal) {
        self.pending.push_back(signal);
    }

    /// Process bar t+1: fill queued signals at open, then evaluate SL/TP on the same bar.
    pub fn process_next_bar_open(&mut self, bar: &NextBar) -> Vec<FillEvent> {
        self.bar_index += 1;
        let mut events = Vec::new();

        if let Some(sig) = self.pending.pop_front() {
            let fill_price = match sig.side {
                PositionSide::Buy => self.config.buy_fill(bar.open),
                PositionSide::Sell => self.config.sell_fill(bar.open),
            };
            let event = FillEvent {
                event: "entry".into(),
                side: sig.side,
                price: fill_price,
                volume: sig.volume,
                pnl: None,
                rationale: sig.rationale.clone(),
                pair: sig.pair.clone(),
            };
            self.fills.push(event.clone());
            events.push(event);

            self.position = Some(OpenPosition {
                side: sig.side,
                volume: sig.volume,
                entry_price: fill_price,
                stop_loss: sig.stop_loss,
                take_profit: sig.take_profit,
                rationale: sig.rationale,
                pair: sig.pair,
            });
        }

        if let Some(pos) = self.position.clone() {
            if let Some(exit) = self.check_exit(&pos, bar) {
                self.apply_exit(&pos, exit, &mut events);
            }
        }

        events
    }

    fn check_exit(&self, pos: &OpenPosition, bar: &NextBar) -> Option<ExitReason> {
        let (sl_hit, tp_hit) = match pos.side {
            PositionSide::Buy => (
                pos.stop_loss.map(|sl| bar.low <= sl).unwrap_or(false),
                pos.take_profit.map(|tp| bar.high >= tp).unwrap_or(false),
            ),
            PositionSide::Sell => (
                pos.stop_loss.map(|sl| bar.high >= sl).unwrap_or(false),
                pos.take_profit.map(|tp| bar.low <= tp).unwrap_or(false),
            ),
        };

        // Dual-breach: stop-loss has priority over take-profit.
        if sl_hit {
            return Some(ExitReason::StopLoss);
        }
        if tp_hit {
            return Some(ExitReason::TakeProfit);
        }
        None
    }

    fn apply_exit(&mut self, pos: &OpenPosition, reason: ExitReason, events: &mut Vec<FillEvent>) {
        let exit_price = match (pos.side, reason) {
            (PositionSide::Buy, ExitReason::StopLoss) => pos.stop_loss.unwrap(),
            (PositionSide::Buy, ExitReason::TakeProfit) => pos.take_profit.unwrap(),
            (PositionSide::Sell, ExitReason::StopLoss) => pos.stop_loss.unwrap(),
            (PositionSide::Sell, ExitReason::TakeProfit) => pos.take_profit.unwrap(),
        };

        let pnl = match pos.side {
            PositionSide::Buy => (exit_price - pos.entry_price) * pos.volume,
            PositionSide::Sell => (pos.entry_price - exit_price) * pos.volume,
        };
        self.balance_usd += pnl;

        let event = FillEvent {
            event: match reason {
                ExitReason::StopLoss => "stop_loss",
                ExitReason::TakeProfit => "take_profit",
            }
            .into(),
            side: pos.side,
            price: exit_price,
            volume: pos.volume,
            pnl: Some(pnl),
            rationale: pos.rationale.clone(),
            pair: pos.pair.clone(),
        };
        self.fills.push(event.clone());
        events.push(event);
        self.position = None;
    }
}

#[derive(Debug, Clone, Copy)]
enum ExitReason {
    StopLoss,
    TakeProfit,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn friction_directionality() {
        let cfg = ExecutionConfig {
            commission_bps: 5.0,
            slippage_bps: 2.0,
        };
        let open = 100.0;
        assert!(cfg.buy_fill(open) > open);
        assert!(cfg.sell_fill(open) < open);
        assert!((cfg.buy_fill(open) - 100.07).abs() < 1e-9);
        assert!((cfg.sell_fill(open) - 99.93).abs() < 1e-9);
    }

    #[test]
    fn sl_priority_dual_breach_long() {
        let mut eng = ExecutionEngine::new(10_000.0, ExecutionConfig::default());
        eng.queue_signal(PendingSignal {
            side: PositionSide::Buy,
            volume: 1.0,
            stop_loss: Some(98.0),
            take_profit: Some(105.0),
            rationale: "test long".into(),
            pair: "ADAUSD".into(),
        });
        // Entry at t+1 open
        eng.process_next_bar_open(&NextBar {
            open: 100.0,
            high: 100.5,
            low: 99.5,
            close: 100.2,
        });
        assert!(eng.position.is_some());

        // Dual breach on same bar: low <= SL AND high >= TP → SL wins (loss).
        let events = eng.process_next_bar_open(&NextBar {
            open: 101.0,
            high: 106.0,
            low: 97.0,
            close: 102.0,
        });
        assert!(eng.position.is_none());
        let exit = events
            .iter()
            .find(|e| e.event == "stop_loss")
            .expect("stop_loss event");
        assert!(exit.pnl.unwrap_or(0.0) < 0.0);
        assert!(
            events.iter().all(|e| e.event != "take_profit"),
            "TP must not fire when SL dual-breaches"
        );
    }

    #[test]
    fn entry_fills_at_next_bar_open_with_friction() {
        let mut eng = ExecutionEngine::new(10_000.0, ExecutionConfig::default());
        eng.queue_signal(PendingSignal {
            side: PositionSide::Buy,
            volume: 2.0,
            stop_loss: None,
            take_profit: None,
            rationale: "entry".into(),
            pair: "ADAUSD".into(),
        });
        let events = eng.process_next_bar_open(&NextBar {
            open: 50.0,
            high: 51.0,
            low: 49.0,
            close: 50.5,
        });
        assert_eq!(events.len(), 1);
        assert!(events[0].price > 50.0);
        assert_eq!(eng.position.as_ref().unwrap().entry_price, events[0].price);
    }
}
