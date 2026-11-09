# Experiment and hypothesis ledger (reconstructed, NOT raw logs)

**Status definitions:** REJECTED = tested/counterexample-damaged; OPEN = hypothesis only; CANDIDATE = evidence incomplete; EXECUTION FIX = implementation rather than trading edge. Each new experiment should receive an immutable ID, year-by-year baseline table, source-data hash, exact configuration, all eligible winners and losers, final decision.

| ID / area | Finding | Status / next action |
|---|---|---|
| ORB moved-stop after +0.5R | 9B denominator 2022–23: 113 entries, 71 armed (33 armed winners, 38 moved-stop losses); 2023–24: 105 entries, 51 armed (21 winners, 30 losses). These are NOT 68 proved avoidable losses. | **OPEN** first-touch replay against original SL and 90m timeout, keeping winners. |
| ORB short-only SC5 +0.5R cash-out | v1.11 native 2022–23 original/OFF $8,681.96, ON $8,693.62. Reported 21 losses converted but 12 winners reduced; nominal direct cash-out benefit +$298.15 offset ~$286.49 by subsequent sizing/interactions = **+$11.66 portfolio**. | **CANDIDATE, NOT ACCEPTED**. Native unchanged 2023–24 comparison unresolved. |
| PR blanket 30m/−0.30R adverse exit | Sacrificed later recoveries; v1.11's ON/OFF difference in 2022–23 only ~$22.22 and sign can depend on baseline definition. | **REJECTED** as a general strategy fix. |
| PR Monday-only narrowed adverse exit (v1.12) | Not shown to survive winner denominator / independent validation. | **NOT PROMOTED**; source is research artifact only. |
| Same-direction failed ORB/Donchian → block/reduce PR for 45m | Counterexamples: 2025-11-26 ORB LONG -$54.23 → PR LONG **8m31s** later +$83.36; 2025-12-17 ORB LONG ~-$25.74 → PR LONG **8m35s** later +$77.43. | **REJECTED simple ban/throttle**; preserving recovery winners matters. |
| 15–45min delayed PR re-break after failed engine | Five retrospectively observed 20–40m losses, but 0–15m and late winners show complexity and small samples. Keep ORB→PR separate from Donchian→PR; require actual closed realized prior loss, not concurrent exposure. | **OPEN descriptive hypothesis**, no optimized cutoff. |
| One or more failed engines then PR | Limited counterexample/denominator evidence; avoid false sequencing from PR→Donchian or simultaneous signals. | **OPEN**; no rule. |
| Prior Range midnight stale signal / reopen retry | 185 broker market-closed rejects; 172 at 00:00; many entries well beyond breakout. | **REJECT blind chasing**. |
| Prior Range D1 synchronization | Correct source Daily candle only after actual D1 rollover, rather than using stale shift at broker midnight. | **EXECUTION FIX** in older v1.3; independently verify source. |
| Generic EMA opposition, broad PR short bans, prior range threshold mining, routine MFE/time exits | Historical winners often removed or rules failed OOS. | **REJECTED / NOT PROMOTED**. |
| NR10 NY compression-expansion | Exact Dukascopy ticks: TRAIN 39 trades -0.135R PF .69; VALID 16 -0.011R PF .97; TEST 10 +0.264R PF 2.11; FINAL 9 +0.173R PF 1.58; **all 74 -0.017R PF .96**. | **REJECTED** despite late positive periods. |
| Indicator strategy tournament | DMI train +0.97R/valid +0.48R then July -0.60R; MACD similarly failed July. | **REJECTED** unvalidated optimization. |
| M30 Keltner rejection | TRAIN +0.296R; VALID +0.330R; TEST +0.043R; FINAL +0.379R with only six FINAL trades. | **HOLD**, too sparse and TEST PF ~1.08. |
| HWM 6/4 vs 8/5 | Historical net $23,133.82 vs $26,852.32, lost $7,360.73 gross profit to save $3,642.23 gross loss; does not distinguish setup quality. | **OUT OF SCOPE** for further optimization; keep frozen if in EA. |
| v1.10 12% capital-protection latch | 2022–23 stopped at +$1,280.89 rather than 9B -$1,295.82; measured risk brake, not repaired entry/exit logic. | **OUT OF SCOPE**; not a strategy edge. |
| BTC v0.2 micro mean-reversion | 231 trades -$30.36 PF .664; mid-price apparent +$4.31; multiple entries worsened outcome. | **REJECTED v0.x architecture** pending new causal hypothesis. |

### Rules against false findings
- A collection of losses with feature X is NOT evidence unless ALL winners with X are counted.
- Reconstruct actual cashflow, sizing propagation, fees and interaction changes, not only hypothetical R saved.
- Compare identical years/builds/flags; never merge tables from 9B, v1.11, SC5 ON, and PR adverse-exit ON/OFF.
- Do not use attractive 2025–26 numbers to repeatedly choose thresholds.
