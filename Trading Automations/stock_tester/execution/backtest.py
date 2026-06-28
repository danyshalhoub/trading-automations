"""
Honest Stock Strategy Backtester
=================================
SAFETY NOTICE: This script is a LEARNING TOOL ONLY. It does not and cannot
place real trades. It tests historical data to form a hypothesis — not a
promise — about whether a trading rule would have worked.

SHORTING WARNING: Shorting a stock has theoretically unlimited loss potential.
A stock that "spikes" can keep spiking. Never trade real money based on a
backtest alone.
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

# =============================================================================
# SETTINGS — Change these to experiment
# =============================================================================

DIRECTION         = "long"  # "long"  = buy the spike, profit if price keeps rising (Gap and Go)
                            # "short" = bet against the spike, profit if price falls (Short the Spike)

JUMP_THRESHOLD    = 0.10    # A day's close must be this much above prior close to trigger a trade (0.10 = 10%)
HOLD_DAYS         = 5       # How many trading days to hold before closing
COMMISSION        = 0.001   # Commission per trade, each side (0.001 = 0.1%)
SLIPPAGE          = 0.001   # Slippage per trade, each side (0.001 = 0.1%) — assume we always get a slightly worse price

START_DATE        = "2019-01-01"
END_DATE          = "2024-12-31"
POSITION_SIZE     = 10_000  # Dollars allocated per trade

# Stock universe: S&P 500 large-caps + a basket of more-volatile names (ETFs, growth stocks)
# that are more likely to produce the big daily spikes we're looking for.
# You can add or remove tickers here.
SP500_SAMPLE = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","JPM","V","UNH",
    "JNJ","PG","XOM","HD","MA","BAC","ABBV","MRK","CVX","PEP",
    "KO","LLY","AVGO","COST","TMO","MCD","CSCO","WMT","DIS","ACN",
    "ABT","CRM","NEE","DHR","VZ","ADBE","NFLX","INTC","TXN","NKE",
    "PM","RTX","QCOM","HON","AMGN","LIN","IBM","SBUX","CAT","GE",
    "BLK","GS","AXP","SPGI","BKNG","MDLZ","ADP","MMM","GILD","MO",
    "TGT","CVS","CI","DE","SYK","ZTS","ISRG","MU","REGN","BDX",
    "EOG","SLB","PLD","AMT","CCI","EQIX","PSA","O","SPG","WELL",
    "F","GM","BA","LMT","NOC","GD","MMC","AON","CB","ALL",
    "WFC","USB","PNC","TFC","COF","MS","SCHW","BK","STT","MTB",
]

VOLATILE_EXTRAS = [
    # High-beta / growth names more prone to big single-day moves
    "ROKU","SNAP","UBER","LYFT","PINS","TWLO","DDOG","NET","CRWD","ZS",
    "BILL","AFRM","SOFI","HOOD","RIVN","LCID","COIN","MSTR","AMC","GME",
    "BBBY","SPCE","NKLA","WKHS","SKLZ","OPEN","UWMC","CLOV","WISH","RIDE",
    "PLTR","PATH","U","GTLB","SMAR","FROG","STEM","RUN","NOVA","ARRY",
]

ALL_TICKERS = SP500_SAMPLE + VOLATILE_EXTRAS

# Benchmark
BENCHMARK_TICKER = "SPY"

# =============================================================================
# CONSTANTS — don't touch
# =============================================================================

TOTAL_COST_ENTRY = COMMISSION + SLIPPAGE   # paid as a fraction of entry price
TOTAL_COST_EXIT  = COMMISSION + SLIPPAGE   # paid as a fraction of exit price


# =============================================================================
# Step 1 — Download data
# =============================================================================

def download_prices(tickers, start, end):
    print(f"\nDownloading price data for {len(tickers)} tickers ({start} → {end})...")
    print("This may take a minute.\n")

    all_data = {}
    failed = []
    for i, ticker in enumerate(tickers):
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            # yfinance 1.x returns multi-level columns like ('Close', 'TSLA') — flatten them
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            if len(df) > 100:
                all_data[ticker] = df
        except Exception:
            failed.append(ticker)

        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(tickers)} downloaded")

    print(f"\nSuccess: {len(all_data)} tickers | Failed/skipped: {len(failed)}")
    if failed:
        print(f"  Skipped: {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")
    return all_data


# =============================================================================
# Step 2 + 3 + 4 — Find trades, apply costs, record results
# =============================================================================

def run_backtest(price_data, start_filter=None, end_filter=None):
    """
    For each ticker and each day: if the close jumped > JUMP_THRESHOLD,
    enter a short at next day's open, exit HOLD_DAYS later at open.
    Apply commission and slippage to both entry and exit.
    Returns a DataFrame of all trades.
    """
    trades = []

    for ticker, df in price_data.items():
        df = df.copy()

        # Apply date filter if provided (for train/test split)
        if start_filter:
            df = df[df.index >= start_filter]
        if end_filter:
            df = df[df.index <= end_filter]

        if len(df) < HOLD_DAYS + 2:
            continue

        # Daily return (close-to-close)
        df["prev_close"] = df["Close"].shift(1)
        df["daily_ret"] = (df["Close"] - df["prev_close"]) / df["prev_close"]

        # Find spike days
        spike_days = df[df["daily_ret"] > JUMP_THRESHOLD].index

        for spike_date in spike_days:
            spike_loc = df.index.get_loc(spike_date)

            # Entry: next day's open
            entry_loc = spike_loc + 1
            # Exit: HOLD_DAYS later
            exit_loc  = entry_loc + HOLD_DAYS

            if exit_loc >= len(df):
                continue  # not enough data to complete the trade

            entry_price = df["Open"].iloc[entry_loc]
            exit_price  = df["Open"].iloc[exit_loc]
            entry_date  = df.index[entry_loc]
            exit_date   = df.index[exit_loc]

            if entry_price <= 0 or exit_price <= 0:
                continue

            if DIRECTION == "long":
                # Long P&L: profit when price rises, loss when price falls
                gross_pnl_pct = (exit_price - entry_price) / entry_price
            else:
                # Short P&L: profit when price falls, loss when price rises
                gross_pnl_pct = (entry_price - exit_price) / entry_price

            # Costs: commission + slippage paid on both entry and exit sides
            net_pnl_pct = gross_pnl_pct - TOTAL_COST_ENTRY - TOTAL_COST_EXIT

            # Dollar P&L on this trade
            net_pnl_dollars = net_pnl_pct * POSITION_SIZE

            trades.append({
                "ticker":       ticker,
                "spike_date":   spike_date,
                "entry_date":   entry_date,
                "exit_date":    exit_date,
                "entry_price":  round(entry_price, 4),
                "exit_price":   round(exit_price, 4),
                "gross_pnl_pct": round(gross_pnl_pct * 100, 3),
                "net_pnl_pct":  round(net_pnl_pct * 100, 3),
                "net_pnl_$":    round(net_pnl_dollars, 2),
                "won":          net_pnl_dollars > 0,
            })

    return pd.DataFrame(trades)


# =============================================================================
# Step 5 — Honest reporting
# =============================================================================

def compute_benchmark_return(start, end):
    """Buy-and-hold SPY return over the same period."""
    try:
        spy = yf.download(BENCHMARK_TICKER, start=start, end=end,
                          auto_adjust=True, progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [col[0] for col in spy.columns]
        if len(spy) < 2:
            return None
        start_price = float(spy["Close"].iloc[0])
        end_price   = float(spy["Close"].iloc[-1])
        return (end_price - start_price) / start_price * 100
    except Exception:
        return None


def max_drawdown(cumulative_pnl_series):
    """Largest peak-to-trough drop in cumulative P&L."""
    peak = cumulative_pnl_series.cummax()
    drawdown = cumulative_pnl_series - peak
    return drawdown.min()


def consecutive_losses(trades_df):
    """Longest run of consecutive losing trades."""
    if trades_df.empty:
        return 0
    results = trades_df["won"].tolist()
    max_streak = streak = 0
    for w in results:
        if not w:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def print_report(label, trades_df, period_start, period_end):
    print("\n" + "=" * 65)
    print(f"  RESULTS: {label}")
    print(f"  Period: {period_start}  →  {period_end}")
    print("=" * 65)

    if trades_df.empty:
        print("  No trades fired in this period.")
        return

    n = len(trades_df)
    n_wins = trades_df["won"].sum()
    n_loss = n - n_wins
    win_rate = n_wins / n * 100

    total_pnl = trades_df["net_pnl_$"].sum()
    avg_pnl   = trades_df["net_pnl_$"].mean()
    worst     = trades_df["net_pnl_$"].min()
    best      = trades_df["net_pnl_$"].max()

    trades_df_sorted = trades_df.sort_values("entry_date").reset_index(drop=True)
    cum_pnl = trades_df_sorted["net_pnl_$"].cumsum()
    mdd = max_drawdown(cum_pnl)
    streak = consecutive_losses(trades_df_sorted)

    bm = compute_benchmark_return(period_start, period_end)

    # How much capital would we have deployed total (rough)?
    total_deployed = n * POSITION_SIZE
    total_pnl_pct  = (total_pnl / total_deployed * 100) if total_deployed > 0 else 0

    print(f"  Trades fired:           {n:,}")
    print(f"  Win rate:               {win_rate:.1f}%  ({n_wins:,} wins / {n_loss:,} losses)")
    print(f"  Total net P&L ($):      ${total_pnl:>10,.2f}")
    print(f"  Total deployed ($):     ${total_deployed:>10,.0f}  (${POSITION_SIZE:,}/trade × {n:,} trades)")
    print(f"  Return on deployed:     {total_pnl_pct:.2f}%")
    print(f"  Avg P&L per trade ($):  ${avg_pnl:,.2f}")
    print(f"  Best single trade ($):  ${best:,.2f}")
    loss_note = "max loss = full position" if DIRECTION == "long" else "shorting has no ceiling on loss"
    print(f"\n  ⚠  WORST SINGLE TRADE:  ${worst:,.2f}  ← {loss_note}")
    print(f"  Max drawdown:           ${mdd:,.2f}  ← deepest account drop from a peak")
    print(f"  Longest losing streak:  {streak} trades in a row")

    if bm is not None:
        print(f"\n  Benchmark (SPY buy-and-hold): {bm:.1f}% total return over same period")
        verdict = "BEATS" if total_pnl_pct > bm else "TRAILS"
        print(f"  Strategy vs benchmark:        {verdict} the market")
        if verdict == "TRAILS":
            print("  → You'd have done better just buying SPY and doing nothing.")
    else:
        print("\n  (Could not fetch benchmark data)")


# =============================================================================
# Step 6 — Train / Test split (the cheat-check)
# =============================================================================

def train_test_split_dates(start, end):
    """Split the date range in half."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    mid = s + (e - s) / 2
    mid_str = mid.strftime("%Y-%m-%d")
    return start, mid_str, mid_str, end


