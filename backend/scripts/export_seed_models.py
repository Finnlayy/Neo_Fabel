"""Generate seed model.onnx / model2.onnx / model4.onnx under backend/data/onnx."""

from __future__ import annotations

import json
import sys


def main() -> int:
    from backend.app.integrations.onnx.runtime import ensure_seed_models, onnx_deps_available

    if not onnx_deps_available():
        print('Missing deps. Install: pip install -e ".[onnx]"', file=sys.stderr)
        return 1
    metas = ensure_seed_models()
    print(json.dumps(metas, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
