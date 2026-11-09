# Master XAUUSD portfolio — reconstructed architecture and performance

## Environment
MT5 Expert Advisor on **XM `GOLD.i#` M1**, user-operated through a Lubuntu/Wine workstation; historical research also used Dukascopy millisecond bid/ask. Typical native tester setup: **$10,000 initial deposit, 1:500 leverage, Every tick / real ticks when available**. XM tester `UTCOffsetSec=0` was once found despite live `+10800` seconds, causing incorrect session mapping; time assumptions must be verified per history and broker.

## Engines (read actual source before assuming parameters)
1. **Asia Opening Range Breakout (ORB)**: early-session range breakout, with original research describing a 15-minute range, 2R target and modified/trailing stop behavior after +0.5R. Highest forensic priority due to historical regime failures.
2. **Prior Range (PR)**: breakout of prior daily levels; research notes a 0.25 range fraction and 3R target. Broker-day D1 rollover synchronization was a real execution defect. Do not chase stale level breaks after maintenance.
3. **Donchian**: M15 trend/momentum breakout with ATR-based trailing, 64-bar lookback, 200 EMA, ATR(14), roughly 2x ATR stop in historical research. Treat inputs as source-to-verify.
4. **Overnight**: thresholded overnight move / Western-session continuation; historical notes include threshold 1.2 ATR, 1 ATR stop, UTC window roughly 08–18. Used as a regime/control engine.

Architecture evolved from separate observers to `XAUUSD_MasterPortfolio_Execution` integrating trade conflicts, logging and execution. Four strategies were profitable in the heavily tuned 2025–26 year but not robust across earlier years.

## Four independent annual windows — 9B CONTROL, NOT v1.11
Source: prior reconstructed broker-deal summaries; precise build/input parity must be re-established.

| MT5 historical year | P&L from $10k | PF | Interpretation |
|---|---:|---:|---|
| 2022-09-15 → 2023-09-15 | -$1,295.82 (final ~$8,704.18) | not recovered here | Failed |
| 2023-09-15 → 2024-09-15 | +$255.64 | 1.017 | Almost flat |
| 2024-09-15 → 2025-09-15 | +$385.90 | 1.022 | Almost flat |
| 2025-09-15 → 2026-09-15 | +$30,328.08 | ~1.86 | Heavily researched/tuned outlier |

In 2023–24 9B, strategy split: Donchian +$1,087.77 (PF 1.40), Overnight +$1,015.08 (PF 1.67), PR +$135.64 (PF 1.02), ORB **-$1,982.85 (PF 0.56)**. The 2025–26 results must not be described as typical future yearly expectancy.

## Separate four-year v1.11 checkpoint
**Do not merge with 9B figures**. Prior notes say the original v1.11 configuration included PR adverse-exit ON. Test-report parity cannot be independently verified from this repository.

| Year | Net P&L |
|---|---:|
| 2022–23 | **-$1,318.04** |
| 2023–24 | **+$138.24** |
| 2024–25 | **+$1,190.27** |
| 2025–26 | **+$30,860.13** |

Only 2025–26 reached the user's aspirational $30k+ annual result. Across all four windows **neither zero losses nor $30k every year was established**.

## Execution lessons worth preserving
- Earlier 0.01-minimum backtests: 230 PR signals, 185 `market closed` rejects, **172 exactly at broker 00:00**. These rejected entries were often already far past the level (median ~37.69 Gold points / ~60% R); blindly retrying was rejected.
- Correcting PR D1 series rollover in **v1.3** raised filled PR trades from 38 to 154 in an older test, with 18 market-closed rejects remaining. v1.3 reported 317 trades, +$16,287.28, PF 1.72 and ~13% max equity DD over a different 2026 subperiod. It is not a comparable four-year score.
- A prior tester started on $100, rejected all signals at minimum volume, and used wrong UTC mapping. Zero trades there was an invalid setup, not proof of a strategy failure.
- Do not treat historical risk-governor experiments (HWM thresholds, latches, Overnight exemption) as strategy improvements; they altered exposure rather than selecting better trades.

## Strategy-level opportunity
ORB's weak 2023–24 regime, trailing stop first-touch ambiguity, and false-break / delayed re-break structure are the primary research directions. Any new feature must beat a fixed version across independent years and include winners sacrificed.
