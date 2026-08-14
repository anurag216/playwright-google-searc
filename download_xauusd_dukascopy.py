#!/usr/bin/env python3
"""
download_xauusd_dukascopy.py

Downloads Dukascopy XAU/USD 1-minute BID and ASK candles through Dukascopy's
official Trading Tools historicalPrices API, stores them in a resumable SQLite
database, validates the series, and exports a single gzip-compressed CSV.

Default range:
    2018-01-01 00:00:00 UTC -> 2026-08-14 00:00:00 UTC

Output:
    dukascopy_xauusd/
      xauusd_dukascopy_m1.sqlite
      XAUUSD_Dukascopy_M1_2018-01-01_2026-08-14.csv.gz
      XAUUSD_Dukascopy_M1_manifest.json
      XAUUSD_Dukascopy_M1_gaps.csv

No trading credentials are required by this script. An optional Dukascopy
Trading Tools API key can be supplied with --key if Dukascopy requires one
for your connection.

Usage:
    python download_xauusd_dukascopy.py

Resume:
    Run the same command again. Existing completed chunks are skipped.

Notes:
- Dates are interpreted as UTC.
- Requests are made in <=3-day chunks so the documented 5,000-row maximum
  cannot truncate a full continuous 1-minute interval.
- BID and ASK are downloaded independently and joined by timestamp.
- Missing market-closed minutes are not fabricated.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    print("Install it with: python -m pip install requests")
    raise

BASE_URL = "https://freeserv.dukascopy.com/2.0/"
API_INSTRUMENT_LIST = "api/instrumentList"
API_HISTORICAL = "api/historicalPrices"
DEFAULT_START = "2018-01-01"
DEFAULT_END = "2026-08-14"
DEFAULT_SYMBOL = "XAUUSD"
DEFAULT_CHUNK_DAYS = 3
MAX_COUNT = 5000
TIMEFRAME = "1min"
DAY_START_TIME = "UTC"


@dataclass
class Candle:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None


def parse_utc_date(value: str) -> datetime:
    s = value.strip()
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def ms_to_iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def api_get(session: requests.Session, path: str, params: dict[str, Any],
            retries: int = 6, timeout: int = 45) -> Any:
    q = dict(params)
    q["path"] = path
    last_error = None

    for attempt in range(retries):
        try:
            response = session.get(BASE_URL, params=q, timeout=timeout)

            if response.status_code == 429:
                wait = min(60, 2 ** attempt)
                print(f"Rate limited (429). Sleeping {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()

            try:
                return response.json()
            except Exception:
                raise RuntimeError(
                    "Expected JSON from Dukascopy but received something else. "
                    f"Content-Type={response.headers.get('content-type')!r}; "
                    f"first 500 chars={response.text[:500]!r}"
                )

        except Exception as exc:
            last_error = exc
            if attempt + 1 >= retries:
                break
            wait = min(30, 1.5 * (2 ** attempt))
            print(f"Request failed ({exc}). Retrying in {wait:.1f}s...")
            time.sleep(wait)

    raise RuntimeError(f"Dukascopy request failed after {retries} attempts: {last_error}")


def unwrap_rows(payload: Any) -> list[Any]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("data", "candles", "prices", "result", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

        if any(k in payload for k in ("open", "o", "timestamp", "time")):
            return [payload]

        err = payload.get("error") or payload.get("message")
        if err:
            raise RuntimeError(f"Dukascopy API error: {err}")

    raise RuntimeError(
        "Unexpected Dukascopy payload shape. "
        f"Type={type(payload).__name__}, sample={str(payload)[:1000]}"
    )


def first_present(d: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in d and d[name] is not None:
            return d[name]
    return None


def normalize_timestamp(raw: Any) -> int:
    if raw is None:
        raise ValueError("Missing candle timestamp")

    if isinstance(raw, (int, float)):
        value = float(raw)
        return int(value * 1000 if abs(value) < 10_000_000_000 else value)

    if isinstance(raw, str):
        s = raw.strip()
        try:
            value = float(s)
            return int(value * 1000 if abs(value) < 10_000_000_000 else value)
        except ValueError:
            return dt_to_ms(parse_utc_date(s))

    raise ValueError(f"Unsupported timestamp type: {type(raw).__name__}")


def normalize_candle(row: Any) -> Candle:
    """
    Normalize a Dukascopy candle object.

    The public API documentation defines historicalPrices and its parameters,
    but does not show a complete candle-response example on the documentation
    page. To avoid silently guessing, this parser accepts common named fields
    and deliberately fails with the raw sample if Dukascopy returns a different
    representation.
    """
    if not isinstance(row, dict):
        raise RuntimeError(
            "Dukascopy returned an array-form candle. This safe parser will not "
            "guess the element ordering. Send the printed sample row back for "
            f"a parser update. Sample: {str(row)[:500]}"
        )

    ts = first_present(row, ("timestamp", "time", "date", "datetime", "start", "startTime"))
    o = first_present(row, ("open", "o", "openPrice"))
    h = first_present(row, ("high", "h", "highPrice"))
    l = first_present(row, ("low", "l", "lowPrice"))
    c = first_present(row, ("close", "c", "closePrice"))
    v = first_present(row, ("volume", "v", "vol"))

    missing = [
        name for name, value in (
            ("timestamp", ts), ("open", o), ("high", h), ("low", l), ("close", c)
        )
        if value is None
    ]

    if missing:
        raise RuntimeError(
            f"Missing expected candle fields {missing}. "
            f"Available keys: {sorted(row.keys())}. Sample: {row}"
        )

    candle = Candle(
        ts_ms=normalize_timestamp(ts),
        open=float(o),
        high=float(h),
        low=float(l),
        close=float(c),
        volume=None if v is None else float(v),
    )

    if candle.high < max(candle.open, candle.close, candle.low):
        raise ValueError(f"Invalid candle high: {row}")

    if candle.low > min(candle.open, candle.close, candle.high):
        raise ValueError(f"Invalid candle low: {row}")

    return candle


def resolve_instrument_id(
    session: requests.Session,
    symbol: str,
    key: str | None,
) -> tuple[int, dict[str, Any]]:
    params: dict[str, Any] = {}
    if key:
        params["key"] = key

    payload = api_get(session, API_INSTRUMENT_LIST, params)
    rows = unwrap_rows(payload)

    wanted = symbol.upper().replace("/", "")
    candidates: list[dict[str, Any]] = []

    for item in rows:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).upper().replace("/", "")
        long_name = str(item.get("nameLong", "")).upper().replace("/", "")

        if name == wanted or wanted in long_name:
            candidates.append(item)

    if not candidates:
        sample = [x for x in rows if isinstance(x, dict)][:5]
        raise RuntimeError(
            f"Could not find instrument {symbol}. First instrument rows: {sample}"
        )

    item = candidates[0]
    if "id" not in item:
        raise RuntimeError(f"Instrument row has no id: {item}")

    return int(item["id"]), item


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            ts_ms INTEGER PRIMARY KEY,
            bid_open REAL,
            bid_high REAL,
            bid_low REAL,
            bid_close REAL,
            bid_volume REAL,
            ask_open REAL,
            ask_high REAL,
            ask_low REAL,
            ask_close REAL,
            ask_volume REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            side TEXT NOT NULL,
            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            PRIMARY KEY (side, start_ms, end_ms)
        )
    """)

    conn.commit()
    return conn


