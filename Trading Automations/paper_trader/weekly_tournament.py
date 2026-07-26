#!/usr/bin/env python3
"""
Weekly Strategy Tournament
============================
Runs after market close every Friday via GitHub Actions:

  1. Downloads fresh price data, END_DATE = today (a rolling window — this is
     what makes "re-run the tournament weekly" mean something; the test half
     of the cheat-check keeps extending toward the present instead of testing
     the same fixed 2019-2024 window every week).
  2. Asks Claude for NUM_CANDIDATES new candidate strategies (thesis_generator.py) —
     structured params only, no code generation.
  3. Backtests the current 4 live strategies + all new candidates together
     (candidates + incumbents = one pool), applies the train/test cheat-check.
  4. Ranks cheat-check survivors by test-half P&L, takes the top 4. If fewer
     than 4 survive, keeps incumbents in their prior order to fill the
     remaining slots rather than leaving the roster short.
  5. Writes the new roster to active_strategies.json (which trader.py reads
     every day) and appends the full week's results to thesis_history.jsonl
     for an audit trail.

SAFETY: Every candidate — whether from Claude or an incumbent — is backtested
through the same fixed, vetted indicator engine in strategies_lib.py before
it can ever go live. Claude only ever selects indicator_type + params from a
closed registry; it never writes or influences execution code.
"""

import json
import os
import warnings
from datetime import date, timedelta
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

import strategies_lib as lib
import thesis_generator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVE_STRATEGIES_FILE = os.path.join(BASE_DIR, "active_strategies.json")
THESIS_HISTORY_FILE = os.path.join(BASE_DIR, "thesis_history.jsonl")
REPORT_FILE = os.path.join(BASE_DIR, "weekly_tournament_report.md")

START_DATE = "2019-01-01"
TRAIN_CUTOFF = "2021-12-31"
MIN_TRADES_TO_SURVIVE = 30
ROSTER_SIZE = 4


def load_active_strategies():
    if not os.path.exists(ACTIVE_STRATEGIES_FILE):
        return []
    with open(ACTIVE_STRATEGIES_FILE) as f:
        return json.load(f)


def save_active_strategies(specs):
    with open(ACTIVE_STRATEGIES_FILE, "w") as f:
        json.dump(specs, f, indent=2, default=str)


