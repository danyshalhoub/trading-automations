#!/usr/bin/env python3
"""
Strategies Library — Shared Indicator Engine
==============================================
A fixed, vetted set of indicator "types" (RSI, MACD, Bollinger, moving-average
crosses, gaps, volume, seasonality, relative strength, etc.), each of which
takes tunable parameters (period, threshold, hold_days, ...).

Both the weekly tournament (backtesting many parameterizations to find the
current best performers) and the live trader (checking today's signal for
whatever 4 strategies are currently in the active roster) run through this
same code. The set of indicator TYPES is fixed and human-reviewed — only the
parameters vary week to week. Direction (long/short) is fixed per indicator
type, not settable by a strategy spec, so a generated "spec" can never invert
a mean-reversion signal into a nonsensical short or vice versa.

A "strategy spec" is a plain dict:
    {
        "name": "rsi_oversold_p10_t25",
        "indicator_type": "rsi_oversold",
        "params": {"period": 10, "threshold": 25},
        "hold_days": 12,
    }

SAFETY: This module only ever computes signals from vetted, hand-written
indicator formulas. Generated specs may vary the PARAMETERS passed into these
formulas, never the formulas themselves — see clamp_params() for the bounds
enforced on every spec before it is ever backtested or traded live.
"""

import numpy as np
import pandas as pd

# =============================================================================
# TICKER UNIVERSE (shared across the tournament, weekly re-tournament, and
# live trader so backtests and live scans always cover the same names)
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
BENCHMARK = "SPY"

# =============================================================================
# INDICATOR TYPE REGISTRY
# =============================================================================
# direction is fixed per type — not overridable by a generated spec.

DIRECTIONS = {
    "rsi_oversold":            "long",
    "bb_lower_touch":          "long",
    "bb_squeeze_breakout":     "long",
    "macd_bull_cross":         "long",
    "buy_dip_ma":              "long",
    "low_52w_bounce":          "long",
    "three_red_days":          "long",
    "high_volume_hammer":      "long",
    "golden_cross":            "long",
    "death_cross_short":       "short",
    "n_day_breakout":          "long",
    "gap_down_recovery":       "long",
    "gap_up_continuation":     "long",
    "inside_day_breakout":     "long",
    "relative_strength_spy":   "long",
    "turn_of_month":           "long",
    "capitulation_exhaustion": "long",
    "failed_breakout_short":   "short",
}

# (min, max) clamp bounds for every tunable param, enforced on every spec
# regardless of where it came from (generator output or hand-authored).
PARAM_BOUNDS = {
    "rsi_oversold":            {"period": (5, 30), "threshold": (10, 40)},
    "bb_lower_touch":          {"window": (10, 40), "num_std": (1.0, 3.0)},
    "bb_squeeze_breakout":     {"window": (10, 40), "num_std": (1.0, 3.0),
                                 "squeeze_lookback": (60, 200), "squeeze_ratio": (1.0, 1.5)},
    "macd_bull_cross":         {"fast": (5, 20), "slow": (15, 40), "signal": (5, 15)},
    "buy_dip_ma":              {"drop_pct": (0.05, 0.20), "ma_period": (100, 250)},
    "low_52w_bounce":          {"pct_from_low": (1.00, 1.10)},
    "three_red_days":          {"num_days": (2, 5)},
    "high_volume_hammer":      {"drop_pct": (0.02, 0.06), "vol_ratio": (1.2, 3.0), "intra_pos_pct": (0.5, 0.9)},
    "golden_cross":            {"fast_ma": (20, 100), "slow_ma": (100, 250)},
    "death_cross_short":       {"fast_ma": (20, 100), "slow_ma": (100, 250)},
    "n_day_breakout":          {"lookback": (10, 60)},
    "gap_down_recovery":       {"gap_pct": (0.02, 0.08)},
    "gap_up_continuation":     {"gap_pct": (0.02, 0.08)},
    "inside_day_breakout":     {},
    "relative_strength_spy":   {"lookback_days": (21, 126), "outperform_pct": (0.05, 0.30)},
    "turn_of_month":           {},
    "capitulation_exhaustion": {"cum_ret_days": (5, 20), "cum_ret_threshold": (0.05, 0.15),
                                 "vol_ratio_threshold": (0.5, 0.9)},
    "failed_breakout_short":   {"lookback": (10, 60)},
}

HOLD_DAYS_BOUNDS = (3, 30)

