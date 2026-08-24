from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from pydantic import BaseModel, Field

from .config import settings


class Trade(BaseModel):
    id: int | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tick: int = 0
    instId: str = ""
    side: str = ""
    action: str = ""
    sz: str = ""
    px: str = ""
    leverage: int | None = None
    rationale: str = ""
    pnl_usdt: float | None = None
    decision_raw: str | None = None


class OpenLot(BaseModel):
    id: int | None = None
    instId: str = ""
    side: str = ""
    sz: str = ""
    entry_px: str = ""
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trade_id: int | None = None


class SummaryCache(BaseModel):
    id: int = 1
    generated_at: datetime | None = None
    summary: str = ""


class AxiomJournal:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or settings.journal.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._tx() as conn:
            conn.execute(
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
                    pnl_usdt REAL,
                    decision_raw TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS open_lots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instId TEXT NOT NULL,
                    side TEXT NOT NULL,
                    sz TEXT NOT NULL,
                    entry_px TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    trade_id INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summary_cache (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    generated_at TEXT,
                    summary TEXT
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_tick ON trades(tick);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_inst ON trades(instId);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_open_lots_inst ON open_lots(instId);")

    def append_trade(self, trade: Trade) -> int:
        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO trades (ts, tick, instId, side, action, sz, px, leverage, rationale, pnl_usdt, decision_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.ts.isoformat(),
                    trade.tick,
                    trade.instId,
                    trade.side,
                    trade.action,
                    trade.sz,
                    trade.px,
                    trade.leverage,
                    trade.rationale,
                    trade.pnl_usdt,
                    trade.decision_raw,
                ),
            )
            return cur.lastrowid

    def record_decision_raw(self, tick: int, decision_raw: str | None) -> None:
        if not decision_raw:
            return
        with self._tx() as conn:
            conn.execute(
                "UPDATE trades SET decision_raw = ? WHERE tick = ? AND decision_raw IS NULL",
                (decision_raw, tick),
            )

    def add_open_lots(self, trade_id: int, lots: Sequence[OpenLot]) -> None:
        with self._tx() as conn:
            conn.executemany(
                """
                INSERT INTO open_lots (instId, side, sz, entry_px, ts, trade_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        l.instId,
                        l.side,
                        l.sz,
                        l.entry_px,
                        l.ts.isoformat() if isinstance(l.ts, datetime) else str(l.ts),
                        trade_id,
                    )
                    for l in lots
                ],
            )

    def close_lots_fifo(self, instId: str, side: str, close_sz: str | float, close_px: str | float, trade_id: int | None = None) -> tuple[float, str]:
        try:
            target = float(close_sz)
        except (TypeError, ValueError):
            return 0.0, ""
        close_price = float(close_px)
        remaining = target
        realized = 0.0
        pnl_notes: list[str] = []
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, sz, entry_px FROM open_lots WHERE instId = ? AND side = ? ORDER BY id ASC",
                (instId, side),
            ).fetchall()
            to_delete: list[int] = []
            for row in rows:
                if remaining <= 0:
                    break
                lot_id = row["id"]
                lot_sz = float(row["sz"])
                entry_px = float(row["entry_px"])
                qty = min(remaining, lot_sz)
                if side == "buy":
                    pnl = (close_price - entry_px) * qty
                else:
                    pnl = (entry_px - close_price) * qty
                realized += pnl
                pnl_notes.append(f"lot={lot_id} qty={qty} entry={entry_px} close={close_price} pnl={pnl:.6f}")
                remaining -= qty
                if qty >= lot_sz - 1e-12:
                    to_delete.append(lot_id)
            if to_delete:
                conn.execute(f"DELETE FROM open_lots WHERE id IN ({','.join(['?'] * len(to_delete))})", to_delete)
            if remaining > 1e-12:
                pnl_notes.append(f"shortfall={remaining}")
        return realized, "; ".join(pnl_notes)

    def recent_trades(self, limit: int = 30) -> list[Trade]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY tick DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_trade(r) for r in rows]

    def trades_since_tick(self, tick: int) -> list[Trade]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE tick > ? ORDER BY tick ASC, id ASC",
                (tick,),
            ).fetchall()
            return [self._row_to_trade(r) for r in rows]

    def summary(self) -> SummaryCache:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM summary_cache WHERE id = 1").fetchone()
            if not row:
                return SummaryCache()
            return SummaryCache(generated_at=self._parse_dt(row["generated_at"]), summary=row["summary"] or "")

    def set_summary(self, text: str) -> None:
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO summary_cache (id, generated_at, summary)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET generated_at=excluded.generated_at, summary=excluded.summary
                """,
                (datetime.now(timezone.utc).isoformat(), text),
            )

    def last_tick(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(tick) AS mx FROM trades").fetchone()
            return int(row["mx"]) if row and row["mx"] is not None else 0

    def last_heartbeat_tick(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(tick) AS mx FROM trades WHERE action = 'heartbeat'").fetchone()
            return int(row["mx"]) if row and row["mx"] is not None else 0

    def append_heartbeat(self, tick: int, decision_raw: str | None) -> None:
        trade = Trade(tick=tick, instId="-", side="-", action="heartbeat", sz="0", px="0", rationale="tick heartbeat", decision_raw=decision_raw)
        with self._tx() as conn:
            conn.execute(
                """
                INSERT INTO trades (ts, tick, instId, side, action, sz, px, leverage, rationale, pnl_usdt, decision_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.ts.isoformat(),
                    tick,
                    trade.instId,
                    trade.side,
                    trade.action,
                    trade.sz,
                    trade.px,
                    trade.leverage,
                    trade.rationale,
                    trade.pnl_usdt,
                    decision_raw,
                ),
            )

    def realized_pnl(self) -> float:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(SUM(pnl_usdt), 0) AS total FROM trades WHERE action IN ('close','reduce')").fetchone()
            return float(row["total"]) if row else 0.0

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        return Trade(
            id=row["id"],
            ts=self._parse_dt(row["ts"]),
            tick=row["tick"],
            instId=row["instId"],
            side=row["side"],
            action=row["action"],
            sz=row["sz"],
            px=row["px"] or "",
            leverage=row["leverage"],
            rationale=row["rationale"] or "",
            pnl_usdt=row["pnl_usdt"],
            decision_raw=row["decision_raw"],
        )

    @staticmethod
    def _parse_dt(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now(timezone.utc)
