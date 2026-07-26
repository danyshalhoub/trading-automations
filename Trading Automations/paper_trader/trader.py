#!/usr/bin/env python3
"""
Daily Paper Trader
==================
Runs after market close every weekday via GitHub Actions.
Scans the shared ticker universe (strategies_lib.ALL_TICKERS) for whatever
strategies are currently listed in active_strategies.json and places paper
trades automatically on Alpaca.

The live roster (which 4 strategies are active, and their parameters) is
no longer hardcoded here — it's read from active_strategies.json, which
weekly_tournament.py rewrites every Friday after re-testing the current
roster against fresh data plus new Claude-generated candidates. See
directives/paper_trader.md for the weekly re-tournament process.

SAFETY: This script uses Alpaca PAPER trading only.
        paper=True is hardcoded. No real money is ever at risk.
        This is a learning tool, not financial advice.

Every closed trade is appended to trade_log.csv (ticker, strategy, entry/exit
price, % gain, $ P&L). Run performance_report.py to summarize win rate and
trade count from that log, and optionally email a weekly digest.
"""

import csv
import json
import os
from datetime import date
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

import strategies_lib as lib

# =============================================================================
# CONFIG
# =============================================================================

POSITION_SIZE = 10_000   # Dollars per trade

# positions.json, trade_log.csv, and active_strategies.json live in the same
# folder as this script
POSITIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "positions.json")
TRADE_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_log.csv")
ACTIVE_STRATEGIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_strategies.json")
TRADE_LOG_FIELDS = [
    "ticker", "strategy", "entry_date", "exit_date",
    "entry_price", "exit_price", "shares", "pct_gain", "dollar_pnl",
]


def load_active_strategies():
    with open(ACTIVE_STRATEGIES_FILE) as f:
        return json.load(f)


# =============================================================================
# ALPACA HELPERS
# =============================================================================

def make_client():
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_SECRET_KEY"],
        paper=True,  # hardcoded — this script never touches a real account
    )


def place_order(client, ticker, shares, side):
    try:
        client.submit_order(MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=side,
            time_in_force=TimeInForce.DAY,
        ))
        return True
    except Exception as e:
        print(f"    Order failed ({ticker} {side.value} {shares}sh): {e}")
        return False


def get_buying_power(client):
    return float(client.get_account().buying_power)


# =============================================================================
# POSITIONS FILE  (tracks open trades so we know when to exit)
# =============================================================================

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return {}


def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def get_latest_close(ticker):
    """Fetch the most recent close price for a ticker being exited."""
    try:
        df = yf.download(ticker, period="5d", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


def log_trade(ticker, strategy, entry_date, exit_date, entry_price, exit_price, shares):
    pct_gain = (
        (exit_price - entry_price) / entry_price * 100 if exit_price is not None else None
    )
    dollar_pnl = (
        (exit_price - entry_price) * shares if exit_price is not None else None
    )

    file_exists = os.path.exists(TRADE_LOG_FILE)
    with open(TRADE_LOG_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TRADE_LOG_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "ticker":      ticker,
            "strategy":    strategy,
            "entry_date":  entry_date,
            "exit_date":   exit_date,
            "entry_price": entry_price,
            "exit_price":  exit_price,
            "shares":      shares,
            "pct_gain":    round(pct_gain, 4) if pct_gain is not None else "",
            "dollar_pnl":  round(dollar_pnl, 2) if dollar_pnl is not None else "",
        })


# =============================================================================
# MAIN
# =============================================================================

