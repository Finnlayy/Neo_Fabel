"""Static and runtime paper-only assertions for the signal feature."""

from __future__ import annotations

import ast
from pathlib import Path

from ..settings import Settings
from ..trading.autonomy import AutonomyLevel

FORBIDDEN_NAMES = frozenset({"Level4Session", "execute_order", "place_order"})
SIGNALS_ROOT = Path(__file__).resolve().parent


class SignalSafetyError(RuntimeError):
    pass


def assert_signal_paper_only(settings: Settings) -> None:
    """Fail worker/API composition when live trading capabilities are present."""
    if settings.kraken_live_trading_enabled:
        raise SignalSafetyError("signal worker refuses live trading flag")
    if settings.trade_commands_enabled:
        raise SignalSafetyError("signal worker refuses trade commands")
    if settings.autonomy not in {AutonomyLevel.READ_ONLY, AutonomyLevel.PAPER}:
        # Allow level 1–2 only; paper is level 2.
        if int(settings.autonomy) > int(AutonomyLevel.PAPER):
            raise SignalSafetyError("signal worker requires autonomy <= paper (2)")
    if settings.signal_execution_enabled and settings.autonomy != AutonomyLevel.PAPER:
        raise SignalSafetyError("signal execution requires autonomy level paper (2)")


def assert_signals_module_imports() -> None:
    """Scan signal package AST so tests fail if live Kraken symbols are referenced."""
    offenders: list[str] = []
    for path in SIGNALS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
                offenders.append(f"{path.name}:{node.lineno}:{node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
                offenders.append(f"{path.name}:{node.lineno}:{node.attr}")
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in FORBIDDEN_NAMES:
                        offenders.append(f"{path.name}:import:{alias.name}")
    if offenders:
        raise SignalSafetyError(f"forbidden live symbols in signals package: {', '.join(offenders)}")
