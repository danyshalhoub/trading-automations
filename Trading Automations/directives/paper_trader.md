# Directive: Live Paper Trader

## Objective
Run a roster of strategies live against real daily price data on Alpaca **paper** trading only, keep an honest record of how they actually perform, and automatically re-test and refresh that roster every week so it stays adapted to current market conditions instead of decaying silently.

## Tools
- Script: `paper_trader/strategies_lib.py` — shared indicator engine (RSI, MACD, Bollinger, MA crosses, gaps, volume, seasonality, relative strength, etc.). Every strategy is a "spec" — `{name, indicator_type, params, hold_days}` — evaluated through this same fixed, vetted code, whether backtesting or trading live. `indicator_type` must be one of the registered types; `params`/`hold_days` are clamped to hard-coded safe bounds (`clamp_params`, `clamp_hold_days`) before ever being backtested or traded, regardless of where the spec came from.
- Script: `paper_trader/active_strategies.json` — the current live roster (4 strategy specs). `trader.py` reads this every day; `weekly_tournament.py` rewrites it every Friday.
- Script: `paper_trader/thesis_generator.py` — asks Claude (Opus 4.8) for 16 new candidate strategy *parameterizations* each week, as structured JSON (indicator_type + params + a plain-English thesis) — never code. Degrades gracefully to zero new candidates if `ANTHROPIC_API_KEY` is unset or the API call fails; the weekly tournament still re-tests the current 4 either way. Typical cost: a few cents to ~20 cents/week (Sonnet 5/Opus 4.8 pricing on ~5K input + ~7K output tokens) — well under the ~$0.50/week ceiling this was designed against.
- Script: `paper_trader/weekly_tournament.py` — the weekly re-tournament: downloads price data through *today* (a rolling window, not the original fixed 2019-2024 range — this is what makes "re-run weekly" actually mean something), backtests the current 4 roster strategies + the 16 new candidates together, applies the train/test cheat-check (train ≤ 2021-12-31, test > 2021-12-31 through today), ranks cheat-check survivors by test-half P&L, and takes the top 4. If fewer than 4 survive, keeps incumbents (in their prior order) in the remaining slots rather than shrinking the roster. Writes the new roster to `active_strategies.json`, appends full results to `thesis_history.jsonl`, and writes `weekly_tournament_report.md`.
- Script: `paper_trader/trader.py` — scans `strategies_lib.ALL_TICKERS` for whatever's in `active_strategies.json`, enters/exits positions on each strategy's `hold_days` timer, appends every closed trade to `paper_trader/trade_log.csv`.
- Script: `paper_trader/performance_report.py` — reads `trade_log.csv`, writes `paper_trader/performance_report.md` (win rate, total trades, per-trade % gain, per-strategy breakdown), and emails a weekly digest. The report and email both show two sections: "This Week" (trades with `exit_date` in the last 7 days) and "All-Time" (cumulative since inception) — don't conflate the two when reading the Total P&L figure (fixed 2026-07-26 after the cumulative total was mistakenly sent as if it were the week's P&L).
- Script: `paper_trader/notify_failure.py` — emails an alert if any workflow step fails (auth expired, rate-limited, unhandled exception). Shared by both workflows via the `WORKFLOW_NAME` env var. Only runs on failure.
- Workflow: `.github/workflows/daily_trader.yml` — runs `trader.py` + `performance_report.py` after US market close on weekdays, commits `positions.json`, `trade_log.csv`, and `performance_report.md` back to the repo.
- Workflow: `.github/workflows/weekly_tournament.yml` — runs `weekly_tournament.py` Friday evening (after `daily_trader.yml`'s run), auto-commits the new `active_strategies.json` + `thesis_history.jsonl` + report straight to `main`. No human review step by design (paper trading only, no real money at risk) — see Safety Rules.

## Expected Outputs
- `positions.json` — currently open positions.
- `trade_log.csv` — one row per closed trade (ticker, strategy, entry/exit date, entry/exit price, shares, % gain, $ P&L). This is the source of truth for live performance — never delete rows from it.
- `performance_report.md` — regenerated every run; summary stats + full trade table.
- `active_strategies.json` — the current live roster of exactly 4 strategy specs; rewritten every Friday.
- `thesis_history.jsonl` — one JSON line per week: every candidate evaluated that week (new + incumbent), its full backtest stats, cheat-check verdict, and which 4 made the next roster. Append-only audit trail — never delete rows from it.
- `weekly_tournament_report.md` — human-readable summary of the latest weekly run.
- A weekly email (Fridays) to `GMAIL_ADDRESS` summarizing win rate, trade count, and P&L. Skipped automatically if no trades have closed yet.
- A failure-alert email to `GMAIL_ADDRESS` any day either workflow errors out (no silent failures — if you don't hear from it and don't get an alert, check the Actions tab manually).

## Key Settings
- `active_strategies.json` — the live roster; each spec's `hold_days` and `params` are the per-strategy exit timer / thresholds.
- `POSITION_SIZE` (top of `trader.py` and `strategies_lib.py`) — flat dollar amount per trade.
- `strategies_lib.PARAM_BOUNDS` / `HOLD_DAYS_BOUNDS` — the hard safety clamps every strategy spec passes through before it can be backtested or traded, regardless of source.
- `weekly_tournament.TRAIN_CUTOFF` / `MIN_TRADES_TO_SURVIVE` / `ROSTER_SIZE` — cheat-check split date, minimum trade count to be statistically meaningful, and roster size (currently 4).
- Required secrets (GitHub Actions repo secrets, or local `.env` — see `.env.example`): `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` (a Gmail *app password*, not the real password), `ANTHROPIC_API_KEY` (optional — see thesis_generator.py above).

## How the Roster Changes Over Time
This replaced the old manual process (re-run the tournament scripts by hand, eyeball `performance_report.md`, hand-edit `trader.py`'s `STRATEGIES`/`HOLD_DAYS`). Now it's fully automatic and auto-committed every Friday — see `weekly_tournament.py` above for the mechanics. Claude only ever picks `indicator_type` + tunable params from the fixed registry in `strategies_lib.py` and writes a plain-English thesis; it never writes or influences execution code, so a bad or adversarial response can't produce out-of-range behavior — every param is re-clamped before use regardless of source. To retire an indicator type entirely (not just let it lose the weekly ranking), remove it from `strategies_lib.DIRECTIONS`/`PARAM_BOUNDS` — that requires a human edit and a normal commit, same as any other code change.

## Safety Rules
- `paper=True` must never be removed from `make_client()` in `trader.py`.
- Never hardcode `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`/`GMAIL_APP_PASSWORD`/`ANTHROPIC_API_KEY` — always read from environment/secrets.
- `trade_log.csv` and `thesis_history.jsonl` are append-only records — trading logic should only ever add rows, never rewrite or delete history.
- Claude (via `thesis_generator.py`) never writes or executes code — only structured JSON (`indicator_type`, `params`, `hold_days`, `thesis`) that strategies_lib.py clamps to fixed bounds and evaluates through hand-written, human-reviewed indicator formulas. This is why weekly auto-commit to `main` is acceptable here despite no human review step: the blast radius of a bad weekly proposal is bounded by the clamps and the fixed indicator set, and it's paper money regardless.
- If you ever add real-money trading, revisit the "no human review" decision above — it was made specifically because this is paper-only.
