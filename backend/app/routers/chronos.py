"""Chronos API — normalize / tokenize substrate (paper research only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth import require_user
from backend.app.chronos.bsq import BinarySphericalQuantizer, LATENT_DIM
from backend.app.chronos.charts import build_chronos_charts, matplotlib_available
from backend.app.chronos.deps import chronos_deps_status
from backend.app.chronos.indicators import compute_indicator_context, indicators_available
from backend.app.chronos.normalize import ChronosNormalizer, OHLCVA_DIM
from backend.app.chronos.pipeline import tokenize_ohlcva, tokenize_result_to_dict
from backend.app.chronos.plot_prediction import build_prediction_charts
from backend.app.chronos.predictor import ChronosPredictor
from backend.app.chronos.vectorbt_eval import simple_momentum_backtest_summary, vectorbt_available

router = APIRouter(prefix="/api/v1/chronos", tags=["chronos"])


class OhlcvaWindowRequest(BaseModel):
    """Lookback-only OHLCVA matrix — do not include forecast horizon rows."""

    bars: list[list[float]] = Field(
        ...,
        description="List of [open, high, low, close, volume, amount] rows (lookback only)",
        min_length=2,
        max_length=4096,
    )
    eps: float = Field(default=1e-6, gt=0, le=1e-2)
    clip_val: float = Field(default=5.0, gt=0, le=20.0)


class BsqEncodeRequest(BaseModel):
    z: list[float] = Field(..., min_length=LATENT_DIM, max_length=LATENT_DIM)


class BsqDecodeRequest(BaseModel):
    s1_id: int = Field(..., ge=0, le=1023)
    s2_id: int = Field(..., ge=0, le=1023)


class ChronosChartsRequest(OhlcvaWindowRequest):
    include_tokens: bool = Field(
        default=True,
        description="If true, also render coarse/fine token series + histograms",
    )


class ChronosPredictRequest(OhlcvaWindowRequest):
    pred_len: int = Field(default=32, ge=1, le=512)
    temperature: float = Field(default=1.0, gt=0, le=5.0, alias="T")
    top_p: float = Field(default=0.9, gt=0, le=1.0)
    sample_count: int = Field(default=1, ge=1, le=64)
    include_volume: bool = True
    monte_carlo: bool = Field(
        default=False,
        description="If true (or sample_count>1), render MC mean + uncertainty band",
    )
    mc_samples: int = Field(
        default=30,
        ge=2,
        le=64,
        description="Monte Carlo path count when monte_carlo is true",
    )
    pattern_bias: str | None = Field(
        default=None,
        description="Optional blind-pattern bias from RNA: bullish, bearish, or neutral.",
    )
    pattern_confidence: float | None = Field(
        default=None,
        description="Optional blind-pattern confidence from RNA (0..100).",
        ge=0.0,
        le=100.0,
    )

    model_config = {"populate_by_name": True}


def _validate_bars(bars: list[list[float]]) -> None:
    for i, row in enumerate(bars):
        if len(row) != OHLCVA_DIM:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_ohlcva",
                    "message": f"row {i}: expected {OHLCVA_DIM} floats (OHLCVA), got {len(row)}",
                },
            )


CHRONOS_PIPELINE_STATUS = "Phase-1 substrate ready — awaiting lookback tokenize."


@router.get("/status")
async def chronos_status(_user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    deps = chronos_deps_status()
    return {
        "agent": "chronos",
        "paper_only": True,
        "live_trading": False,
        "phase": 1,
        "pipeline_status": CHRONOS_PIPELINE_STATUS,
        "encoder": "stub_linear_v1",
        "latent_dim": LATENT_DIM,
        "vocab": {"coarse": 1024, "fine": 1024, "full_bits": 20},
        "features": ["open", "high", "low", "close", "volume", "amount"],
        "normalization": {"type": "causal_zscore", "ddof": 0, "clip": 5.0, "eps": 1e-6},
        "matplotlib_available": matplotlib_available(),
        "deps": deps,
        "indicators_available": indicators_available(),
        "vectorbt_available": vectorbt_available(),
        "endpoints": {
            "normalize": "POST /api/v1/chronos/normalize",
            "tokenize": "POST /api/v1/chronos/tokenize",
            "charts": "POST /api/v1/chronos/charts",
            "predict": "POST /api/v1/chronos/predict",
            "indicators": "POST /api/v1/chronos/indicators",
            "research_backtest": "POST /api/v1/chronos/research/backtest",
            "bsq_encode": "POST /api/v1/chronos/bsq/encode",
            "bsq_decode": "POST /api/v1/chronos/bsq/decode",
        },
        "note": "Raw signals only — never auto-routes to /api/v1/trade/execute",
        "predict_output": "OHLCVA rows (KronosPredictor-style DataFrame columns)",
    }


@router.post("/normalize")
async def chronos_normalize(
    body: OhlcvaWindowRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    _validate_bars(body.bars)
    try:
        result = ChronosNormalizer(eps=body.eps, clip_val=body.clip_val).normalize_window(body.bars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "normalize_error", "message": str(exc)}) from exc
    return {
        "paper_only": True,
        "lookback": result.lookback,
        "feature_order": list(result.feature_order),
        "mean": result.mean,
        "std": result.std,
        "x_norm": result.x_norm,
    }


@router.post("/tokenize")
async def chronos_tokenize(
    body: OhlcvaWindowRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    _validate_bars(body.bars)
    try:
        result = tokenize_ohlcva(body.bars, eps=body.eps, clip_val=body.clip_val)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "tokenize_error", "message": str(exc)}) from exc
    return tokenize_result_to_dict(result)


@router.post("/charts")
async def chronos_charts(
    body: ChronosChartsRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Render matplotlib PNG charts (base64 data-URLs) for the lookback window."""
    if not matplotlib_available():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "matplotlib_missing",
                "message": 'Install optional deps: pip install -e ".[chronos]"',
            },
        )
    _validate_bars(body.bars)
    try:
        return build_chronos_charts(
            body.bars,
            eps=body.eps,
            clip_val=body.clip_val,
            include_tokens=body.include_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "charts_error", "message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "matplotlib_error", "message": str(exc)},
        ) from exc