DEFAULT_PARAMS = {
    "rsi_oversold":            {"period": 14, "threshold": 30},
    "bb_lower_touch":          {"window": 20, "num_std": 2.0},
    "bb_squeeze_breakout":     {"window": 20, "num_std": 2.0, "squeeze_lookback": 126, "squeeze_ratio": 1.10},
    "macd_bull_cross":         {"fast": 12, "slow": 26, "signal": 9},
    "buy_dip_ma":              {"drop_pct": 0.10, "ma_period": 200},
    "low_52w_bounce":          {"pct_from_low": 1.03},
    "three_red_days":          {"num_days": 3},
    "high_volume_hammer":      {"drop_pct": 0.03, "vol_ratio": 1.5, "intra_pos_pct": 0.70},
    "golden_cross":            {"fast_ma": 50, "slow_ma": 200},
    "death_cross_short":       {"fast_ma": 50, "slow_ma": 200},
    "n_day_breakout":          {"lookback": 20},
    "gap_down_recovery":       {"gap_pct": 0.05},
    "gap_up_continuation":     {"gap_pct": 0.03},
    "inside_day_breakout":     {},
    "relative_strength_spy":   {"lookback_days": 63, "outperform_pct": 0.15},
    "turn_of_month":           {},
    "capitulation_exhaustion": {"cum_ret_days": 10, "cum_ret_threshold": 0.08, "vol_ratio_threshold": 0.80},
    "failed_breakout_short":   {"lookback": 20},
}


def clamp_params(indicator_type, params):
    """Clamp every param to its vetted bounds. Unknown params are dropped;
    missing params fall back to the default for that indicator type."""
    if indicator_type not in DIRECTIONS:
        raise ValueError(f"Unknown indicator_type: {indicator_type!r}")

    bounds = PARAM_BOUNDS[indicator_type]
    defaults = DEFAULT_PARAMS[indicator_type]
    clamped = {}
    for key, (lo, hi) in bounds.items():
        val = params.get(key, defaults[key])
        try:
            val = float(val) if isinstance(defaults[key], float) else int(val)
        except (TypeError, ValueError):
            val = defaults[key]
        clamped[key] = max(lo, min(hi, val))

    if "macd_bull_cross" == indicator_type and clamped["slow"] <= clamped["fast"]:
        clamped["slow"] = clamped["fast"] + 5
    if indicator_type in ("golden_cross", "death_cross_short") and clamped["slow_ma"] <= clamped["fast_ma"]:
        clamped["slow_ma"] = clamped["fast_ma"] + 50

    return clamped


def clamp_hold_days(hold_days):
    lo, hi = HOLD_DAYS_BOUNDS
    try:
        hold_days = int(hold_days)
    except (TypeError, ValueError):
        hold_days = 10
    return max(lo, min(hi, hold_days))


# =============================================================================
# BASE INDICATORS (computed once per ticker; shared across all strategy types)
# =============================================================================

def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_base_columns(df, spy_ret_lookback=None):
    """Raw OHLCV-derived columns used across multiple indicator types.
    Per-strategy rolling windows (RSI period, BB window, MA periods, etc.)
    are computed on demand inside get_signal_mask, since those vary by spec."""
    df = df.copy()
    df["ret"] = df["Close"].pct_change()
    df["gap_pct"] = (df["Open"] / df["Close"].shift(1)) - 1
    df["vol20"] = df["Volume"].rolling(20).mean()
    df["vol_ratio"] = df["Volume"] / df["vol20"].replace(0, np.nan)
    day_range = (df["High"] - df["Low"]).replace(0, np.nan)
    df["intra_pos"] = (df["Close"] - df["Low"]) / day_range
    df["month"] = df.index.month
    df["is_last_trading_day_of_month"] = df["month"] != df["month"].shift(-1)
    if spy_ret_lookback is not None:
        df["ret_63"] = df["Close"].pct_change(63)
        df["spy_ret_63"] = spy_ret_lookback.reindex(df.index, method="ffill")
        df["rel_ret_63"] = df["ret_63"] - df["spy_ret_63"]
    return df


# =============================================================================
# SIGNAL EVALUATION — one function per indicator type
# Each returns a boolean mask (pd.Series aligned to df.index) of signal days.
# =============================================================================

def _sig_rsi_oversold(df, p):
    rsi = compute_rsi(df["Close"], p["period"])
    return rsi < p["threshold"]


def _sig_bb_lower_touch(df, p):
    ma = df["Close"].rolling(p["window"]).mean()
    std = df["Close"].rolling(p["window"]).std()
    lower = ma - p["num_std"] * std
    return df["Close"] < lower


def _sig_bb_squeeze_breakout(df, p):
    ma = df["Close"].rolling(p["window"]).mean()
    std = df["Close"].rolling(p["window"]).std()
    lower = ma - p["num_std"] * std
    upper = ma + p["num_std"] * std
    width = (upper - lower) / ma.replace(0, np.nan)
    width_min = width.rolling(p["squeeze_lookback"], min_periods=int(p["squeeze_lookback"] * 0.8)).min()
    squeeze = width <= width_min * p["squeeze_ratio"]
    squeeze_recent = squeeze.rolling(5).max()
    return (df["Close"] > upper) & (squeeze_recent.shift(1) == 1)


