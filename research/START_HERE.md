# Trading research — Codex handover (9 November 2026)

**Status:** contextual handover only. No MT5 backtest, source-code compilation, scientific validation, or EA modification was performed while creating this handover.

## What is here
- `BROKER_EXECUTION_PROFILE.md`: verified XM MT5 account, exact GOLD.i# contract and price/spread mechanics, micro-scalping settings and outstanding cost questions.
- `AGENTS.md`: controlling research rules. **Read first**.
- `RESEARCH_STATE.md`: latest known baseline, versions, and immediate bounded next task.
- `MASTER_PORTFOLIO.md`: ORB, Prior Range, Donchian, Overnight architecture and multi-year numbers.
- `SCALPING_TRACK.md`: video-inspired bidirectional scalper and separate XAUUSD/BTC micro research.
- `EXPERIMENT_LEDGER.md`: rejected rules, open questions, counterexamples, and execution defects.
- `REPRODUCIBILITY_AND_GAPS.md`: precise artifacts still missing and how to import them safely.

## Repository inspection at handover
The existing repository has only `README.md` and these data-acquisition scripts:
`download_xauusd_dukascopy.py`, `download_xauusd_dukascopy_raw.py`, `download_xauusd_dukascopy_raw_v3.py`, `download_xauusd_dukascopy_raw_v4.py`.
The v4 script's docstring describes Dukascopy native **M1 BID/ASK candle** data, default 2018-01-01 through 2026-08-14. Do NOT assume these are millisecond tick executions. The repository tree had **no .mq5/.ex5 code, research logs, or raw ticks**.

## Two independent tracks
**A — XAUUSD Master Portfolio:** continue loss forensics and strategy-level improvements across four engines. Primary priority is ORB. v1.11/v1.12 research copies exist in earlier work but were NOT found in this repository. Older 9B is a control, NOT the replacement champion.

**B — Bidirectional micro-scalping:** investigate the bot shown in a user video, whose actual recording was not recovered. Do not assert the video implements a specific grid, hedge, or martingale algorithm. BTC and XAUUSD micro experiments so far did **not** establish positive net expectancy after realistic costs.

## Critical caveats
This is a **research-context reconstruction**, not a complete verbatim export of every ChatGPT message. Values are drawn from accessible prior research summaries, project notes and recovered user-context evidence. Some reports used different EA versions, data feeds or experimental flags; never combine them as one backtest. The account/repository is **public**. Raw conversation archives, broker account details, and private datasets were intentionally excluded.

## Entry point for Codex
First **inventory exact EA source, configs and tester reports**, reconcile this handover against primary records, then perform the already-defined bounded ORB moved-stop counterfactual. Do not invent new parameters or ask for another EA test until existing evidence is exhausted.
