# Directive: Stock Strategy Backtester

## Objective
Test a trading idea against historical price data to find out — honestly — whether it would have made money. This tool exists to disprove ideas, not validate them. A result that shows a loss is a correct result if that's what the data says.

## First Strategy Being Tested: "Short the Spike"
When a stock jumps more than 10% in one day, short it (bet the price will fall), then close 5 trading days later.

## Tools
- Script: `execution/stock_tester/backtest.py`
- Data: yfinance (free, no account needed)
- Dependencies: requirements.txt in `execution/stock_tester/`

## To Run
```bash
cd "execution/stock_tester"
pip install -r requirements.txt
python backtest.py
```

## Expected Outputs
- Console report with all stats (total P&L, win rate, max loss, max drawdown)
- Train/test split verdict — did the edge survive unseen data?
- Benchmark comparison vs. buy-and-hold S&P 500

## Known Limitations (always disclose these in output)
1. **Survivorship bias**: yfinance only shows companies that still exist. Bankrupt companies are missing. This makes every backtest look rosier than reality.
2. **Borrow fees not modeled**: Real short selling charges a daily fee to borrow shares. This tool does not model that. Real results would be worse than shown.
3. **Historical ≠ future**: A backtest is a hypothesis. It is not a promise.

## Key Settings (top of backtest.py)
- JUMP_THRESHOLD: float (default 0.10 = 10%)
- HOLD_DAYS: int (default 5)
- COMMISSION_PER_TRADE: float (default 0.001 = 0.1% each side)
- SLIPPAGE_PER_TRADE: float (default 0.001 = 0.1% each side)
- START_DATE / END_DATE: date strings
- POSITION_SIZE: dollar amount per trade

## Safety Rules
- This script must NEVER connect to a brokerage or place real trades
- Always print the survivorship bias and borrow fee warnings
- Never remove the safety notes from the output
