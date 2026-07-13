#!/usr/bin/env python3
"""
Daily Paper Trader
==================
Runs after market close every weekday via GitHub Actions.
Scans 134 US stocks for 4 trading signals and places paper
trades automatically on Alpaca.

Strategies traded:
  1. Buy Dip + 200-Day MA        — hold 5 trading days
  2. 52-Week Low Bounce          — hold 20 trading days
  3. RSI Oversold Bounce         — hold 10 trading days
  4. MACD Bullish Cross (< 0)    — hold 20 trading days

  (Bollinger Band Lower Touch was retired 2026-07-12 after failing its
  train/test cheat-check in the tournament rerun — profitable 2019-2021,
  lost money 2022-2024. Replaced with MACD Bullish Cross, which survived
  the cheat-check in both halves. See round2_strategy_tournament.py.)

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
import numpy as np
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# =============================================================================
# CONFIG
# =============================================================================

POSITION_SIZE = 10_000   # Dollars per trade

HOLD_DAYS = {
    "buy_dip_200ma":    5,
    "52w_low_bounce":   20,
    "rsi_oversold":     10,
    "macd_bull_cross":  20,
}

# positions.json and trade_log.csv live in the same folder as this script
POSITIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "positions.json")
TRADE_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_log.csv")
TRADE_LOG_FIELDS = [
    "ticker", "strategy", "entry_date", "exit_date",
    "entry_price", "exit_price", "shares", "pct_gain", "dollar_pnl",
]

# =============================================================================
# TICKER UNIVERSE (same 134 stocks used in backtests)
# =============================================================================

SP500_SAMPLE = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","JPM","V","UNH",
    "JNJ","PG","XOM","HD","MA","BAC","ABBV","MRK","CVX","PEP",
    "KO","LLY","AVGO","COST","TMO","MCD","CSCO","WMT","DIS","ACN",
    "ABT","CRM","NEE","DHR","VZ","ADBE","NFLX","INTC","TXN","NKE",
    "PM","RTX","QCOM","HON","AMGN","LIN","IBM","SBUX","CAT","GE",
    "BLK","GS","AXP","SPGI","BKNG","MDLZ","ADP","MMM","GILD","MO",
    "TGT","CVS","CI","DE","SYK","ZTS","ISRG","MU","REGN","BDX",
    "EOG","SLB","PLD","AMT","CCI","EQIX","PSA","O","SPG","WELL",
    "F","GM","BA","LMT","NOC","GD","AON","CB","ALL",
    "WFC","USB","PNC","TFC","COF","MS","SCHW","BK","STT","MTB",
]
VOLATILE_EXTRAS = [
    "ROKU","SNAP","UBER","LYFT","PINS","TWLO","DDOG","NET","CRWD","ZS",
    "BILL","AFRM","SOFI","HOOD","RIVN","LCID","COIN","MSTR","AMC","GME",
    "SPCE","WKHS","SKLZ","OPEN","UWMC","CLOV","PLTR","PATH","U","GTLB",
    "FROG","STEM","RUN","ARRY","BBBY","SMAR","NOVA",
]
ALL_TICKERS = SP500_SAMPLE + VOLATILE_EXTRAS


# =============================================================================
# TECHNICAL INDICATORS
# =============================================================================

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df):
    df = df.copy()
    df["ret"]     = df["Close"].pct_change()
    df["ma200"]   = df["Close"].rolling(200).mean()
    df["low_52w"] = df["Close"].shift(1).rolling(252, min_periods=200).min()
    df["rsi"]     = compute_rsi(df["Close"])

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    return df


# =============================================================================
# SIGNAL CHECKERS
# Each checks whether today's (last row's) data triggers the strategy.
# =============================================================================

def check_buy_dip_200ma(df):
    """Drop >10% today AND still above the 200-day moving average."""
    row = df.iloc[-1]
    return bool(row["ret"] < -0.10 and row["Close"] > row["ma200"])


def check_52w_low_bounce(df):
    """Price is within 3% of its 52-week low."""
    row = df.iloc[-1]
    return bool(pd.notna(row["low_52w"]) and row["Close"] <= row["low_52w"] * 1.03)


def check_rsi_oversold(df):
    """RSI(14) drops below 30 — technically oversold."""
    row = df.iloc[-1]
    return bool(pd.notna(row["rsi"]) and row["rsi"] < 30)


def check_macd_bull_cross(df):
    """MACD line crosses above its signal line while still below zero."""
    if len(df) < 2:
        return False
    curr, prev = df.iloc[-1], df.iloc[-2]
    if pd.isna(curr["macd"]) or pd.isna(curr["macd_signal"]) or pd.isna(prev["macd"]) or pd.isna(prev["macd_signal"]):
        return False
    crossed_up = curr["macd"] > curr["macd_signal"] and prev["macd"] <= prev["macd_signal"]
    return bool(crossed_up and curr["macd"] < 0)


STRATEGIES = {
    "buy_dip_200ma":   check_buy_dip_200ma,
    "52w_low_bounce":  check_52w_low_bounce,
    "rsi_oversold":    check_rsi_oversold,
    "macd_bull_cross": check_macd_bull_cross,
}


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

    lookback_start = (
        pd.Timestamp.today() - pd.DateOffset(days=420)
    ).strftime("%Y-%m-%d")

    new_trades   = 0
    data_skipped = 0

    for ticker in ALL_TICKERS:
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

        df            = add_indicators(df)
        current_price = float(df["Close"].iloc[-1])
        if current_price <= 0:
            continue

        shares = int(POSITION_SIZE / current_price)
        if shares < 1:
            continue  # stock price > $10,000 — skip

        for strategy_name, check_fn in STRATEGIES.items():
            pos_key = f"{ticker}_{strategy_name}"

            if pos_key in positions:
                continue  # already holding this ticker/strategy combo

            if not check_fn(df):
                continue  # signal did not trigger today

            # Signal fired — calculate exit date in trading days
            hold   = HOLD_DAYS[strategy_name]
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
