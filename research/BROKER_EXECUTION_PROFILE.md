# XM MT5 — XAUUSD broker and execution profile (recovered 2026-11-09)

**Purpose:** prevent Codex from silently using the wrong broker, symbol, contract specifications, account sizing, or friction assumptions when researching the video-inspired XAUUSD scalper. Read alongside `AGENTS.md` and `SCALPING_TRACK.md`. All values are **historical snapshots**; there is no current live MT5 terminal access from this repository. Re-probe the actual account before executable deployment.

## 1. Confirmed trading environment
| Field | Historical value | Source / confidence |
|---|---|---|
| Broker | XM / XM Global | User-confirmed in Sept 2026 |
| MT5 server | `XMGlobal-MT5 5` | MT5 tester/run instructions; confirmed |
| Platform | **MetaTrader 5**, desktop installed via **Wine on Lubuntu/Ubuntu** | User-confirmed |
| Environment | **Demo** | User-confirmed; historical research EA `DemoOnly=true` |
| Position accounting | **Hedging** | User-confirmed and MT5 test instructions |
| Named account type | Described as **Standard XM demo** in earlier EA/deployment notes | Prior EA wording, **not an independently confirmed live account-class API field** |
| **Raw Spread account** | **UNVERIFIED; do not assert** | No recovered user/account screenshot or commission schedule proves a Raw Spread plan |
| Tester account currency | **USD** | MT5 test instructions; current live account currency must be re-probed |
| Tester initial deposit | **$10,000 USD** | Exact historical test setup; not a minimum/requirement for strategy |
| Tester leverage | **1:500** | Exact historical test setup; re-probe current account for forward trading |
| Gold broker symbol | **`GOLD.i#`** (case and suffix exact) | MT5 logs/user confirmation |
| Master EA timeframe | **M1** | Historical Master backtests |
| Micro-regime research timeframe | **M5** for `XAUUSD Micro Regime Edge Lab v0.9.1` | Research log only, not the master EA |
| Broker observed UTC offset | **UTC+3 / 10,800 s** in sampled sessions | Actual live/test logs; do **not** assume same offset in all historical/DST periods |

**Do not confuse `GOLD.i#` with generic `XAUUSD` from Dukascopy or with `BTCUSD#` from a separate experimental BTC scalper.** The historical tick data feeds, symbol settings, and P&L units are not interchangeable.

## 2. Verified GOLD.i# symbol economics
Recovered verbatim from a historical `ACCOUNT_PROFILE` log:
```text
symbol=GOLD.i#
balance=10000.00
equity=10000.00
contractSize=100.00
tickSize=0.01
tickValue=1.0000
brokerMinVol=0.01
effectiveMinVol=0.01
marginMode=2
tradeMode=0
```
Another user-confirmed historical profile had `volumeStep=0.01` and `effectiveMinVol=0.10`: this was the **EA's effective deployment minimum** then, NOT a change in broker minimum. Later EA tests used `DeploymentMinVolume=0.01`. Don't hardcode the earlier 0.10 as broker volume minimum.

| Field | Value in historical logs | Interpretation |
|---|---:|---|
| Contract size | **100.00 troy oz/lot** | 1 standard lot represents 100 ounces |
| Trade volume minimum | **0.01 lot** | Minimum **broker** size |
| Volume step | **0.01 lot** | From historical user-confirmed account profile |
| Tick size | **0.01 GOLD quote units** | Quote-step reported by symbol |
| Tick value | **$1.00 per tick at 1.0 lot** | In logged USD test configuration |
| Exposure at 0.01 lot | **1.00 oz** | 100 oz × 0.01 |
| P&L per $1.00 Gold price movement at 0.01 lot | **~$1.00 gross** | Before spread, commissions, swaps and slippage |

For a standard one-way 0.01-lot long:
`gross price P&L USD = (Bid_exit - Ask_entry) * 100 oz/lot * 0.01 lot`;
for a short:
`gross price P&L USD = (Bid_entry - Ask_exit) * 100 * 0.01`.
Account/broker-specific currency and non-linear exceptions should be verified via MT5 `OrderCalcProfit` rather than only this simplified formula.

## 3. **Observed spread**, not 'Raw Spread' account status
From prior MT5 heartbeat/tester logs, `GOLD.i#` spreads expressed as **Gold price units**, not USD commission or points:
- observed examples: **0.12, 0.14, 0.16, 0.17, 0.18, 0.19, 0.20**;
- also **0.24, 0.25, 0.26, 0.27, 0.29**, and **0.36**;
- an isolated **1.01** wider reading occurred in a separate test/run.

These are **not** a guaranteed minimum, fixed spread, median, typical live spread, or timestamp-uniform distribution. The account's commission structure is **unknown**: do NOT assume either `commission=0` or a Raw Spread plus per-lot fee.

At **0.01 lot**, a constant **0.25 Gold price-unit bid–ask spread** contributes roughly **$0.25** of cost to a round trip versus an unchanged mid-price, before other fees. A **$1 Gold price move** translates into **$1 gross price movement** for this 1-oz exposure, but a scalp targeting $1 account P&L must account for spread, fees and fill mechanics. Don't double-count the full spread on both entry and exit in a standard spread P&L calculation.

