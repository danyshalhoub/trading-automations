---
description: Rerun the weekly paper-trading strategy tournament end-to-end — generate candidates, backtest, report results, and ask before pushing.
---

Run this week's strategy tournament for the paper trader in `Trading Automations/paper_trader/`, start to finish:

1. **Generate candidates.** Follow the `stock-thesis-generator` skill
   (`Trading Automations/.claude/skills/stock-thesis-generator/SKILL.md`) to
   propose 20 new candidate strategies given current market conditions and
   the current roster, and write them to
   `Trading Automations/paper_trader/weekly_candidates.json`.

2. **Run the tournament.** From `Trading Automations/paper_trader/`, run
   `python3 weekly_tournament.py`. It backtests the 4 incumbents + the 20
   candidates, applies the train/test cheat-check, picks the new top-4
   roster, writes `active_strategies.json`, appends to
   `thesis_history.jsonl`, writes `weekly_tournament_report.md`, and deletes
   `weekly_candidates.json`. If the current `active_strategies.json` doesn't
   look like the last known-good roster (e.g. it was already overwritten by
   an out-of-band run), check `git status`/`git diff` before running rather
   than assuming — see the note on the 2026-07-31 cron/merge incident in
   conversation history if this comes up again.

3. **Report the results in plain English**, not finance jargon:
   - Which strategies are in for the new roster, which got dropped, and why
     (in simple terms — what each strategy actually does).
   - For each of the 4 roster strategies: number of trades, win rate,
     average $ per trade, worst single trade, worst losing streak
     (drawdown), and profit in both the older/training half and the
     recent/test half of the backtest — pulled from `thesis_history.jsonl`'s
     latest record (the `stats` field per result) and `weekly_tournament_report.md`.
   - Flag it clearly if a strategy's live paper-trading win rate (from
     `performance_report.md`) diverges a lot from its backtested win rate —
     that's expected with a small live sample, but worth a one-line note.

4. **Ask before pushing.** Show a `git status`/`git diff --stat` summary of
   what changed, then explicitly ask whether to commit and push. Never push
   automatically — this rewrites the live roster file `trader.py` reads
   every day, so it needs a yes each time, same as any other push in this
   repo.

   Once approved, always run `git pull --rebase origin main` right before
   `git push`, even if the push hasn't been rejected yet — the daily-trader
   cron (`daily_trader.yml`) can land a `positions.json`/`pending_entries.json`
   commit at any time and race a manual push (see the 2026-08-07 push
   rejection in conversation history). Pulling first avoids the rejection
   instead of reacting to it after the fact. If the rebase surfaces a real
   conflict (not just divergent unrelated files), stop and show it rather
   than resolving it silently.
