"""Strategy and engine configuration (pure pydantic; no IO)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StrategyConfig(BaseModel):
    """Per-strategy bot config (Pionex-analog Grid / DCA)."""

    strategy_id: str
    kind: Literal["grid", "dca"]
    pair: str = "BTCUSD"
    enabled: bool = True
    # Grid
    range_low: float | None = None
    range_high: float | None = None
    grid_count: int = Field(default=5, ge=2, le=50)
    volume_per_zone: Decimal = Field(default=Decimal("0.001"))
    # DCA
    reference_price: float | None = None
    drawdown_steps_pct: list[float] = Field(default_factory=lambda: [2.0, 4.0, 8.0])
    dca_volume: Decimal = Field(default=Decimal("0.001"))
    take_profit_pct: float = Field(default=1.5, gt=0)

    @model_validator(mode="after")
    def _validate_grid_range(self) -> StrategyConfig:
        if self.kind == "grid":
            if self.range_low is None or self.range_high is None:
                raise ValueError("grid strategy requires range_low and range_high")
            if self.range_high <= self.range_low:
                raise ValueError("range_high must be > range_low")
        return self


class EngineSettings(BaseModel):
    """Runtime knobs for FableEngine (subset mirrored from app Settings)."""

    enabled: bool = False
    dry_run: bool = True
    poll_seconds: float = Field(default=10.0, gt=0)
    market_rpm: float = Field(default=30.0, gt=0)
    onnx_bias: Literal["off", "filter", "scale"] = "off"
    strategies: list[StrategyConfig] = Field(default_factory=list)
