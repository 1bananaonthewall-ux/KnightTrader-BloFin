from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.config import AppConfig


class TradeJournal:
    def __init__(self, cfg: AppConfig) -> None:
        self.path = Path(cfg.journal.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with self._conn() as con:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=NORMAL;")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    instId TEXT NOT NULL,
                    side TEXT NOT NULL,
                    action TEXT NOT NULL,
                    sz TEXT NOT NULL,
                    px TEXT,
                    leverage INTEGER,
                    rationale TEXT,
                    pnl_usdt REAL DEFAULT 0,
                    decision_raw TEXT
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS open_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    instId TEXT NOT NULL,
                    side TEXT NOT NULL,
                    sz TEXT NOT NULL,
                    entry_px TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    FOREIGN KEY(trade_id) REFERENCES trades(id)
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS summary_cache (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    generated_at TEXT NOT NULL,
                    summary TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def record_trade(self, tick: int, trade: dict[str, Any], decision_raw: str) -> int:
        with self._conn() as con:
            cur = con.execute(
                """
                INSERT INTO trades (ts, tick, instId, side, action, sz, px, leverage, rationale, decision_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    tick,
                    trade.get("instId"),
                    trade.get("side"),
                    trade.get("action"),
                    str(trade.get("sz")),
                    str(trade.get("px")) if trade.get("px") is not None else None,
                    trade.get("leverage"),
                    trade.get("rationale"),
                    decision_raw,
                ),
            )
            trade_id = int(cur.lastrowid)
            if trade.get("action") in {"open", "add"}:
                con.execute(
                    """
                    INSERT INTO open_lots (trade_id, instId, side, sz, entry_px, ts)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade_id,
                        trade.get("instId"),
                        trade.get("side"),
                        str(trade.get("sz")),
                        str(trade.get("px")) if trade.get("px") is not None else "",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            if trade.get("action") in {"close", "reduce"}:
                self._realize_pnl(con, trade)
            return trade_id

    def _realize_pnl(self, con: sqlite3.Connection, trade: dict[str, Any]) -> None:
        inst_id = trade.get("instId")
        target = Decimal(str(trade.get("sz", "0")))
        if target <= 0:
            return
        rows = con.execute(
            "SELECT id, sz, entry_px FROM open_lots WHERE instId=? ORDER BY id ASC",
            (inst_id,),
        ).fetchall()
        realized = Decimal("0")
        remain = target
        price = Decimal(str(trade.get("px") or "0"))
        side = trade.get("side", "buy")
        sign = Decimal("1") if side == "buy" else Decimal("-1")
        for row in rows:
            lid, lot_sz, entry_px = row
            lot = Decimal(str(lot_sz))
            take = lot if lot <= remain else remain
            entry = Decimal(str(entry_px))
            if entry == 0 or price == 0:
                continue
            pnl = sign * (price - entry) * take
            realized += pnl
            remain -= take
            new_sz = lot - take
            if new_sz <= 0:
                con.execute("DELETE FROM open_lots WHERE id=?", (lid,))
            else:
                con.execute("UPDATE open_lots SET sz=? WHERE id=?", (str(new_sz), lid))
            if remain <= 0:
                break
        con.execute("UPDATE trades SET pnl_usdt=? WHERE id=?", (float(realized), trade.get("trade_id", 0)))

    def last_trades(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, ts, tick, instId, side, action, sz, px, leverage, rationale, pnl_usdt, decision_raw FROM trades ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            cols = ["id", "ts", "tick", "instId", "side", "action", "sz", "px", "leverage", "rationale", "pnl_usdt", "decision_raw"]
            return [dict(zip(cols, r)) for r in rows]

    def get_summary(self) -> str | None:
        with self._conn() as con:
            row = con.execute("SELECT generated_at, summary FROM summary_cache WHERE id=1").fetchone()
            return row[1] if row else None

    def set_summary(self, summary: str) -> None:
        with self._conn() as con:
            con.execute(
                "INSERT INTO summary_cache (id, generated_at, summary) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET generated_at=excluded.generated_at, summary=excluded.summary",
                (datetime.now(timezone.utc).isoformat(), summary),
            )

    def heartbeats(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT id, ts, tick, instId, side, action, sz, px, leverage, rationale, pnl_usdt FROM trades ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            cols = ["id", "ts", "tick", "instId", "side", "action", "sz", "px", "leverage", "rationale", "pnl_usdt"]
            return [dict(zip(cols, r)) for r in rows]
