"""Optional PineTS (`pinets` CLI) bridge — run Pine Script indicators on OHLC JSON."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from backend.app.chronos.deps import pinets_cli_available
from backend.app.chronos.frame import bars_to_dataframe


def pinets_available() -> bool:
    return pinets_cli_available()


def _bars_to_pinets_json(bars: list[list[float]]) -> str:
    df = bars_to_dataframe(bars)
    # pinets-cli accepts candle JSON; use ISO-less index + OHLCV columns.
    records: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        records.append(
            {
                "time": int(i),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
        )
    return json.dumps(records)


def run_pinets_indicator(
    pine_path: str | Path,
    bars: list[list[float]],
    *,
    symbol: str = "BTCUSDT",
    timeframe: str = "60",
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Execute a .pine file via `pinets run` with local candle JSON."""
    if not pinets_available():
        raise RuntimeError("pinets CLI not on PATH — install: npm install -g pinets-cli")

    pine_path = Path(pine_path)
    if not pine_path.is_file():
        raise FileNotFoundError(str(pine_path))

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        tmp.write(_bars_to_pinets_json(bars))
        data_path = tmp.name

    try:
        proc = subprocess.run(
            [
                "pinets",
                "run",
                str(pine_path),
                "--data",
                data_path,
                "--symbol",
                symbol,
                "--timeframe",
                timeframe,
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    finally:
        Path(data_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "pinets run failed")

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pinets returned non-JSON: {proc.stdout[:200]}") from exc
