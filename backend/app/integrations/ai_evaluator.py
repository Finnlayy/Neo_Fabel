"""Concrete advisory provider adapter — gated behind human approval.

Until ADVISORY_PROVIDER is approved for production, use FakeSignalEvaluator.
This module exists so composition can swap in a real provider without touching
the signal worker pipeline.
"""

from __future__ import annotations

from ..settings import Settings
from ..signals.evaluator import EvaluationResult, FakeSignalEvaluator, SignalEvaluator


def build_evaluator(settings: Settings) -> SignalEvaluator:
    if settings.advisory_provider in {"", "fake", "deterministic-fake"}:
        return FakeSignalEvaluator(settings)
    # Production providers require explicit human approval before enablement.
    raise RuntimeError(
        f"advisory provider '{settings.advisory_provider}' is not approved; "
        "set ADVISORY_PROVIDER=fake or complete the provider review gate"
    )


__all__ = ["build_evaluator", "EvaluationResult", "SignalEvaluator"]