# =============================================================================
# Main
# =============================================================================

def main():
    strategy_name = "GAP AND GO (Buy the Spike)" if DIRECTION == "long" else "SHORT THE SPIKE (Bet Against the Spike)"
    print("=" * 65)
    print("  HONEST STOCK STRATEGY BACKTESTER")
    print(f"  Strategy: {strategy_name}")
    print("=" * 65)

    # Print safety warnings — always
    if DIRECTION == "short":
        borrow_notice = """
2. BORROW FEES NOT MODELED: Real short-selling requires borrowing shares
   and paying a daily "borrow fee," which can be 1–10%+ per year for
   heavily-shorted or hard-to-borrow stocks. This tool does not charge
   those fees. Real results would be measurably worse than shown here.
"""
    else:
        borrow_notice = """
2. LONG TRADES: Buying a stock limits your loss to what you put in (the
   stock can only go to $0). This is safer than shorting in terms of
   downside, but big spikes can still reverse sharply against you.
"""

    print(f"""
⚠  SAFETY NOTICES (read before interpreting results):

1. SURVIVORSHIP BIAS: yfinance only shows stocks that still exist today.
   Companies that went bankrupt or were delisted during this period are
   missing. This makes every backtest look better than real life would have
   been. Treat results as optimistic estimates.
{borrow_notice}
3. THIS IS NOT FINANCIAL ADVICE. A backtest is a hypothesis about the past,
   not a promise about the future. Most trading edges disappear once they
   are widely known.

4. NO REAL TRADES: This tool cannot and does not connect to any brokerage.
   Never trade real money based on a backtest alone.
""")

    direction_label = "BUY (go long)" if DIRECTION == "long" else "SELL SHORT"
    print(f"Settings in use:")
    print(f"  Direction:        {direction_label}")
    print(f"  Jump threshold:   {JUMP_THRESHOLD*100:.0f}% daily gain triggers the trade")
    print(f"  Hold period:      {HOLD_DAYS} trading days")
    print(f"  Commission:       {COMMISSION*100:.2f}% per side ({COMMISSION*2*100:.2f}% round-trip)")
    print(f"  Slippage:         {SLIPPAGE*100:.2f}% per side ({SLIPPAGE*2*100:.2f}% round-trip)")
    print(f"  Position size:    ${POSITION_SIZE:,} per trade")
    print(f"  Date range:       {START_DATE} → {END_DATE}")
    print(f"  Universe:         {len(ALL_TICKERS)} tickers")

    # Download data
    price_data = download_prices(ALL_TICKERS, START_DATE, END_DATE)

    if not price_data:
        print("\nERROR: No price data downloaded. Check your internet connection.")
        sys.exit(1)

    # Full backtest
    print("\nRunning backtest across all dates...")
    all_trades = run_backtest(price_data)
    print_report("FULL PERIOD", all_trades, START_DATE, END_DATE)

    # Train/test split
    train_start, train_end, test_start, test_end = train_test_split_dates(START_DATE, END_DATE)
    mid_str = train_end

    print(f"\n\nTHE CHEAT-CHECK: Train / Test Split at {mid_str}")
    print("The rule is built on the FIRST half. Then run UNCHANGED on the SECOND half.")
    print("If it only works on the first half, the edge was fake.\n")

    train_trades = run_backtest(price_data, start_filter=train_start, end_filter=train_end)
    test_trades  = run_backtest(price_data, start_filter=test_start,  end_filter=test_end)

    print_report("TRAIN (first half — seen data)", train_trades, train_start, train_end)
    print_report("TEST  (second half — unseen data)", test_trades, test_start, test_end)

    # Verdict
    print("\n" + "=" * 65)
    print("  CHEAT-CHECK VERDICT")
    print("=" * 65)
    if not train_trades.empty and not test_trades.empty:
        train_pnl = train_trades["net_pnl_$"].sum()
        test_pnl  = test_trades["net_pnl_$"].sum()
        if train_pnl > 0 and test_pnl > 0:
            print("  SURVIVED: Strategy was profitable in BOTH halves.")
            print("  This is the minimum bar for taking an idea seriously.")
            print("  Still: past performance does not guarantee future results.")
        elif train_pnl > 0 and test_pnl <= 0:
            print("  FAILED: Profitable in the first half, UNPROFITABLE in the second.")
            print("  This is the classic overfitting signature. The 'edge' was an artifact")
            print("  of the specific market conditions in the training period.")
            print("  Do NOT trade this rule with real money.")
        elif train_pnl <= 0:
            print("  FAILED IN TRAINING: The strategy lost money even on the data")
            print("  it was meant to look good on. It has no identifiable edge.")
        else:
            print("  MIXED: Unprofitable in training, profitable in testing.")
            print("  This is statistically unusual and likely coincidence.")
    else:
        print("  Not enough trades in one or both halves to assess.")

    print("\n" + "=" * 65)
    print("  END OF REPORT")
    print("  Remember: change settings at the top of backtest.py and re-run.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
