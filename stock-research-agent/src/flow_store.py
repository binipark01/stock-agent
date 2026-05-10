"""SQLite storage for US sector/theme flow tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_flow_db(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS theme_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                theme_key TEXT NOT NULL,
                theme_name TEXT,
                flow_score REAL,
                average_pct_change REAL,
                breadth_positive_pct REAL,
                relative_to_spy_pct REAL,
                trading_value REAL,
                vwap_above_count INTEGER,
                top_5m_symbols TEXT,
                flow_proxy_active INTEGER DEFAULT 0,
                payload_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                theme_key TEXT NOT NULL,
                theme_name TEXT,
                score REAL,
                previous_score REAL,
                summary TEXT,
                payload_json TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_theme_snapshots_theme_time ON theme_snapshots(theme_key, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_flow_events_signature_time ON flow_events(event_type, theme_key, timestamp)")
        conn.execute("CREATE TABLE IF NOT EXISTS flow_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO flow_meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()


def save_theme_snapshots(db_path: str | Path, snapshots: list[dict[str, Any]]) -> None:
    init_flow_db(db_path)
    if not snapshots:
        return
    rows = []
    for row in snapshots:
        timestamp = str(row.get("timestamp") or _iso_now())
        rows.append((
            timestamp,
            str(row.get("theme_key") or ""),
            row.get("theme_name"),
            row.get("flow_score"),
            row.get("average_pct_change"),
            row.get("breadth_positive_pct"),
            row.get("relative_to_spy_pct"),
            row.get("trading_value"),
            row.get("vwap_above_count"),
            json.dumps(row.get("top_5m_symbols") or [], ensure_ascii=False),
            1 if row.get("flow_proxy_active") else 0,
            json.dumps(row, ensure_ascii=False),
        ))
    with _connect(db_path) as conn:
        conn.executemany("""
            INSERT INTO theme_snapshots(
                timestamp, theme_key, theme_name, flow_score, average_pct_change,
                breadth_positive_pct, relative_to_spy_pct, trading_value,
                vwap_above_count, top_5m_symbols, flow_proxy_active, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()


def load_recent_theme_snapshots(
    db_path: str | Path,
    *,
    theme_key: str | None = None,
    lookback_minutes: int = 90,
    now: str | None = None,
) -> list[dict[str, Any]]:
    init_flow_db(db_path)
    cutoff = None
    now_dt = _parse_dt(now) if now else None
    if now_dt is not None:
        cutoff = (now_dt - timedelta(minutes=lookback_minutes)).isoformat()
    query = "SELECT payload_json FROM theme_snapshots"
    params: list[Any] = []
    clauses = []
    if theme_key:
        clauses.append("theme_key = ?")
        params.append(str(theme_key))
    if cutoff:
        clauses.append("timestamp >= ?")
        params.append(cutoff)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY timestamp ASC, id ASC"
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    out = []
    for row in rows:
        try:
            out.append(json.loads(row["payload_json"]))
        except Exception:
            continue
    return out


def save_flow_events(db_path: str | Path, events: list[dict[str, Any]]) -> None:
    init_flow_db(db_path)
    if not events:
        return
    rows = []
    for event in events:
        timestamp = str(event.get("timestamp") or _iso_now())
        rows.append((
            timestamp,
            str(event.get("event_type") or ""),
            str(event.get("theme_key") or ""),
            event.get("theme_name"),
            event.get("score"),
            event.get("previous_score"),
            event.get("summary"),
            json.dumps(event, ensure_ascii=False),
        ))
    with _connect(db_path) as conn:
        conn.executemany("""
            INSERT INTO flow_events(timestamp, event_type, theme_key, theme_name, score, previous_score, summary, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()


def should_emit_event(
    db_path: str | Path,
    event: dict[str, Any],
    *,
    cooldown_minutes: int = 20,
    now: str | None = None,
) -> bool:
    init_flow_db(db_path)
    event_type = str(event.get("event_type") or "")
    theme_key = str(event.get("theme_key") or "")
    if not event_type or not theme_key:
        return False
    now_dt = _parse_dt(now or event.get("timestamp")) or datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(minutes=cooldown_minutes)).isoformat()
    with _connect(db_path) as conn:
        row = conn.execute("""
            SELECT timestamp FROM flow_events
            WHERE event_type = ? AND theme_key = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT 1
        """, (event_type, theme_key, cutoff)).fetchone()
    return row is None
