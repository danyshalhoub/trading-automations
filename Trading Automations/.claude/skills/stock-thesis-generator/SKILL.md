---
name: stock-thesis-generator
description: Generate 20 new candidate trading strategy theses for the weekly paper-trading tournament in Trading Automations/paper_trader/, as structured JSON written to weekly_candidates.json. Use when Dany wants to manually rerun the weekly strategy tournament — this replaces the old passive/paid Claude API call in thesis_generator.py with the same session of Claude Code doing the thesis generation directly, for free.
---

# Stock Strategy Thesis Generator

Propose candidate trading strategy *parameterizations* for this week's
tournament in `Trading Automations/paper_trader/`. This replaced
`thesis_generator.py`'s automated Anthropic API call — the same reasoning now
happens directly in a Claude Code session, on demand, at no marginal cost.

This is research-only, paper-trading strategy design. No code execution, no
real money, no live trades — just proposing parameters that
`weekly_tournament.py` will backtest through the fixed, vetted indicator
engine before anything can affect the live roster.

## What to do

1. **Read the registry.** Open `Trading Automations/paper_trader/strategies_lib.py`
   and read `DIRECTIONS` and `PARAM_BOUNDS`. You may only pick
   `indicator_type` from this exact list, and only vary the params it lists,
   within their `(min, max)` bounds — these are the only signal formulas the
   system knows how to execute. Do not invent new indicator types or params.

2. **Read the current roster.** Open
   `Trading Automations/paper_trader/active_strategies.json` for the 4
   incumbent strategies (name, indicator_type, params, hold_days, thesis).
   They'll be re-tested automatically alongside your candidates — you don't
   need to re-propose them, but a different parameterization of one is fine
   if current conditions call for it.

3. **Get market context.** Pull recent SPY performance to reason about
   current conditions (trending vs. choppy, high vs. low volatility). Quick
   way to get it:
   ```bash
   cd "Trading Automations/paper_trader" && python3 -c "
   import yfinance as yf
   spy = yf.download('SPY', period='4mo', auto_adjust=True, progress=False)
   if hasattr(spy.columns, 'get_level_values'):
       spy.columns = [c[0] for c in spy.columns]
   close = spy['Close']
   print(f\"SPY 1-month return: {(close.iloc[-1]/close.iloc[-21]-1)*100:+.1f}%\")
   print(f\"SPY 3-month return: {(close.iloc[-1]/close.iloc[-63]-1)*100:+.1f}%\")
   print(f\"Annualized 1-month volatility: {close.pct_change().tail(21).std()*(252**0.5)*100:.1f}%\")
   "
   ```

4. **Propose exactly 20 candidates.** For each, give a short plain-English
   thesis for why this specific parameterization might perform well given
   current market conditions (reference the market context — e.g. tighter or
   looser thresholds in a high- or low-volatility regime). Repeating an idea
   similar to a prior week is fine if it still seems feasible. Prefer
   diversity across indicator types over many variations of one type.
   `hold_days` must be a whole number between 3 and 30.

5. **Write the output.** Save the 20 candidates as a JSON array to
   `Trading Automations/paper_trader/weekly_candidates.json`, matching this
   exact shape (one object per candidate):
   ```json
   [
     {
       "name": "rsi_oversold_p10_t25",
       "indicator_type": "rsi_oversold",
       "params": {"period": 10, "threshold": 25},
       "hold_days": 12,
       "thesis": "Tighter RSI threshold for a choppier tape: ..."
     }
   ]
   ```
   `weekly_tournament.py` clamps every param to the registry's bounds before
   backtesting regardless, so exact precision isn't critical — just stay
   sensibly within the documented ranges.

6. **Hand off.** Tell Dany the candidates file is ready and that running
   `python3 weekly_tournament.py` (from `Trading Automations/paper_trader/`)
   will backtest incumbents + candidates together, apply the train/test
   cheat-check, and update `active_strategies.json` with the new top-4
   roster. Offer to run it for him if he wants — don't run it silently
   without saying so, since it rewrites the live roster file.

## Safety

- Never propose an `indicator_type` outside `DIRECTIONS` in `strategies_lib.py`.
- Never propose params outside `PARAM_BOUNDS` — even though they'd be
  clamped anyway, out-of-range proposals are a sign of a broken thesis.
- This only ever produces a candidates *list* for backtesting — it must
  never touch `active_strategies.json`, `trader.py`, or place any live
  trades directly.
