"""Trade feedback package — rationales + idle error/feedback engine."""

from backend.app.trading.feedback.engine import feedback_engine
from backend.app.trading.feedback.rationale import format_trade_rationale, rationale_from_fill_row

__all__ = ["feedback_engine", "format_trade_rationale", "rationale_from_fill_row"]
