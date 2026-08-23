# Weekly Strategy Tournament Report

_Run date: 2026-08-23_

## New Candidates Generated: 20
## Total Evaluated (incumbents + new): 24
## Survivors: 17

## Next Week's Roster
| Name | Indicator | Params | Hold Days | Test P&L | Verdict |
|---|---|---|---|---|---|
| rsi_oversold_p21_t35 | rsi_oversold | {'period': 21, 'threshold': 35} | 14 | $305,150 | SURVIVED |
| low_52w_bounce_loose | low_52w_bounce | {'pct_from_low': 1.08} | 22 | $298,243 | SURVIVED |
| low_52w_bounce_mid | low_52w_bounce | {'pct_from_low': 1.05} | 18 | $288,158 | SURVIVED |
| three_red_days_quick | three_red_days | {'num_days': 3} | 8 | $222,674 | SURVIVED |

## All Candidates This Week
| Name | Type | Incumbent | Trades | Train P&L | Test P&L | Verdict | Thesis |
|---|---|---|---|---|---|---|---|
| rsi_oversold_p21_t35 | rsi_oversold | no | 4262 | $163,077 | $305,150 | SURVIVED | A looser, slower RSI to catch the shallow, short-lived dips that happen inside a steady low-vol uptrend, since deep over |
| low_52w_bounce_loose | low_52w_bounce | yes | 1830 | $88,407 | $298,243 | SURVIVED | A looser band than the two incumbent 52-week-low strategies, to test whether casting a wider net for laggards still work |
| low_52w_bounce_mid | low_52w_bounce | yes | 1627 | $56,739 | $288,158 | SURVIVED | A middle-ground proximity-to-low band between the two incumbents (1.015 tight / 1.08 loose) to triangulate whether the s |
| three_red_days_quick | three_red_days | no | 11245 | $280,435 | $222,674 | SURVIVED | A quick mean-reversion bounce after three consecutive down days, sized for a fast exit since pullbacks inside this uptre |
| low_52w_bounce_tight | low_52w_bounce | yes | 945 | $51,692 | $198,879 | SURVIVED | Tighter proximity to the 52-week low is a higher-conviction capitulation signal than the incumbent's 3% band; long hold  |
| relative_strength_spy_long | relative_strength_spy | yes | 2694 | $426,033 | $193,240 | SURVIVED | A longer 6-month lookback with a higher outperformance bar for more durable leaders, held longer to let sustained relati |
| low_52w_bounce_tighter_short_hold | low_52w_bounce | no | 1269 | $22,454 | $189,616 | SURVIVED | A tighter proximity-to-low band than the current tight incumbent (1.015) with a shorter hold, testing whether quicker ex |
| n_day_breakout_long | n_day_breakout | no | 4737 | $360,974 | $172,088 | SURVIVED | A longer lookback breakout for more durable trend-followers, contrasting the short variant to see which horizon the curr |
| macd_bull_cross_fast | macd_bull_cross | no | 4972 | $367,172 | $148,334 | SURVIVED | A faster MACD cross to catch trend-continuation entries earlier in a market that's been grinding higher for three months |
| rsi_oversold_p10_t25 | rsi_oversold | no | 5504 | $137,131 | $137,935 | SURVIVED | SPY is up 3.6% over the last month with volatility near 13% annualized -- a quiet grind higher. Real oversold reads are  |
| bb_lower_touch_wide | bb_lower_touch | no | 2007 | $-43,264 | $118,118 | FAILED (lost in training too) | Wider bands than the default 2.0 std so a lower-band touch stays a meaningful signal even though the market's low volati |
| relative_strength_spy_short_lookback | relative_strength_spy | no | 4247 | $393,025 | $83,080 | SURVIVED | A shorter 2-month lookback with a lower outperformance bar than the incumbent's 6-month/20% version, to catch emerging l |
| inside_day_breakout_std | inside_day_breakout | no | 7113 | $250,091 | $52,217 | SURVIVED | A classic volatility-contraction setup (inside day followed by a breakout) that should fire often given how compressed d |
| bb_squeeze_breakout_std | bb_squeeze_breakout | no | 1455 | $82,176 | $38,220 | SURVIVED | Low realized volatility means squeezes are common right now; this looks for names breaking out of a genuine multi-month  |
| n_day_breakout_short | n_day_breakout | no | 10315 | $545,037 | $32,468 | SURVIVED | A short lookback breakout to catch momentum names making fresh local highs frequently in a grinding, low-volatility uptr |
| buy_dip_ma_deep | buy_dip_ma | no | 93 | $11,127 | $19,623 | SURVIVED | Contrast to the shallow variant -- a deeper capitulation drop above the 200-day MA should be rarer but higher-conviction |
| capitulation_exhaustion_std | capitulation_exhaustion | no | 719 | $92,691 | $8,163 | SURVIVED | Looks for a sharp pullback on fading volume while still above the 200-day MA -- an exhaustion pattern that should be rar |
| high_volume_hammer_std | high_volume_hammer | no | 207 | $-743 | $6,758 | FAILED (lost in training too) | Capitulation-and-reversal candles on above-average volume, tuned for the smaller daily ranges typical of a low-vol tape. |
| gap_down_recovery_std | gap_down_recovery | no | 2344 | $33,053 | $4,574 | SURVIVED | Fast reversal of overnight gap-downs that close green, betting that isolated bad-news gaps get bought quickly while the  |
| buy_dip_ma_shallow | buy_dip_ma | no | 852 | $125,287 | $-7,227 | FAILED (test half lost money) | In a low-vol uptrend, single-day drops rarely exceed 6-8%, so a shallower drop threshold above a shorter 150-day MA shou |
| golden_cross_fast | golden_cross | no | 1264 | $94,730 | $-38,996 | FAILED (test half lost money) | A faster MA pairing than the standard 50/200 to pick up trend-continuation crosses sooner, given the market has been tre |
| gap_up_continuation_std | gap_up_continuation | no | 3087 | $36,374 | $-103,895 | FAILED (test half lost money) | Momentum continuation off a strong gap-up day, fitting a tape where good news tends to keep working rather than getting  |
| turn_of_month_std | turn_of_month | no | 11509 | $273,152 | $-230,275 | FAILED (test half lost money) | The well-documented turn-of-month seasonal drift, which should still hold in a steady grinding-higher regime like this o |
| failed_breakout_short_std | failed_breakout_short | no | 6232 | $-243,752 | $-264,261 | FAILED (lost in training too) | A short strategy betting against breakouts that fail on weak volume -- a useful hedge-style candidate even in an uptrend |
