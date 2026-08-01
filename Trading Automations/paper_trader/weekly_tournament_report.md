# Weekly Strategy Tournament Report

_Run date: 2026-07-31_

## New Candidates Generated: 20
## Total Evaluated (incumbents + new): 24
## Survivors: 15

## Next Week's Roster
| Name | Indicator | Params | Hold Days | Test P&L | Verdict |
|---|---|---|---|---|---|
| low_52w_bounce_tight | low_52w_bounce | {'pct_from_low': 1.015} | 25 | $203,710 | SURVIVED |
| macd_bull_cross | macd_bull_cross | {'fast': 12, 'slow': 26, 'signal': 9} | 20 | $158,892 | SURVIVED |
| 52w_low_bounce | low_52w_bounce | {'pct_from_low': 1.03} | 20 | $158,357 | SURVIVED |
| macd_bull_cross_fast | macd_bull_cross | {'fast': 8, 'slow': 21, 'signal': 6} | 12 | $117,013 | SURVIVED |

## All Candidates This Week
| Name | Type | Incumbent | Trades | Train P&L | Test P&L | Verdict | Thesis |
|---|---|---|---|---|---|---|---|
| bb_lower_touch_wide | bb_lower_touch | no | 1722 | $-32,856 | $213,817 | FAILED (lost in training too) | A wider window and stricter 2.5-std band is a higher-conviction extreme-deviation signal for when the market does have a |
| low_52w_bounce_tight | low_52w_bounce | no | 955 | $48,763 | $203,710 | SURVIVED | Tighter proximity to the 52-week low is a higher-conviction capitulation signal than the incumbent's 3% band; long hold  |
| macd_bull_cross | macd_bull_cross | yes | 3767 | $340,636 | $158,892 | SURVIVED | Early-stage momentum shift: MACD bullish crossover while still below zero. Replaced bb_lower_touch on 2026-07-12 after i |
| 52w_low_bounce | low_52w_bounce | yes | 1227 | $69,894 | $158,357 | SURVIVED | Contrarian bounce off maximum pessimism: stock within 3% of its 52-week low. |
| macd_bull_cross_fast | macd_bull_cross | no | 5492 | $432,343 | $117,013 | SURVIVED | A faster MACD pair should catch momentum shifts sooner in a low-vol grind, where the incumbent 12/26/9 cross can be slow |
| n_day_breakout_20 | n_day_breakout | no | 9095 | $480,656 | $98,866 | SURVIVED | 20-day high breakouts in a low-vol grind-up market should be cleaner (less noise, less immediate fade) with steadier fol |
| rsi_oversold | rsi_oversold | yes | 5161 | $32,810 | $85,759 | SURVIVED | Classic oversold bounce: RSI(14) drops below 30. |
| rsi_oversold_tight | rsi_oversold | no | 4781 | $24,117 | $63,546 | SURVIVED | SPY is in a low-vol grind (12.4% annualized 1-month vol, +0.3% 1mo / +3.9% 3mo). A tighter RSI threshold and shorter per |
| bb_squeeze_breakout_default | bb_squeeze_breakout | no | 1253 | $45,877 | $41,467 | SURVIVED | Low realized vol means Bollinger squeezes are common right now. A breakout from a squeeze inside a mild 3-month uptrend  |
| buy_dip_ma_long_ma | buy_dip_ma | no | 435 | $110,823 | $39,295 | SURVIVED | Same shallow-dip logic, but filtered by the full 1-year MA for a stricter 'still in a real uptrend' check before buying  |
| buy_dip_200ma | buy_dip_ma | yes | 222 | $28,483 | $32,948 | SURVIVED | Panic dip inside a healthy uptrend: stock drops >10% in a day but stays above its 200-day MA. |
| golden_cross_classic | golden_cross | no | 716 | $54,061 | $32,430 | SURVIVED | Classic trend-following entry. The market's already in a mild 3-month uptrend with low vol, so a fresh golden cross shou |
| bb_lower_touch_tight | bb_lower_touch | no | 8026 | $42,530 | $25,853 | SURVIVED | With realized vol this low, the default 2.0-std lower band rarely gets touched. Tightening to 1.5 std should generate en |
| relative_strength_spy_default | relative_strength_spy | no | 3199 | $468,625 | $18,682 | SURVIVED | Names meaningfully outperforming SPY's +3.9% 3-month return show real relative strength worth riding, rather than bettin |
| inside_day_breakout_default | inside_day_breakout | no | 7319 | $192,194 | $6,016 | SURVIVED | Inside-day contraction followed by a breakout is a volatility-contraction signal that should show up more often in the c |
| high_volume_hammer_lowvol | high_volume_hammer | no | 430 | $20,865 | $5,926 | SURVIVED | Lowering the drop threshold to fit current low volatility, while still requiring above-average volume and a strong intra |
| gap_down_recovery_default | gap_down_recovery | no | 2439 | $-28,593 | $-4,480 | FAILED (lost in training too) | An intraday reversal of a gap-down is a quick mean-reversion play; short hold to capture just the snapback, not a longer |
| capitulation_exhaustion_lowvol | capitulation_exhaustion | no | 759 | $227,950 | $-9,092 | FAILED (test half lost money) | Lowering the cumulative-return threshold to fit current low realized vol, so a 7% pullback on below-average volume (exha |
| gap_up_continuation_default | gap_up_continuation | no | 2465 | $-4,539 | $-16,883 | FAILED (lost in training too) | In a mild uptrend, gap-ups that hold and close green often continue short-term as a momentum-continuation play. |
| buy_dip_ma_shallow | buy_dip_ma | no | 1020 | $58,088 | $-17,431 | FAILED (test half lost money) | The incumbent's 10% single-day drop threshold will be rare at 12.4% annualized vol. Lowering to 6% with a shorter 150-da |
| three_red_days_quick | three_red_days | no | 23109 | $428,397 | $-85,679 | FAILED (test half lost money) | In a calm, mildly-up tape, even two consecutive red days stands out more than usual. Short hold to capture the immediate |
| death_cross_short_classic | death_cross_short | no | 653 | $-98,859 | $-96,826 | FAILED (lost in training too) | A hedge/diversifier on the short side: even with SPY in a mild uptrend, individual names breaking their own long-term tr |
| failed_breakout_short_default | failed_breakout_short | no | 5739 | $-316,440 | $-264,619 | FAILED (lost in training too) | In a low-vol tape, genuine breakouts should hold; ones that fail immediately on weak volume are a cleaner exhaustion sig |
| turn_of_month_default | turn_of_month | no | 11468 | $203,873 | $-425,422 | FAILED (test half lost money) | Well-documented turn-of-month seasonal drift is regime-independent, so it's a useful diversifier regardless of the curre |
