"""
10-Strategy Tournament — Honest Backtester
============================================
Tests 10 distinct trading hypotheses on ~140 US stocks (2019-2024).

Cheat-check rule: a strategy must be profitable in BOTH the training half
(2019-2021) AND the test half (2022-2024) to be considered real.
If it only works in the training half, it is likely curve-fitted noise.

SAFETY: This is a research tool only. It never places real trades or
connects to any brokerage. Past results are not a promise about the future.
Survivorship bias warning: yfinance only includes stocks still trading today.
Bankrupt/delisted companies are missing, which makes all results look better
than they would have been in real life.
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import yfinance as yf

# =============================================================================
# SETTINGS
# =============================================================================

COMMISSION      = 0.001    # 0.1% per side
SLIPPAGE        = 0.001    # 0.1% per side
POSITION_SIZE   = 10_000   # Dollars per trade
ROUND_TRIP_COST = (COMMISSION + SLIPPAGE) * 2

START_DATE      = "2019-01-01"
END_DATE        = "2024-12-31"
TRAIN_CUTOFF    = "2021-12-31"   # Cheat-check split date

# Minimum trades for a strategy to be considered statistically meaningful
MIN_TRADES_TO_SURVIVE = 50

# =============================================================================
# TICKER UNIVERSE (~140 stocks — same as other scripts)
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
    "FROG","STEM","RUN","ARRY","BBBY","WISH","NKLA","RIDE","SMAR","NOVA",
]
ALL_TICKERS = SP500_SAMPLE + VOLATILE_EXTRAS
BENCHMARK   = "SPY"


# =============================================================================
# TECHNICAL INDICATORS
# All computed once per ticker so every strategy can share them efficiently.
# =============================================================================

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df):
    df = df.copy()

    df["ret"]       = df["Close"].pct_change()
    df["ma20"]      = df["Close"].rolling(20).mean()
    df["ma50"]      = df["Close"].rolling(50).mean()
    df["ma200"]     = df["Close"].rolling(200).mean()
    df["vol20"]     = df["Volume"].rolling(20).mean()
    df["vol_ratio"] = df["Volume"] / df["vol20"].replace(0, np.nan)

    # Bollinger Bands (20-day, 2 standard deviations)
    bb_std          = df["Close"].rolling(20).std()
    df["bb_lower"]  = df["ma20"] - 2 * bb_std
    df["bb_upper"]  = df["ma20"] + 2 * bb_std

    # RSI(14)
    df["rsi"] = compute_rsi(df["Close"])

    # 52-week high and low — shift(1) removes look-ahead bias
    df["high_52w"] = df["Close"].shift(1).rolling(252, min_periods=200).max()
    df["low_52w"]  = df["Close"].shift(1).rolling(252, min_periods=200).min()

    # 20-day high — shift(1) removes look-ahead bias
    df["high_20d"] = df["Close"].shift(1).rolling(20, min_periods=15).max()

    # Intraday position: 1.0 = closed at high, 0.0 = closed at low
    day_range       = (df["High"] - df["Low"]).replace(0, np.nan)
    df["intra_pos"] = (df["Close"] - df["Low"]) / day_range

    # MA crossover signals (fires only on the cross day itself)
    above_200       = df["ma50"] > df["ma200"]
    df["golden_x"]  = above_200 & (~above_200.shift(1).fillna(True))   # just crossed above
    df["death_x"]   = (~above_200) & (above_200.shift(1).fillna(False)) # just crossed below

    # Consecutive down days (rolling 3 — all three including today must be red)
    df["consec_dn"] = (df["ret"] < 0).astype(int).rolling(3).sum()

    # Gap-down open vs prior close
    df["gap_pct"]   = (df["Open"] / df["Close"].shift(1)) - 1

    return df


# =============================================================================
# THE 10 STRATEGIES
# Each entry: name, hold_days, direction, plain-english thesis, signal function.
# Signal functions return a list of signal dates (the day the rule fires).
# Entry happens at the OPEN of the following day (realistic: you see the
# close-of-day signal and enter the next morning).
# =============================================================================

def sig_buy_dip_200ma(df):
    """
    1. Buy the Dip + 200-Day MA Filter
    Our best survivor from the last research session. A stock drops >10% in
    one day — but only buy if it's still above its 200-day moving average.
    That filter removes 'falling knives' (stocks already in a downtrend) and
    keeps only genuine panic dips inside a healthy uptrend.
    """
    mask = (df["ret"] < -0.10) & (df["Close"] > df["ma200"])
    return df.index[mask].tolist()


def sig_rsi_oversold(df):
    """
    2. RSI Oversold Bounce
    RSI (Relative Strength Index) measures how 'overbought' or 'oversold'
    a stock is on a 0-100 scale. Below 30 is the classic 'oversold' zone —
    the stock has fallen so fast that a short-term bounce is statistically
    likely. This is one of the most widely taught signals in technical analysis.
    """
    mask = df["rsi"] < 30
    return df.index[mask].tolist()


def sig_bb_lower_touch(df):
    """
    3. Bollinger Band Lower-Band Touch
    Bollinger Bands surround price with a channel: the middle is the 20-day
    average, and the bands are 2 standard deviations above/below. Price
    touches the lower band fewer than 5% of the time. The thesis: when
    price is that far from its average, it tends to snap back (mean reversion).
    """
    mask = df["Close"] < df["bb_lower"]
    return df.index[mask].tolist()


def sig_three_red_days(df):
    """
    4. Three Consecutive Down Days
    Three losing days in a row creates a psychological low — retail panic
    peaks, stop-losses have triggered, and the marginal seller has already
    sold. Buyers are statistically more likely to show up on day 4.
    Simple, well-known, and easy to execute.
    """
    mask = df["consec_dn"] >= 3
    return df.index[mask].tolist()


def sig_52w_low_bounce(df):
    """
    5. 52-Week Low Bounce
    The mirror image of the 52-week high breakout (which we tested and failed
    last time). A stock at its 52-week low is universally hated — max bearish
    sentiment, max media negativity. Contrarian thesis: extreme pessimism is
    often overdone, and the stock is priced for catastrophe even when the
    underlying business just had a bad quarter.
    Hold 20 days to give the bounce time to play out.
    """
    mask = (df["Close"] <= df["low_52w"] * 1.03) & df["low_52w"].notna()
    return df.index[mask].tolist()


def sig_high_volume_hammer(df):
    """
    6. High-Volume Hammer (Intraday Reversal)
    The stock drops >3% intraday, big volume (>1.5x normal) shows up, BUT
    the stock closes in the top 30% of the day's range. This is the 'hammer'
    candlestick pattern: sellers showed up, buyers overwhelmed them, and the
    stock closed near its high for the day. High volume + intraday reversal
    = real institutional buying stepping in.
    """
    mask = (
        (df["ret"] < -0.03)
        & (df["vol_ratio"] > 1.5)
        & (df["intra_pos"] > 0.70)
    )
    return df.index[mask].tolist()


def sig_golden_cross(df):
    """
    7. Golden Cross Entry
    The 50-day moving average crosses above the 200-day moving average.
    This is one of Wall Street's most-cited bullish signals — it shows
    that short-term momentum has shifted above the long-term trend.
    Major financial media cover every Golden Cross on the S&P 500.
    The question: is this actually predictive, or is it too widely known
    to have edge? We hold 30 days to capture the alleged follow-through.
    """
    return df.index[df["golden_x"]].tolist()


def sig_death_cross_short(df):
    """
    8. Death Cross Short
    The 50-day MA crosses below the 200-day MA — the exact opposite of the
    Golden Cross. Wall Street treats this as a major bearish signal.
    If the Golden Cross doesn't work, maybe the Death Cross does on the
    short side? We go short for 20 days after the cross fires.
    WARNING: Short-selling has theoretically unlimited loss if the stock
    keeps rising. This is tested only as a research exercise.
    """
    return df.index[df["death_x"]].tolist()


def sig_20d_breakout(df):
    """
    9. 20-Day High Breakout (Short-Term Momentum)
    When a stock closes above its highest price of the prior 20 trading days,
    it's breaking out of a recent range. Shorter time horizon than the 52-week
    breakout (which failed). Theory: short-term momentum traders pile in after
    a clean breakout, creating follow-through in the next 1-2 weeks.
    """
    mask = (df["Close"] > df["high_20d"]) & df["high_20d"].notna()
    return df.index[mask].tolist()


def sig_gap_down_recovery(df):
    """
    10. Gap-Down Recovery
    The stock opens more than 5% below yesterday's close (a 'gap down' —
    scary pre-market news or earnings miss), but then closes ABOVE where it
    opened that same day. This means buyers absorbed all the panic selling
    at the open and pushed the stock back up during the day. Institutional
    'buy the bad news' behavior. Hold 5 days.
    """
    mask = (df["gap_pct"] < -0.05) & (df["Close"] > df["Open"])
    return df.index[mask].tolist()


STRATEGIES = [
    # (display name,                   hold_days, direction, signal_fn)
    ("1. Buy Dip + 200-Day MA",         5,  "long",  sig_buy_dip_200ma),
    ("2. RSI Oversold Bounce",          10, "long",  sig_rsi_oversold),
    ("3. Bollinger Band Lower Touch",   10, "long",  sig_bb_lower_touch),
    ("4. Three Consecutive Down Days",   5, "long",  sig_three_red_days),
    ("5. 52-Week Low Bounce",           20, "long",  sig_52w_low_bounce),
    ("6. High-Volume Hammer",            5, "long",  sig_high_volume_hammer),
    ("7. Golden Cross Entry",           30, "long",  sig_golden_cross),
    ("8. Death Cross Short",            20, "short", sig_death_cross_short),
    ("9. 20-Day High Breakout",         10, "long",  sig_20d_breakout),
    ("10. Gap-Down Recovery",            5, "long",  sig_gap_down_recovery),
]


# =============================================================================
# EXECUTION ENGINE
# =============================================================================

def run_strategy_on_ticker(ticker, df, hold_days, direction, signal_fn):
    """Run one strategy on one ticker's full history. Returns list of trade dicts."""
    df = df.copy()
    # Need enough history for 200-day MA + some buffer
    if len(df) < 260:
        return []

    df = add_indicators(df)
    signals = signal_fn(df)

    trades        = []
    last_exit_loc = -1  # no overlapping trades on the same stock

    for sig_date in signals:
        try:
            sig_loc = df.index.get_loc(sig_date)
        except KeyError:
            continue

        entry_loc = sig_loc + 1           # enter at next day's open
        exit_loc  = entry_loc + hold_days # exit hold_days later at open

        if entry_loc <= last_exit_loc:    # still in a prior trade on this ticker
            continue
        if exit_loc >= len(df):           # not enough data to exit
            continue

        entry_price = float(df["Open"].iloc[entry_loc])
        exit_price  = float(df["Open"].iloc[exit_loc])
        if entry_price <= 0 or exit_price <= 0:
            continue

        if direction == "long":
            gross_pct = (exit_price - entry_price) / entry_price
        else:
            gross_pct = (entry_price - exit_price) / entry_price

        net_pct = gross_pct - ROUND_TRIP_COST
        net_pnl = net_pct * POSITION_SIZE

        trades.append({
            "ticker":     ticker,
            "sig_date":   sig_date,
            "entry_date": df.index[entry_loc],
            "exit_date":  df.index[exit_loc],
            "direction":  direction,
            "net_pnl":    round(net_pnl, 2),
            "win":        net_pnl > 0,
        })
        last_exit_loc = exit_loc

    return trades


