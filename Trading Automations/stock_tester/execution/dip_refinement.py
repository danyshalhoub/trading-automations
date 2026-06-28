"""
Buy the Dip — Refinement Research
===================================
The base "Buy the Dip" (>10% drop, hold 5 days) survived the cheat-check.
This script tries to sharpen the edge by testing:

  Phase 1 — Parameter grid: which threshold and hold period work best?
  Phase 2 — Filters: does adding conditions make it stronger?
             • 200-day MA filter  (only buy if stock is in an uptrend)
             • High-volume filter (only buy if panic selling backed by high volume)
             • Market regime     (only buy when SPY itself is in an uptrend)
  Phase 3 — Best combo: combine the best threshold + best filters

The cheat-check (train/test split) is applied to EVERY combination.
A result that only looks good on the full period but fails the split is discarded.

SAFETY: Learning tool only. No real trades. No brokerage connection.
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from itertools import product

# =============================================================================
# SETTINGS
# =============================================================================

START_DATE    = "2019-01-01"
END_DATE      = "2024-12-31"
POSITION_SIZE = 10_000
COMMISSION    = 0.001
SLIPPAGE      = 0.001
ROUND_TRIP    = (COMMISSION + SLIPPAGE) * 2

# Phase 1 grid
TEST_THRESHOLDS  = [0.05, 0.07, 0.10, 0.15]   # drop % that triggers a trade
TEST_HOLD_DAYS   = [3, 5, 10]                   # days to hold before exiting

# Phase 2 filter settings
MA_LONG        = 200   # "is stock in uptrend?" — close must be above 200-day MA
VOL_PANIC_MULT = 1.5   # "was the sell-off real?" — volume > 1.5x 20-day average
SPY_MA_SHORT   = 50    # "is the market healthy?" — SPY must be above its 50-day MA

# Ticker universe
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
    "FROG","STEM","RUN","ARRY",
]
ALL_TICKERS = SP500_SAMPLE + VOLATILE_EXTRAS
BENCHMARK   = "SPY"


# =============================================================================
# DATA DOWNLOAD
# =============================================================================

def download_prices(tickers, start, end):
    print(f"Downloading {len(tickers)} tickers ({start} → {end})...")
    data = {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            if len(df) > 260:
                data[t] = df
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  ... {i+1}/{len(tickers)}")
    print(f"  Usable: {len(data)} tickers\n")
    return data


def download_spy(start, end):
    df = yf.download(BENCHMARK, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    df[f"spy_ma{SPY_MA_SHORT}"] = df["Close"].rolling(SPY_MA_SHORT).mean()
    df["spy_uptrend"] = df["Close"] > df[f"spy_ma{SPY_MA_SHORT}"]
    return df


# =============================================================================
# TRADE ENGINE
# =============================================================================

def get_trades(ticker, df, spy_df,
               threshold, hold_days,
               use_ma_filter, use_vol_filter, use_spy_filter,
               start_filter=None, end_filter=None):
    """
    Returns list of trade P&L dicts for one ticker under one configuration.
    Filters applied:
      use_ma_filter  — stock close must be above its MA_LONG-day moving average
      use_vol_filter — today's volume must be > VOL_PANIC_MULT × 20-day avg volume
      use_spy_filter — SPY must be above its 50-day MA on the signal day
    """
    df = df.copy()
    if start_filter:
        df = df[df.index >= start_filter]
    if end_filter:
        df = df[df.index <= end_filter]
    if len(df) < hold_days + MA_LONG + 5:
        return []

    # Pre-compute indicators
    df["prev_close"] = df["Close"].shift(1)
    df["daily_ret"]  = (df["Close"] - df["prev_close"]) / df["prev_close"]
    df[f"ma{MA_LONG}"] = df["Close"].rolling(MA_LONG).mean()
    df["avg_vol20"]  = df["Volume"].shift(1).rolling(20).mean()
    df["vol_ratio"]  = df["Volume"] / df["avg_vol20"]

    # Base signal: dropped more than threshold
    mask = df["daily_ret"] < -threshold

    # Optional filters
    if use_ma_filter:
        mask = mask & (df["Close"] > df[f"ma{MA_LONG}"])

    if use_vol_filter:
        mask = mask & (df["vol_ratio"] > VOL_PANIC_MULT)

    signal_dates = df[mask].index
    trades = []
    last_exit_loc = -1

    for sig_date in signal_dates:
        # Market regime filter: check SPY on signal day
        if use_spy_filter and spy_df is not None:
            if sig_date in spy_df.index:
                if not spy_df.loc[sig_date, "spy_uptrend"]:
                    continue
            else:
                continue

        try:
            sig_loc = df.index.get_loc(sig_date)
        except KeyError:
            continue

        entry_loc = sig_loc + 1
        exit_loc  = entry_loc + hold_days

        if entry_loc <= last_exit_loc:
            continue
        if exit_loc >= len(df):
            continue

        entry_price = float(df["Open"].iloc[entry_loc])
        exit_price  = float(df["Open"].iloc[exit_loc])
        if entry_price <= 0 or exit_price <= 0:
            continue

        gross  = (exit_price - entry_price) / entry_price
        net    = gross - ROUND_TRIP
        pnl    = net * POSITION_SIZE

        trades.append({
            "ticker":     ticker,
            "entry_date": df.index[entry_loc],
            "net_pnl_$":  round(pnl, 2),
            "won":        pnl > 0,
        })
        last_exit_loc = exit_loc

    return trades


def run_config(price_data, spy_df, threshold, hold_days,
               use_ma, use_vol, use_spy,
               start_filter=None, end_filter=None):
    all_trades = []
    for ticker, df in price_data.items():
        all_trades.extend(
            get_trades(ticker, df, spy_df, threshold, hold_days,
                       use_ma, use_vol, use_spy, start_filter, end_filter)
        )
    return pd.DataFrame(all_trades) if all_trades else pd.DataFrame()


# =============================================================================
# STATS
# =============================================================================

def stats(df):
    if df.empty:
        return dict(n=0, win_pct=0, total=0, avg=0, worst=0, mdd=0)
    n    = len(df)
    wins = df["won"].sum()
    tot  = df["net_pnl_$"].sum()
    avg  = df["net_pnl_$"].mean()
    wst  = df["net_pnl_$"].min()
    cum  = df.sort_values("entry_date")["net_pnl_$"].cumsum()
    mdd  = (cum - cum.cummax()).min()
    return dict(n=n, win_pct=round(wins/n*100,1), total=round(tot,0),
                avg=round(avg,2), worst=round(wst,2), mdd=round(mdd,0))


def cheat_check_label(train_total, test_total):
    if train_total > 0 and test_total > 0:
        return "SURVIVED"
    elif train_total > 0 and test_total <= 0:
        return "FAILED (test)"
    elif train_total <= 0:
        return "FAILED (train)"
    else:
        return "MIXED"


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("  BUY THE DIP — REFINEMENT RESEARCH")
    print("=" * 70)
    print("""
