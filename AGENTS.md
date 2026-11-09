# Codex instructions — trading research

Read `research/START_HERE.md` and `research/RESEARCH_STATE.md` before modifying anything. This repository is currently a Dukascopy XAUUSD downloader plus a **documentary handover**. It does NOT yet contain the portfolio EA, the BTC scalper source, or the complete backtest datasets.

## Immutable primary objective
Improve the **underlying expectancy and decision quality** of XAUUSD strategies, especially ORB, Prior Range, Donchian, and Overnight. Diagnose exactly why losing trades occur; improve setup selection, entries, exits, and opportunity capture while preserving winners and preferably frequency. The video-inspired high-frequency scalper is an independent research track. Never silently replace one objective with the other.

## Not authorized without explicit user approval
Do not pivot to capital protection, account latches/shutdowns, HWM throttling, loss-streak sizing, daily caps, reducing lot size due to losses, or portfolio emergency brakes as the research goal. Previously researched safeguards may remain frozen in the EA, but they are NOT strategy improvements. Do not compile, replace, or deploy the user's live EA merely to test a weak hypothesis.

## Evidence standard for EVERY proposed trading rule
1. Identify the exact repeated loss mechanism and the causal hypothesis.
2. Show what was knowable **before entry**; distinguish ex-ante signals from hindsight labels.
3. Include **every reasonably identifiable winner** meeting the same condition (winner-denominator rule).
4. Count affected trades, losing trades avoided, winners sacrificed, opportunities missed/recovered, changes in frequency and net P&L/R.
5. Report expectancy, profit factor, win rate, gross profits/losses, drawdown, trade count, and execution/friction sensitivity.
6. Evaluate multiple independent years/regimes. Separately name TRAIN, VALID, TEST, and untouched HOLDOUT, and log when data is first inspected.
7. Find counterexamples proactively. Reject rules that only work after mining narrow thresholds.
8. Prefer parameter plateaus and a plausible causal effect to one P&L-maximizing threshold.
9. Change one logical variable at a time; retain an unchanged baseline and reproducible settings.
10. Do not make or recommend EA changes until evidence survives validation. Be honest when the original tick path / first-touch ordering is unavailable.

## Research priorities
ORB loss forensics first; Prior Range second; Donchian third; Overnight as relevant control; then directly causal duplicated/conflicting signals. Never improve PF merely by eliminating most trades.

## Operational practices
- Source of truth: exact versioned `.mq5`, MT5 trade/deal/order journals, full tester configuration, and suitable broker bid/ask data. Summaries in this handover are **not** executable proof.
- Distinguish Dukascopy from XM `GOLD.i#`; verify broker UTC offset, contract specs, spread, swaps, and symbol point size. Do not substitute M1 candle fills for intrabar bid/ask first-touch proof.
- Avoid further parameter tuning on heavily studied 2025–26. Preserve genuinely untouched years when available.
- Never claim zero-loss or guaranteed annual profit. The aspirational $30k+ per year was NOT validated historically.
- Record each experiment, rejected hypothesis, counterexample, and resulting decision in version-controlled files.
- Preserve the repository's existing downloader scripts. Do not modify them as part of the handover.
- No credentials, account identifiers, raw unrelated conversations, personal data, or proprietary raw MT5 logs in a **public** GitHub repository. Store sensitive material privately.
- No work on a separate research objective without explicit approval.

## Required progress reporting
For substantive research notes include: **Objective / Hypothesis / Evidence (winners AND losers) / Finding / Counterexamples / EA changes / Scope check**. Usually EA changes = none.
