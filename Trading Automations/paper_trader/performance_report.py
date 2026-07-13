#!/usr/bin/env python3
"""
Performance Report
===================
Reads trade_log.csv (written by trader.py on every closed trade) and:
  1. Writes performance_report.md — win rate, trade count, per-trade
     % gain, and a per-strategy breakdown.
  2. On Fridays, emails that same summary to GMAIL_ADDRESS via Gmail SMTP,
     using a GMAIL_APP_PASSWORD (not your real password).

Run manually any time with:
    python performance_report.py

To force-send the email regardless of day (e.g. for testing):
    python performance_report.py --force-email
"""

import csv
import os
import smtplib
import sys
from datetime import date
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRADE_LOG_FILE = os.path.join(BASE_DIR, "trade_log.csv")
REPORT_FILE = os.path.join(BASE_DIR, "performance_report.md")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def load_trades():
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    with open(TRADE_LOG_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    # Only trades with a known exit price count toward stats.
    return [r for r in rows if r["pct_gain"] not in ("", None)]


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


def build_report_markdown(stats, trades):
    today = date.today().isoformat()

    if stats is None:
        return f"# Paper Trading Performance Report\n\n_Last updated: {today}_\n\nNo closed trades yet.\n"

    lines = [
        "# Paper Trading Performance Report",
        f"\n_Last updated: {today}_\n",
        "## Summary",
        f"- **Total closed trades:** {stats['total_trades']}",
        f"- **Win rate:** {stats['win_rate']:.1f}%",
        f"- **Average % gain per trade:** {stats['avg_pct_gain']:+.2f}%",
        f"- **Total P&L:** ${stats['total_pnl']:+,.2f}",
        f"- **Best trade:** {stats['best_trade']['ticker']} "
        f"({stats['best_trade']['strategy']}) {float(stats['best_trade']['pct_gain']):+.2f}%",
        f"- **Worst trade:** {stats['worst_trade']['ticker']} "
        f"({stats['worst_trade']['strategy']}) {float(stats['worst_trade']['pct_gain']):+.2f}%",
        "\n## By Strategy",
        "| Strategy | Trades | Win Rate | Avg % Gain |",
        "|---|---|---|---|",
    ]
    for s, st in sorted(stats["by_strategy"].items()):
        lines.append(f"| {s} | {st['trades']} | {st['win_rate']:.1f}% | {st['avg_gain']:+.2f}% |")

    lines.append("\n## All Trades")
    lines.append("| Ticker | Strategy | Entry Date | Exit Date | % Gain | $ P&L |")
    lines.append("|---|---|---|---|---|---|")
    for t in trades:
        lines.append(
            f"| {t['ticker']} | {t['strategy']} | {t['entry_date']} | {t['exit_date']} "
            f"| {float(t['pct_gain']):+.2f}% | ${float(t['dollar_pnl']):+,.2f} |"
        )

    return "\n".join(lines) + "\n"


def build_email_body(stats):
    if stats is None:
        return "No closed paper trades yet this week."

    lines = [
        f"Paper Trading Weekly Digest — {date.today().isoformat()}",
        "",
        f"Total closed trades: {stats['total_trades']}",
        f"Win rate: {stats['win_rate']:.1f}%",
        f"Average % gain per trade: {stats['avg_pct_gain']:+.2f}%",
        f"Total P&L: ${stats['total_pnl']:+,.2f}",
        "",
        "By strategy:",
    ]
    for s, st in sorted(stats["by_strategy"].items()):
        lines.append(f"  {s}: {st['trades']} trades, {st['win_rate']:.1f}% win rate, {st['avg_gain']:+.2f}% avg gain")
    return "\n".join(lines)


def send_email(body):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Skipping email — GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set.")
        return

    msg = MIMEText(body)
    msg["Subject"] = f"Paper Trading Weekly Digest — {date.today().isoformat()}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"  Email sent to {GMAIL_ADDRESS}.")


def main():
    trades = load_trades()
    stats = compute_stats(trades)

    report_md = build_report_markdown(stats, trades)
    with open(REPORT_FILE, "w") as f:
        f.write(report_md)
    print(f"Wrote {REPORT_FILE}")

    is_friday = date.today().weekday() == 4
    force_email = "--force-email" in sys.argv

    if is_friday or force_email:
        send_email(build_email_body(stats))
    else:
        print("  Not Friday — skipping weekly email (use --force-email to override).")


if __name__ == "__main__":
    main()
