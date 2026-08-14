"""Optional Chronos stack — detect numpy/pandas/torch/vectorbt/pinets-cli at runtime."""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any


def _importable(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def pinets_cli_available() -> bool:
    """PineTS CLI (`pinets run …`) — npm global or npx; not a Python wheel."""
    return shutil.which("pinets") is not None


def chronos_deps_status() -> dict[str, Any]:
    torch_ok = _importable("torch")
    vbt_ok = _importable("vectorbt")
    return {
        "numpy": _importable("numpy"),
        "pandas": _importable("pandas"),
        "matplotlib": _importable("matplotlib"),
        "torch": torch_ok,
        "vectorbt": vbt_ok,
        "pinets_cli": pinets_cli_available(),
        "research_ready": all(
            [
                _importable("numpy"),
                _importable("pandas"),
                torch_ok,
                vbt_ok,
            ]
        ),
        "install_hint": 'pip install -e ".[chronos]"',
        "pinets_hint": "npm install -g pinets-cli  (or: npx pinets-cli run …)",
    }


def require_numpy() -> None:
    if not _importable("numpy"):
        raise RuntimeError('numpy required: pip install -e ".[chronos]"')


def require_pandas() -> None:
    if not _importable("pandas"):
        raise RuntimeError('pandas required: pip install -e ".[chronos]"')


def require_torch() -> None:
    if not _importable("torch"):
        raise RuntimeError('torch required: pip install -e ".[chronos]"')


def require_vectorbt() -> None:
    if not _importable("vectorbt"):
        raise RuntimeError('vectorbt required: pip install -e ".[chronos]"')
