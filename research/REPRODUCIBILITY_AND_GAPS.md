# Provenance, missing artifacts, and privacy

## Where these statements came from
This handover was reconstructed from accessible trading-conversation summaries and available local project notes on 2026-11-09, including:
- `Automate SMC Gold Trading.txt`: Dukascopy tick-level strategy tournament, split hygiene, NR10 rejection.
- `Backtesting EA Modules.txt`: HWM experiment evidence (historical, now out of research scope).
- `Trading Results Summary.txt`: PR midnight market-closed failure diagnosis and missing-source note.
- `Continue PR Retry Guard Research.txt`: PR retry winner counterexamples and denominator requirements.
- `Continue denominator analysis.txt`: reconciled 9B ORB armed/moved-stop trade counts.
- Prior recovered research checkpoints named `XAUUSD_Profitability_Checkpoint.md`, `ORB_9B_Denominator_Checkpoint.md`, `ORB_Native_2022_23_Review.md` and `XAUUSD_Ranked_Loss_Diagnosis.md` — their actual bytes are **not stored in this repo**.
- Recovered historical BTC scalper summaries and tester journal excerpts, but **not its actual source or the video**.

These are **secondary research notes**. They should be reconciled against original tester reports and source code. We intentionally have NOT claimed to transfer every verbatim ChatGPT turn; such a complete conversation export is unavailable from this connected view.

## Exact missing inputs
1. Portfolio: `XAUUSD_MasterPortfolio_Execution_v1_11_EntryLossQualityResearch_SC5.mq5`, `XAUUSD_MasterPortfolio_Execution_v1_12_PRMondayAdverseResearch_SC5.mq5`; original 9B, baseline older versions, `.set` files, changelogs.
2. Native MT5 Strategy Tester exports and journals for four 15-Sep yearly windows, including exact build/account type/symbol specs, transaction costs, slippage, and entry/exit/deal linkage.
3. Full original broker `GOLD.i#` bid/ask and/or accurately replayable millisecond ticks; Dukascopy files with separate source labeling; contract-spec/timezone snapshots.
4. `ORB_9B_Denominator_Checkpoint.md` and its case-level data and executable replay code; `v0_7_event_driven_opportunity_lab.py`.
5. Scalping prototype `BTC_MicroReversion_Scalper_v0_1.mq5`, v0.2–v0.4 variants if they exist, complete BTCUSD# real-tick test logs, and the original user-supplied video.
6. Any full raw conversation archive the user explicitly wants to retain, after reviewing for sensitive information.

## Import procedure for Codex
- Start with **read-only inventory**; compare hashes and map every version to every result.
- Keep a local/private data directory outside git, e.g. `private_data/`, with a `.gitignore` if added to local clone; do NOT commit private material to this public repo.
- Store only sanitized manifests in public git: artifact filename, SHA256, time window, data provenance, experiment ID, status, location in private storage.
- For each exact backtest, save a machine-readable manifest with EA source hash, `.set` hash, MT5 build, test mode, symbol, account deposit/leverage, timezone handling, start/end inclusive conventions, tick source, broker friction, gross/net P&L, trades, PF, drawdown and journal hash.
- Use an **immutable result ledger** and explicit TRAIN/VALID/TEST/HOLDOUT timestamps.
- If the user exports full ChatGPT conversations, treat them as private input to a sanitizer; do not commit the export itself. Extract decisions, hypotheses, denominators, artifacts and status changes only.

## Integrity cautions
- Some earlier experiments used generated ticks and others native real ticks; these are not interchangeable.
- One earlier v1.3 test covered a different 2026 span than the four full-year controls.
- Raw MT5 logs may reveal account IDs, broker server details, financial information, and personal paths.
- A successful-looking profit figure is not a guarantee or evidence of repeatable annual profitability.
- `download_xauusd_dukascopy_raw_v4.py` operates on native **M1 BID/ASK candles**, not automatically millisecond ticks. Treat it as a downloader to audit, not an executable fill oracle.
