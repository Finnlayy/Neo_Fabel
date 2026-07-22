#!/usr/bin/env python3
"""Prueft Pine-Skripte gegen die Regeln aus dem Pionex Pine Bot Skill."""

from __future__ import annotations

import argparse
from pathlib import Path


def run_checks(path: Path) -> int:
    code = path.read_text(encoding="utf-8")
    lines = code.splitlines()

    has_action = '"action"' in code or '\\"action\\"' in code
    has_contracts = '"contracts"' in code or '\\"contracts\\"' in code
    has_signal_type = '"signal_type"' in code or '\\"signal_type\\"' in code

    checks = {
        "Pine v6 Deklaration": code.startswith("//@version=6"),
        "indicator() statt strategy()": "indicator(" in code and "strategy(" not in code,
        "barstate.isconfirmed vorhanden": "barstate.isconfirmed" in code,
        "lookahead_off vorhanden": "lookahead=barmerge.lookahead_off" in code,
        "alert.freq_once_per_bar_close vorhanden": "alert.freq_once_per_bar_close" in code,
        "Pionex signal_type vorhanden": has_signal_type,
        "Pionex action vorhanden": has_action,
        "Pionex contracts vorhanden": has_contracts,
        "Keine Tabs": "\t" not in code,
        "Keine offensichtlichen Secrets": "api_key" not in code.lower() and "secret" not in code.lower(),
        "Klammern grob balanciert": code.count("(") == code.count(")"),
        "Zeilen unter 500": len(lines) < 500,
    }

    passed = sum(1 for ok in checks.values() if ok)
    print("=" * 58)
    print(f"REVIEW COMPLETE - {path.name}")
    print("=" * 58)
    for name, ok in checks.items():
        print(f"  {'OK' if ok else 'FAIL'}  {name}")
    print("-" * 58)
    print(f"  Zeilen gesamt:  {len(lines)}")
    print(f"  Score:          {passed}/{len(checks)}")
    print(f"  Status:         {'READY FOR USE' if passed == len(checks) else 'NEEDS REVISION'}")
    print("=" * 58)
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Pionex Pine Bot Quality Check")
    parser.add_argument("path", type=Path, help="Pfad zur .pine Datei")
    args = parser.parse_args()
    return run_checks(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
