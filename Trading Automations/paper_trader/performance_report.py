#!/usr/bin/env python3
"""
Performance Report
===================
Reads trade_log.csv (written by trader.py on every closed trade) and:
  1. Writes performance_report.md — win rate, trade count, per-trade
     % gain, a per-strategy breakdown, and a trade-by-trade S&P 500
     (SPY) benchmark comparison.
  2. On Fridays, emails that same summary to GMAIL_ADDRESS via Gmail SMTP,
     using a GMAIL_APP_PASSWORD (not your real password).

The S&P 500 comparison is trade-by-trade, not calendar buy-and-hold: for
each closed trade it looks up what the same $POSITION_SIZE would have
earned in SPY over that exact entry_date -> exit_date window, then rolls
those up the same way real trades are rolled up (This Week / All-Time).
This isolates strategy skill from market beta instead of comparing to
SPY's return over an arbitrary calendar window. If SPY data can't be
fetched (no network, Yahoo Finance hiccup), the comparison is silently
omitted rather than failing the whole report/email.

Run manually any time with:
    python performance_report.py

To force-send the email regardless of day (e.g. for testing):
    python performance_report.py --force-email
"""

import csv
import json
import os
import smtplib
import sys
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

import strategies_lib as lib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.csv")
POSITIONS_FILE = os.path.join(BASE_DIR, "positions.json")
REPORT_FILE = os.path.join(BASE_DIR, "performance_report.md")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

# The GitHub Actions runner's system clock is UTC, not US market time. A run
# that's delayed enough to cross UTC midnight (which lands at 5 PM Pacific /
# 8 PM Eastern in summer) would otherwise silently report tomorrow's date -
# this bit us 2026-08-06/07, when a slow Thursday run crossed into Friday
# UTC and fired the Friday-only weekly email a day early, dated a day ahead
# of what was still Thursday for Dany. "Today" here always means the US
# market's own calendar day, regardless of the runner's local clock.
MARKET_TZ = ZoneInfo("America/New_York")


def today_et():
    return datetime.now(MARKET_TZ).date()


def load_trades():
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    with open(TRADE_LOG_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    # Only trades with a known exit price count toward stats.
    return [r for r in rows if r["pct_gain"] not in ("", None)]


def trades_closed_since(trades, days=7):
    cutoff = today_et() - timedelta(days=days)
    return [t for t in trades if date.fromisoformat(t["exit_date"]) >= cutoff]


def load_positions():
    """Currently open positions from positions.json, soonest-to-close first."""
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE) as f:
        positions = list(json.load(f).values())
    today = today_et()
    for p in positions:
        p["days_until_close"] = (date.fromisoformat(p["exit_date"]) - today).days
    return sorted(positions, key=lambda p: p["days_until_close"])


