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

Order handling — submit now, confirm next run
-----------------------------------------------
This workflow runs at 5:30 PM ET, after regular market hours. A DAY market
order submitted then cannot fill until the next session opens, hours after
this job has already finished — so a run can never learn its own orders'
outcome synchronously. Instead:
  - New entries are submitted and recorded in pending_entries.json (keyed
    by Alpaca order ID) rather than being written into positions.json
    immediately. They only become a tracked open position once a *later*
    run confirms the order actually filled.
  - Exits are submitted and the position gets a `pending_exit_order_id`
    field, but stays in positions.json — it's only logged to trade_log.csv
    and removed once a later run confirms the sell filled.
  - Every run's first step is reconciling whatever was left pending by the
    run before it, using the order's real status and fill price from
    Alpaca (not an approximated yfinance close).
  - If a pending order comes back expired/canceled/rejected instead of
    filled: a failed entry is just dropped (never became a position); a
    failed exit clears the pending flag so the normal exit scan retries it
    that same run, since its hold period has already passed.
Previously, submitting an order without error was treated as success and
logged/removed immediately — which let at least one exit (ACN, 2026-07-14)
get logged as closed and dropped from tracking despite never actually
filling, while the real shares stayed in the account, untracked. See
directives/paper_trader.md for that incident.

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
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce

import strategies_lib as lib

# =============================================================================
# CONFIG
# =============================================================================

POSITION_SIZE = 10_000   # Dollars per trade

TERMINAL_FAILURE_STATUSES = {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}

# positions.json, pending_entries.json, trade_log.csv, and active_strategies.json
# live in the same folder as this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSITIONS_FILE = os.path.join(BASE_DIR, "positions.json")
PENDING_ENTRIES_FILE = os.path.join(BASE_DIR, "pending_entries.json")
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.csv")
ACTIVE_STRATEGIES_FILE = os.path.join(BASE_DIR, "active_strategies.json")
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
    """Submits a market order and returns the resulting Order (with its
    Alpaca order ID), or None if submission itself failed. Does NOT wait
    for or check the fill — that only happens on a later run, once a
    market session has actually had a chance to execute it.

    Self-heals from a duplicate-order rejection: if a prior run already
    submitted this exact order but crashed before its ID got saved locally
    (as happened 2026-08-06), Alpaca rejects the resubmit because the
    shares/cash are already held by that still-outstanding order - and its
    rejection includes that order's real ID in `related_orders`. Rather
    than failing and repeating the same rejection every run forever, adopt
    that ID so the caller tracks the real order and reconciliation can
    check its actual status next run."""
    try:
        return client.submit_order(MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=side,
            time_in_force=TimeInForce.DAY,
        ))
    except APIError as e:
        try:
            related = json.loads(str(e)).get("related_orders") or []
        except (ValueError, TypeError):
            related = []
        if len(related) == 1:
            print(f"    {ticker} {side.value} {shares}sh already has an outstanding "
                  f"order ({related[0]}) — adopting it instead of resubmitting.")
            try:
                return client.get_order_by_id(related[0])
            except Exception as lookup_err:
                print(f"    Could not look up existing order {related[0]}: {lookup_err}")
                return None
        print(f"    Order failed ({ticker} {side.value} {shares}sh): {e}")
        return None
    except Exception as e:
        print(f"    Order failed ({ticker} {side.value} {shares}sh): {e}")
        return None


def get_buying_power(client):
    return float(client.get_account().buying_power)


# =============================================================================
# POSITIONS / PENDING-ORDER FILES
# =============================================================================

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return {}


def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)


def load_pending_entries():
    if os.path.exists(PENDING_ENTRIES_FILE):
        with open(PENDING_ENTRIES_FILE) as f:
            return json.load(f)
    return {}


def save_pending_entries(pending):
    with open(PENDING_ENTRIES_FILE, "w") as f:
        json.dump(pending, f, indent=2)


def log_trade(ticker, strategy, entry_date, exit_date, entry_price, exit_price, shares):
    pct_gain = (exit_price - entry_price) / entry_price * 100
    dollar_pnl = (exit_price - entry_price) * shares

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
            "pct_gain":    round(pct_gain, 4),
            "dollar_pnl":  round(dollar_pnl, 2),
        })


# =============================================================================
# RECONCILIATION  (check what a *previous* run's orders actually did)
# =============================================================================

