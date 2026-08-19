"""Generate slim Kraken skill index from local plugin cache."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(
    r"C:\Users\finnp\.cursor\plugins\cache\cursor-public\kraken-cli"
    r"\aa32814cea70913a70c9909693a7abd762963e83\skills"
)
OUT = Path(__file__).resolve().parents[1] / "app" / "ai_prompts" / "kraken_broker_skill_index.md"

LIVE_MARKERS = (
    "withdrawal",
    "cold-storage",
    "paper-to-live",
    "emergency-flatten",
    "funding-ops",
    "autonomy-levels",
)
LIVE_EXACT = {
    "kraken-spot-execution",
    "kraken-futures-trading",
    "kraken-funding-ops",
}


def domain(name: str) -> str:
    if name.startswith("recipe-"):
        if "paper" in name or "backtest" in name:
            return "paper"
        if "earn" in name:
            return "earn"
        if any(x in name for x in ("emergency", "drawdown", "fee-tier")):
            return "risk"
        if any(x in name for x in ("basis", "funding", "futures", "hedge")):
            return "futures"
        if any(
            x in name
            for x in (
                "dca",
                "grid",
                "trailing",
                "rebalance",
                "orderbook",
                "breakout",
                "price-level",
            )
        ):
            return "spot"
        return "recipes"
    if "paper" in name:
        return "paper"
    if "earn" in name:
        return "earn"
    if any(x in name for x in ("futures", "basis", "funding", "liquidation")):
        return "futures"
    if any(x in name for x in ("risk", "autonomy", "alert", "error", "fee", "rate-limit")):
        return "risk"
    if any(
        x in name
        for x in (
            "spot",
            "order",
            "stop",
            "twap",
            "dca",
            "grid",
            "multi-pair",
            "rebalanc",
        )
    ):
        return "spot"
    return "platform"


def gate(name: str) -> str:
    n = name.lower()
    if any(k in n for k in LIVE_MARKERS) or n in LIVE_EXACT:
        return "live_gated"
    return "paper_ok"


def description(text: str) -> str:
    m = re.search(r"^description:\s*[\"']?(.*?)[\"']?\s*$", text, re.MULTILINE)
    if m:
        desc = m.group(1).strip().strip('"').strip("'")
    else:
        m2 = re.search(r"^description:\s*>-?\s*\n((?:\s+.+\n)+)", text, re.MULTILINE)
        desc = " ".join(m2.group(1).split()) if m2 else "Kraken CLI skill"
    if len(desc) > 90:
        desc = desc[:87] + "..."
    return desc


def main() -> None:
    by: dict[str, list[str]] = {
        k: [] for k in ("paper", "spot", "futures", "risk", "earn", "recipes", "platform")
    }
    if not ROOT.is_dir():
        raise SystemExit(f"skill root missing: {ROOT}")

    for d in sorted(ROOT.iterdir()):
        if not d.is_dir():
            continue
        skill = d / "SKILL.md"
        if not skill.exists():
            continue
        text = skill.read_text(encoding="utf-8", errors="replace")
        name = d.name
        by[domain(name)].append(f"- `{name}` — {description(text)} — {gate(name)}")

    lines = [
        "# Kraken broker skill index (slim)",
        "",
        "Format: `name — description — paper_ok|live_gated`",
        "",
    ]
    for sec in ("paper", "spot", "futures", "risk", "earn", "recipes", "platform"):
        lines.append(f"## {sec}")
        lines.extend(by[sec] or ["- (none)"])
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines)
    OUT.write_text(body, encoding="utf-8")
    count = sum(len(v) for v in by.values())
    print(f"wrote {OUT} chars={len(body)} skills={count}")


if __name__ == "__main__":
    main()