def main():
    today = date.today().isoformat()
    print(f"=== Daily Paper Trader — {today} ===\n")

    client    = make_client()
    positions = load_positions()

    # ── Step 1: Exit positions that have hit their hold-period end date ───────
    print("── Exits ──────────────────────────────────────────────────────")

    to_remove = []
    for key, pos in positions.items():
        if today >= pos["exit_date"]:
            print(f"  EXIT  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"{pos['shares']} shares  (entered {pos['entry_date']})")
            ok = place_order(client, pos["ticker"], pos["shares"], OrderSide.SELL)
            if ok:
                exit_price = get_latest_close(pos["ticker"])
                log_trade(
                    ticker=pos["ticker"], strategy=pos["strategy"],
                    entry_date=pos["entry_date"], exit_date=today,
                    entry_price=pos["entry_price"], exit_price=exit_price,
                    shares=pos["shares"],
                )
                to_remove.append(key)
        else:
            print(f"  HOLD  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"exits {pos['exit_date']}")

    for key in to_remove:
        del positions[key]

    if not to_remove and not any(
        today >= p["exit_date"] for p in positions.values()
    ):
        print("  No exits today.")

    print()

    # ── Step 2: Scan for new entry signals ───────────────────────────────────
    print("── Signal Scan ────────────────────────────────────────────────")

    buying_power = get_buying_power(client)
    print(f"  Buying power: ${buying_power:,.0f}\n")

    active_specs = load_active_strategies()
    print(f"  Active strategies: {', '.join(s['name'] for s in active_specs)}\n")

    lookback_start = (
        pd.Timestamp.today() - pd.DateOffset(days=420)
    ).strftime("%Y-%m-%d")

    spy_df = yf.download(lib.BENCHMARK, start=lookback_start, auto_adjust=True, progress=False)
    if isinstance(spy_df.columns, pd.MultiIndex):
        spy_df.columns = [col[0] for col in spy_df.columns]
    spy_ret_63 = spy_df["Close"].pct_change(63)

    new_trades   = 0
    data_skipped = 0

    for ticker in lib.ALL_TICKERS:
        # Stop if we've run out of capital
        if buying_power < POSITION_SIZE:
            print("  Buying power exhausted — scan stopped.")
            break

        # Download ~420 days of history (need 200 days for MA warmup)
        try:
            df = yf.download(
                ticker, start=lookback_start,
                auto_adjust=True, progress=False
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            if len(df) < 250:
                continue
        except Exception as e:
            print(f"  Data error {ticker}: {e}")
            continue

        # Only act if the most recent data is actually from today.
        # If the market was closed today, the last row is yesterday's data
        # and we could falsely re-trigger yesterday's signals.
        last_market_date = df.index[-1].date()
        if last_market_date != date.today():
            data_skipped += 1
            continue

        df            = lib.add_base_columns(df, spy_ret_lookback=spy_ret_63)
        current_price = float(df["Close"].iloc[-1])
        if current_price <= 0:
            continue

        shares = int(POSITION_SIZE / current_price)
        if shares < 1:
            continue  # stock price > $10,000 — skip

        for spec in active_specs:
            strategy_name = spec["name"]
            pos_key = f"{ticker}_{strategy_name}"

            if pos_key in positions:
                continue  # already holding this ticker/strategy combo

            if not lib.check_signal_today(df, spec["indicator_type"], spec["params"]):
                continue  # signal did not trigger today

            # Signal fired — calculate exit date in trading days
            hold   = spec["hold_days"]
            entry  = pd.Timestamp.today() + pd.offsets.BDay(1)   # tomorrow's open
            exit_d = (entry + pd.offsets.BDay(hold)).strftime("%Y-%m-%d")

            print(f"  SIGNAL  {ticker:6s}  [{strategy_name:18s}]  "
                  f"${current_price:.2f} × {shares} sh  →  exit {exit_d}")

            ok = place_order(client, ticker, shares, OrderSide.BUY)
            if ok:
                positions[pos_key] = {
                    "ticker":      ticker,
                    "strategy":    strategy_name,
                    "entry_date":  today,
                    "exit_date":   exit_d,
                    "shares":      shares,
                    "entry_price": round(current_price, 2),
                }
                buying_power -= POSITION_SIZE
                new_trades   += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n── Summary ────────────────────────────────────────────────────")
    print(f"  New trades placed : {new_trades}")
    print(f"  Exits today       : {len(to_remove)}")
    print(f"  Open positions    : {len(positions)}")
    print(f"  Buying power left : ${get_buying_power(client):,.0f}")

    if data_skipped > 0:
        print(f"\n  Note: {data_skipped} tickers skipped — market may be closed today "
              f"or data not yet settled.")

    save_positions(positions)
    print("\nDone.")


if __name__ == "__main__":
    main()