def fetch_spy_history(start_date):
    """SPY daily closes from start_date to today, for the trade-by-trade benchmark."""
    try:
        df = yf.download(lib.BENCHMARK, start=start_date, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        if df.empty:
            return None
        return df["Close"]
    except Exception as e:
        print(f"  Could not fetch SPY benchmark data: {e}")
        return None


def spy_price_on(spy_close, date_str):
    ts = pd.Timestamp(date_str)
    idx = spy_close.index.asof(ts)
    if pd.isna(idx):
        return None
    return float(spy_close.loc[idx])


def compute_benchmark_stats(trades, spy_close):
    """For each trade, what the same $POSITION_SIZE would have earned in
    SPY over that trade's own entry_date -> exit_date window."""
    if spy_close is None or not trades:
        return None

    pcts, pnls = [], []
    for t in trades:
        entry_px = spy_price_on(spy_close, t["entry_date"])
        exit_px = spy_price_on(spy_close, t["exit_date"])
        if entry_px is None or exit_px is None:
            continue
        pct = (exit_px / entry_px - 1) * 100
        pcts.append(pct)
        pnls.append(pct / 100 * lib.POSITION_SIZE)

    if not pcts:
        return None

    return {
        "total_trades": len(pcts),
        "avg_pct_gain": sum(pcts) / len(pcts),
        "total_pnl": sum(pnls),
    }


def vs_spy_parts(stats, bench):
    """Returns (verb, alpha_pct, alpha_pnl, spy_avg_pct, spy_total_pnl, n_trades) or None."""
    if bench is None:
        return None
    alpha_pct = stats["avg_pct_gain"] - bench["avg_pct_gain"]
    alpha_pnl = stats["total_pnl"] - bench["total_pnl"]
    verb = "beat" if alpha_pct >= 0 else "trailed"
    return verb, alpha_pct, alpha_pnl, bench["avg_pct_gain"], bench["total_pnl"], bench["total_trades"]


def build_vs_spy_line_md(stats, bench):
    parts = vs_spy_parts(stats, bench)
    if parts is None:
        return None
    verb, alpha_pct, alpha_pnl, spy_avg_pct, spy_total_pnl, n = parts
    return (
        f"- **vs S&P 500** (same {n} trades, same entry/exit dates): "
        f"SPY averaged {spy_avg_pct:+.2f}%/trade (${spy_total_pnl:+,.2f} total) "
        f"— you {verb} SPY by {alpha_pct:+.2f} pts (${alpha_pnl:+,.2f})"
    )


def build_vs_spy_line_plain(stats, bench):
    parts = vs_spy_parts(stats, bench)
    if parts is None:
        return None
    verb, alpha_pct, alpha_pnl, spy_avg_pct, spy_total_pnl, n = parts
    return (
        f"  vs S&P 500 (same {n} trades, same entry/exit dates): "
        f"SPY averaged {spy_avg_pct:+.2f}%/trade (${spy_total_pnl:+,.2f} total) "
        f"- you {verb} SPY by {alpha_pct:+.2f} pts (${alpha_pnl:+,.2f})"
    )


def days_label(days):
    if days < 0:
        return f"overdue by {-days}d"
    if days == 0:
        return "closes today"
    return f"{days}d"


def build_open_positions_md(positions):
    lines = ["## Open Positions", ""]
    if not positions:
        return lines + ["No open positions.", ""]
    lines.append("| Ticker | Strategy | Entry Date | Exit Date | Days Until Close |")
    lines.append("|---|---|---|---|---|")
    for p in positions:
        lines.append(
            f"| {p['ticker']} | {p['strategy']} | {p['entry_date']} | {p['exit_date']} "
            f"| {days_label(p['days_until_close'])} |"
        )
    lines.append("")
    return lines


def build_open_positions_plain(positions):
    lines = ["Open Positions:"]
    if not positions:
        return lines + ["  No open positions."]
    for p in positions:
        lines.append(
            f"  {p['ticker']} ({p['strategy']}): entered {p['entry_date']}, "
            f"closes {p['exit_date']} ({days_label(p['days_until_close'])})"
        )
    return lines


def compute_stats(trades):
    total = len(trades)
    if total == 0:
        return None

    gains = [float(t["pct_gain"]) for t in trades]
    pnls = [float(t["dollar_pnl"]) for t in trades]
    wins = [g for g in gains if g > 0]

    by_strategy = {}
    for t in trades:
        s = t["strategy"]
        by_strategy.setdefault(s, []).append(float(t["pct_gain"]))

    strategy_stats = {}
    for s, pct_list in by_strategy.items():
        s_wins = [g for g in pct_list if g > 0]
        strategy_stats[s] = {
            "trades":   len(pct_list),
            "win_rate": len(s_wins) / len(pct_list) * 100,
            "avg_gain": sum(pct_list) / len(pct_list),
        }

    return {
        "total_trades":  total,
        "win_rate":      len(wins) / total * 100,
        "avg_pct_gain":  sum(gains) / total,
        "total_pnl":     sum(pnls),
        "best_trade":    max(trades, key=lambda t: float(t["pct_gain"])),
        "worst_trade":   min(trades, key=lambda t: float(t["pct_gain"])),
        "by_strategy":   strategy_stats,
    }


def build_summary_lines(stats, heading, bench=None):
    lines = [
        f"## {heading}",
        f"- **Total closed trades:** {stats['total_trades']}",
        f"- **Win rate:** {stats['win_rate']:.1f}%",
        f"- **Average % gain per trade:** {stats['avg_pct_gain']:+.2f}%",
        f"- **Total P&L:** ${stats['total_pnl']:+,.2f}",
        f"- **Best trade:** {stats['best_trade']['ticker']} "
        f"({stats['best_trade']['strategy']}) {float(stats['best_trade']['pct_gain']):+.2f}%",
        f"- **Worst trade:** {stats['worst_trade']['ticker']} "
        f"({stats['worst_trade']['strategy']}) {float(stats['worst_trade']['pct_gain']):+.2f}%",
    ]
    vs_spy = build_vs_spy_line_md(stats, bench)
    if vs_spy is not None:
        lines.append(vs_spy)
    lines += [
        "",
        "| Strategy | Trades | Win Rate | Avg % Gain |",
        "|---|---|---|---|",
    ]
    for s, st in sorted(stats["by_strategy"].items()):
        lines.append(f"| {s} | {st['trades']} | {st['win_rate']:.1f}% | {st['avg_gain']:+.2f}% |")
    return lines


def build_report_markdown(stats, trades, week_stats, week_bench=None, all_bench=None, positions=None):
    today = today_et().isoformat()
    positions = positions or []

    if stats is None:
        lines = ["# Paper Trading Performance Report", f"\n_Last updated: {today}_\n"]
        lines += build_open_positions_md(positions)
        lines.append("No closed trades yet.")
        return "\n".join(lines) + "\n"

    lines = ["# Paper Trading Performance Report", f"\n_Last updated: {today}_\n"]
    lines += build_open_positions_md(positions)

    if week_stats is not None:
        lines += build_summary_lines(week_stats, "This Week (last 7 days)", bench=week_bench)
    else:
        lines += ["## This Week (last 7 days)", "", "No trades closed in the last 7 days."]
    lines.append("")
    lines += build_summary_lines(stats, "All-Time (cumulative)", bench=all_bench)

    lines.append("\n## All Trades")
    lines.append("| Ticker | Strategy | Entry Date | Exit Date | % Gain | $ P&L |")
    lines.append("|---|---|---|---|---|---|")
    for t in trades:
        lines.append(
            f"| {t['ticker']} | {t['strategy']} | {t['entry_date']} | {t['exit_date']} "
            f"| {float(t['pct_gain']):+.2f}% | ${float(t['dollar_pnl']):+,.2f} |"
        )

    return "\n".join(lines) + "\n"


def build_email_section(stats, heading, bench=None):
    lines = [
        heading,
        f"  Total closed trades: {stats['total_trades']}",
        f"  Win rate: {stats['win_rate']:.1f}%",
        f"  Average % gain per trade: {stats['avg_pct_gain']:+.2f}%",
        f"  Total P&L: ${stats['total_pnl']:+,.2f}",
    ]
    vs_spy = build_vs_spy_line_plain(stats, bench)
    if vs_spy is not None:
        lines.append(vs_spy)
    lines.append("  By strategy:")
    for s, st in sorted(stats["by_strategy"].items()):
        lines.append(f"    {s}: {st['trades']} trades, {st['win_rate']:.1f}% win rate, {st['avg_gain']:+.2f}% avg gain")
    return lines


def build_email_body(stats, week_stats, week_bench=None, all_bench=None, positions=None):
    positions = positions or []

    if stats is None:
        lines = [f"Paper Trading Weekly Digest — {today_et().isoformat()}", ""]
        lines += build_open_positions_plain(positions)
        lines += ["", "No closed paper trades yet."]
        return "\n".join(lines)

    lines = [f"Paper Trading Weekly Digest — {today_et().isoformat()}", ""]
    lines += build_open_positions_plain(positions)
    lines.append("")

    if week_stats is not None:
        lines += build_email_section(week_stats, "This Week (last 7 days):", bench=week_bench)
    else:
        lines += ["This Week (last 7 days):", "  No trades closed in the last 7 days."]
    lines.append("")
    lines += build_email_section(stats, "All-Time (cumulative):", bench=all_bench)

    return "\n".join(lines)


def send_email(body):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Skipping email — GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set.")
        return

    msg = MIMEText(body)
    msg["Subject"] = f"Paper Trading Weekly Digest — {today_et().isoformat()}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"  Email sent to {GMAIL_ADDRESS}.")


def main():
    trades = load_trades()
    stats = compute_stats(trades)
    week_trades = trades_closed_since(trades, days=7)
    week_stats = compute_stats(week_trades)
    positions = load_positions()

    week_bench = all_bench = None
    if stats is not None:
        earliest_entry = min(t["entry_date"] for t in trades)
        spy_close = fetch_spy_history(earliest_entry)
        all_bench = compute_benchmark_stats(trades, spy_close)
        week_bench = compute_benchmark_stats(week_trades, spy_close)

    report_md = build_report_markdown(
        stats, trades, week_stats, week_bench=week_bench, all_bench=all_bench, positions=positions
    )
    with open(REPORT_FILE, "w") as f:
        f.write(report_md)
    print(f"Wrote {REPORT_FILE}")

    is_friday = today_et().weekday() == 4
    force_email = "--force-email" in sys.argv

    if is_friday or force_email:
        send_email(build_email_body(
            stats, week_stats, week_bench=week_bench, all_bench=all_bench, positions=positions
        ))
    else:
        print("  Not Friday — skipping weekly email (use --force-email to override).")


if __name__ == "__main__":
    main()
