# Weekly Strategy Tournament Report

_Run date: 2026-08-07_

## New Candidates Generated: 20
## Total Evaluated (incumbents + new): 24
## Survivors: 15

## Next Week's Roster
| Name | Indicator | Params | Hold Days | Test P&L | Verdict |
|---|---|---|---|---|---|
| low_52w_bounce_loose | low_52w_bounce | {'pct_from_low': 1.08} | 22 | $296,015 | SURVIVED |
| low_52w_bounce_tight | low_52w_bounce | {'pct_from_low': 1.015} | 25 | $207,979 | SURVIVED |
| relative_strength_spy_long | relative_strength_spy | {'lookback_days': 126, 'outperform_pct': 0.2} | 25 | $177,543 | SURVIVED |
| n_day_breakout_40 | n_day_breakout | {'lookback': 40} | 20 | $171,316 | SURVIVED |

## All Candidates This Week
| Name | Type | Incumbent | Trades | Train P&L | Test P&L | Verdict | Thesis |
|---|---|---|---|---|---|---|---|
| low_52w_bounce_loose | low_52w_bounce | no | 1846 | $83,269 | $296,015 | SURVIVED | A looser band than the two incumbent 52-week-low strategies, to test whether casting a wider net for laggards still work |
| low_52w_bounce_tight | low_52w_bounce | yes | 961 | $48,763 | $207,979 | SURVIVED | Tighter proximity to the 52-week low is a higher-conviction capitulation signal than the incumbent's 3% band; long hold  |
| relative_strength_spy_long | relative_strength_spy | no | 2706 | $446,098 | $177,543 | SURVIVED | A longer 6-month lookback with a higher outperformance bar for more durable leaders, held longer to let sustained relati |
| n_day_breakout_40 | n_day_breakout | no | 4733 | $378,233 | $171,316 | SURVIVED | A longer 40-day breakout lookback for higher-conviction confirmation, held longer to capture more of the trend — a secon |
| macd_bull_cross | macd_bull_cross | yes | 3789 | $340,636 | $167,063 | SURVIVED | Early-stage momentum shift: MACD bullish crossover while still below zero. Replaced bb_lower_touch on 2026-07-12 after i |
| 52w_low_bounce | low_52w_bounce | yes | 1229 | $69,894 | $156,174 | SURVIVED | Contrarian bounce off maximum pessimism: stock within 3% of its 52-week low. |
| macd_bull_cross_fast | macd_bull_cross | yes | 5498 | $432,343 | $120,284 | SURVIVED | A faster MACD pair should catch momentum shifts sooner in a low-vol grind, where the incumbent 12/26/9 cross can be slow |
| bb_lower_touch_tight | bb_lower_touch | no | 6222 | $172,914 | $99,674 | SURVIVED | Tighter Bollinger band on a shorter window flags smaller deviations from the mean, appropriate when overall volatility i |
| macd_bull_cross_mid | macd_bull_cross | no | 4588 | $359,662 | $89,305 | SURVIVED | A middle-speed MACD pair (between the incumbent's standard and fast variants) to catch momentum shifts a bit sooner than |
| rsi_oversold_p10_t25 | rsi_oversold | no | 5919 | $38,858 | $77,228 | SURVIVED | In a low-vol uptrend (SPY 3mo +5.1%, ann. vol 14%), dips get bought fast — a tighter/faster RSI oversold read should cat |
| n_day_breakout_20 | n_day_breakout | no | 8332 | $457,511 | $57,048 | SURVIVED | Classic momentum breakout — a 20-day high in a market with low volatility and a positive trend is more likely to be a ge |
| bb_squeeze_breakout_std | bb_squeeze_breakout | no | 1460 | $83,578 | $44,111 | SURVIVED | Low current volatility means more names are likely coiled in squeezes; a breakout out of that squeeze in a broadly risin |
| relative_strength_spy_std | relative_strength_spy | no | 3206 | $468,625 | $17,284 | SURVIVED | With SPY itself up 5.1% over 3 months, screening for names outperforming that already-rising benchmark should surface ge |
| buy_dip_ma_shallow | buy_dip_ma | no | 600 | $109,185 | $6,789 | SURVIVED | In a market up 5% over 3 months, deep 10%+ single-day drops are rare; a shallower drop threshold against a shorter trend |
| capitulation_exhaustion_std | capitulation_exhaustion | no | 742 | $205,262 | $2,410 | SURVIVED | Looks for a sharp cumulative decline on fading volume while still above the 200-day MA — a pullback-within-an-uptrend pa |
| high_volume_hammer_std | high_volume_hammer | no | 172 | $-2,273 | $-1,521 | FAILED (lost in training too) | Capitulation-style reversal on elevated volume; a higher volume-ratio bar filters for real panic selling even though the |
| gap_down_recovery_std | gap_down_recovery | no | 1403 | $-6,558 | $-2,805 | FAILED (lost in training too) | A same-day recovery from a 4%+ gap down suggests the drop was noise rather than a real regime shift, consistent with an  |
| golden_cross_fast | golden_cross | no | 1246 | $123,849 | $-19,501 | FAILED (test half lost money) | Faster moving-average pair should confirm the current uptrend sooner than a classic 50/200 cross, letting the strategy r |
| inside_day_breakout_std | inside_day_breakout | no | 7616 | $158,140 | $-80,470 | FAILED (test half lost money) | Inside-day compression followed by a breakout is a low-vol-friendly pattern — consolidation-then-continuation fits a mar |
| gap_up_continuation_std | gap_up_continuation | no | 3118 | $44,705 | $-99,846 | FAILED (test half lost money) | Gap-up-and-hold continuation should work better than usual right now since low volatility means gaps are more likely dri |
| death_cross_short_std | death_cross_short | no | 846 | $-64,679 | $-101,012 | FAILED (lost in training too) | Even in a rising tape, individual laggards break down; this shorts names whose own trend rolls over, providing diversifi |
| three_red_days_quick | three_red_days | no | 21147 | $517,521 | $-154,060 | FAILED (test half lost money) | Only two consecutive red days needed — a short, shallow pullback signal suited to a low-vol tape where extended down-str |
| failed_breakout_short_std | failed_breakout_short | no | 5173 | $-300,123 | $-226,767 | FAILED (lost in training too) | Shorts breakouts that fail on weak volume the next day — a check against complacency, since low volatility can mask thin |
| turn_of_month_std | turn_of_month | no | 11468 | $291,175 | $-261,924 | FAILED (test half lost money) | Turn-of-month seasonality is regime-agnostic and worth re-testing every cycle; current calm conditions shouldn't interfe |
