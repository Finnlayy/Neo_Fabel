"""Pydantic schemas for GA optimizer API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    population: int = Field(default=30, ge=2, le=200)
    generations: int = Field(default=50, ge=1, le=500)
    elite: int = Field(default=3, ge=1, le=50)
    mutation_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    mutation_strength: float = Field(default=0.40, ge=0.0, le=2.0)
    crossover_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    train_ratio: float = Field(default=0.70, gt=0.1, lt=0.95)
    max_symbols: int = Field(default=40, ge=0, le=500)
    lookback_bars: int = Field(default=600, ge=150, le=5000)
    fee_r: float = Field(default=0.03, ge=0.0, le=1.0)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    symbols: list[str] | None = Field(
        default=None,
        description="Optional explicit universe (e.g. ETHUSDT). Overrides volume ranking.",
    )
    market_source: Literal["ccxt", "cache", "binance_fapi"] | None = None


class OptimizeStartResponse(BaseModel):
    runId: str
    status: str


class ExportPineRequest(BaseModel):
    runId: str | None = None
    results: dict[str, Any] | None = None
    template_id: str = "eth_glintnews_pionex_v6"
    target_symbol: str = "ETH/USDT"
    limit: int = Field(default=3, ge=1, le=10)
    tf_high: str = "48"
    tf_mid: str = "12"
    tf_low: str = "3"


class GenomeModel(BaseModel):
    min_conf: int
    risk_pct: float
    sl_atr_mul: float
    tp_atr_mul: float
    vol_mult: float
    max_daily_move_pct: float
    ob_body_mult: float
    cisd_len: int
    w_trend: int
    w_cisd: int
    w_ob: int
    w_fvg: int
    w_vol: int
    allow_shorts: bool


class TopResultModel(BaseModel):
    genome: GenomeModel | dict[str, Any]
    fitness: float
    train: float
    forward: float
    gap: float
    symbol: str | None = None