def run_strategy(hold_days, direction, signal_fn, price_data):
    """Run one strategy across all tickers. Returns a DataFrame of trades."""
    all_trades = []
    for ticker, df in price_data.items():
        all_trades.extend(
            run_strategy_on_ticker(ticker, df, hold_days, direction, signal_fn)
        )
    if not all_trades:
        return pd.DataFrame()
    return pd.DataFrame(all_trades)


# =============================================================================
# STATS & REPORTING
# =============================================================================

def compute_stats(trades_df):
    if trades_df.empty:
        return {"n": 0, "win_pct": 0, "total": 0, "avg": 0, "worst": 0, "max_dd": 0}
    n      = len(trades_df)
    total  = trades_df["net_pnl"].sum()
    avg    = trades_df["net_pnl"].mean()
    worst  = trades_df["net_pnl"].min()
    # Max drawdown on time-ordered cumulative P&L
    cum    = trades_df.sort_values("entry_date")["net_pnl"].cumsum()
    max_dd = float((cum - cum.cummax()).min())
    return {
        "n":       n,
        "win_pct": round(trades_df["win"].mean() * 100, 1),
        "total":   round(total, 0),
        "avg":     round(avg, 2),
        "worst":   round(worst, 2),
        "max_dd":  round(max_dd, 0),
    }