def reconcile_pending_exits(client, positions):
    """For positions awaiting a sell confirmation, checks the real order
    status. Filled -> logs the real trade and drops the position. Expired/
    canceled/rejected -> clears the flag so today's exit scan retries it.
    Still pending -> left alone for the next run to check again."""
    confirmed = []
    for key, pos in positions.items():
        order_id = pos.get("pending_exit_order_id")
        if not order_id:
            continue

        order = client.get_order_by_id(order_id)
        if order.status == OrderStatus.FILLED:
            exit_price = float(order.filled_avg_price)
            exit_date = (order.filled_at.date() if order.filled_at else date.today()).isoformat()
            log_trade(
                ticker=pos["ticker"], strategy=pos["strategy"],
                entry_date=pos["entry_date"], exit_date=exit_date,
                entry_price=pos["entry_price"], exit_price=exit_price,
                shares=pos["shares"],
            )
            print(f"  EXIT CONFIRMED   {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"filled @ ${exit_price:.2f}")
            confirmed.append(key)
        elif order.status in TERMINAL_FAILURE_STATUSES:
            print(f"  EXIT DID NOT FILL  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"order {order.status.value} — retrying today")
            del pos["pending_exit_order_id"]
        else:
            print(f"  EXIT STILL PENDING  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"order {order.status.value}")

    for key in confirmed:
        del positions[key]
    return len(confirmed)


def reconcile_pending_entries(client, pending, positions):
    """For entry orders submitted on a previous run, checks the real order
    status. Filled -> creates the tracked position using the real fill
    price/date. Expired/canceled/rejected -> dropped, never retried
    automatically (that ticker/strategy is simply eligible to signal again
    on a future scan). Still pending -> left alone."""
    resolved = []
    confirmed = 0
    for order_id, info in pending.items():
        order = client.get_order_by_id(order_id)
        if order.status == OrderStatus.FILLED:
            fill_date = (order.filled_at.date() if order.filled_at else date.today())
            entry_price = float(order.filled_avg_price)
            exit_d = (pd.Timestamp(fill_date) + pd.offsets.BDay(info["hold_days"])).strftime("%Y-%m-%d")
            pos_key = f"{info['ticker']}_{info['strategy']}"
            positions[pos_key] = {
                "ticker":      info["ticker"],
                "strategy":    info["strategy"],
                "entry_date":  fill_date.isoformat(),
                "exit_date":   exit_d,
                "shares":      int(float(order.filled_qty)),
                "entry_price": round(entry_price, 2),
            }
            print(f"  ENTRY CONFIRMED  {info['ticker']:6s}  [{info['strategy']}]  "
                  f"filled @ ${entry_price:.2f}  →  exits {exit_d}")
            confirmed += 1
            resolved.append(order_id)
        elif order.status in TERMINAL_FAILURE_STATUSES:
            print(f"  ENTRY DID NOT FILL  {info['ticker']:6s}  [{info['strategy']}]  "
                  f"order {order.status.value}")
            resolved.append(order_id)
        else:
            print(f"  ENTRY STILL PENDING  {info['ticker']:6s}  [{info['strategy']}]  "
                  f"order {order.status.value}")

    for order_id in resolved:
        del pending[order_id]
    return confirmed


# =============================================================================
# MAIN
# =============================================================================

def main():
    today = date.today().isoformat()
    print(f"=== Daily Paper Trader — {today} ===\n")

    client    = make_client()
    positions = load_positions()
    pending   = load_pending_entries()

    # ── Step 0: Reconcile whatever last run's orders actually did ─────────────
    print("── Reconciling Pending Orders ──────────────────────────────────")
    n_exits_confirmed = reconcile_pending_exits(client, positions)
    n_entries_confirmed = reconcile_pending_entries(client, pending, positions)
    if n_exits_confirmed == 0 and n_entries_confirmed == 0:
        still_pending = pending or any("pending_exit_order_id" in p for p in positions.values())
        print("  Nothing new to reconcile." if not still_pending else "  Still waiting on some orders.")
    print()

    # ── Step 1: Submit exits for positions whose hold period has ended ───────
    print("── Exits ──────────────────────────────────────────────────────")

    new_exit_orders = 0
    for key, pos in positions.items():
        if "pending_exit_order_id" in pos:
            print(f"  AWAITING EXIT  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"sell already submitted, not yet confirmed")
            continue
        if today >= pos["exit_date"]:
            print(f"  EXIT  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"{pos['shares']} shares  (entered {pos['entry_date']})")
            order = place_order(client, pos["ticker"], pos["shares"], OrderSide.SELL)
            if order is not None:
                pos["pending_exit_order_id"] = str(order.id)
                new_exit_orders += 1
        else:
            print(f"  HOLD  {pos['ticker']:6s}  [{pos['strategy']}]  "
                  f"exits {pos['exit_date']}")

    if new_exit_orders == 0:
        print("  No new exit orders submitted today.")

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

    new_entry_orders = 0
    data_skipped = 0
    pending_combos = {(info["ticker"], info["strategy"]) for info in pending.values()}

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
            if (ticker, strategy_name) in pending_combos:
                continue  # already have an unconfirmed entry order out for this combo

            if not lib.check_signal_today(df, spec["indicator_type"], spec["params"]):
                continue  # signal did not trigger today

            print(f"  SIGNAL  {ticker:6s}  [{strategy_name:18s}]  "
                  f"${current_price:.2f} × {shares} sh")

            order = place_order(client, ticker, shares, OrderSide.BUY)
            if order is not None:
                pending[str(order.id)] = {
                    "ticker":    ticker,
                    "strategy":  strategy_name,
                    "hold_days": spec["hold_days"],
                }
                pending_combos.add((ticker, strategy_name))
                buying_power    -= POSITION_SIZE
                new_entry_orders += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n── Summary ────────────────────────────────────────────────────")
    print(f"  Entries confirmed this run : {n_entries_confirmed}")
    print(f"  Exits confirmed this run   : {n_exits_confirmed}")
    print(f"  New entry orders submitted : {new_entry_orders}")
    print(f"  New exit orders submitted  : {new_exit_orders}")
    print(f"  Open positions             : {len(positions)}")
    print(f"  Orders still awaiting fill : {len(pending) + sum(1 for p in positions.values() if 'pending_exit_order_id' in p)}")
    print(f"  Buying power left          : ${get_buying_power(client):,.0f}")

    if data_skipped > 0:
        print(f"\n  Note: {data_skipped} tickers skipped — market may be closed today "
              f"or data not yet settled.")

    save_positions(positions)
    save_pending_entries(pending)
    print("\nDone.")


if __name__ == "__main__":
    main()