## 4. Historically used testing parameters — distinguish source modes
**Master EA, common annual tests**
```ini
Server=XMGlobal-MT5 5
Symbol=GOLD.i#
Period=M1
Deposit=10000
Currency=USD
Leverage=1:500
PositionAccounting=Hedging
TestMode=Every tick  # precise 'real' vs 'generated' varied between test batches
DateWindow=2022-09-15..2023-09-15 # plus other independent yearly windows
```
Test mode **was not always the same**: some studies used `Every tick` generated ticks while others used `Every tick based on real ticks`, and off-platform research used Dukascopy millisecond bid/ask. Reconcile all result claims with the original specific tester report; never silently treat generated ticks as genuine quote paths.

**Micro-research only** — a historical `XAUUSD Micro Regime Edge Lab v0.9.1` tester log (no order placement):
```ini
Symbol=GOLD.i#
Period=M5
TestVolume=0.01
MaxHoldSeconds=300
MaxEntrySpreadPrice=0.60
TesterServerUtcOffsetSec=10800
DateWindow=2026-01-01..2026-06-30
Mode=RESEARCH ONLY, ZERO ORDER-SEND FUNCTIONS
```
`MaxEntrySpreadPrice=0.60` was a **research input**, not an observed spread or recommended production filter. The user expressed an aspiration of frequent ~$1 scalp outcomes over ~5 minutes; this was **not** a demonstrated profitable executable strategy.

Prior tester defect: one initial backtest accidentally used **$100** deposit, causing minimum-volume risk rejection; another used `UTCOffsetSec=0` while live XM showed `+10800`, corrupting session placement. Both invalidate naive interpretations of that run.

## 5. REQUIRED runtime audit before Codex calibrates an executable scalper
Use the **actual MT5 terminal** (demo first) to log a redacted, timestamped capability report. Never log account numbers, credentials, or personal paths into this public repository.

**Account-level data to re-probe:**
- `ACCOUNT_COMPANY`, `ACCOUNT_SERVER`, `ACCOUNT_CURRENCY`, `ACCOUNT_MARGIN_MODE`, `ACCOUNT_LEVERAGE`, `ACCOUNT_TRADE_MODE`; account classification/marketing name separately via broker portal if necessary.
- Hedge vs netting permissions; whether shorting `GOLD.i#` and multiple positions is allowed in this exact account.
- Broker **commission and fee** schedule: sample deal-history commissions and fees (`DEAL_COMMISSION`, `DEAL_FEE`, swap); do not assume zero if none appears in a single record.

**Symbol-level data to re-probe via SymbolInfo... APIs:**
- Exact `SYMBOL_NAME` / `SYMBOL_DESCRIPTION`; `SYMBOL_TRADE_CONTRACT_SIZE`, `SYMBOL_POINT`, `SYMBOL_DIGITS`, `SYMBOL_TRADE_TICK_SIZE`, `SYMBOL_TRADE_TICK_VALUE`, `SYMBOL_TRADE_TICK_VALUE_PROFIT`, `SYMBOL_TRADE_TICK_VALUE_LOSS`.
- `SYMBOL_VOLUME_MIN`, `SYMBOL_VOLUME_STEP`, `SYMBOL_VOLUME_MAX`; stops and freeze levels; fill policies, execution mode, margin requirements, trading sessions and maintenance/rollover gaps.
- Live `SYMBOL_BID`, `SYMBOL_ASK` sampled over multiple full sessions (incl. rollover), timestamps, actual spread in **price units**, and latency/slippage, separately for bid/ask.
- `OrderCalcProfit` and `OrderCalcMargin` for sample 0.01-lot BUY/SELL and +/-$1 price movements, cross-checked with deal P&L.

**Time/data integrity:** Record current broker GMT offset and seasonal changes; ensure `TimeTradeServer` / `TimeGMT` logic works **inside tester**; align XM real bid/ask ticks, bars, and Dukascopy timezones without mixing symbols. Ensure no lookahead and realistic stops, margin, commissions, slippage, partial fills and execution rejection.

## 6. Values that remain UNKNOWN (must not be invented)
- Whether the current login is marketed as **Raw Spread**, `Standard`, `Ultra Low`, `Zero`, or other; old developer wording suggested Standard demo but no definitive account-plan API evidence exists.
- Current actual **commission per side / per lot**, account fee schedule, and whether fees are embedded in spread.
- `SYMBOL_DIGITS`, spread-time distribution by session, min stops/freeze, max volume, order filling policies, execution delay, slippage and lot-size limits beyond the sampled fields.
- Current live account balance/leverage/currency/server (historical tester values are not live guarantees).
- Original video order mechanics, whether hedging/grid behavior was truly present, or whether any version achieved sustained net profitable high-frequency scalping.

**No EA modifications, MT5 runs, or live orders were made to prepare this profile.**
