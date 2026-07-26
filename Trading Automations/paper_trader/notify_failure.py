#!/usr/bin/env python3
"""
Failure Notifier
=================
Sends an email alert when a paper-trader workflow fails (e.g. yfinance
rate-limited, Alpaca auth expired, unhandled exception). Wired into both
daily_trader.yml and weekly_tournament.yml with `if: failure()`, so it only
runs when an earlier step in the job has already failed. WORKFLOW_NAME
identifies which workflow failed in the alert email.
"""

import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RUN_URL = os.environ.get("RUN_URL", "(no run URL provided)")
WORKFLOW_NAME = os.environ.get("WORKFLOW_NAME", "Daily Paper Trader")


def main():
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set — cannot send failure alert.")
        return

    body = (
        f"The {WORKFLOW_NAME} workflow failed on {date.today().isoformat()}.\n\n"
        f"Run logs: {RUN_URL}"
    )

    msg = MIMEText(body)
    msg["Subject"] = f"{WORKFLOW_NAME} FAILED — {date.today().isoformat()}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Failure alert sent to {GMAIL_ADDRESS}.")


if __name__ == "__main__":
    main()
