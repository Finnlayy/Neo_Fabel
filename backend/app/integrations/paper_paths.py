"""Paper ledger persistence under backend/data/paper."""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PAPER_DATA_DIR = BACKEND_ROOT / "data" / "paper"
LEDGER_FILE = PAPER_DATA_DIR / "ledger.json"


def ensure_paper_data_dir() -> Path:
    PAPER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return PAPER_DATA_DIR


def ledger_path() -> Path:
    ensure_paper_data_dir()
    return LEDGER_FILE
