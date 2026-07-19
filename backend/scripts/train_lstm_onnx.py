"""CLI: train flatten→Gemm ONNX proxy on synthetic (or provided) OHLC windows.

Usage (from repo root, with onnx extra installed):
  python -m backend.scripts.train_lstm_onnx --model model4 --symbol BTCUSD
"""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train Neo Fabel ONNX proxy model")
    parser.add_argument("--model", default="model4", help="model | model2 | model4")
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=400)
    args = parser.parse_args(argv)

    try:
        from backend.app.integrations.onnx.runtime import onnx_deps_available
        from backend.app.integrations.onnx.train import train_and_export
    except ImportError as exc:
        print(f"Import error: {exc}", file=sys.stderr)
        return 1

    if not onnx_deps_available():
        print('Missing deps. Install: pip install -e ".[onnx]"', file=sys.stderr)
        return 1

    meta = train_and_export(
        model_id=args.model,
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
        source="cli_synthetic",
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
