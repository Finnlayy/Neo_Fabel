"""TradingView / MCP signal ingress — paper-only by design."""

from .safety import assert_signal_paper_only, assert_signals_module_imports

__all__ = ["assert_signal_paper_only", "assert_signals_module_imports"]
