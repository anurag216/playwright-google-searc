# Research state — 2026-11-09

## Objective and scope
Improve XAUUSD entry/exit/setup quality and net expectancy across independent regimes; preserve winners and trade frequency. Not portfolio drawdown masking. Separate scalping track is exploratory and must not be conflated with the master EA.

## Source/version hierarchy
- **v1.11 and v1.12**: later research versions that the user regarded as the preferred working line; `v1.12` Monday-specific Prior Range adverse-exit hypothesis was **not promoted**. Their code is absent from this repo.
- **v1.11 four-year checkpoint**: recorded configuration with a Prior Range adverse-exit feature ON; not equivalent to 9B or to every SC5 variant. See `MASTER_PORTFOLIO.md`.
- **9B**: controlled baseline used to reconstruct the complete ORB winner/loss denominator. It is **not** the newest preferred deployment file.
- **SC5**: short-only +0.5R cash-out experiment, initially default-OFF in research copies; native 2022–23 test delivered only +$11.66 portfolio improvement; not accepted.
- The exact current on-disk `.mq5`, `.set`, terminal/build metadata, and logged test configurations must be recovered before new EA work.

## Last specifically bounded loss-forensics task
Reconstruct the **38 moved-stop loss paths in 2022-09-15 to 2023-09-15** from the 9B ORB denominator, using frozen rules and original-entry / original-stop / 90-minute deadline. Contrast them with all **33 armed winners** and **42 unarmed losses** in the same year. Then analyze 30 moved-stop losses, 21 armed winners, and 54 unarmed losses for 2023–24. Do not label a moved-stop loss a recoverable winner until bid/ask first-touch order proves it. A prior generated-tick recovery simulation lacked sufficient feed/quote parity and was rejected as XM execution proof.

Denominator counts:
| 9B period | Executed ORB | Moved-stop armed | Armed winners | Moved-stop losses | Unarmed losses |
|---|---:|---:|---:|---:|---:|
| 2022–23 | 113 | 71 | 33 | 38 | 42 |
| 2023–24 | 105 | 51 | 21 | 30 | 54 |

**Current decision:** No EA change and no new threshold tuning. This is forensic reconstruction, not a trailing-rule approval.

## Separate pending SC5 validation
For v1.11's short-only cash-out, 2022–23 native MT5 original/OFF parity succeeded; the ON uplift was negligible after position-sizing propagation. Next independent native 2023–24 original/OFF/ON match was requested, but no reconciled result is available here. Do not call SC5 validated.

## Data gaps / required next actions
1. Identify or retrieve authoritative `XAUUSD_MasterPortfolio_Execution_v1_11_EntryLossQualityResearch_SC5.mq5` and `XAUUSD_MasterPortfolio_Execution_v1_12_PRMondayAdverseResearch_SC5.mq5` (referenced in prior records, not present in this repo).
2. Locate original 9B `.mq5`, all `.set`, complete MT5 deals/orders/journal, strategy-specific signal logs, and raw tick files, preferably in a PRIVATE storage workflow.
3. Reproduce baseline unchanged before changing strategy logic.
4. Record first-touch classification of all cases, preserving winning denominator and year separation.

## Report template
Objective: ORB loss forensics.
Hypothesis: some post-+0.5R moved stops realize an avoidable loss, versus original stop and 90m exit.
Evidence: all armed winners, moved-stop losers, and unarmed losses.
Current finding: counts reconciled, counterfactual survival unproven.
Counterexamples: profitable moved-stop winners; replays not executable broker proof.
EA changes: none.
Scope check: improving actual exit logic, not risk throttling.
