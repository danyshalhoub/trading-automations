"""
Multi-Strategy Research Script
================================
Tests 4 distinct trading strategies on the same data to find which —
if any — show a genuine edge that survives an out-of-sample test.

Each strategy has a clear thesis (why it SHOULD work). The cheat-check
(train/test split) determines which ones are real vs. lucky noise.

SAFETY: This is a research tool only. No real trades, no brokerage connection.
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# =============================================================================
# SHARED SETTINGS — same for all strategies so the comparison is fair
# =============================================================================

HOLD_DAYS       = 5       # Trading days to hold before closing
COMMISSION      = 0.001   # Commission per side (0.1%)
SLIPPAGE        = 0.001   # Slippage per side (0.1%)
POSITION_SIZE   = 10_000  # Dollars per trade

START_DATE      = "2019-01-01"
END_DATE        = "2024-12-31"

# Strategy-specific thresholds
SPIKE_THRESHOLD = 0.10    # 10% up day triggers spike strategies
DROP_THRESHOLD  = 0.10    # 10% down day triggers the dip strategy
VOL_HIGH_MULT   = 2.0     # "High volume" = 2× 20-day rolling average
VOL_LOW_MULT    = 0.70    # "Low volume"  = 0.7× 20-day rolling average
VOL_LOOKBACK    = 20      # Days for rolling average volume
HIGH_52W_MIN_PERIODS = 200  # Min days of history needed for 52-week signal

ROUND_TRIP_COST = (COMMISSION + SLIPPAGE) * 2  # Total cost per trade

# Ticker universe (same as backtest.py)
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
    "FROG","STEM","RUN","ARRY","BBBY","WISH","NKLA","RIDE","SMAR","NOVA",
]
ALL_TICKERS = SP500_SAMPLE + VOLATILE_EXTRAS
BENCHMARK   = "SPY"


# =============================================================================
# STRATEGY SIGNAL FUNCTIONS
# Each returns a list of (signal_date, direction) tuples: "long" or "short"
# =============================================================================

def signals_buy_the_dip(df):
    """
    STRATEGY 1: Buy the Dip
    THESIS: When a stock drops 10%+ in a single day, it often overshoots due
    to panic selling. Buyers step in over the next week and the stock partially
    recovers. This is the mirror-image of our failed short-the-spike strategy.
    """
    prev_close = df["Close"].shift(1)
    daily_ret  = (df["Close"] - prev_close) / prev_close
    triggered  = df[daily_ret < -DROP_THRESHOLD].index
    return [(date, "long") for date in triggered]


def signals_volume_confirmed_spike(df):
    """
    STRATEGY 2: Volume-Confirmed Spike (Long)
    THESIS: The original gap-and-go failed because we treated all spikes equally.
    A spike backed by 2x+ normal volume = real institutional buying — fund managers,
    not retail noise. These moves have conviction and are more likely to continue
    because the players who moved it are still holding and buying more.
    """
    prev_close = df["Close"].shift(1)
    daily_ret  = (df["Close"] - prev_close) / prev_close
    avg_vol    = df["Volume"].shift(1).rolling(VOL_LOOKBACK).mean()
    vol_ratio  = df["Volume"] / avg_vol
    triggered  = df[(daily_ret > SPIKE_THRESHOLD) & (vol_ratio > VOL_HIGH_MULT)].index
    return [(date, "long") for date in triggered]


def signals_weak_spike_fade(df):
    """
    STRATEGY 3: Weak Spike Fade (Short)
    THESIS: A stock that jumps 10%+ on BELOW-normal volume is a 'thin' move —
    nobody significant showed up to buy. Low volume spikes lack the fuel to
    sustain. When real sellers return the next day, the price drifts back.
    This refines short-the-spike with a volume filter.
    """
    prev_close = df["Close"].shift(1)
    daily_ret  = (df["Close"] - prev_close) / prev_close
    avg_vol    = df["Volume"].shift(1).rolling(VOL_LOOKBACK).mean()
    vol_ratio  = df["Volume"] / avg_vol
    triggered  = df[(daily_ret > SPIKE_THRESHOLD) & (vol_ratio < VOL_LOW_MULT)].index
    return [(date, "short") for date in triggered]


def signals_52w_high_breakout(df):
    """
    STRATEGY 4: 52-Week High Breakout (Long)
    THESIS: Documented in academic research (George & Hwang 2004) as one of the
    most robust momentum signals. The 52-week high is a psychological anchor —
    when a stock punches through it, it signals that prior resistance is gone.
    Momentum buyers pile in, and the stock tends to keep running in the near term.
    Different from spike strategies: the 52-week high can be broken quietly.
    """
    # Look back at prior 252 trading days only (shift(1) prevents look-ahead bias)
    prior_252_max = df["Close"].shift(1).rolling(252, min_periods=HIGH_52W_MIN_PERIODS).max()
    triggered     = df[df["Close"] > prior_252_max].index
    return [(date, "long") for date in triggered]


# Register all strategies
STRATEGIES = [
    ("Buy the Dip",                  signals_buy_the_dip),
    ("Volume-Confirmed Spike (Long)", signals_volume_confirmed_spike),
    ("Weak Spike Fade (Short)",       signals_weak_spike_fade),
    ("52-Week High Breakout (Long)",  signals_52w_high_breakout),
]


# =============================================================================
# EXECUTION ENGINE
# =============================================================================

def run_strategy_on_ticker(ticker, df, signal_func, start_filter=None, end_filter=None):
    """Generate trades for one strategy on one ticker."""
    df = df.copy()
    if start_filter:
        df = df[df.index >= start_filter]
    if end_filter:
        df = df[df.index <= end_filter]
    if len(df) < max(HOLD_DAYS + 2, 260):
        return []

    signals = signal_func(df)
    trades = []
    last_exit_loc = -1  # cooldown: no overlapping trades on same stock

    for sig_date, direction in signals:
        try:
            sig_loc = df.index.get_loc(sig_date)
        except KeyError:
            continue
        entry_loc = sig_loc + 1
        exit_loc  = entry_loc + HOLD_DAYS

        # Enforce cooldown: skip if still in a prior trade on this stock
        if entry_loc <= last_exit_loc:
            continue
        if exit_loc >= len(df):
            continue

        entry_price = float(df["Open"].iloc[entry_loc])
        exit_price  = float(df["Open"].iloc[exit_loc])
        if entry_price <= 0 or exit_price <= 0:
            continue

        if direction == "long":
            gross_pnl_pct = (exit_price - entry_price) / entry_price
        else:
            gross_pnl_pct = (entry_price - exit_price) / entry_price

        net_pnl_pct    = gross_pnl_pct - ROUND_TRIP_COST
        net_pnl_dollars = net_pnl_pct * POSITION_SIZE

        trades.append({
            "ticker":     ticker,
            "sig_date":   sig_date,
            "entry_date": df.index[entry_loc],
            "exit_date":  df.index[exit_loc],
            "direction":  direction,
            "net_pnl_$":  round(net_pnl_dollars, 2),
            "won":        net_pnl_dollars > 0,
        })
        last_exit_loc = exit_loc

    return trades


def run_strategy(name, signal_func, price_data, start_filter=None, end_filter=None):
    all_trades = []
    for ticker, df in price_data.items():
        all_trades.extend(
            run_strategy_on_ticker(ticker, df, signal_func, start_filter, end_filter)
        )
    return pd.DataFrame(all_trades)


# =============================================================================
# REPORTING
# =============================================================================

def strategy_summary(trades_df):
    """Return a dict of key stats for one strategy."""
    if trades_df.empty:
        return {"trades": 0, "win_pct": 0, "total_pnl": 0,
                "avg_pnl": 0, "worst": 0, "max_dd": 0}

    n       = len(trades_df)
    wins    = trades_df["won"].sum()
    total   = trades_df["net_pnl_$"].sum()
    avg     = trades_df["net_pnl_$"].mean()
    worst   = trades_df["net_pnl_$"].min()
    sorted_ = trades_df.sort_values("entry_date").reset_index(drop=True)
    cum     = sorted_["net_pnl_$"].cumsum()
    mdd     = (cum - cum.cummax()).min()

    return {
        "trades":    n,
        "win_pct":   round(wins / n * 100, 1),
        "total_pnl": round(total, 0),
        "avg_pnl":   round(avg, 2),
        "worst":     round(worst, 2),
        "max_dd":    round(mdd, 0),
    }


def get_benchmark_return(start, end):
    try:
        spy = yf.download(BENCHMARK, start=start, end=end, auto_adjust=True, progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [col[0] for col in spy.columns]
        if len(spy) < 2:
            return None
        return round((float(spy["Close"].iloc[-1]) / float(spy["Close"].iloc[0]) - 1) * 100, 1)
    except Exception:
        return None


def print_strategy_detail(name, full_df, train_df, test_df, train_end):
    print(f"\n{'─'*65}")
    print(f"  {name}")
    print(f"{'─'*65}")
    fs = strategy_summary(full_df)
    ts = strategy_summary(train_df)
    qs = strategy_summary(test_df)

    direction = full_df["direction"].iloc[0] if not full_df.empty else "n/a"
    loss_note = "max loss = position size" if direction == "long" else "unlimited loss possible"

    print(f"  FULL PERIOD ({START_DATE} → {END_DATE})")
    print(f"    Trades: {fs['trades']:,}  |  Win rate: {fs['win_pct']}%  |  "
          f"Total P&L: ${fs['total_pnl']:,.0f}")
    print(f"    Avg/trade: ${fs['avg_pnl']:,.2f}  |  "
          f"Worst trade: ${fs['worst']:,.2f} ({loss_note})")
    print(f"    Max drawdown: ${fs['max_dd']:,.0f}")

    print(f"\n  TRAIN (first half, through {train_end})")
    print(f"    Trades: {ts['trades']:,}  |  Win rate: {ts['win_pct']}%  |  "
          f"Total P&L: ${ts['total_pnl']:,.0f}")

    print(f"\n  TEST (second half — UNSEEN data, {train_end} onward)")
    print(f"    Trades: {qs['trades']:,}  |  Win rate: {qs['win_pct']}%  |  "
          f"Total P&L: ${qs['total_pnl']:,.0f}")

    # Verdict
    tp = ts["total_pnl"]
    qp = qs["total_pnl"]
    if tp > 0 and qp > 0:
        verdict = "✓ SURVIVED CHEAT-CHECK (profitable in both halves)"
    elif tp > 0 and qp <= 0:
        verdict = "✗ FAILED cheat-check (profitable first half only — likely noise)"
    elif tp <= 0:
        verdict = "✗ FAILED in training (no edge to test)"
    else:
        verdict = "? MIXED (unusual — profitable in test but not training)"
    print(f"\n  VERDICT: {verdict}")


def print_comparison_table(results, benchmark_full):
    print("\n\n" + "=" * 65)
    print("  HEAD-TO-HEAD COMPARISON")
    print(f"  Benchmark (SPY buy-and-hold 2019–2024): {benchmark_full}% total return")
    print("=" * 65)
    header = f"  {'Strategy':<35} {'Trades':>6}  {'Win%':>5}  {'Total P&L':>12}  {'Cheat-check':>10}"
    print(header)
    print("  " + "-" * 63)

    for name, full_df, train_df, test_df, _ in results:
        fs = strategy_summary(full_df)
        ts = strategy_summary(train_df)
        qs = strategy_summary(test_df)
        survived = "SURVIVED" if ts["total_pnl"] > 0 and qs["total_pnl"] > 0 else "FAILED"
        pnl_str = f"${fs['total_pnl']:,.0f}"
        print(f"  {name:<35} {fs['trades']:>6,}  {fs['win_pct']:>4}%  {pnl_str:>12}  {survived:>10}")

    print()


# =============================================================================
# DOWNLOAD
# =============================================================================

def download_prices(tickers, start, end):
    print(f"\nDownloading {len(tickers)} tickers ({start} → {end})...")
    all_data = {}
    for i, ticker in enumerate(tickers):
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            if len(df) > 260:
                all_data[ticker] = df
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  ... {i+1}/{len(tickers)} done")
    print(f"  Got usable data for {len(all_data)} tickers.\n")
    return all_data


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 65)
    print("  MULTI-STRATEGY RESEARCH: Which edge is real?")
    print("=" * 65)
    print("""