def _sig_macd_bull_cross(df, p):
    ema_fast = df["Close"].ewm(span=p["fast"], adjust=False).mean()
    ema_slow = df["Close"].ewm(span=p["slow"], adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=p["signal"], adjust=False).mean()
    cross = (macd > signal) & (macd.shift(1) <= signal.shift(1))
    return cross & (macd < 0)


def _sig_buy_dip_ma(df, p):
    ma = df["Close"].rolling(p["ma_period"]).mean()
    return (df["ret"] < -p["drop_pct"]) & (df["Close"] > ma)


def _sig_low_52w_bounce(df, p):
    low_52w = df["Close"].shift(1).rolling(252, min_periods=200).min()
    return (df["Close"] <= low_52w * p["pct_from_low"]) & low_52w.notna()


def _sig_three_red_days(df, p):
    consec_dn = (df["ret"] < 0).astype(int).rolling(p["num_days"]).sum()
    return consec_dn >= p["num_days"]


def _sig_high_volume_hammer(df, p):
    return (
        (df["ret"] < -p["drop_pct"])
        & (df["vol_ratio"] > p["vol_ratio"])
        & (df["intra_pos"] > p["intra_pos_pct"])
    )


def _sig_golden_cross(df, p):
    ma_fast = df["Close"].rolling(p["fast_ma"]).mean()
    ma_slow = df["Close"].rolling(p["slow_ma"]).mean()
    above = ma_fast > ma_slow
    return above & (~above.shift(1).fillna(True))


def _sig_death_cross_short(df, p):
    ma_fast = df["Close"].rolling(p["fast_ma"]).mean()
    ma_slow = df["Close"].rolling(p["slow_ma"]).mean()
    above = ma_fast > ma_slow
    return (~above) & (above.shift(1).fillna(False))


def _sig_n_day_breakout(df, p):
    high_n = df["Close"].shift(1).rolling(p["lookback"], min_periods=int(p["lookback"] * 0.75)).max()
    return (df["Close"] > high_n) & high_n.notna()


def _sig_gap_down_recovery(df, p):
    return (df["gap_pct"] < -p["gap_pct"]) & (df["Close"] > df["Open"])


def _sig_gap_up_continuation(df, p):
    return (df["gap_pct"] > p["gap_pct"]) & (df["Close"] > df["Open"])


def _sig_inside_day_breakout(df, p):
    inside_day = (df["High"] < df["High"].shift(1)) & (df["Low"] > df["Low"].shift(1))
    prev_inside = inside_day.shift(1)
    breakout = df["Close"] > df["High"].shift(1)
    return prev_inside & breakout


def _sig_relative_strength_spy(df, p):
    ret_n = df["Close"].pct_change(p["lookback_days"])
    if "spy_ret_63" not in df.columns:
        return pd.Series(False, index=df.index)
    rel = ret_n - df["spy_ret_63"]
    return rel > p["outperform_pct"]


def _sig_turn_of_month(df, p):
    return df["is_last_trading_day_of_month"]


def _sig_capitulation_exhaustion(df, p):
    ma200 = df["Close"].rolling(200).mean()
    cum_ret = df["Close"] / df["Close"].shift(p["cum_ret_days"]) - 1
    return (
        (cum_ret < -p["cum_ret_threshold"])
        & (df["vol_ratio"] < p["vol_ratio_threshold"])
        & (df["Close"] > ma200)
    )


def _sig_failed_breakout_short(df, p):
    high_n = df["Close"].shift(1).rolling(p["lookback"], min_periods=int(p["lookback"] * 0.75)).max()
    breakout_yesterday = df["Close"].shift(1) > high_n.shift(1)
    weak_volume = df["vol_ratio"].shift(1) < 1.0
    failed_today = df["Close"] < df["Close"].shift(1)
    return breakout_yesterday & weak_volume & failed_today


_SIGNAL_FNS = {
    "rsi_oversold": _sig_rsi_oversold,
    "bb_lower_touch": _sig_bb_lower_touch,
    "bb_squeeze_breakout": _sig_bb_squeeze_breakout,
    "macd_bull_cross": _sig_macd_bull_cross,
    "buy_dip_ma": _sig_buy_dip_ma,
    "low_52w_bounce": _sig_low_52w_bounce,
    "three_red_days": _sig_three_red_days,
    "high_volume_hammer": _sig_high_volume_hammer,
    "golden_cross": _sig_golden_cross,
    "death_cross_short": _sig_death_cross_short,
    "n_day_breakout": _sig_n_day_breakout,
    "gap_down_recovery": _sig_gap_down_recovery,
    "gap_up_continuation": _sig_gap_up_continuation,
    "inside_day_breakout": _sig_inside_day_breakout,
    "relative_strength_spy": _sig_relative_strength_spy,
    "turn_of_month": _sig_turn_of_month,
    "capitulation_exhaustion": _sig_capitulation_exhaustion,
    "failed_breakout_short": _sig_failed_breakout_short,
}