def cheat_check(trades_df):
    """
    Split at TRAIN_CUTOFF. Strategy must profit in BOTH halves.
    Also flags if trade count is too low to be meaningful.
    """
    if trades_df.empty:
        return 0, 0, "NO TRADES"

    train = trades_df[trades_df["sig_date"] <= TRAIN_CUTOFF]
    test  = trades_df[trades_df["sig_date"]  > TRAIN_CUTOFF]

    train_pnl = train["net_pnl"].sum()
    test_pnl  = test["net_pnl"].sum()

    if len(trades_df) < MIN_TRADES_TO_SURVIVE:
        return train_pnl, test_pnl, "TOO FEW TRADES (not enough data)"

    if train_pnl > 0 and test_pnl > 0:
        verdict = "SURVIVED"
    elif train_pnl > 0 and test_pnl <= 0:
        verdict = "FAILED (test half lost money)"
    elif train_pnl <= 0:
        verdict = "FAILED (lost in training too)"
    else:
        verdict = "MIXED (lost training, won test)"

    return train_pnl, test_pnl, verdict


def get_benchmark_return():
    try:
        spy = yf.download(BENCHMARK, start=START_DATE, end=END_DATE,
                          auto_adjust=True, progress=False)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = [col[0] for col in spy.columns]
        pct = (float(spy["Close"].iloc[-1]) / float(spy["Close"].iloc[0]) - 1) * 100
        return round(pct, 1)
    except Exception:
        return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 72)
    print("  10-STRATEGY TOURNAMENT — Honest Stock Backtester")
    print(f"  Period : {START_DATE} → {END_DATE}")
    print(f"  Split  : Train ≤ {TRAIN_CUTOFF}  |  Test > {TRAIN_CUTOFF}")
    print(f"  Costs  : {COMMISSION*100:.1f}% commission + {SLIPPAGE*100:.1f}% slippage each way")
    print(f"  Size   : ${POSITION_SIZE:,} per trade  |  Tickers: {len(ALL_TICKERS)}")
    print("=" * 72)

    # ── Download all tickers once ─────────────────────────────────────────────
    print("\nDownloading price data...")
    price_data = {}
    failed     = []

    for i, ticker in enumerate(ALL_TICKERS):
        try:
            df = yf.download(
                ticker, start=START_DATE, end=END_DATE,
                auto_adjust=True, progress=False
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            if len(df) > 150:
                price_data[ticker] = df
            else:
                failed.append(ticker)
        except Exception:
            failed.append(ticker)

        if (i + 1) % 30 == 0:
            pct = (i + 1) / len(ALL_TICKERS) * 100
            print(f"  [{pct:5.1f}%] {i+1}/{len(ALL_TICKERS)} tickers downloaded")

    print(f"  Done. {len(price_data)} tickers loaded, {len(failed)} skipped.")
    if failed:
        print(f"  Skipped: {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")

    # ── Benchmark ─────────────────────────────────────────────────────────────
    spy_return = get_benchmark_return()

    # ── Run all 10 strategies ─────────────────────────────────────────────────
    print(f"\nRunning {len(STRATEGIES)} strategies...\n")
    results = []

    for name, hold_days, direction, signal_fn in STRATEGIES:
        sys.stdout.write(f"  {name}... ")
        sys.stdout.flush()

        trades_df = run_strategy(hold_days, direction, signal_fn, price_data)
        stats     = compute_stats(trades_df)
        train_pnl, test_pnl, verdict = cheat_check(trades_df)

        sys.stdout.write(f"{stats['n']} trades → {verdict}\n")
        sys.stdout.flush()

        results.append({
            "name":      name,
            "hold_days": hold_days,
            "direction": direction,
            "stats":     stats,
            "train_pnl": train_pnl,
            "test_pnl":  test_pnl,
            "verdict":   verdict,
        })

    # ── Sort by total P&L ─────────────────────────────────────────────────────
    results.sort(key=lambda r: r["stats"]["total"], reverse=True)

    # ── Print full results ────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  FULL RESULTS  (sorted by total P&L, best to worst)")
    print("=" * 72)

    for r in results:
        s       = r["stats"]
        verdict = r["verdict"]
        survived = "SURVIVED" in verdict

        marker = "✅" if survived else ("⚠️ " if "TOO FEW" in verdict else "❌")
        direction_note = "(SHORT)" if r["direction"] == "short" else ""

        print(f"\n{marker}  {r['name']} {direction_note}")
        print(f"     Hold: {r['hold_days']} days  |  Trades: {s['n']}  |  Win rate: {s['win_pct']}%")
        print(f"     Total P&L    : ${s['total']:>10,.0f}")
        print(f"     Avg / trade  : ${s['avg']:>10,.2f}")
        print(f"     Worst trade  : ${s['worst']:>10,.2f}")
        print(f"     Max drawdown : ${s['max_dd']:>10,.0f}")
        print(f"     Train P&L    : ${r['train_pnl']:>10,.0f}")
        print(f"     Test  P&L    : ${r['test_pnl']:>10,.0f}")
        print(f"     Cheat-check  : {verdict}")

    # ── Survivors summary ─────────────────────────────────────────────────────
    survivors = [r for r in results if "SURVIVED" in r["verdict"]]

    print("\n" + "=" * 72)
    print(f"  SURVIVORS: {len(survivors)} out of {len(STRATEGIES)}")
    print("=" * 72)

    if survivors:
        for r in survivors:
            s = r["stats"]
            print(f"\n  ✅ {r['name']}")
            print(f"     ${s['total']:,.0f} total | ${s['avg']:,.2f}/trade | "
                  f"{s['n']} trades | {s['win_pct']}% wins")
            print(f"     Train: ${r['train_pnl']:,.0f}  |  Test: ${r['test_pnl']:,.0f}")
    else:
        print("\n  No strategies survived the cheat-check in both halves.")

    if spy_return is not None:
        print(f"\n  Benchmark: SPY buy-and-hold over same period = +{spy_return}%")
        if spy_return > 0:
            spy_dollar = spy_return / 100 * POSITION_SIZE
            print(f"  (Equivalent to ${spy_dollar:,.0f} profit on a single {POSITION_SIZE:,} investment)")

    print("\n" + "=" * 72)
    print("  IMPORTANT DISCLOSURES")
    print("=" * 72)
    print("""
  1. SURVIVORSHIP BIAS: yfinance only returns data for stocks that still
     exist. Bankrupt or delisted companies are missing. All results above
     are optimistically biased — real historical returns would be worse.

  2. SHORT SELLING RISK: Strategies marked (SHORT) have unlimited loss
     potential. If the stock keeps rising, losses are uncapped. Real short
     positions also incur daily borrow fees (1-10%+ annually) that are NOT
     modeled here, making real short results even worse than shown.

  3. PAST PERFORMANCE: A strategy that survived the cheat-check passed
     one additional test — it is a stronger hypothesis, not a guarantee.
     Markets change. An edge that existed 2019-2024 may not exist tomorrow.

  4. NOT FINANCIAL ADVICE: This is a personal learning tool. No output
     from this script should be used to make real investment decisions.
""")


if __name__ == "__main__":
    main()
