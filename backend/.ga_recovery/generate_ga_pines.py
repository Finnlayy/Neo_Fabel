#!/usr/bin/env python3
"""Generate Pine v6 variants from local GA result files."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

WORKDIR = Path(__file__).resolve().parent
DEFAULT_RESULTS = WORKDIR / "ga_forward_results.json"
DEFAULT_TEMPLATE = WORKDIR / "ETH_USDT_GlintNews_PionexBot_v6_strategy.pine"
DEFAULT_OUTPUT = WORKDIR / "generated_pines"
DEFAULT_TARGET_SYMBOL = "WTI/USDT PERP"
DEFAULT_TF_HIGH = "48"
DEFAULT_TF_MID = "12"
DEFAULT_TF_LOW = "3"
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")
SAFE_SYMBOL_TEXT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /._-]{0,63}$")


@dataclass(frozen=True)
class Candidate:
    symbol: str
    fitness: float
    params: Dict[str, Any]
    source: str


def format_float(value: float, digits: int = 3) -> str:
    text = f"{float(value):.{digits}f}"
    return text.rstrip("0").rstrip(".")


def pine_bool(value: bool) -> str:
    return "true" if value else "false"


def validate_symbol_text(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise ValueError("Symbol must be a text value.")
    clean = symbol.strip()
    if not clean:
        raise ValueError("Symbol must not be empty.")
    if CONTROL_CHARS_RE.search(clean):
        raise ValueError(f"Symbol contains control characters: {symbol!r}")
    if not SAFE_SYMBOL_TEXT_RE.fullmatch(clean):
        raise ValueError(f"Symbol contains unsupported characters: {symbol!r}")
    return clean


def pine_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def sanitize_symbol(symbol: str) -> str:
    clean = validate_symbol_text(symbol).upper()
    clean = re.sub(r"[^A-Z0-9]+", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if "_" not in clean and clean.endswith("USDT") and len(clean) > 4:
        clean = f"{clean[:-4]}_USDT"
    if not clean:
        raise ValueError(f"Unable to derive a safe symbol tag from {symbol!r}")
    return clean


def display_symbol(symbol: str) -> str:
    clean = sanitize_symbol(symbol)
    parts = clean.split("_")
    if len(parts) >= 3 and parts[-1] == "PERP":
        base = "_".join(parts[:-2])
        quote = parts[-2]
        return f"{base}/{quote} PERP"
    if len(parts) >= 2:
        base = "_".join(parts[:-1])
        quote = parts[-1]
        return f"{base}/{quote}"
    return clean


def replace_input_default(text: str, var_name: str, value: str, kind: str) -> str:
    pattern = rf"{re.escape(var_name)}\s*=\s*input\.{kind}\([^,]+,"
    replacement = f"{var_name} = input.{kind}({value},"
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        return text
    return updated


def detect_template_kind(template_text: str) -> str:
    strategy_match = re.search(r"\bstrategy\s*\(", template_text)
    indicator_match = re.search(r"\bindicator\s*\(", template_text)
    if strategy_match and indicator_match:
        return "strategy" if strategy_match.start() < indicator_match.start() else "indicator"
    if strategy_match:
        return "strategy"
    if indicator_match:
        return "indicator"
    raise ValueError("Template must contain either strategy(...) or indicator(...).")


def extract_template_symbol(template_text: str, fallback: str) -> str:
    match = re.search(r'title\s*=\s*"([^"]+)"', template_text)
    if not match:
        return fallback
    title = match.group(1)
    symbol_match = re.search(r"([A-Z0-9]+/[A-Z0-9]+)", title)
    if symbol_match:
        return symbol_match.group(1)
    return fallback


def normalize_candidates(payload: Dict[str, Any], fallback_symbol: str) -> List[Candidate]:
    candidates: List[Candidate] = []

    if isinstance(payload.get("per_symbol"), dict):
        for symbol, data in payload["per_symbol"].items():
            for row in data.get("top3", []):
                params = row.get("genes") or row.get("genome") or row.get("params") or {}
                candidates.append(
                    Candidate(
                        symbol=row.get("symbol") or symbol or fallback_symbol,
                        fitness=float(row.get("fitness", -1e9)),
                        params=dict(params),
                        source="per_symbol.top3",
                    )
                )
        return candidates

    if isinstance(payload.get("top_results"), list):
        for row in payload["top_results"]:
            top_sets = row.get("top_datasets") or []
            best_symbol = fallback_symbol
            if top_sets:
                best_symbol = top_sets[0].get("symbol") or fallback_symbol
            params = row.get("params") or row.get("genome") or row.get("genes") or {}
            candidates.append(
                Candidate(
                    symbol=row.get("symbol") or best_symbol,
                    fitness=float(row.get("fitness", -1e9)),
                    params=dict(params),
                    source="top_results",
                )
            )
        return candidates

    if isinstance(payload.get("top3"), list):
        for row in payload["top3"]:
            params = row.get("params") or row.get("genome") or row.get("genes") or {}
            candidates.append(
                Candidate(
                    symbol=row.get("symbol") or fallback_symbol,
                    fitness=float(row.get("fitness", -1e9)),
                    params=dict(params),
                    source="top3",
                )
            )
        return candidates

    raise ValueError("Unsupported GA result schema. Expected top3, top_results, or per_symbol.")


def unique_top(candidates: Iterable[Candidate], limit: int) -> List[Candidate]:
    ranked = sorted(candidates, key=lambda row: row.fitness, reverse=True)
    seen = set()
    unique: List[Candidate] = []
    for row in ranked:
        key = (sanitize_symbol(row.symbol), json.dumps(row.params, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def replace_once(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Expected exactly one match for pattern: {pattern}")
    return updated


def replace_optional(text: str, pattern: str, replacement: str, count: int = 1) -> str:
    updated, _ = re.subn(pattern, replacement, text, count=count, flags=re.MULTILINE)
    return updated


def session_defaults(session_mode: int) -> tuple[bool, str]:
    mapping = {
        0: (False, "0000-2359"),
        1: (True, "0600-1800"),
        2: (True, "0800-2200"),
        3: (True, "1200-2300"),
    }
    return mapping.get(session_mode, (True, "0800-2200"))


def apply_candidate(
    template_text: str,
    candidate: Candidate,
    rank: int,
    target_symbol: str,
    tf_high: str,
    tf_mid: str,
    tf_low: str,
) -> str:
    params = candidate.params
    template_kind = detect_template_kind(template_text)
    template_kind_label = "Strategie" if template_kind == "strategy" else "Indicator"
    selected_symbol = validate_symbol_text(target_symbol.strip() or candidate.symbol)
    symbol_label = display_symbol(selected_symbol)
    symbol_file_tag = sanitize_symbol(selected_symbol)
    output = template_text

    title = f"{symbol_label} Glint News Pionex Bot GA #{rank}"
    shorttitle = f"{symbol_file_tag} GA #{rank}"
    output = replace_once(output, r'title\s*=\s*"[^"]+"', f'title = "{pine_string_literal(title)}"')
    output = replace_once(output, r'shorttitle\s*=\s*"[^"]+"', f'shorttitle = "{pine_string_literal(shorttitle)}"')
    output = replace_once(
        output,
        r"// Abhaengig: TradingView Pine Script v6, Pionex Signal Bot Webhook\n",
        "// Abhaengig: TradingView Pine Script v6, Pionex Signal Bot Webhook\n"
        f"// Generiert aus {candidate.source} | Rank: {rank} | Fitness: {candidate.fitness:.4f}\n",
    )

    if "pivot_len = input.int(" not in output:
        output = replace_optional(
            output,
            r"(max_daily_move_pct = input\.float\([^\n]+\)\n)",
            (
                r"\1"
                "pivot_len = input.int(4, \"CISD Pivot Laenge\", minval=1, maxval=20, group=grp_risk)\n"
                "body_floor_mult = input.float(0.1, \"OB Body Floor (ATR Faktor)\", minval=0.01, step=0.01, group=grp_risk)\n"
                "ob_body_mult = input.float(1.1, \"OB Body Multiplikator\", minval=0.5, step=0.1, group=grp_risk)\n"
                "w_trend = input.int(9, \"Gewicht Trend\", minval=0, maxval=100, group=grp_risk)\n"
                "w_cisd = input.int(35, \"Gewicht CISD\", minval=0, maxval=100, group=grp_risk)\n"
                "w_ob = input.int(22, \"Gewicht Order Block\", minval=0, maxval=100, group=grp_risk)\n"
                "w_fvg = input.int(23, \"Gewicht FVG\", minval=0, maxval=100, group=grp_risk)\n"
                "w_news = input.int(20, \"Gewicht News\", minval=0, maxval=100, group=grp_risk)\n"
                "w_vol = input.int(16, \"Gewicht Volumen\", minval=0, maxval=100, group=grp_risk)\n"
                "\n"
                "grp_tf = \"Zeitfenster (3m Setup)\"\n"
                "tf_trend_high = input.timeframe(\"48\", \"Trend TF High\", group=grp_tf)\n"
                "tf_trend_mid = input.timeframe(\"12\", \"Trend TF Mid\", group=grp_tf)\n"
                "tf_trend_low = input.timeframe(\"3\", \"Trend TF Low\", group=grp_tf)\n"
            ),
            count=1,
        )

    output = replace_input_default(output, "tf_trend_high", f"\"{tf_high}\"", "timeframe")
    output = replace_input_default(output, "tf_trend_mid", f"\"{tf_mid}\"", "timeframe")
    output = replace_input_default(output, "tf_trend_low", f"\"{tf_low}\"", "timeframe")

    output = replace_optional(
        output,
        r'bool h4_bull = request\.security\(syminfo\.tickerid, "240", f_trend_bull\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool h4_bull = request.security(syminfo.tickerid, tf_trend_high, f_trend_bull()[1], lookahead=barmerge.lookahead_off)',
    )
    output = replace_optional(
        output,
        r'bool h4_bear = request\.security\(syminfo\.tickerid, "240", f_trend_bear\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool h4_bear = request.security(syminfo.tickerid, tf_trend_high, f_trend_bear()[1], lookahead=barmerge.lookahead_off)',
    )
    output = replace_optional(
        output,
        r'bool h1_bull = request\.security\(syminfo\.tickerid, "60", f_trend_bull\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool h1_bull = request.security(syminfo.tickerid, tf_trend_mid, f_trend_bull()[1], lookahead=barmerge.lookahead_off)',
    )
    output = replace_optional(
        output,
        r'bool h1_bear = request\.security\(syminfo\.tickerid, "60", f_trend_bear\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool h1_bear = request.security(syminfo.tickerid, tf_trend_mid, f_trend_bear()[1], lookahead=barmerge.lookahead_off)',
    )
    output = replace_optional(
        output,
        r'bool m15_bull = request\.security\(syminfo\.tickerid, "15", f_trend_bull\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool m15_bull = request.security(syminfo.tickerid, tf_trend_low, f_trend_bull()[1], lookahead=barmerge.lookahead_off)',
    )
    output = replace_optional(
        output,
        r'bool m15_bear = request\.security\(syminfo\.tickerid, "15", f_trend_bear\(\)\[1\], lookahead=barmerge\.lookahead_off\)',
        'bool m15_bear = request.security(syminfo.tickerid, tf_trend_low, f_trend_bear()[1], lookahead=barmerge.lookahead_off)',
    )

    output = replace_optional(
        output,
        r"pivot_high = ta\.pivothigh\(high, \d+, \d+\)",
        "pivot_high = ta.pivothigh(high, pivot_len, pivot_len)",
    )
    output = replace_optional(
        output,
        r"pivot_low = ta\.pivotlow\(low, \d+, \d+\)",
        "pivot_low = ta.pivotlow(low, pivot_len, pivot_len)",
    )
    output = replace_optional(
        output,
        r"float body_min = math\.max\(body_prev, atr_safe \* [0-9.]+\)",
        "float body_min = math.max(body_prev, atr_safe * body_floor_mult)",
    )
    output = replace_optional(
        output,
        r"bool ob_bull = close\[1\] < open\[1\] and close > open and body_curr > body_min \* [0-9.]+",
        "bool ob_bull = close[1] < open[1] and close > open and body_curr > body_min * ob_body_mult",
    )
    output = replace_optional(
        output,
        r"bool ob_bear = close\[1\] > open\[1\] and close < open and body_curr > body_min \* [0-9.]+",
        "bool ob_bear = close[1] > open[1] and close < open and body_curr > body_min * ob_body_mult",
    )

    if "news_dual_active" not in output:
        output = replace_optional(
            output,
            r"int score_long = 0",
            "bool news_dual_active = news_bull and news_bear\n"
            "bool news_long_active = news_bull and not news_dual_active\n"
            "bool news_short_active = news_bear and not news_dual_active\n"
            "\n"
            "int score_long = 0",
            count=1,
        )

    output = replace_optional(output, r"if h4_bull\s*\n\s*score_long \+= \d+", "if h4_bull\n    score_long += w_trend")
    output = replace_optional(output, r"if h4_bear\s*\n\s*score_short \+= \d+", "if h4_bear\n    score_short += w_trend")
    output = replace_optional(output, r"if h1_bull\s*\n\s*score_long \+= \d+", "if h1_bull\n    score_long += w_trend")
    output = replace_optional(output, r"if h1_bear\s*\n\s*score_short \+= \d+", "if h1_bear\n    score_short += w_trend")
    output = replace_optional(output, r"if m15_bull\s*\n\s*score_long \+= \d+", "if m15_bull\n    score_long += w_trend")
    output = replace_optional(output, r"if m15_bear\s*\n\s*score_short \+= \d+", "if m15_bear\n    score_short += w_trend")
    output = replace_optional(output, r"if cisd_bull\s*\n\s*score_long \+= \d+", "if cisd_bull\n    score_long += w_cisd")
    output = replace_optional(output, r"if cisd_bear\s*\n\s*score_short \+= \d+", "if cisd_bear\n    score_short += w_cisd")
    output = replace_optional(output, r"if ob_bull\s*\n\s*score_long \+= \d+", "if ob_bull\n    score_long += w_ob")
    output = replace_optional(output, r"if ob_bear\s*\n\s*score_short \+= \d+", "if ob_bear\n    score_short += w_ob")
    output = replace_optional(output, r"if fvg_bull\s*\n\s*score_long \+= \d+", "if fvg_bull\n    score_long += w_fvg")
    output = replace_optional(output, r"if fvg_bear\s*\n\s*score_short \+= \d+", "if fvg_bear\n    score_short += w_fvg")
    output = replace_optional(output, r"if news_bull\s*\n\s*score_long \+= \d+", "if news_long_active\n    score_long += w_news")
    output = replace_optional(output, r"if news_bear\s*\n\s*score_short \+= \d+", "if news_short_active\n    score_short += w_news")
    output = replace_optional(
        output,
        r"if is_vol_high\s*\n\s*score_long \+= \d+\n\s*score_short \+= \d+",
        "if is_vol_high\n    score_long += w_vol\n    score_short += w_vol",
    )

    output = replace_optional(
        output,
        r"bool block_long = news_bear or not in_session or daily_guard_active",
        "bool block_long = news_short_active or not in_session or daily_guard_active",
    )
    output = replace_optional(
        output,
        r"bool block_short = news_bull or not in_session or daily_guard_active",
        "bool block_short = news_long_active or not in_session or daily_guard_active",
    )
    output = replace_optional(
        output,
        r"bool blocker_hit = news_bear or not in_session or daily_guard_active",
        "bool blocker_hit = news_short_active or not in_session or daily_guard_active",
        count=1,
    )
    output = replace_optional(
        output,
        r"bool blocker_hit = news_bull or not in_session or daily_guard_active",
        "bool blocker_hit = news_long_active or not in_session or daily_guard_active",
        count=1,
    )
    output = replace_optional(output, r'table\.cell\(dash, 0, 3, "H4/H1/M15"', 'table.cell(dash, 0, 3, "TF(H/M/L)"')

    applied_keys = set()

    if "min_conf" in params:
        output = replace_once(output, r"min_conf = input\.int\([^,]+,", f"min_conf = input.int({int(params['min_conf'])},")
        applied_keys.add("min_conf")

    use_shorts_value = params.get("allow_shorts", params.get("use_shorts"))
    if use_shorts_value is not None:
        output = replace_once(
            output,
            r"use_shorts = input\.bool\((true|false),",
            f"use_shorts = input.bool({pine_bool(bool(use_shorts_value))},",
        )
        applied_keys.update({"allow_shorts", "use_shorts"})

    float_inputs = {
        "risk_pct": "risk_pct",
        "sl_atr_mul": "sl_atr_mul",
        "tp_atr_mul": "tp_atr_mul",
        "vol_mult": "vol_mult",
        "max_daily_move_pct": "max_daily_move_pct",
        "max_dd_pct": "max_daily_move_pct",
    }
    for key, target in float_inputs.items():
        if key not in params:
            continue
        output = replace_once(
            output,
            rf"{target} = input\.float\([^,]+,",
            f"{target} = input.float({format_float(params[key])},",
        )
        applied_keys.add(key)

    cisd_len = params.get("cisd_len", params.get("pivot_lb"))
    if cisd_len is not None:
        cisd_len = int(cisd_len)
        updated = replace_input_default(output, "pivot_len", str(cisd_len), "int")
        if updated != output:
            output = updated
        else:
            output = replace_optional(output, r"pivot_high = ta\.pivothigh\(high, \d+, \d+\)", f"pivot_high = ta.pivothigh(high, {cisd_len}, {cisd_len})")
            output = replace_optional(output, r"pivot_low = ta\.pivotlow\(low, \d+, \d+\)", f"pivot_low = ta.pivotlow(low, {cisd_len}, {cisd_len})")
        applied_keys.update({"cisd_len", "pivot_lb"})

    body_floor = params.get("body_atr_floor")
    if body_floor is not None:
        updated = replace_input_default(output, "body_floor_mult", format_float(body_floor), "float")
        if updated != output:
            output = updated
        else:
            output = replace_optional(
                output,
                r"float body_min = math\.max\(body_prev, atr_safe \* [0-9.]+\)",
                f"float body_min = math.max(body_prev, atr_safe * {format_float(body_floor)})",
            )
        applied_keys.add("body_atr_floor")

    body_ratio = params.get("ob_body_mult", params.get("ob_ratio", params.get("body_factor")))
    if body_ratio is not None:
        updated = replace_input_default(output, "ob_body_mult", format_float(body_ratio), "float")
        if updated != output:
            output = updated
        else:
            output = replace_optional(output, r"body_curr > body_min \* [0-9.]+", f"body_curr > body_min * {format_float(body_ratio)}", count=2)
        applied_keys.update({"ob_body_mult", "ob_ratio", "body_factor"})

    if "session_mode" in params:
        use_session, session_time = session_defaults(int(params["session_mode"]))
        output = replace_once(
            output,
            r"use_session = input\.bool\((true|false),",
            f"use_session = input.bool({pine_bool(use_session)},",
        )
        output = replace_once(
            output,
            r'session_time = input\.session\("[0-9]{4}-[0-9]{4}",',
            f'session_time = input.session("{session_time}",',
        )
        applied_keys.add("session_mode")

    trend_weight_raw = params.get("w_trend")
    if trend_weight_raw is not None:
        per_tf_weight = max(1, int(round(float(trend_weight_raw) / 3.0)))
        updated = replace_input_default(output, "w_trend", str(per_tf_weight), "int")
        if updated != output:
            output = updated
        else:
            output = replace_optional(output, r"if h4_bull\s*\n\s*score_long \+= \d+", f"if h4_bull\n    score_long += {per_tf_weight}")
            output = replace_optional(output, r"if h4_bear\s*\n\s*score_short \+= \d+", f"if h4_bear\n    score_short += {per_tf_weight}")
            output = replace_optional(output, r"if h1_bull\s*\n\s*score_long \+= \d+", f"if h1_bull\n    score_long += {per_tf_weight}")
            output = replace_optional(output, r"if h1_bear\s*\n\s*score_short \+= \d+", f"if h1_bear\n    score_short += {per_tf_weight}")
            output = replace_optional(output, r"if m15_bull\s*\n\s*score_long \+= \d+", f"if m15_bull\n    score_long += {per_tf_weight}")
            output = replace_optional(output, r"if m15_bear\s*\n\s*score_short \+= \d+", f"if m15_bear\n    score_short += {per_tf_weight}")
        applied_keys.add("w_trend")

    if "w_news" in params:
        output = replace_input_default(output, "w_news", str(int(round(float(params["w_news"])))), "int")
        applied_keys.add("w_news")

    weight_patterns = {
        "w_cisd": [
            (r"if cisd_bull\s*\n\s*score_long \+= \d+", "if cisd_bull\n    score_long += {value}"),
            (r"if cisd_bear\s*\n\s*score_short \+= \d+", "if cisd_bear\n    score_short += {value}"),
        ],
        "w_ob": [
            (r"if ob_bull\s*\n\s*score_long \+= \d+", "if ob_bull\n    score_long += {value}"),
            (r"if ob_bear\s*\n\s*score_short \+= \d+", "if ob_bear\n    score_short += {value}"),
        ],
        "w_fvg": [
            (r"if fvg_bull\s*\n\s*score_long \+= \d+", "if fvg_bull\n    score_long += {value}"),
            (r"if fvg_bear\s*\n\s*score_short \+= \d+", "if fvg_bear\n    score_short += {value}"),
        ],
        "w_vol": [
            (r"if is_vol_high\s*\n\s*score_long \+= \d+", "if is_vol_high\n    score_long += {value}"),
            (r"score_short \+= \d+", "score_short += {value}"),
        ],
    }
    for key, replacements in weight_patterns.items():
        if key not in params:
            continue
        value = int(round(float(params[key])))
        updated = replace_input_default(output, key, str(value), "int")
        if updated != output:
            output = updated
            applied_keys.add(key)
            continue
        for idx, (pattern, template) in enumerate(replacements):
            if key == "w_vol" and idx == 1:
                output = replace_optional(
                    output,
                    r"if is_vol_high\s*\n\s*score_long \+= \d+\n\s*score_short \+= \d+",
                    f"if is_vol_high\n    score_long += {value}\n    score_short += {value}",
                )
                break
            output = replace_optional(output, pattern, template.format(value=value))
        applied_keys.add(key)

    ignored_keys = sorted(key for key in params if key not in applied_keys)
    if ignored_keys:
        marker = f"// Generiert aus {candidate.source} | Rank: {rank} | Fitness: {candidate.fitness:.4f}\n"
        if marker not in output:
            raise ValueError("Generator metadata marker not found in template output.")
        output = output.replace(
            marker,
            marker + f"// Nicht direkt auf das {template_kind_label}-Template gemappt: {', '.join(ignored_keys)}\n",
            1,
        )

    output = replace_optional(output, r'table\.cell\(dash, 0, 0, "[^"]+"', f'table.cell(dash, 0, 0, "{pine_string_literal(shorttitle)}"')
    output = replace_optional(output, r"// Datei: .+\n", f"// Datei: Top{rank}_{symbol_file_tag}_GA_Optimized.pine\n")
    output = replace_optional(output, r"// Zweck: .+\n", f"// Zweck: GA-optimierte Pine-v6-{template_kind_label} fuer {symbol_label}.\n")
    return output


def generate_files(
    results_path: Path,
    template_path: Path,
    output_dir: Path,
    limit: int,
    fallback_symbol: str,
    target_symbol: str,
    tf_high: str,
    tf_mid: str,
    tf_low: str,
) -> List[Path]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    template_text = template_path.read_text(encoding="utf-8")
    template_symbol = extract_template_symbol(template_text, fallback_symbol)
    candidates = unique_top(normalize_candidates(payload, template_symbol), limit)
    if not candidates:
        raise ValueError("No unique candidates found in the GA results.")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for rank, candidate in enumerate(candidates, start=1):
        selected_symbol = target_symbol.strip() or candidate.symbol
        symbol_tag = sanitize_symbol(selected_symbol)
        target = output_dir / f"Top{rank}_{symbol_tag}_GA_Optimized.pine"
        target.write_text(
            apply_candidate(template_text, candidate, rank, selected_symbol, tf_high, tf_mid, tf_low),
            encoding="utf-8",
        )
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GA-tuned Pine v6 templates from local optimizer results.")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS, help="Path to a GA results JSON file")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Pine v6 template used as the base indicator or strategy")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for generated .pine files")
    parser.add_argument("--limit", type=int, default=3, help="Maximum number of unique outputs to create")
    parser.add_argument("--fallback-symbol", default=DEFAULT_TARGET_SYMBOL, help="Used when the JSON does not contain a symbol")
    parser.add_argument("--target-symbol", default=DEFAULT_TARGET_SYMBOL, help="Forced symbol label for generated files")
    parser.add_argument("--tf-high", default=DEFAULT_TF_HIGH, help="Higher trend timeframe for MTF checks (minutes)")
    parser.add_argument("--tf-mid", default=DEFAULT_TF_MID, help="Middle trend timeframe for MTF checks (minutes)")
    parser.add_argument("--tf-low", default=DEFAULT_TF_LOW, help="Lower trend timeframe for MTF checks (minutes)")
    args = parser.parse_args()

    written = generate_files(
        args.results,
        args.template,
        args.output_dir,
        args.limit,
        args.fallback_symbol,
        args.target_symbol,
        args.tf_high,
        args.tf_mid,
        args.tf_low,
    )
    print(f"Generated {len(written)} Pine file(s):")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
