"""SQLite-backed trade journal with rolling verbatim window + cached summary."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_trades_instId ON trades(instId);

CREATE TABLE IF NOT EXISTS open_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instId TEXT NOT NULL,
    side TEXT NOT NULL,
    sz REAL NOT NULL,
    entry_px REAL NOT NULL,
    ts INTEGER NOT NULL,
    trade_id INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_open_lots_inst ON open_lots(instId, side);

CREATE TABLE IF NOT EXISTS summary_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    generated_at INTEGER NOT NULL,
    summary TEXT NOT NULL
);
"""


@dataclass
class Trade:
    id: int
    ts: int
    tick: int
    instId: str
    side: str
    action: str
    sz: str
    px: str | None
    leverage: int | None
    rationale: str | None
    pnl_usdt: float | None
    decision_raw: str | None


@dataclass
class SummaryCache:
    generated_at: int
    summary: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Trade":
        return cls(
            id=row["id"],
            ts=row["ts"],
            tick=row["tick"],
            instId=row["instId"],
            side=row["side"],
            action=row["action"],
            sz=row["sz"],
            px=row["px"],
            leverage=row["leverage"],
            rationale=row["rationale"],
            pnl_usdt=row["pnl_usdt"],
            decision_raw=row["decision_raw"],
        )


class Journal:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def add_trade(
        self,
        *,
        tick: int,
        inst_id: str,
        side: str,
        action: str,
        sz: str,
        px: str | None,
        leverage: int | None,
        rationale: str | None,
        decision_raw: str | None,
    ) -> Trade:
        ts = int(time.time() * 1000)
        pnl = self._compute_and_apply_fill(
            inst_id=inst_id,
            side=side,
            action=action,
            sz=float(sz),
            px=float(px) if px else None,
        )

        with self._tx() as conn:
            cur = conn.execute(
                """
                INSERT INTO trades
                    (ts, tick, instId, side, action, sz, px, leverage, rationale, pnl_usdt, decision_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts, tick, inst_id, side, action, sz, px, leverage,
                    rationale, pnl, decision_raw,
                ),
            )
            trade_id = cur.lastrowid

        return Trade(
            id=trade_id, ts=ts, tick=tick, instId=inst_id, side=side,
            action=action, sz=sz, px=px, leverage=leverage,
            rationale=rationale, pnl_usdt=pnl, decision_raw=decision_raw,
        )

    def _compute_and_apply_fill(
        self,
        *,
        inst_id: str,
        side: str,
        action: str,
        sz: float,
        px: float | None,
    ) -> float | None:
        if px is None:
            return None

        if action in ("close", "reduce"):
            target_side = "sell" if side == "buy" else "buy"
        else:
            target_side = side

        with self._tx() as conn:
            rows = conn.execute(
                "SELECT id, sz, entry_px FROM open_lots "
                "WHERE instId = ? AND side = ? ORDER BY ts ASC",
                (inst_id, target_side),
            ).fetchall()
            remaining = sz
            realized = 0.0
            closed_anything = False
            for row in rows:
                if remaining <= 0:
                    break
                lot_sz = row["sz"]
                take = min(lot_sz, remaining)
                if target_side == "buy":
                    pnl = (px - row["entry_px"]) * take
                else:
                    pnl = (row["entry_px"] - px) * take
                realized += pnl
                closed_anything = True
                new_lot_sz = lot_sz - take
                remaining -= take
                if new_lot_sz <= 1e-12:
                    conn.execute("DELETE FROM open_lots WHERE id = ?", (row["id"],))
                else:
                    conn.execute(
                        "UPDATE open_lots SET sz = ? WHERE id = ?",
                        (new_lot_sz, row["id"]),
                    )

            if remaining > 0 and action in ("close", "reduce", "open", "add"):
                conn.execute(
                    "INSERT INTO open_lots (instId, side, sz, entry_px, ts, trade_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (inst_id, side, remaining, px, int(time.time() * 1000), -1),
                )

        if not closed_anything:
            return None
        return round(realized, 8)

    def update_fill(self, trade_id: int, fill_px: str, fill_sz: str, pnl_usdt: float | None) -> None:
        with self._tx() as conn:
            conn.execute(
                "UPDATE trades SET px = ?, sz = ?, pnl_usdt = ? WHERE id = ?",
                (fill_px, fill_sz, pnl_usdt, trade_id),
            )

    def get_verbatim(self, n: int) -> list[Trade]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [Trade.from_row(r) for r in reversed(rows)]

    def get_summary(self) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT summary FROM summary_cache WHERE id = 1").fetchone()
        return row["summary"] if row else ""

    def set_summary(self, summary: str) -> None:
        ts = int(time.time() * 1000)
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO summary_cache (id, generated_at, summary) VALUES (1, ?, ?)",
                (ts, summary),
            )

    def pnl_today(self) -> float:
        now = time.time()
        utc_midnight = now - (now % 86400)
        midnight_ms = int(utc_midnight * 1000)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(pnl_usdt), 0.0) AS total FROM trades "
                "WHERE ts >= ? AND pnl_usdt IS NOT NULL",
                (midnight_ms,),
            ).fetchone()
        return float(row["total"] or 0.0)

    def total_trades(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM trades").fetchone()
        return int(row["c"])

    @staticmethod
    def should_refresh_summary_tick(current_tick: int, every_n: int) -> bool:
        if every_n <= 0:
            return False
        return current_tick > 0 and current_tick % every_n == 0


def serialize_trades_for_prompt(trades: list[Trade]) -> str:
    if not trades:
        return "(no trades yet)"
    out = []
    for t in trades:
        pnl = f"{t.pnl_usdt:+.2f}" if t.pnl_usdt is not None else "n/a"
        out.append(
            f"#{t.id} t={t.tick} {t.instId} {t.side} {t.action} "
            f"sz={t.sz} px={t.px or '?'} lev={t.leverage or '?'} pnl={pnl} "
            f"| {t.rationale or ''}"
        )
    return "\n".join(out)
