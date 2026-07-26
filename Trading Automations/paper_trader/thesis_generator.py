#!/usr/bin/env python3
"""
Thesis Generator
==================
Asks Claude (Opus 4.8) to propose N new candidate trading strategies each
week, as structured JSON — not free-form code. Claude only ever chooses an
indicator_type from the fixed, vetted registry in strategies_lib.py plus
parameters (period, threshold, hold_days, ...); it never writes execution
code. The returned params are re-clamped to vetted bounds by strategies_lib
before they're ever backtested or traded live, so a bad or adversarial
response can't produce out-of-range behavior.

Cost: ~5K input + ~6K output tokens per call on Opus 4.8 ≈ $0.15-0.20/week —
trivially small, but if ANTHROPIC_API_KEY isn't set (e.g. secret not yet
configured in the repo), this degrades gracefully to an empty candidate list
rather than failing the whole weekly tournament run.
"""

import json
import os
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf

from strategies_lib import DIRECTIONS, PARAM_BOUNDS

MODEL = "claude-opus-4-8"
NUM_CANDIDATES = 16

# Every possible tunable param key across all indicator types, used to build
# a single flat, permissive JSON schema for the "params" object (structured
# outputs require additionalProperties: false, so every key must be named).
ALL_PARAM_KEYS = sorted({key for bounds in PARAM_BOUNDS.values() for key in bounds})


def get_market_context():
    """Recent SPY performance, for Claude to reason about current conditions."""
    try:
        spy = yf.download("SPY", period="4mo", auto_adjust=True, progress=False)
        if spy.empty:
            return "Recent SPY data unavailable."
        if hasattr(spy.columns, "get_level_values"):
            spy.columns = [c[0] for c in spy.columns]
        close = spy["Close"]
        ret_21 = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 21 else None
        ret_63 = (close.iloc[-1] / close.iloc[-63] - 1) * 100 if len(close) > 63 else None
        vol_21 = close.pct_change().tail(21).std() * (252 ** 0.5) * 100
        parts = []
        if ret_21 is not None:
            parts.append(f"SPY 1-month return: {ret_21:+.1f}%")
        if ret_63 is not None:
            parts.append(f"SPY 3-month return: {ret_63:+.1f}%")
        parts.append(f"Annualized 1-month volatility: {vol_21:.1f}%")
        return " | ".join(parts)
    except Exception as e:
        return f"Recent SPY data unavailable ({e})."


def build_schema():
    param_props = {key: {"type": "number"} for key in ALL_PARAM_KEYS}
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "minItems": NUM_CANDIDATES,
                "maxItems": NUM_CANDIDATES,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "indicator_type": {"type": "string", "enum": sorted(DIRECTIONS)},
                        "params": {
                            "type": "object",
                            "properties": param_props,
                            "additionalProperties": False,
                        },
                        "hold_days": {"type": "integer"},
                        "thesis": {"type": "string"},
                    },
                    "required": ["name", "indicator_type", "params", "hold_days", "thesis"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }


def build_prompt(current_strategies, market_context):
    catalog_lines = []
    for itype, bounds in sorted(PARAM_BOUNDS.items()):
        bound_str = ", ".join(f"{k} in [{lo}, {hi}]" for k, (lo, hi) in bounds.items()) or "no tunable params"
        catalog_lines.append(f"- {itype} ({DIRECTIONS[itype]}): {bound_str}")

    current_lines = [
        f"- {s['name']}: {s['indicator_type']} params={s.get('params', {})} hold_days={s['hold_days']}"
        for s in current_strategies
    ] or ["(none yet — first run)"]

    return f"""You are proposing new candidate trading strategies for a paper-trading
research pipeline (no real money — this is a learning/research tool).

Recent market context: {market_context}

Currently live strategies (already trading, will also be re-tested this week
alongside your candidates — you don't need to re-propose these, but a
different parameterization of one is fine if you think current conditions
call for it):
{chr(10).join(current_lines)}

Available indicator types and their tunable parameter bounds (you MUST pick
indicator_type from this exact list, and only vary the listed params —
these are the only signal formulas this system knows how to execute):
{chr(10).join(catalog_lines)}

Propose exactly {NUM_CANDIDATES} candidate strategies. For each, give a short
plain-English thesis for why this specific parameterization might perform
well given current market conditions — reference the market context where
relevant (e.g. tighter/looser thresholds in a high or low volatility regime).
Repeating an idea similar to a prior week is fine if it still seems feasible;
diversity across indicator types is preferred over 16 variations of one type.
hold_days must be a whole number of trading days between 3 and 30."""


def generate_candidates(current_strategies):
    """Returns a list of candidate spec dicts, or [] if generation is
    unavailable (missing API key, API error) — callers should treat this as
    'no new candidates this week', not a fatal error."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — skipping thesis generation this week.")
        return []

    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed — skipping thesis generation.")
        return []

    market_context = get_market_context()
    print(f"  Market context: {market_context}")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            output_config={"format": {"type": "json_schema", "schema": build_schema()}},
            messages=[{"role": "user", "content": build_prompt(current_strategies, market_context)}],
        )
    except Exception as e:
        print(f"  Claude API call failed ({e}) — skipping thesis generation this week.")
        return []

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        print("  Claude returned no text content — skipping thesis generation.")
        return []

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print("  Claude response was not valid JSON — skipping thesis generation.")
        return []

    candidates = data.get("candidates", [])
    print(f"  Generated {len(candidates)} candidate strategies "
          f"(usage: {response.usage.input_tokens} in / {response.usage.output_tokens} out tokens).")
    return candidates


if __name__ == "__main__":
    print(generate_candidates([]))