def chunk_done(
    conn: sqlite3.Connection,
    side: str,
    start_ms: int,
    end_ms: int,
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM chunks WHERE side=? AND start_ms=? AND end_ms=?",
        (side, start_ms, end_ms),
    ).fetchone()
    return row is not None


def upsert_candles(
    conn: sqlite3.Connection,
    side: str,
    candles: list[Candle],
) -> None:
    if not candles:
        return

    if side == "B":
        sql = """
            INSERT INTO candles (
                ts_ms, bid_open, bid_high, bid_low, bid_close, bid_volume
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_ms) DO UPDATE SET
                bid_open=excluded.bid_open,
                bid_high=excluded.bid_high,
                bid_low=excluded.bid_low,
                bid_close=excluded.bid_close,
                bid_volume=excluded.bid_volume
        """
    else:
        sql = """
            INSERT INTO candles (
                ts_ms, ask_open, ask_high, ask_low, ask_close, ask_volume
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ts_ms) DO UPDATE SET
                ask_open=excluded.ask_open,
                ask_high=excluded.ask_high,
                ask_low=excluded.ask_low,
                ask_close=excluded.ask_close,
                ask_volume=excluded.ask_volume
        """

    conn.executemany(
        sql,
        [
            (c.ts_ms, c.open, c.high, c.low, c.close, c.volume)
            for c in candles
        ],
    )


