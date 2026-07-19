"""Cached loaders for doctrine, slim Kraken index, and prompt shots."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).resolve().parent
SHOTS_DIR = PROMPTS_DIR / "prompt_shots"

MAX_SYSTEM_CHARS = 6_000
MAX_SHOTS = 3
MAX_SHOT_CHARS = 280
MAX_SHOTS_BLOCK = 1_000
MAX_DOCTRINE_CHARS = 3_500
MAX_INDEX_CHARS = 2_500

_LIVE_MARKERS = (
    "withdrawal",
    "cold-storage",
    "paper-to-live",
    "emergency-flatten",
    "funding-ops",
    "autonomy-levels",
)
_LIVE_EXACT = {
    "kraken-spot-execution",
    "kraken-futures-trading",
    "kraken-funding-ops",
}


def classify_skill_gate(skill_name: str) -> str:
    """Return paper_ok or live_gated for a skill id (no SKILL.md body)."""
    n = (skill_name or "").strip().lower().removeprefix("skill:").strip()
    if any(k in n for k in _LIVE_MARKERS) or n in _LIVE_EXACT:
        return "live_gated"
    return "paper_ok"


@lru_cache(maxsize=1)
def load_doctrine() -> str:
    path = PROMPTS_DIR / "orchestrator_doctrine.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def load_kraken_skill_index() -> str:
    path = PROMPTS_DIR / "kraken_broker_skill_index.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _format_shot(shot: dict[str, Any]) -> str:
    expected = str(shot.get("expected") or "HANDOFF")
    scenario = _clip(str(shot.get("scenario") or ""), 120)
    kraken = _clip(str(shot.get("kraken") or ""), 80)
    directives = shot.get("directives") if isinstance(shot.get("directives"), dict) else {}
    bits = [f"{k}:{_clip(str(v), 40)}" for k, v in list(directives.items())[:4]]
    line = f"[{expected}] {scenario} | {'; '.join(bits)} | {kraken}"
    return _clip(line, MAX_SHOT_CHARS)


def load_prompt_shots(
    mode: str = "orchestrator",
    *,
    max_shots: int = MAX_SHOTS,
    budget_chars: int = MAX_SHOTS_BLOCK,
) -> tuple[str, list[str]]:
    """Load curated shots; return (formatted block, shot_ids)."""
    del mode  # reserved for future per-mode filtering
    if not SHOTS_DIR.is_dir():
        return "", []

    shots: list[dict[str, Any]] = []
    for path in sorted(SHOTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            data.setdefault("id", path.stem)
            shots.append(data)

    # Prefer one swarm + one paper DELEGATE + one live REFUSE when present.
    preferred = ("swarm_handoff", "kraken_paper_delegate", "kraken_live_refuse")
    by_id = {str(s.get("id")): s for s in shots}
    ordered = [by_id[i] for i in preferred if i in by_id]
    for shot in shots:
        if shot not in ordered:
            ordered.append(shot)

    lines: list[str] = []
    ids: list[str] = []
    used = 0
    for shot in ordered[: max(1, max_shots)]:
        line = _format_shot(shot)
        if used + len(line) + 1 > budget_chars:
            break
        lines.append(line)
        ids.append(str(shot.get("id") or "shot"))
        used += len(line) + 1

    if not lines:
        return "", []
    block = "PROMPT SHOTS (few-shot; do not expand):\n" + "\n".join(lines)
    return _clip(block, budget_chars), ids


def build_orchestrator_system(
    *,
    include_index: bool = True,
    max_chars: int = MAX_SYSTEM_CHARS,
    channel: str = "orchestrate",
) -> tuple[str, list[str]]:
    """Compose systemInstruction under budget. Returns (text, shot_ids)."""
    doctrine = _clip(load_doctrine(), MAX_DOCTRINE_CHARS)
    shots_block, shot_ids = load_prompt_shots(budget_chars=MAX_SHOTS_BLOCK)

    parts = [
        "You are Neo Fabel MASTER ORCHESTRATOR. Paper trading only.",
        doctrine,
        shots_block,
    ]
    if channel == "orchestrate":
        parts.append(
            "Return JSON keys: planTitle, summary, subAgentDirectives "
            "(marketData, adaptiveAgent, rnaSmartelligent, riskGovernor, "
            "krakenBroker, predictive, analytic, orchestrator), "
            "resourceAllocation (array of {name, value} ~100), suggestedRules (string array)."
        )
    else:
        parts.append(
            "Reply as the coordinator using CONCLUSION/QUESTION/BLOCKED/HANDOFF. "
            "Name Kraken skills as skill:kraken-* or skill:recipe-* only — never paste skill bodies."
        )

    body = "\n\n".join(p for p in parts if p).strip()
    remaining = max_chars - len(body) - 80
    if include_index and remaining > 200:
        index = _clip(load_kraken_skill_index(), min(MAX_INDEX_CHARS, remaining))
        if index:
            body = f"{body}\n\nKRAKEN SKILL INDEX (slim):\n{index}"

    return _clip(body, max_chars), shot_ids


def skill_names_in_text(text: str) -> list[str]:
    return re.findall(r"(?:skill:\s*)?((?:kraken|recipe)-[a-z0-9-]+)", text or "", flags=re.I)