⚠  Survivorship bias applies. Borrow fees not modeled. Not financial advice.
   This tool cannot place real trades.
""")

    price_data = download_prices(ALL_TICKERS, START_DATE, END_DATE)
    spy_df     = download_spy(START_DATE, END_DATE)
    if not price_data:
        print("ERROR: No data downloaded.")
        sys.exit(1)

    # Train/test split
    s   = datetime.strptime(START_DATE, "%Y-%m-%d")
    e   = datetime.strptime(END_DATE, "%Y-%m-%d")
    mid = (s + (e - s) / 2).strftime("%Y-%m-%d")
    print(f"Cheat-check split: {mid}\n")

    # -------------------------------------------------------------------------
    # PHASE 1 — Parameter grid: threshold × hold days, no filters
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("  PHASE 1: Parameter Grid (no filters)")
    print("  Finding which drop threshold and hold period work best")
    print("=" * 70)
    header = f"  {'Threshold':>10}  {'Hold':>5}  {'Trades':>7}  {'Win%':>5}  {'Total P&L':>11}  {'Avg/Trade':>10}  {'Cheat-check':>13}"
    print(header)
    print("  " + "-" * 68)

    phase1_results = []
    for threshold, hold_days in product(TEST_THRESHOLDS, TEST_HOLD_DAYS):
        full  = run_config(price_data, spy_df, threshold, hold_days, False, False, False)
        train = run_config(price_data, spy_df, threshold, hold_days, False, False, False,
                           start_filter=START_DATE, end_filter=mid)
        test  = run_config(price_data, spy_df, threshold, hold_days, False, False, False,
                           start_filter=mid, end_filter=END_DATE)
        fs = stats(full); ts = stats(train); qs = stats(test)
        label = cheat_check_label(ts["total"], qs["total"])
        phase1_results.append((threshold, hold_days, fs, ts, qs, label))
        mark = "✓" if label == "SURVIVED" else " "
        print(f" {mark}  {threshold*100:>8.0f}%  {hold_days:>5}d  {fs['n']:>7,}  "
              f"{fs['win_pct']:>4}%  ${fs['total']:>10,.0f}  "
              f"${fs['avg']:>9,.2f}  {label:>13}")

    # -------------------------------------------------------------------------
    # PHASE 2 — Filters (applied to baseline: 10% drop, 5 days)
    # -------------------------------------------------------------------------
    print("\n\n" + "=" * 70)
    print("  PHASE 2: Filter Testing (baseline: 10% drop, 5-day hold)")
    print("  Testing whether additional conditions strengthen the edge")
    print("=" * 70)

    filter_configs = [
        ("No filter (baseline)",                         False, False, False),
        ("200-day MA filter only",                       True,  False, False),
        ("High-volume filter only",                      False, True,  False),
        ("SPY uptrend filter only",                      False, False, True),
        ("200-day MA + high volume",                     True,  True,  False),
        ("200-day MA + SPY uptrend",                     True,  False, True),
        ("High volume + SPY uptrend",                    False, True,  True),
        ("All three filters combined",                   True,  True,  True),
    ]

    BASE_THRESHOLD = 0.10
    BASE_HOLD      = 5

    filter_results = []
    header2 = f"  {'Filter Config':<38}  {'Trades':>7}  {'Win%':>5}  {'Total P&L':>11}  {'Avg/Trade':>10}  {'Cheat-check':>13}"
    print(header2)
    print("  " + "-" * 88)

    for fname, use_ma, use_vol, use_spy in filter_configs:
        full  = run_config(price_data, spy_df, BASE_THRESHOLD, BASE_HOLD,
                           use_ma, use_vol, use_spy)
        train = run_config(price_data, spy_df, BASE_THRESHOLD, BASE_HOLD,
                           use_ma, use_vol, use_spy,
                           start_filter=START_DATE, end_filter=mid)
        test  = run_config(price_data, spy_df, BASE_THRESHOLD, BASE_HOLD,
                           use_ma, use_vol, use_spy,
                           start_filter=mid, end_filter=END_DATE)
        fs = stats(full); ts = stats(train); qs = stats(test)
        label = cheat_check_label(ts["total"], qs["total"])
        filter_results.append((fname, fs, ts, qs, label, use_ma, use_vol, use_spy))
        mark = "✓" if label == "SURVIVED" else " "
        print(f" {mark}  {fname:<38}  {fs['n']:>7,}  {fs['win_pct']:>4}%  "
              f"${fs['total']:>10,.0f}  ${fs['avg']:>9,.2f}  {label:>13}")

    # -------------------------------------------------------------------------
    # PHASE 3 — Best combination
    # Pick the best surviving threshold/hold from Phase 1, then apply the
    # filter combo that most improves avg P&L per trade (also must survive)
    # -------------------------------------------------------------------------
    print("\n\n" + "=" * 70)
    print("  PHASE 3: Best Combination")
    print("=" * 70)

    surviving_params = [(t, h, fs, ts, qs) for t, h, fs, ts, qs, l in phase1_results
                        if l == "SURVIVED"]
    surviving_filters = [(fn, fs, ts, qs, uma, uvol, uspy)
                         for fn, fs, ts, qs, l, uma, uvol, uspy in filter_results
                         if l == "SURVIVED"]

    if not surviving_params:
        print("  No parameter combinations survived Phase 1. Cannot proceed to Phase 3.")
        best_t, best_h = BASE_THRESHOLD, BASE_HOLD
    else:
        best_param = max(surviving_params, key=lambda x: x[2]["avg"])
        best_t, best_h = best_param[0], best_param[1]
        print(f"  Best surviving parameters from Phase 1: "
              f"{best_t*100:.0f}% drop threshold, {best_h}-day hold")

    if not surviving_filters:
        print("  No filter configs survived Phase 2.")
        best_uma, best_uvol, best_uspy = False, False, False
        best_filter_name = "No filter"
    else:
        best_filt = max(surviving_filters, key=lambda x: x[1]["avg"])
        best_filter_name, _, _, _, best_uma, best_uvol, best_uspy = best_filt
        print(f"  Best surviving filter from Phase 2: {best_filter_name}")

    print(f"\n  Running best combination: {best_t*100:.0f}% drop | "
          f"{best_h}-day hold | {best_filter_name}\n")

    best_full  = run_config(price_data, spy_df, best_t, best_h,
                            best_uma, best_uvol, best_uspy)
    best_train = run_config(price_data, spy_df, best_t, best_h,
                            best_uma, best_uvol, best_uspy,
                            start_filter=START_DATE, end_filter=mid)
    best_test  = run_config(price_data, spy_df, best_t, best_h,
                            best_uma, best_uvol, best_uspy,
                            start_filter=mid, end_filter=END_DATE)

    bf = stats(best_full); bt = stats(best_train); bq = stats(best_test)
    label = cheat_check_label(bt["total"], bq["total"])

    print(f"  FULL PERIOD ({START_DATE} → {END_DATE})")
    print(f"    Trades: {bf['n']:,}  |  Win rate: {bf['win_pct']}%")
    print(f"    Total P&L: ${bf['total']:,.0f}  |  Avg per trade: ${bf['avg']:,.2f}")
    print(f"    Worst trade: ${bf['worst']:,.2f}  |  Max drawdown: ${bf['mdd']:,.0f}")
    print(f"\n  TRAIN (through {mid})")
    print(f"    Trades: {bt['n']:,}  |  Win%: {bt['win_pct']}%  |  P&L: ${bt['total']:,.0f}")
    print(f"\n  TEST (unseen: {mid} → {END_DATE})")
    print(f"    Trades: {bq['n']:,}  |  Win%: {bq['win_pct']}%  |  P&L: ${bq['total']:,.0f}")
    print(f"\n  CHEAT-CHECK: {label}")

    # -------------------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------------------
    print("\n\n" + "=" * 70)
    print("  FINAL SUMMARY")
    print("=" * 70)

    all_survivors = [(t, h, fs, l)
                     for t, h, fs, ts, qs, l in phase1_results if l == "SURVIVED"]

    if all_survivors:
        print(f"\n  Surviving parameter combinations (Phase 1):")
        for t, h, fs, l in all_survivors:
            print(f"    {t*100:.0f}% drop / {h}-day hold → "
                  f"{fs['n']:,} trades | ${fs['total']:,.0f} total | ${fs['avg']:,.2f}/trade")

    if surviving_filters:
        print(f"\n  Surviving filter configurations (Phase 2):")
        for fn, fs, ts, qs, _, _, _ in surviving_filters:
            print(f"    {fn} → {fs['n']:,} trades | ${fs['total']:,.0f} total | "
                  f"${fs['avg']:,.2f}/trade")

    print(f"\n  Best combination tested:")
    print(f"    Rule:    Buy when stock drops >{best_t*100:.0f}% in one day")
    print(f"    Filter:  {best_filter_name}")
    print(f"    Hold:    {best_h} trading days, then sell")
    print(f"    Result:  {bf['n']:,} trades | ${bf['total']:,.0f} total P&L | "
          f"${bf['avg']:,.2f}/trade | Cheat-check: {label}")

    print(f"""
  KEY LIMITATIONS (always keep these in mind):
  1. Still trails SPY buy-and-hold by a wide margin
  2. Survivorship bias makes all results optimistic
  3. Avg profit per trade is small — real friction costs can erase it
  4. Past performance does not guarantee future results
""")
    print("=" * 70)
    print("  END OF REFINEMENT REPORT")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
