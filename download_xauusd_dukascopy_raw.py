#!/usr/bin/env python3
"""
download_xauusd_dukascopy_raw.py

Downloads Dukascopy XAU/USD native 1-minute BID and ASK candle files directly
from Dukascopy's historical datafeed, decodes them, validates them, and exports
one gzip-compressed CSV suitable for our backtest research.

This version DOES NOT use the Dukascopy Trading Tools developer API and therefore
does not need its developer API key.

Default range:
    2018-01-01 00:00 UTC -> 2026-08-14 00:00 UTC (end exclusive)

Output directory:
    dukascopy_xauusd_raw/

Main output:
    XAUUSD_Dukascopy_M1_2018-01-01_2026-08-14.csv.gz

Resume:
    Re-run the exact same command. Completed daily BID/ASK chunks are stored in
    SQLite and skipped.

Important:
- Dukascopy native datafeed months are zero-indexed in the URL:
  January=00, ..., December=11.
- The native M1 file is LZMA-compressed binary candle data.
- We parse the native M1 candle record as:
      seconds_from_day_start, open, high, low, close, volume
  where the first five fields are big-endian unsigned 32-bit integers and volume
  is a big-endian 32-bit float.
- Price scaling is auto-detected for XAUUSD from the downloaded native values and
  then locked for the run. The detector only accepts a scale that produces a
  plausible gold price range.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import lzma
import sqlite3
import struct
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Missing dependency: requests")
    print("Install with: python -m pip install requests")
    raise

BASE = "https://www.dukascopy.com/datafeed"
SYMBOL = "XAUUSD"
RECORD = struct.Struct(">IIIIIf")  # seconds, O, H, L, C, V
RECORD_SIZE = RECORD.size         # 24 bytes
DEFAULT_START = "2018-01-01"
DEFAULT_END = "2026-08-14"

# Candidate dividers used only for safe auto-detection.
PRICE_DIVIDERS = (1, 10, 100, 1000, 10000, 100000, 1000000)

# Broad sanity band, intentionally much wider than historical gold trading ranges.
GOLD_MIN = 100.0
GOLD_MAX = 10000.0


@dataclass
class NativeBar:
    sec: int
    o: int
    h: int
    l: int
    c: int
    v: float


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def iter_dates(start: date, end_exclusive: date):
    d = start
    while d < end_exclusive:
        yield d
        d += timedelta(days=1)


def url_for(d: date, side: str) -> str:
    # Dukascopy's native path uses zero-based month indexing.
    month0 = d.month - 1
    return (
        f"{BASE}/{SYMBOL}/{d.year:04d}/{month0:02d}/{d.day:02d}/"
        f"{side}_candles_min_1.bi5"
    )


def get_bytes(session: requests.Session, url: str, retries: int = 5) -> Optional[bytes]:
    """
    Return file bytes, or None for a missing/non-trading-day file.
    Retry transient server/network failures.
    """
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=45)

            if r.status_code in (404, 410):
                return None

            if r.status_code == 429:
                wait = min(60, 2 ** attempt)
                print(f"429 rate-limit; sleeping {wait}s")
                time.sleep(wait)
                continue

            r.raise_for_status()

            # Some missing paths can occasionally be represented by an empty body.
            if not r.content:
                return None

            return r.content

        except requests.RequestException as exc:
            last = exc
            if attempt + 1 == retries:
                break
            wait = min(20, 1.5 * (2 ** attempt))
            print(f"Request problem: {exc}; retry in {wait:.1f}s")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {retries} attempts: {url}\n{last}")


def decompress_bi5(data: bytes) -> bytes:
    errors = []

    for fmt in (lzma.FORMAT_AUTO, lzma.FORMAT_ALONE):
        try:
            return lzma.decompress(data, format=fmt)
        except lzma.LZMAError as exc:
            errors.append(str(exc))

    raise RuntimeError(
        "Could not LZMA-decompress the Dukascopy .bi5 file. "
        f"Errors: {errors}"
    )


def decode_native_bars(raw: bytes) -> list[NativeBar]:
    if len(raw) % RECORD_SIZE != 0:
        raise RuntimeError(
            f"Decoded M1 file length {len(raw)} is not divisible by native "
            f"record size {RECORD_SIZE}."
        )

    bars = []
    for off in range(0, len(raw), RECORD_SIZE):
        sec, o, h, l, c, v = RECORD.unpack_from(raw, off)

        # Native M1 bar timestamps should be aligned to minute boundaries.
        if sec >= 86400:
            raise RuntimeError(f"Invalid seconds-from-day-start value: {sec}")
        if sec % 60 != 0:
            raise RuntimeError(f"Non-minute-aligned native timestamp: {sec}")

        # Native OHLC sanity before scaling.
        if h < max(o, c, l):
            raise RuntimeError(
                f"Invalid native high at sec={sec}: O={o} H={h} L={l} C={c}"
            )
        if l > min(o, c, h):
            raise RuntimeError(
                f"Invalid native low at sec={sec}: O={o} H={h} L={l} C={c}"
            )

        bars.append(NativeBar(sec, o, h, l, c, float(v)))

    return bars


def choose_divider(bars: list[NativeBar]) -> int:
    closes = sorted(b.c for b in bars if b.c > 0)
    if not closes:
        raise RuntimeError("Cannot detect price scale: no native close values.")

    median_raw = closes[len(closes) // 2]
    plausible = []

    for div in PRICE_DIVIDERS:
        p = median_raw / div
        if GOLD_MIN <= p <= GOLD_MAX:
            plausible.append((div, p))

    if len(plausible) != 1:
        raise RuntimeError(
            "Could not safely auto-detect XAUUSD native price divider. "
            f"median_raw={median_raw}; plausible={plausible}. "
            "Do not guess the scale; send this error back to ChatGPT."
        )

    return plausible[0][0]


def init_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS candles (
            ts INTEGER PRIMARY KEY,
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
        CREATE TABLE IF NOT EXISTS day_status (
            day TEXT NOT NULL,
            side TEXT NOT NULL,
            status TEXT NOT NULL,
            rows INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            PRIMARY KEY(day, side)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()
    return conn


def meta_get(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
    return None if row is None else row[0]


def meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)",
        (key, value),
    )


def done(conn: sqlite3.Connection, d: date, side: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM day_status WHERE day=? AND side=?",
        (d.isoformat(), side),
    ).fetchone() is not None


def mark_day(
    conn: sqlite3.Connection,
    d: date,
    side: str,
    status: str,
    rows: int,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO day_status(day,side,status,rows,completed_at)
        VALUES(?,?,?,?,?)
        """,
        (
            d.isoformat(),
            side,
            status,
            rows,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def timestamp_for(d: date, sec: int) -> int:
    base = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int((base + timedelta(seconds=sec)).timestamp())


def store_bars(
    conn: sqlite3.Connection,
    d: date,
    side: str,
    bars: list[NativeBar],
    divider: int,
) -> None:
    if side == "BID":
        sql = """
            INSERT INTO candles(
                ts,bid_open,bid_high,bid_low,bid_close,bid_volume
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(ts) DO UPDATE SET
                bid_open=excluded.bid_open,
                bid_high=excluded.bid_high,
                bid_low=excluded.bid_low,
                bid_close=excluded.bid_close,
                bid_volume=excluded.bid_volume
        """
    else:
        sql = """
            INSERT INTO candles(
                ts,ask_open,ask_high,ask_low,ask_close,ask_volume
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(ts) DO UPDATE SET
                ask_open=excluded.ask_open,
                ask_high=excluded.ask_high,
                ask_low=excluded.ask_low,
                ask_close=excluded.ask_close,
                ask_volume=excluded.ask_volume
        """

    rows = []
    for b in bars:
        rows.append(
            (
                timestamp_for(d, b.sec),
                b.o / divider,
                b.h / divider,
                b.l / divider,
                b.c / divider,
                b.v,
            )
        )

    conn.executemany(sql, rows)


def download_one_side(
    session: requests.Session,
    conn: sqlite3.Connection,
    d: date,
    side: str,
    divider: Optional[int],
) -> Optional[int]:
    if done(conn, d, side):
        return divider

    url = url_for(d, side)
    payload = get_bytes(session, url)

    if payload is None:
        with conn:
            mark_day(conn, d, side, "missing", 0)
        return divider

    decoded = decompress_bi5(payload)
    bars = decode_native_bars(decoded)

    if not bars:
        with conn:
            mark_day(conn, d, side, "empty", 0)
        return divider

    if divider is None:
        divider = choose_divider(bars)

    with conn:
        store_bars(conn, d, side, bars, divider)
        mark_day(conn, d, side, "ok", len(bars))
        meta_set(conn, "price_divider", str(divider))

    return divider


def export_csv(
    conn: sqlite3.Connection,
    out_path: Path,
    start: date,
    end_exclusive: date,
) -> dict:
    start_ts = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_ts = int(
        datetime(
            end_exclusive.year,
            end_exclusive.month,
            end_exclusive.day,
            tzinfo=timezone.utc,
        ).timestamp()
    )

    total = conn.execute(
        "SELECT COUNT(*) FROM candles WHERE ts>=? AND ts<?",
        (start_ts, end_ts),
    ).fetchone()[0]

    both = conn.execute(
        """
        SELECT COUNT(*) FROM candles
        WHERE ts>=? AND ts<?
          AND bid_open IS NOT NULL
          AND ask_open IS NOT NULL
        """,
        (start_ts, end_ts),
    ).fetchone()[0]

    print(f"\nExporting {total:,} timestamps to {out_path}")

    spread_n = 0
    spread_sum = 0.0
    spread_min = None
    spread_max = None

    with gzip.open(out_path, "wt", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp_utc",
            "bid_open","bid_high","bid_low","bid_close","bid_volume",
            "ask_open","ask_high","ask_low","ask_close","ask_volume",
            "mid_open","mid_high","mid_low","mid_close",
            "spread_open","spread_close",
        ])

        cur = conn.execute(
            """
            SELECT
                ts,
                bid_open,bid_high,bid_low,bid_close,bid_volume,
                ask_open,ask_high,ask_low,ask_close,ask_volume
            FROM candles
            WHERE ts>=? AND ts<?
            ORDER BY ts
            """,
            (start_ts, end_ts),
        )

        for row in cur:
            (
                ts,
                bo,bh,bl,bc,bv,
                ao,ah,al,ac,av
            ) = row

            def midpoint(a, b):
                return None if a is None or b is None else (a + b) / 2.0

            so = None if ao is None or bo is None else ao - bo
            sc = None if ac is None or bc is None else ac - bc

            if sc is not None:
                spread_n += 1
                spread_sum += sc
                spread_min = sc if spread_min is None else min(spread_min, sc)
                spread_max = sc if spread_max is None else max(spread_max, sc)

            iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            w.writerow([
                iso,
                bo,bh,bl,bc,bv,
                ao,ah,al,ac,av,
                midpoint(bo,ao),
                midpoint(bh,ah),
                midpoint(bl,al),
                midpoint(bc,ac),
                so,sc,
            ])

    return {
        "rows_total": total,
        "rows_with_bid_and_ask": both,
        "average_close_spread": None if spread_n == 0 else spread_sum / spread_n,
        "minimum_close_spread": spread_min,
        "maximum_close_spread": spread_max,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END, help="Exclusive end date")
    p.add_argument("--output-dir", default="dukascopy_xauusd_raw")
    p.add_argument("--delay", type=float, default=0.10)
    p.add_argument(
        "--smoke-test",
        action="store_true",
        help="Only download 2025-01-02 through 2025-01-06 for validation.",
    )
    args = p.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)

    if args.smoke_test:
        start = date(2025, 1, 2)
        end = date(2025, 1, 7)

    if end <= start:
        p.error("--end must be later than --start")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    db_path = out_dir / "xauusd_dukascopy_m1.sqlite"
    conn = init_db(db_path)

    divider_text = meta_get(conn, "price_divider")
    divider = int(divider_text) if divider_text else None

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 XAUUSD quantitative research downloader"
    })

    days = list(iter_dates(start, end))
    print(f"XAUUSD native Dukascopy M1: {start} -> {end} (exclusive)")
    print(f"Days to process: {len(days):,}")
    print(f"Resume database: {db_path}")
    print("No Dukascopy developer API key is used.\n")

    try:
        for i, d in enumerate(days, 1):
            before_div = divider
            divider = download_one_side(session, conn, d, "BID", divider)
            divider = download_one_side(session, conn, d, "ASK", divider)

            if before_div is None and divider is not None:
                print(f"Detected and locked XAUUSD native price divider: {divider}")

            if i % 10 == 0 or i == len(days):
                counts = conn.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM day_status
                    GROUP BY status
                    """
                ).fetchall()
                status_text = ", ".join(f"{k}={v}" for k, v in counts)
                print(f"{i:4d}/{len(days)} through {d} | {status_text}")

            if args.delay:
                time.sleep(args.delay)

    except KeyboardInterrupt:
        print("\nStopped. Progress is saved. Re-run the same command to resume.")
        conn.close()
        return 130

    except Exception as exc:
        print("\nDOWNLOAD STOPPED ON VALIDATION ERROR")
        print("------------------------------------")
        print(exc)
        print("\nProgress up to this point is saved.")
        print("Send this exact error back to ChatGPT; do not alter the raw files.")
        conn.close()
        return 2

    suffix = "SMOKE" if args.smoke_test else f"{start}_{end}"
    out_csv = out_dir / f"XAUUSD_Dukascopy_M1_{suffix}.csv.gz"

    stats = export_csv(conn, out_csv, start, end)

    manifest = {
        "source": "Dukascopy native historical datafeed",
        "symbol": SYMBOL,
        "timeframe": "M1",
        "start_inclusive": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "price_divider": divider,
        **stats,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    manifest_path = out_dir / f"XAUUSD_Dukascopy_M1_{suffix}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nDONE")
    print("----")
    print(f"Main file to upload: {out_csv}")
    print(f"Manifest:           {manifest_path}")
    print(f"SQLite resume DB:   {db_path}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