def get_signal_mask(df, indicator_type, params):
    """df must already have add_base_columns() applied. Returns a boolean
    Series aligned to df.index."""
    fn = _SIGNAL_FNS[indicator_type]
    return fn(df, params).fillna(False)


def check_signal_today(df, indicator_type, params):
    """For live trading: does the most recent row trigger this signal?"""
    mask = get_signal_mask(df, indicator_type, params)
    if len(mask) == 0:
        return False
    return bool(mask.iloc[-1])


# =============================================================================
# BACKTEST ENGINE (shared by the weekly tournament)
# =============================================================================

COMMISSION = 0.001
SLIPPAGE = 0.001
ROUND_TRIP_COST = (COMMISSION + SLIPPAGE) * 2
POSITION_SIZE = 10_000


def run_spec_on_ticker(ticker, df, spec, spy_ret_63=None):
    """df is raw OHLCV (not yet base-columned). Returns list of trade dicts."""
    if len(df) < 260:
        return []

    indicator_type = spec["indicator_type"]
    params = clamp_params(indicator_type, spec.get("params", {}))
    hold_days = clamp_hold_days(spec["hold_days"])
    direction = DIRECTIONS[indicator_type]

    df = add_base_columns(df, spy_ret_lookback=spy_ret_63)
    mask = get_signal_mask(df, indicator_type, params)
    signal_dates = df.index[mask].tolist()

    trades = []
    last_exit_loc = -1

    for sig_date in signal_dates:
        try:
            sig_loc = df.index.get_loc(sig_date)
        except KeyError:
            continue

        entry_loc = sig_loc + 1
        exit_loc = entry_loc + hold_days

        if entry_loc <= last_exit_loc:
            continue
        if exit_loc >= len(df):
            continue

        entry_price = float(df["Open"].iloc[entry_loc])
        exit_price = float(df["Open"].iloc[exit_loc])
        if entry_price <= 0 or exit_price <= 0:
            continue

        if direction == "long":
            gross_pct = (exit_price - entry_price) / entry_price
        else:
            gross_pct = (entry_price - exit_price) / entry_price

        net_pct = gross_pct - ROUND_TRIP_COST
        net_pnl = net_pct * POSITION_SIZE

        trades.append({
            "ticker": ticker,
            "sig_date": sig_date,
            "entry_date": df.index[entry_loc],
            "exit_date": df.index[exit_loc],
            "direction": direction,
            "net_pnl": round(net_pnl, 2),
            "win": net_pnl > 0,
        })
        last_exit_loc = exit_loc

    return trades


def run_spec(spec, price_data, spy_ret_63=None):
    all_trades = []
    for ticker, df in price_data.items():
        all_trades.extend(run_spec_on_ticker(ticker, df, spec, spy_ret_63))
    if not all_trades:
        return pd.DataFrame()
    return pd.DataFrame(all_trades)


def compute_stats(trades_df):
    if trades_df.empty:
        return {"n": 0, "win_pct": 0, "total": 0, "avg": 0, "worst": 0, "max_dd": 0}
    n = len(trades_df)
    total = trades_df["net_pnl"].sum()
    avg = trades_df["net_pnl"].mean()
    worst = trades_df["net_pnl"].min()
    cum = trades_df.sort_values("entry_date")["net_pnl"].cumsum()
    max_dd = float((cum - cum.cummax()).min())
    return {
        "n": n,
        "win_pct": round(trades_df["win"].mean() * 100, 1),
        "total": round(total, 0),
        "avg": round(avg, 2),
        "worst": round(worst, 2),
        "max_dd": round(max_dd, 0),
    }


def cheat_check(trades_df, train_cutoff, min_trades):
    if trades_df.empty:
        return 0, 0, "NO TRADES"

    train = trades_df[trades_df["sig_date"] <= train_cutoff]
    test = trades_df[trades_df["sig_date"] > train_cutoff]

    train_pnl = train["net_pnl"].sum()
    test_pnl = test["net_pnl"].sum()

    if len(trades_df) < min_trades:
        return train_pnl, test_pnl, "TOO FEW TRADES"

    if train_pnl > 0 and test_pnl > 0:
        verdict = "SURVIVED"
    elif train_pnl > 0 and test_pnl <= 0:
        verdict = "FAILED (test half lost money)"
    elif train_pnl <= 0:
        verdict = "FAILED (lost in training too)"
    else:
        verdict = "MIXED"

    return train_pnl, test_pnl, verdict
