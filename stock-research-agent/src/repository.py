from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS price_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  price REAL NOT NULL,
  pct_change REAL NOT NULL,
  source TEXT NOT NULL,
  note TEXT,
  UNIQUE(symbol, collected_at)
);

CREATE TABLE IF NOT EXISTS news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  headline TEXT NOT NULL,
  url TEXT,
  source TEXT NOT NULL,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS earnings_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  earnings_date TEXT NOT NULL,
  session TEXT,
  source TEXT NOT NULL,
  note TEXT,
  collected_at TEXT NOT NULL,
  UNIQUE(symbol, earnings_date, session)
);

CREATE TABLE IF NOT EXISTS toss_index_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  index_code TEXT NOT NULL,
  index_name TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  close REAL NOT NULL,
  change_value REAL NOT NULL,
  change_pct REAL NOT NULL,
  volume REAL,
  trading_value_text TEXT,
  open REAL,
  high REAL,
  low REAL,
  source TEXT NOT NULL,
  note TEXT,
  UNIQUE(index_code, collected_at)
);

CREATE TABLE IF NOT EXISTS toss_news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  headline TEXT NOT NULL,
  source_name TEXT,
  published_text TEXT,
  url TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saveticker_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  headline TEXT NOT NULL,
  kind TEXT,
  published_text TEXT,
  tickers_text TEXT,
  popularity_text TEXT,
  source TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  url TEXT
);
"""


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_price_snapshot(
    conn: sqlite3.Connection,
    symbol: str,
    collected_at: str,
    price: float,
    pct_change: float,
    source: str,
    note: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO price_snapshots
        (symbol, collected_at, price, pct_change, source, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (symbol, collected_at, price, pct_change, source, note),
    )


def insert_news_item(
    conn: sqlite3.Connection,
    symbol: str,
    headline: str,
    url: str,
    source: str,
    collected_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO news_items (symbol, headline, url, source, collected_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (symbol, headline, url, source, collected_at),
    )


def insert_earnings_event(
    conn: sqlite3.Connection,
    symbol: str,
    earnings_date: str,
    session: str,
    source: str,
    note: str,
    collected_at: str,
) -> None:
    conn.execute("DELETE FROM earnings_events WHERE symbol = ?", (symbol,))
    conn.execute(
        """
        INSERT OR REPLACE INTO earnings_events
        (symbol, earnings_date, session, source, note, collected_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (symbol, earnings_date, session, source, note, collected_at),
    )


def fetch_latest_snapshot(conn: sqlite3.Connection, symbol: str):
    return conn.execute(
        """
        SELECT symbol, collected_at, price, pct_change, source, note
        FROM price_snapshots
        WHERE symbol = ?
        ORDER BY collected_at DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()


def fetch_latest_news(conn: sqlite3.Connection, symbol: str, limit: int = 2):
    return conn.execute(
        """
        SELECT headline, url, source, collected_at
        FROM news_items
        WHERE symbol = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (symbol, limit),
    ).fetchall()


def fetch_latest_earnings(conn: sqlite3.Connection, symbol: str):
    return conn.execute(
        """
        SELECT symbol, earnings_date, session, source, note, collected_at
        FROM earnings_events
        WHERE symbol = ?
        ORDER BY date(earnings_date) ASC, collected_at DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()


def fetch_upcoming_earnings(conn: sqlite3.Connection, limit: int = 10):
    return conn.execute(
        """
        SELECT symbol, earnings_date, session, source, note, collected_at
        FROM earnings_events
        WHERE date(earnings_date) >= date('now')
        ORDER BY date(earnings_date) ASC, symbol ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def insert_toss_index_snapshot(
    conn: sqlite3.Connection,
    index_code: str,
    index_name: str,
    collected_at: str,
    close: float,
    change_value: float,
    change_pct: float,
    volume: float | None,
    trading_value_text: str | None,
    open: float | None,
    high: float | None,
    low: float | None,
    source: str,
    note: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO toss_index_snapshots
        (index_code, index_name, collected_at, close, change_value, change_pct, volume, trading_value_text, open, high, low, source, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (index_code, index_name, collected_at, close, change_value, change_pct, volume, trading_value_text, open, high, low, source, note),
    )


def insert_toss_news_item(
    conn: sqlite3.Connection,
    headline: str,
    source_name: str,
    published_text: str,
    url: str,
    source: str,
    collected_at: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO toss_news_items
        (headline, source_name, published_text, url, source, collected_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (headline, source_name, published_text, url, source, collected_at),
    )


def fetch_latest_toss_indices(conn: sqlite3.Connection, limit: int = 10):
    return conn.execute(
        """
        SELECT t.index_code, t.index_name, t.collected_at, t.close, t.change_value, t.change_pct, t.volume, t.trading_value_text, t.open, t.high, t.low, t.source, t.note
        FROM toss_index_snapshots t
        JOIN (
          SELECT index_code, MAX(collected_at) AS max_collected_at
          FROM toss_index_snapshots
          GROUP BY index_code
        ) latest
          ON latest.index_code = t.index_code AND latest.max_collected_at = t.collected_at
        ORDER BY t.index_code ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def fetch_latest_toss_news(conn: sqlite3.Connection, limit: int = 5):
    return conn.execute(
        """
        SELECT headline, source_name, published_text, url, source, collected_at
        FROM toss_news_items
        ORDER BY collected_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def insert_saveticker_item(
    conn: sqlite3.Connection,
    headline: str,
    kind: str,
    published_text: str,
    tickers_text: str,
    popularity_text: str,
    source: str,
    collected_at: str,
    url: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO saveticker_items
        (headline, kind, published_text, tickers_text, popularity_text, source, collected_at, url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (headline, kind, published_text, tickers_text, popularity_text, source, collected_at, url),
    )


def fetch_latest_saveticker_items(conn: sqlite3.Connection, limit: int = 10):
    return conn.execute(
        """
        SELECT headline, kind, published_text, tickers_text, popularity_text, source, collected_at, url
        FROM saveticker_items
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
