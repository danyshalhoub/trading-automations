#!/usr/bin/env python3
"""
Print Alpaca's real order history for specific tickers, to determine
exactly which buy/sell orders actually filled vs expired/canceled/
rejected. Read-only — never places, cancels, or modifies any order.

Use this to resolve exactly which trade_log.csv / positions.json entries
are fake (submitted but never filled), especially when reconcile_positions.py
finds a mismatch on a ticker that had multiple same-day trades sharing an
identical share count — those can't be told apart by quantity alone, only
by looking at the real order history.

Run manually:
    python audit_orders.py TICKER [TICKER2 ...]

Example, to check every ticker reconcile_positions.py flagged on 2026-08-06:
    python audit_orders.py ADBE AMT CCI CRM CVX NFLX NOC SLB SNAP SPCE VZ XOM ZTS
"""

import os
import sys

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus


def make_client():
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
        paper=True,  # hardcoded — this script never touches a real account
    )


def main():
    tickers = [t.upper() for t in sys.argv[1:]]
    if not tickers:
        print("Usage: python audit_orders.py TICKER [TICKER2 ...]")
        return

    client = make_client()
    request = GetOrdersRequest(status=QueryOrderStatus.ALL, symbols=tickers, limit=500)
    orders = sorted(client.get_orders(request), key=lambda o: o.submitted_at)

    print(f"{'Symbol':7} {'Side':5} {'Qty':>6}  {'Status':10} {'Submitted':17} {'Filled At':17}  Fill")
    print("-" * 90)
    for o in orders:
        fill = f"{o.filled_qty}@{o.filled_avg_price}" if o.filled_avg_price else "-"
        submitted = o.submitted_at.strftime("%Y-%m-%d %H:%M") if o.submitted_at else "?"
        filled_at = o.filled_at.strftime("%Y-%m-%d %H:%M") if o.filled_at else "-"
        print(f"{o.symbol:7} {o.side.value:5} {str(o.qty):>6}  {o.status.value:10} "
              f"{submitted:17} {filled_at:17}  {fill}")


if __name__ == "__main__":
    main()