@router.post("/predict")
async def chronos_predict(
    body: ChronosPredictRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Kronos-style forecast: OHLCVA pred rows + matplotlib Ground Truth / Prediction charts."""
    _validate_bars(body.bars)
    predictor = ChronosPredictor(eps=body.eps, clip_val=body.clip_val)
    want_mc = body.monte_carlo or body.sample_count > 1
    try:
        if want_mc:
            mc_n = max(body.sample_count, body.mc_samples)
            result, paths = predictor.predict_paths(
                body.bars,
                pred_len=body.pred_len,
                temperature=body.temperature,
                top_p=body.top_p,
                sample_count=mc_n,
            )
        else:
            result = predictor.predict(
                body.bars,
                pred_len=body.pred_len,
                temperature=body.temperature,
                top_p=body.top_p,
                sample_count=body.sample_count,
            )
            paths = None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "predict_error", "message": str(exc)}) from exc

    payload = result.to_dict()
    # Pattern → Chronos Confluence (paper research only).
    # Compare RNA blind bias vs forecast direction derived from predicted vs last-history close.
    if body.pattern_bias:
        pb = body.pattern_bias.lower().strip()
        if pb in {"bullish", "bearish", "neutral"}:
            try:
                last_hist_close = result.history_rows[-1]["close"] if result.history_rows else None
                last_pred_close = result.pred_rows[-1]["close"] if result.pred_rows else None
                pattern_conf = body.pattern_confidence if body.pattern_confidence is not None else 50.0

                forecast_bias = "neutral"
                if last_hist_close is not None and last_pred_close is not None and last_hist_close != 0:
                    delta_pct = (last_pred_close - last_hist_close) / last_hist_close
                    if delta_pct > 0.002:
                        forecast_bias = "bullish"
                    elif delta_pct < -0.002:
                        forecast_bias = "bearish"

                agreement = forecast_bias == pb
                score = (pattern_conf / 100.0) if agreement else (1.0 - pattern_conf / 100.0)

                payload["pattern_confluence"] = {
                    "input_bias": pb,
                    "input_confidence": pattern_conf,
                    "forecast_bias": forecast_bias,
                    "agreement": agreement,
                    "score": score,
                }
            except Exception:
                # Best-effort only; forecasting charts must remain functional.
                payload["pattern_confluence"] = None
    payload["charts"] = {}
    if matplotlib_available():
        try:
            payload["charts"] = build_prediction_charts(
                result.history_rows,
                result.pred_rows,
                paths=paths,
                include_volume=body.include_volume,
            )
        except RuntimeError as exc:
            payload["chart_error"] = str(exc)
    else:
        payload["chart_error"] = "matplotlib not installed"
    return payload


@router.post("/indicators")
async def chronos_indicators(
    body: OhlcvaWindowRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """RSI / EMA distance / ATR% from numpy+pandas (PineTS optional via pinets CLI)."""
    if not indicators_available():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "chronos_indicators_missing",
                "message": 'Install optional deps: pip install -e ".[chronos]"',
            },
        )
    _validate_bars(body.bars)
    try:
        ctx = compute_indicator_context(body.bars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "indicators_error", "message": str(exc)}) from exc
    return {"paper_only": True, "indicators": ctx, "engine": "numpy_pandas"}


@router.post("/research/backtest")
async def chronos_research_backtest(
    body: OhlcvaWindowRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    """Paper-only vectorbt sanity metric on the lookback window (no live orders)."""
    if not vectorbt_available():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "vectorbt_missing",
                "message": 'Install optional deps: pip install -e ".[chronos]"',
            },
        )
    _validate_bars(body.bars)
    try:
        summary = simple_momentum_backtest_summary(body.bars)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "backtest_error", "message": str(exc)}) from exc
    return summary


@router.post("/bsq/encode")
async def chronos_bsq_encode(
    body: BsqEncodeRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    encoded = BinarySphericalQuantizer().encode(body.z)
    return {
        "s1_id": encoded.s1_id,
        "s2_id": encoded.s2_id,
        "bits": list(encoded.bits),
        "entropy_loss": encoded.entropy_loss,
        "paper_only": True,
    }


@router.post("/bsq/decode")
async def chronos_bsq_decode(
    body: BsqDecodeRequest,
    _user: dict[str, Any] = Depends(require_user),
) -> dict[str, Any]:
    try:
        z = BinarySphericalQuantizer().decode(body.s1_id, body.s2_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bsq_decode_error", "message": str(exc)}) from exc
    return {"z": z, "scale": 1.0 / (LATENT_DIM**0.5), "paper_only": True}
