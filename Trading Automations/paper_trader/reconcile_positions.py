#!/usr/bin/env python3
"""
Reconcile positions.json against Alpaca's real, live account positions.

Read-only — never places, cancels, or modifies any order. Run this any
time you want to check whether tracking has drifted from reality, the
same class of problem discovered with ACN on 2026-08-05: an exit order
that expired unfilled got logged as a successful sale and dropped from
tracking, leaving real shares invisible to the system for weeks. See
directives/paper_trader.md for that incident and the trader.py fix.

Checks both directions:
  - Alpaca holds shares of a ticker positions.json doesn't know about, or
    holds MORE than tracked -> an under-tracked/orphaned position (the
    ACN failure mode: a sell that never actually filled).
  - positions.json believes more is open than Alpaca actually holds ->
    a phantom entry that was logged as bought but never actually filled
    (the same bug, mirrored onto the buy side).

Run manually any time:
    python reconcile_positions.py

Requires ALPACA_API_KEY / ALPACA_SECRET_KEY in the environment (same as
trader.py). Nothing here writes to positions.json or trade_log.csv —
any mismatch it finds needs to be reconciled by hand, the same way ACN
was: confirm the real qty/avg-entry-price on the Alpaca dashboard, then
correct positions.json (and trade_log.csv if a phantom "closed" trade
needs removing) to match.
"""

import json
import os
from collections import defaultdict

from alpaca.trading.client import TradingClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSITIONS_FILE = os.path.join(BASE_DIR, "positions.json")


def make_client():
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
        paper=True,  # hardcoded — this script never touches a real account
    )


def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        return {}
    with open(POSITIONS_FILE) as f:
        return json.load(f)


def tracked_shares_by_ticker(positions):
    shares = defaultdict(int)
    detail = defaultdict(list)
    for pos in positions.values():
        shares[pos["ticker"]] += pos["shares"]
        detail[pos["ticker"]].append(
            f"{pos['strategy']} ({pos['shares']}sh, entered {pos['entry_date']}, exits {pos['exit_date']})"
        )
    return shares, detail


def real_shares_by_ticker(client):
    return {p.symbol: int(float(p.qty)) for p in client.get_all_positions()}


def main():
    client = make_client()
    positions = load_positions()

    tracked, detail = tracked_shares_by_ticker(positions)
    real = real_shares_by_ticker(client)

    tickers = sorted(set(tracked) | set(real))

    print(f"{'Ticker':8} {'Tracked':>8} {'Alpaca':>8}  Status")
    print("-" * 70)
    mismatches = []
    for ticker in tickers:
        t, r = tracked.get(ticker, 0), real.get(ticker, 0)
        if t == r:
            status = "OK"
        elif r > t:
            status = f"UNDER-TRACKED by {r - t}sh — Alpaca holds more than tracked"
            mismatches.append(ticker)
        else:
            status = f"OVER-TRACKED by {t - r}sh — tracked more than Alpaca actually holds"
            mismatches.append(ticker)
        print(f"{ticker:8} {t:>8} {r:>8}  {status}")

    print()
    if not mismatches:
        print("No mismatches — positions.json matches Alpaca exactly.")
        return

    print(f"{len(mismatches)} ticker(s) need manual reconciliation:\n")
    for ticker in mismatches:
        print(f"  {ticker}: tracked={tracked.get(ticker, 0)}sh, Alpaca={real.get(ticker, 0)}sh")
        for line in detail.get(ticker, []):
            print(f"    - {line}")
        print()


if __name__ == "__main__":
    main()
