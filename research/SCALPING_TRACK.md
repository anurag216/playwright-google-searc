# High-frequency scalping track — separate from Master Portfolio

**Broker execution baseline:** read [`BROKER_EXECUTION_PROFILE.md`](BROKER_EXECUTION_PROFILE.md) before any executable XAUUSD simulation. No Raw Spread account or commission schedule has been verified.

## Original user intent
The user referenced a **video of a bot harvesting small moves in either price direction**: repeated small buys as price moves down, profit closes on retracements; similarly sells after upward moves and closes on downward retracements, with many intraday trades. **The original video was NOT recovered**, so this description is user intent, not verified order-level mechanics. Do NOT assume the video uses a grid, hedging, martingale, or guaranteed-profit strategy.

## Historical exploratory work: XAUUSD
- SMC / micro opportunity-lab concepts around 2026-09-05, including `v0_7_event_driven_opportunity_lab.py` (referenced, not present in this repo).
- One research pass: **7,399,444 observed ticks, 41,280 observations**, roughly **85.78% availability** of executable +$1 target touches, but only **50.45% no-lookahead first-direction accuracy**; tested stop/timeout/P&L simulations remained negative.
- Earlier generated-tick opportunity statistics (~6,894 windows; ~50% directional accuracy) were not proof of a profitable executable EA.
- Required distinction: **a future price touch is not an entry signal**. Quoting high opportunity availability while ignoring spread, commission, slippage, stop/timeout, and first-touch order creates false optimism.
- The `v0_7` lab was described as entering only after completed windows and treating train/validation distinctly from holdouts. Its actual code/results must be recovered before reuse.

## Historical exploratory work: BTCUSD# (2026-10-04)
Project referenced as **`BTC_MicroReversion_Scalper`**; source is not in this repository.
- v0.1: tick-driven prototype with a tester-time handling issue.
- v0.2: signal-based / mean-reversion basket with sampling and historical millisecond-time fix; 0.01 lots, up to 3 entries, bid/ask handling, volatility/displacement/exhaustion inputs. Recovered tester parameters include 250ms sampling, 120-sample lookback, Z-entry 2.0, Z-exit 0.35, TP 0.2 ATR, SL 0.85 ATR, basket expiry 180s. Verify exact source/settings before repeating.
- **v0.2 single-entry test: 231 trades, -$30.36, PF 0.664.** A mid-price-only accounting comparison was **+$4.31 / PF 1.052**, illustrating how friction destroyed a marginal apparent edge. A later regime was negative.
- **v0.3 ~-$7.55** improvement was mostly from suppressing trades, not clear positive expectancy; **v0.4 ~-$9.21** worsened and was rejected.
- **No v0.5 validated**. More entries during adverse moves empirically worsened results. The v0.x implementation must not be represented as a functioning profitable bidirectional bot.
- Recovered execution journals show real bid/ask fills and mean-reversion basket closes; they do **not** establish the original video's algorithm.

## Next scientific question
Instead of copying superficial order cadence, identify whether *predictable near-term reversal after directional displacement* exists at bid/ask executable prices, in what volatility/spread regimes, and whether expected move > costs + stop/timeout loss. Compare all candidate signals against negative and positive realized outcomes, on multiple non-overlapping regimes. Maintain a distinct research dataset and ledger. Do not start doubling down, averaging losses, or building perpetual grid exposure to imitate a screenshot.

## Explicit status
Exploratory; **no demonstrated positive net expectancy after realistic execution**, no existing code here, no approved EA implementation. Keep this separate from ORB/PR/Donchian/Overnight loss-forensics priority.