def append_thesis_history(record):
    with open(THESIS_HISTORY_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def download_price_data(end_date):
    print(f"Downloading price data ({START_DATE} -> {end_date})...")
    price_data = {}
    failed = []
    for i, ticker in enumerate(lib.ALL_TICKERS):
        try:
            df = yf.download(ticker, start=START_DATE, end=end_date, auto_adjust=True, progress=False)
            if hasattr(df.columns, "get_level_values"):
                df.columns = [c[0] for c in df.columns]
            if len(df) > 150:
                price_data[ticker] = df
            else:
                failed.append(ticker)
        except Exception:
            failed.append(ticker)
        if (i + 1) % 30 == 0:
            print(f"  [{(i + 1) / len(lib.ALL_TICKERS) * 100:5.1f}%] {i + 1}/{len(lib.ALL_TICKERS)}")
    print(f"  Done. {len(price_data)} tickers loaded, {len(failed)} skipped.")

    spy_df = yf.download(lib.BENCHMARK, start=START_DATE, end=end_date, auto_adjust=True, progress=False)
    if hasattr(spy_df.columns, "get_level_values"):
        spy_df.columns = [c[0] for c in spy_df.columns]
    spy_ret_63 = spy_df["Close"].pct_change(63)

    return price_data, spy_ret_63


def evaluate_candidates(candidates, price_data, spy_ret_63):
    results = []
    for spec in candidates:
        params = lib.clamp_params(spec["indicator_type"], spec.get("params", {}))
        hold_days = lib.clamp_hold_days(spec["hold_days"])
        clean_spec = {
            "name": spec["name"],
            "indicator_type": spec["indicator_type"],
            "params": params,
            "hold_days": hold_days,
            "thesis": spec.get("thesis", ""),
            "incumbent": spec.get("incumbent", False),
        }

        trades_df = lib.run_spec(clean_spec, price_data, spy_ret_63)
        stats = lib.compute_stats(trades_df)
        train_pnl, test_pnl, verdict = lib.cheat_check(trades_df, TRAIN_CUTOFF, MIN_TRADES_TO_SURVIVE)

        results.append({
            **clean_spec,
            "stats": stats,
            "train_pnl": train_pnl,
            "test_pnl": test_pnl,
            "verdict": verdict,
        })
        print(f"  {clean_spec['name']:30s} [{clean_spec['indicator_type']:22s}] "
              f"{stats['n']:4d} trades -> {verdict}")
    return results


def select_next_roster(results, incumbents):
    survivors = [r for r in results if r["verdict"] == "SURVIVED"]
    survivors.sort(key=lambda r: r["test_pnl"], reverse=True)

    roster = survivors[:ROSTER_SIZE]
    if len(roster) < ROSTER_SIZE:
        chosen_names = {r["name"] for r in roster}
        for inc in incumbents:
            if len(roster) >= ROSTER_SIZE:
                break
            if inc["name"] not in chosen_names:
                # Re-find this incumbent's fresh backtest result to keep stats consistent
                match = next((r for r in results if r["name"] == inc["name"]), None)
                if match is not None:
                    roster.append(match)
                    chosen_names.add(inc["name"])
    return roster


def build_report(today, candidates_new, results, roster):
    lines = [
        "# Weekly Strategy Tournament Report",
        f"\n_Run date: {today}_\n",
        f"## New Candidates Generated: {len(candidates_new)}",
        f"## Total Evaluated (incumbents + new): {len(results)}",
        f"## Survivors: {sum(1 for r in results if r['verdict'] == 'SURVIVED')}",
        "\n## Next Week's Roster",
        "| Name | Indicator | Params | Hold Days | Test P&L | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in roster:
        lines.append(
            f"| {r['name']} | {r['indicator_type']} | {r['params']} | {r['hold_days']} "
            f"| ${r['test_pnl']:,.0f} | {r['verdict']} |"
        )

    lines.append("\n## All Candidates This Week")
    lines.append("| Name | Type | Incumbent | Trades | Train P&L | Test P&L | Verdict | Thesis |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: x["test_pnl"], reverse=True):
        lines.append(
            f"| {r['name']} | {r['indicator_type']} | {'yes' if r['incumbent'] else 'no'} "
            f"| {r['stats']['n']} | ${r['train_pnl']:,.0f} | ${r['test_pnl']:,.0f} "
            f"| {r['verdict']} | {r['thesis'][:120]} |"
        )
    return "\n".join(lines) + "\n"


def main():
    today = date.today().isoformat()
    print(f"=== Weekly Strategy Tournament — {today} ===\n")

    incumbents = load_active_strategies()
    for spec in incumbents:
        spec["incumbent"] = True
    print(f"Current roster: {len(incumbents)} strategies")
    for s in incumbents:
        print(f"  - {s['name']} [{s['indicator_type']}] {s.get('params', {})} hold={s['hold_days']}")

    print("\nGenerating new candidates via Claude...")
    new_candidates = thesis_generator.generate_candidates(incumbents)
    for spec in new_candidates:
        spec["incumbent"] = False
    print(f"  {len(new_candidates)} new candidates received.\n")

    all_candidates = incumbents + new_candidates
    if not all_candidates:
        print("No candidates to evaluate (no incumbents, no new candidates) — exiting.")
        return

    price_data, spy_ret_63 = download_price_data(today)

    print(f"\nEvaluating {len(all_candidates)} strategies "
          f"(train <= {TRAIN_CUTOFF}, test > {TRAIN_CUTOFF} through {today})...")
    results = evaluate_candidates(all_candidates, price_data, spy_ret_63)

    roster = select_next_roster(results, incumbents)

    print(f"\n=== Next week's roster ({len(roster)} strategies) ===")
    for r in roster:
        print(f"  {r['name']} [{r['indicator_type']}] test P&L ${r['test_pnl']:,.0f} — {r['verdict']}")

    next_roster_specs = [
        {
            "name": r["name"],
            "indicator_type": r["indicator_type"],
            "params": r["params"],
            "hold_days": r["hold_days"],
            "thesis": r["thesis"],
            "added_week": today if not r["incumbent"] else next(
                (s.get("added_week", today) for s in incumbents if s["name"] == r["name"]), today
            ),
        }
        for r in roster
    ]
    save_active_strategies(next_roster_specs)
    print(f"\nWrote {ACTIVE_STRATEGIES_FILE}")

    append_thesis_history({
        "date": today,
        "num_new_candidates": len(new_candidates),
        "num_evaluated": len(results),
        "roster": [r["name"] for r in roster],
        "results": [
            {k: v for k, v in r.items() if k != "stats"} | {"stats": r["stats"]}
            for r in results
        ],
    })
    print(f"Appended results to {THESIS_HISTORY_FILE}")

    report_md = build_report(today, new_candidates, results, roster)
    with open(REPORT_FILE, "w") as f:
        f.write(report_md)
    print(f"Wrote {REPORT_FILE}")


if __name__ == "__main__":
    main()
