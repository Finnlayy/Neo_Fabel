"""RNA pattern context for Fable Engine."""

from decimal import Decimal

from backend.app.signals.rna_context import clear_rna_context, get_rna_context, set_rna_context


def test_rna_context_roundtrip() -> None:
    clear_rna_context()
    assert get_rna_context() is None
    ctx = set_rna_context(bias="bullish", confidence=Decimal("72.5"), symbol="BTC")
    assert get_rna_context() == ctx
    assert ctx.bias == "bullish"
    clear_rna_context()