⚠  REMINDERS:
  • Survivorship bias: failed/delisted companies missing — all results optimistic
  • Borrow fees not modeled for short strategies — real short results worse
  • A strategy that survives the cheat-check is a HYPOTHESIS, not a guarantee
  • This tool cannot and does not place real trades
""")
    print(f"Testing {len(STRATEGIES)} strategies | {len(ALL_TICKERS)} tickers | "
          f"{START_DATE} → {END_DATE}")
    print(f"Cost model: {COMMISSION*100:.1f}% commission + {SLIPPAGE*100:.1f}% slippage each side "
          f"({ROUND_TRIP_COST*100:.1f}% round-trip)\n")

    # Download once, share across all strategies
    price_data = download_prices(ALL_TICKERS, START_DATE, END_DATE)
    if not price_data:
        print("ERROR: No price data. Check internet connection.")
        sys.exit(1)

    # Train/test split
    s = datetime.strptime(START_DATE, "%Y-%m-%d")
    e = datetime.strptime(END_DATE, "%Y-%m-%d")
    mid = (s + (e - s) / 2).strftime("%Y-%m-%d")

    benchmark_full  = get_benchmark_return(START_DATE, END_DATE)
    benchmark_train = get_benchmark_return(START_DATE, mid)
    benchmark_test  = get_benchmark_return(mid, END_DATE)

    print(f"Cheat-check split date: {mid}")
    print(f"Benchmark: SPY full={benchmark_full}% | train={benchmark_train}% | test={benchmark_test}%\n")
    print("Running all strategies...\n")

    results = []
    for name, signal_func in STRATEGIES:
        print(f"  Testing: {name}")
        full_df  = run_strategy(name, signal_func, price_data)
        train_df = run_strategy(name, signal_func, price_data,
                                start_filter=START_DATE, end_filter=mid)
        test_df  = run_strategy(name, signal_func, price_data,
                                start_filter=mid, end_filter=END_DATE)
        results.append((name, full_df, train_df, test_df, mid))
        fs = strategy_summary(full_df)
        ts = strategy_summary(train_df)
        qs = strategy_summary(test_df)
        survived = "SURVIVED" if ts["total_pnl"] > 0 and qs["total_pnl"] > 0 else "FAILED"
        print(f"    → {fs['trades']:,} trades | P&L ${fs['total_pnl']:,.0f} | Cheat-check: {survived}")

    # Detailed results per strategy
    print("\n\n" + "=" * 65)
    print("  DETAILED RESULTS PER STRATEGY")
    print("=" * 65)
    for name, full_df, train_df, test_df, train_end in results:
        print_strategy_detail(name, full_df, train_df, test_df, train_end)

    # Comparison table
    print_comparison_table(results, benchmark_full)

    # Final recommendation
    survivors = [(n, f, tr, te, m) for n, f, tr, te, m in results
                 if strategy_summary(tr)["total_pnl"] > 0
                 and strategy_summary(te)["total_pnl"] > 0]

    print("=" * 65)
    print("  FINAL VERDICT")
    print("=" * 65)
    if survivors:
        print(f"  {len(survivors)} of {len(STRATEGIES)} strategies survived the cheat-check:\n")
        for name, full_df, _, _, _ in survivors:
            fs = strategy_summary(full_df)
            print(f"  ✓ {name}")
            print(f"    {fs['trades']:,} trades | ${fs['total_pnl']:,.0f} total P&L | "
                  f"{fs['win_pct']}% win rate")
        print(f"\n  Note: 'survived' means profitable in both halves — the minimum bar.")
        print(f"  Does not mean it will keep working. Test further before trusting it.")
    else:
        print(f"  No strategies survived the cheat-check.")
        print(f"  All 4 edges appear to be artifacts of specific market conditions,")
        print(f"  not durable rules. This is a normal, honest result.")
        print(f"  Next step: adjust the strategy parameters and re-run, or try new ideas.")

    print("\n" + "=" * 65)
    print("  END OF RESEARCH REPORT")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
