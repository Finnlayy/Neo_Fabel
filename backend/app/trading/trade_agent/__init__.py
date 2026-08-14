"""Neo Trade Agent — scheduled + event-driven runtime (paper-first).

Adapted from Fable5 TradeAgent patterns:
- multi-slot market scans
- background loop with market-hours awareness
- ML trade labeling schedule
- overnight optimizer kick
- status / positions checks

Live order placement stays behind existing Level-4 / LIVE_ALGO gates.
"""

from __future__ import annotations

from backend.app.trading.trade_agent.runtime import trade_agent

__all__ = ["trade_agent"]
