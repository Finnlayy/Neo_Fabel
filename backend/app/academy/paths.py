"""Academy persistence under backend/data/academy (cwd-independent)."""

from __future__ import annotations

from pathlib import Path

# backend/app/academy/paths.py → backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ACADEMY_DATA_DIR = BACKEND_ROOT / "data" / "academy"


def ensure_academy_data_dir() -> Path:
    ACADEMY_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return ACADEMY_DATA_DIR
