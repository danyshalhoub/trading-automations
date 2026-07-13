#!/usr/bin/env python3
"""
Failure Notifier
=================
Sends an email alert when the daily_trader.yml workflow fails (e.g.
yfinance rate-limited, Alpaca auth expired, unhandled exception). Wired
into the workflow with `if: failure()`, so it only runs when an earlier
step in the job has already failed — meaning no trades were placed or
exited that day.
"""

import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RUN_URL = os.environ.get("RUN_URL", "(no run URL provided)")


def main():
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set — cannot send failure alert.")
        return

    body = (
        f"The Daily Paper Trader workflow failed on {date.today().isoformat()}.\n\n"
        f"No trades were placed and no exits were processed today.\n\n"
        f"Run logs: {RUN_URL}"
    )

    msg = MIMEText(body)
    msg["Subject"] = f"Paper Trader FAILED — {date.today().isoformat()}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Failure alert sent to {GMAIL_ADDRESS}.")


if __name__ == "__main__":
    main()