def iter_chunks(
    start: datetime,
    end: datetime,
    chunk_days: int,
):
    cursor = start
    delta = timedelta(days=chunk_days)

    while cursor < end:
        nxt = min(cursor + delta, end)
        yield cursor, nxt
        cursor = nxt


def download_side(
    session: requests.Session,
    conn: sqlite3.Connection,
    instrument_id: int,
    side: str,
    start: datetime,
    end: datetime,
    key: str | None,
    chunk_days: int,
    polite_delay: float,
) -> None:
    chunks = list(iter_chunks(start, end, chunk_days))
    label = "BID" if side == "B" else "ASK"

    for idx, (chunk_start, chunk_end) in enumerate(chunks, 1):
        start_ms = dt_to_ms(chunk_start)
        end_ms = dt_to_ms(chunk_end) - 1

        if chunk_done(conn, side, start_ms, end_ms):
            if idx % 50 == 0 or idx == len(chunks):
                print(f"{label}: {idx}/{len(chunks)} chunks (cached)")
            continue

        params: dict[str, Any] = {
            "instrument": instrument_id,
            "timeFrame": TIMEFRAME,
            "count": MAX_COUNT,
            "start": start_ms,
            "end": end_ms,
            "dayStartTime": DAY_START_TIME,
            "offerSide": side,
        }

        if key:
            params["key"] = key

        payload = api_get(session, API_HISTORICAL, params)
        rows = unwrap_rows(payload)

        try:
            candles = [normalize_candle(row) for row in rows]
        except Exception:
            print("\nCould not parse Dukascopy candle response.")
            print("First raw row:", rows[0] if rows else "<empty>")
            raise

        candles = [
            candle
            for candle in candles
            if start_ms <= candle.ts_ms <= end_ms
        ]

        if len(candles) >= MAX_COUNT:
            raise RuntimeError(
                f"{label} chunk returned {len(candles)} rows, reaching the "
                "documented API limit. Reduce --chunk-days."
            )

        with conn:
            upsert_candles(conn, side, candles)

            conn.execute(
                """
                INSERT OR REPLACE INTO chunks(
                    side, start_ms, end_ms, row_count, completed_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    side,
                    start_ms,
                    end_ms,
                    len(candles),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        display_end = chunk_end - timedelta(seconds=1)

        print(
            f"{label}: {idx:4d}/{len(chunks)}  "
            f"{chunk_start.date()} -> {display_end.date()}  "
            f"{len(candles):4d} candles"
        )

        if polite_delay:
            time.sleep(polite_delay)


def validate_and_export(
    conn: sqlite3.Connection,
    output_dir: Path,
    start: datetime,
    end: datetime,
    instrument_meta: dict[str, Any],
) -> tuple[Path, Path, Path]:
    start_ms = dt_to_ms(start)
    end_ms = dt_to_ms(end)

    total = conn.execute(
        "SELECT COUNT(*) FROM candles WHERE ts_ms>=? AND ts_ms<?",
        (start_ms, end_ms),
    ).fetchone()[0]

    both = conn.execute(
        """
        SELECT COUNT(*)
        FROM candles
        WHERE ts_ms>=? AND ts_ms<?
          AND bid_open IS NOT NULL
          AND ask_open IS NOT NULL
        """,
        (start_ms, end_ms),
    ).fetchone()[0]

    bid_only = conn.execute(
        """
        SELECT COUNT(*)
        FROM candles
        WHERE ts_ms>=? AND ts_ms<?
          AND bid_open IS NOT NULL
          AND ask_open IS NULL
        """,
        (start_ms, end_ms),
    ).fetchone()[0]

    ask_only = conn.execute(
        """
        SELECT COUNT(*)
        FROM candles
        WHERE ts_ms>=? AND ts_ms<?
          AND bid_open IS NULL
          AND ask_open IS NOT NULL
        """,
        (start_ms, end_ms),
    ).fetchone()[0]

    output_csv = output_dir / (
        f"XAUUSD_Dukascopy_M1_{start.date().isoformat()}_{end.date().isoformat()}.csv.gz"
    )

    gaps_csv = output_dir / "XAUUSD_Dukascopy_M1_gaps.csv"
    manifest_path = output_dir / "XAUUSD_Dukascopy_M1_manifest.json"

    print("\nExporting joined BID/ASK CSV.gz ...")

    with gzip.open(output_csv, "wt", newline="", encoding="utf-8") as gz:
        writer = csv.writer(gz)

        writer.writerow([
            "timestamp_utc",
            "bid_open", "bid_high", "bid_low", "bid_close", "bid_volume",
            "ask_open", "ask_high", "ask_low", "ask_close", "ask_volume",
            "mid_open", "mid_high", "mid_low", "mid_close",
            "spread_open", "spread_close",
        ])

        cursor = conn.execute(
            """
            SELECT
                ts_ms,
                bid_open, bid_high, bid_low, bid_close, bid_volume,
                ask_open, ask_high, ask_low, ask_close, ask_volume
            FROM candles
            WHERE ts_ms>=? AND ts_ms<?
            ORDER BY ts_ms
            """,
            (start_ms, end_ms),
        )

        for row in cursor:
            (
                ts_ms,
                bo, bh, bl, bc, bv,
                ao, ah, al, ac, av,
            ) = row

            def mid(a, b):
                return (a + b) / 2.0 if a is not None and b is not None else None

            writer.writerow([
                ms_to_iso(ts_ms),
                bo, bh, bl, bc, bv,
                ao, ah, al, ac, av,
                mid(bo, ao),
                mid(bh, ah),
                mid(bl, al),
                mid(bc, ac),
                (ao - bo) if ao is not None and bo is not None else None,
                (ac - bc) if ac is not None and bc is not None else None,
            ])

    print("Scanning timestamp gaps ...")

    gap_count = 0

    with open(gaps_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "previous_timestamp_utc",
            "next_timestamp_utc",
            "gap_minutes",
        ])

        previous = None

        cursor = conn.execute(
            """
            SELECT ts_ms
            FROM candles
            WHERE ts_ms>=? AND ts_ms<?
            ORDER BY ts_ms
            """,
            (start_ms, end_ms),
        )

        for (ts_ms,) in cursor:
            if previous is not None:
                gap_minutes = (ts_ms - previous) / 60_000

                if gap_minutes > 2.0:
                    writer.writerow([
                        ms_to_iso(previous),
                        ms_to_iso(ts_ms),
                        f"{gap_minutes:.1f}",
                    ])
                    gap_count += 1

            previous = ts_ms

    spread_stats = conn.execute(
        """
        SELECT
            AVG(ask_close-bid_close),
            MIN(ask_close-bid_close),
            MAX(ask_close-bid_close)
        FROM candles
        WHERE ts_ms>=? AND ts_ms<?
          AND ask_close IS NOT NULL
          AND bid_close IS NOT NULL
        """,
        (start_ms, end_ms),
    ).fetchone()

    manifest = {
        "source": "Dukascopy Trading Tools historicalPrices API",
        "instrument_requested": "XAUUSD",
        "instrument_metadata": instrument_meta,
        "timeframe": "1min",
        "day_start_time": "UTC",
        "start_utc_inclusive": start.isoformat(),
        "end_utc_exclusive": end.isoformat(),
        "rows_total": total,
        "rows_with_bid_and_ask": both,
        "rows_bid_only": bid_only,
        "rows_ask_only": ask_only,
        "timestamp_gaps_over_2_minutes": gap_count,
        "spread_close": {
            "average": spread_stats[0],
            "minimum": spread_stats[1],
            "maximum": spread_stats[2],
        },
        "output_csv_gz": output_csv.name,
        "gaps_csv": gaps_csv.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "Missing market-closed minutes are not forward-filled.",
            "BID and ASK candles are joined on exact UTC timestamp.",
            "Mid prices are derived as arithmetic mean of BID and ASK.",
            "Gap file includes normal weekends/holidays and is for review."
        ],
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print("\nValidation summary")
    print("------------------")
    print(f"Total timestamps : {total:,}")
    print(f"BID + ASK        : {both:,}")
    print(f"BID only         : {bid_only:,}")
    print(f"ASK only         : {ask_only:,}")
    print(f"Gaps > 2 min     : {gap_count:,} (includes weekends/holidays)")

    if spread_stats[0] is not None:
        print(f"Avg close spread : {spread_stats[0]:.6f}")
        print(f"Min close spread : {spread_stats[1]:.6f}")
        print(f"Max close spread : {spread_stats[2]:.6f}")

    return output_csv, manifest_path, gaps_csv


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download resumable Dukascopy XAUUSD M1 BID/ASK history."
    )

    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help="UTC start date/time. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=DEFAULT_END,
        help="UTC exclusive end date/time. Default: 2026-08-14",
    )

    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help="Instrument symbol. Default: XAUUSD",
    )

    parser.add_argument(
        "--output-dir",
        default="dukascopy_xauusd",
    )

    parser.add_argument(
        "--key",
        default=None,
        help="Optional Dukascopy Trading Tools API key",
    )

    parser.add_argument(
        "--chunk-days",
        type=int,
        default=DEFAULT_CHUNK_DAYS,
        help="Days per request. Keep <=3 for M1 safety.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Delay between requests in seconds.",
    )

    parser.add_argument(
        "--skip-ask",
        action="store_true",
        help="Download BID only. Not recommended for final research.",
    )

    args = parser.parse_args()

    start = parse_utc_date(args.start)
    end = parse_utc_date(args.end)

    if end <= start:
        parser.error("--end must be later than --start")

    if args.chunk_days < 1 or args.chunk_days > 3:
        parser.error("--chunk-days must be between 1 and 3")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "xauusd_dukascopy_m1.sqlite"

    session = requests.Session()

    session.headers.update({
        "User-Agent": "XAUUSD-research-downloader/1.0"
    })

    print("Resolving Dukascopy instrument ID ...")

    try:
        instrument_id, instrument_meta = resolve_instrument_id(
            session,
            args.symbol,
            args.key,
        )
    except Exception as exc:
        print(f"\nCould not access Dukascopy instrument list: {exc}")
        print(
            "\nIf Dukascopy requires a Trading Tools API key for your connection, "
            "re-run with --key YOUR_KEY. Do not use brokerage login credentials."
        )
        return 2

    print(
        f"Resolved {args.symbol}: "
        f"id={instrument_id}, metadata={instrument_meta}"
    )

    print(
        f"Range: {start.isoformat()} -> "
        f"{end.isoformat()} (end exclusive)"
    )

    print(f"Database: {db_path}")
    print("Progress is resumable. Re-run the same command after interruption.\n")

    conn = init_db(db_path)

    try:
        download_side(
            session=session,
            conn=conn,
            instrument_id=instrument_id,
            side="B",
            start=start,
            end=end,
            key=args.key,
            chunk_days=args.chunk_days,
            polite_delay=args.delay,
        )

        if not args.skip_ask:
            download_side(
                session=session,
                conn=conn,
                instrument_id=instrument_id,
                side="A",
                start=start,
                end=end,
                key=args.key,
                chunk_days=args.chunk_days,
                polite_delay=args.delay,
            )

        output_csv, manifest, gaps = validate_and_export(
            conn,
            output_dir,
            start,
            end,
            instrument_meta,
        )

    except KeyboardInterrupt:
        print("\nInterrupted. Progress is saved; run the same command to resume.")
        return 130

    finally:
        conn.close()

    print("\nDone.")
    print("Upload this main file back to ChatGPT:")
    print(f"  {output_csv}")

    print("\nAlso useful for validation:")
    print(f"  {manifest}")
    print(f"  {gaps}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
