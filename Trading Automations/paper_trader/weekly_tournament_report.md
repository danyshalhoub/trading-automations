# Weekly Strategy Tournament Report

_Run date: 2026-08-14_

## New Candidates Generated: 20
## Total Evaluated (incumbents + new): 24
## Survivors: 17

## Next Week's Roster
| Name | Indicator | Params | Hold Days | Test P&L | Verdict |
|---|---|---|---|---|---|
| low_52w_bounce_loose | low_52w_bounce | {'pct_from_low': 1.08} | 22 | $297,865 | SURVIVED |
| low_52w_bounce_mid | low_52w_bounce | {'pct_from_low': 1.05} | 18 | $287,856 | SURVIVED |
| low_52w_bounce_tight | low_52w_bounce | {'pct_from_low': 1.015} | 25 | $206,418 | SURVIVED |
| relative_strength_spy_long | relative_strength_spy | {'lookback_days': 126, 'outperform_pct': 0.2} | 25 | $180,271 | SURVIVED |

## All Candidates This Week
| Name | Type | Incumbent | Trades | Train P&L | Test P&L | Verdict | Thesis |
|---|---|---|---|---|---|---|---|
| low_52w_bounce_loose | low_52w_bounce | yes | 1852 | $83,269 | $297,865 | SURVIVED | A looser band than the two incumbent 52-week-low strategies, to test whether casting a wider net for laggards still work |
| low_52w_bounce_mid | low_52w_bounce | no | 1646 | $52,482 | $287,856 | SURVIVED | A middle-ground proximity-to-low band between the two incumbents (1.015 tight / 1.08 loose) to triangulate whether the s |
| low_52w_bounce_tight | low_52w_bounce | yes | 962 | $48,763 | $206,418 | SURVIVED | Tighter proximity to the 52-week low is a higher-conviction capitulation signal than the incumbent's 3% band; long hold  |
| relative_strength_spy_long | relative_strength_spy | yes | 2709 | $446,098 | $180,271 | SURVIVED | A longer 6-month lookback with a higher outperformance bar for more durable leaders, held longer to let sustained relati |
| n_day_breakout_40 | n_day_breakout | yes | 4749 | $378,233 | $171,673 | SURVIVED | A longer 40-day breakout lookback for higher-conviction confirmation, held longer to capture more of the trend — a secon |
| bb_lower_touch_tight | bb_lower_touch | no | 8526 | $-11,983 | $147,805 | FAILED (lost in training too) | Tighter Bollinger bands (1.5 std, 15-day window) fire more often on quick low-vol pullbacks to the lower band, fitting a |
| macd_bull_cross_fast | macd_bull_cross | no | 4797 | $428,909 | $138,006 | SURVIVED | A faster MACD cross (8/21 vs. the usual 12/26) catches momentum turns earlier, useful in a persistent uptrend where wait |
| n_day_breakout_55 | n_day_breakout | no | 3677 | $266,815 | $109,958 | SURVIVED | An even longer 55-day breakout lookback for the highest-conviction trend confirmation, given the persistent 3-month uptr |
| three_red_days_quick | three_red_days | no | 11866 | $240,226 | $105,242 | SURVIVED | Short, sharp mean-reversion bounce after 3 red days and a quick exit, since in this grinding uptrend even small pullback |
| rsi_oversold_p21_t25 | rsi_oversold | no | 1195 | $111,150 | $79,015 | SURVIVED | A longer-period, stricter RSI variant (21-day, threshold 25) for higher-conviction, longer-hold reversal trades — the op |
| rsi_oversold_p10_t35 | rsi_oversold | no | 9256 | $241,203 | $68,077 | SURVIVED | In this low-vol grind (13.7% annualized), pullbacks are shallow and RSI rarely gets deeply oversold. Loosening the thres |
| n_day_breakout_20 | n_day_breakout | no | 8352 | $457,511 | $55,150 | SURVIVED | A shorter 20-day breakout lookback (vs. the incumbent's 40) should fire more frequently and catch continuation legs earl |
| inside_day_breakout_std | inside_day_breakout | no | 7137 | $259,004 | $53,894 | SURVIVED | Inside-day coiling followed by a breakout is a natural fit for the current low realized-vol environment — compression te |
| bb_squeeze_breakout_std | bb_squeeze_breakout | no | 1463 | $83,578 | $41,938 | SURVIVED | Realized vol is compressed right now, which is exactly the setup for band squeezes. If the market keeps trending, squeez |
| golden_cross_classic | golden_cross | no | 717 | $72,932 | $27,332 | SURVIVED | The classic 50/200 trend-confirmation cross should keep paying off while SPY continues grinding to new highs on sustaine |
| capitulation_exhaustion_std | capitulation_exhaustion | no | 503 | $156,138 | $20,529 | SURVIVED | True capitulation is unlikely in this calm tape, but it's cheap to keep testing as a tail-risk hedge in case volatility  |
| high_volume_hammer_loose | high_volume_hammer | no | 271 | $7,141 | $17,296 | SURVIVED | True capitulation candles are rare in a low-vol tape, so loosening the drop threshold to 3% should surface smaller-scale |
| relative_strength_spy_broad | relative_strength_spy | no | 4609 | $403,129 | $352 | SURVIVED | A shorter 3-month lookback with a lower 10% outperformance bar (vs. the incumbent's 6-month/20%) should catch relative-s |
| gap_down_recovery_fast | gap_down_recovery | no | 2382 | $40,002 | $-9,220 | FAILED (test half lost money) | Small gap-downs should recover quickly given the underlying uptrend's strength — a fast in-and-out trade rather than a d |
| gap_up_continuation_std | gap_up_continuation | no | 2284 | $57,033 | $-35,052 | FAILED (test half lost money) | Momentum continuation after gap-ups fits a trending regime where strength tends to keep following through rather than me |
| buy_dip_ma_shallow | buy_dip_ma | no | 835 | $168,600 | $-50,063 | FAILED (test half lost money) | With SPY up 5.3% over 3 months and pullbacks staying shallow, a 6% drop-from-MA trigger (vs. the default 10%) should act |
| death_cross_short_hedge | death_cross_short | no | 847 | $-64,680 | $-101,099 | FAILED (lost in training too) | A contrarian short as a cheap diversifier against the otherwise long-heavy roster — low cost to test even though the reg |
| turn_of_month_std | turn_of_month | no | 11600 | $291,175 | $-237,245 | FAILED (test half lost money) | The turn-of-month seasonal effect is uncorrelated with trend or volatility regime, making it a useful diversifier alongs |
| failed_breakout_short_std | failed_breakout_short | no | 5767 | $-316,440 | $-270,975 | FAILED (lost in training too) | Shorting failed breakouts tests whether false breakouts still occur amid the grind — a diversifying hedge against the ro |
