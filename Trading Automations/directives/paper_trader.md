# Directive: Live Paper Trader

## Objective
Run the strategies that survived the backtest tournament's train/test cheat-check (see `stock_strategy_tester.md`) live against real daily price data, on Alpaca **paper** trading only, and keep an honest record of how they actually perform.

## Tools
- Script: `paper_trader/trader.py` — scans tickers, enters/exits positions on a fixed hold-days timer, appends every closed trade to `paper_trader/trade_log.csv`.
- Script: `paper_trader/performance_report.py` — reads `trade_log.csv`, writes `paper_trader/performance_report.md` (win rate, total trades, per-trade % gain, per-strategy breakdown), and emails a weekly digest.
- Script: `paper_trader/notify_failure.py` — emails an alert if `trader.py` or `performance_report.py` fails (auth expired, rate-limited, unhandled exception). Only runs on failure.
- Workflow: `.github/workflows/daily_trader.yml` — runs all scripts after US market close on weekdays, commits `positions.json`, `trade_log.csv`, and `performance_report.md` back to the repo.

## Expected Outputs
- `positions.json` — currently open positions.
- `trade_log.csv` — one row per closed trade (ticker, strategy, entry/exit date, entry/exit price, shares, % gain, $ P&L). This is the source of truth for live performance — never delete rows from it.
- `performance_report.md` — regenerated every run; summary stats + full trade table.
- A weekly email (Fridays) to `GMAIL_ADDRESS` summarizing win rate, trade count, and P&L. Skipped automatically if no trades have closed yet.
- A failure-alert email to `GMAIL_ADDRESS` any day the workflow errors out (no silent failures — if you don't hear from it and don't get an alert, check the Actions tab manually).

## Key Settings
- `HOLD_DAYS` (top of `trader.py`) — exit timer per strategy, in trading days.
- `POSITION_SIZE` — flat dollar amount per trade.
- Required secrets (GitHub Actions repo secrets, or local `.env` — see `.env.example`): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (a Gmail *app password*, not the real password).

## Process to Add/Retire a Strategy
1. Validate it in the backtester first (`stock_tester/`) — it must pass the train/test cheat-check.
2. Add/remove it in `STRATEGIES` and `HOLD_DAYS` in `trader.py`.
3. Note the change and the date in `trader.py`'s module docstring, same as the BB Lower Touch -> MACD Bullish Cross swap on 2026-07-12.

## Re-validation Cadence
Strategies can decay after going live (this already happened once — BB Lower Touch passed the original tournament but failed on rerun). Periodically re-run the tournament scripts against fresh data and compare against `performance_report.md`'s per-strategy stats; retire anything that's clearly underperforming its backtest.

## Safety Rules
- `paper=True` must never be removed from `make_client()` in `trader.py`.
- Never hardcode `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`/`GMAIL_APP_PASSWORD` — always read from environment/secrets.
- `trade_log.csv` is an append-only record — trading logic should only ever add rows, never rewrite or delete history.
