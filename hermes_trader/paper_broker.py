"""Paper / demo account broker — never places live Blofin orders.

Persists state to JSON so the dashboard can poll equity, positions, and
mark-to-market at 500ms while the agent ticks on its own interval.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .market_data import AccountSnapshot, PositionSnapshot, TickerSnapshot

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    instId: str
    side: str  # long | short
    sz: float
    entry_px: float
    leverage: int
    margin: float
    opened_ts: int


@dataclass
class PaperState:
    starting_equity: float = 40.0
    cash: float = 40.0
    realized_pnl: float = 0.0
    positions: list[PaperPosition] = field(default_factory=list)
    universe_count: int = 0
    last_tick: int = 0
    mode: str = "demo"
    updated_at: float = 0.0
    tickers: dict[str, float] = field(default_factory=dict)  # last prices for MTM


class PaperBroker:
    """Thread-safe simulated USDT-perp account starting at $40."""

    def __init__(self, path: str | Path, *, starting_equity: float = 40.0, reset: bool = False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.starting_equity = float(starting_equity)
        if reset or not self.path.exists():
            self.state = PaperState(starting_equity=self.starting_equity, cash=self.starting_equity)
            self._save()
        else:
            self.state = self._load()

    def _load(self) -> PaperState:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        positions = [PaperPosition(**p) for p in raw.get("positions", [])]
        return PaperState(
            starting_equity=float(raw.get("starting_equity", self.starting_equity)),
            cash=float(raw.get("cash", self.starting_equity)),
            realized_pnl=float(raw.get("realized_pnl", 0.0)),
            positions=positions,
            universe_count=int(raw.get("universe_count", 0)),
            last_tick=int(raw.get("last_tick", 0)),
            mode=str(raw.get("mode", "demo")),
            updated_at=float(raw.get("updated_at", 0.0)),
            tickers={str(k): float(v) for k, v in (raw.get("tickers") or {}).items()},
        )

    def _save(self) -> None:
        self.state.updated_at = time.time()
        payload = {
            "starting_equity": self.state.starting_equity,
            "cash": self.state.cash,
            "realized_pnl": self.state.realized_pnl,
            "positions": [asdict(p) for p in self.state.positions],
            "universe_count": self.state.universe_count,
            "last_tick": self.state.last_tick,
            "mode": self.state.mode,
            "updated_at": self.state.updated_at,
            "tickers": self.state.tickers,
            "equity": self.equity(),
            "available": self.state.cash,
            "margin_used": self.margin_used(),
            "unrealized_pnl": self.unrealized_pnl(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def reset(self, starting_equity: float | None = None) -> None:
        with self._lock:
            eq = float(starting_equity if starting_equity is not None else self.starting_equity)
            self.starting_equity = eq
            self.state = PaperState(starting_equity=eq, cash=eq)
            self._save()

    def update_marks(self, tickers: dict[str, TickerSnapshot] | dict[str, float], *, tick: int | None = None, universe_count: int | None = None) -> None:
        with self._lock:
            for iid, val in tickers.items():
                if isinstance(val, TickerSnapshot):
                    if val.last > 0:
                        self.state.tickers[iid] = float(val.last)
                else:
                    px = float(val or 0)
                    if px > 0:
                        self.state.tickers[str(iid)] = px
            if tick is not None:
                self.state.last_tick = int(tick)
            if universe_count is not None:
                self.state.universe_count = int(universe_count)
            self._save()

    def margin_used(self) -> float:
        return float(sum(p.margin for p in self.state.positions))

    def unrealized_pnl(self) -> float:
        total = 0.0
        for p in self.state.positions:
            mark = self.state.tickers.get(p.instId, p.entry_px)
            if p.side == "long":
                total += (mark - p.entry_px) * p.sz
            else:
                total += (p.entry_px - mark) * p.sz
        return float(total)

    def equity(self) -> float:
        return float(self.state.cash + self.margin_used() + self.unrealized_pnl())

    def account_snapshot(self) -> AccountSnapshot:
        with self._lock:
            return AccountSnapshot(
                equity=self.equity(),
                available=self.state.cash,
                margin_used=self.margin_used(),
                unrealized_pnl=self.unrealized_pnl(),
                details=[{"ccy": "USDT", "eq": self.equity(), "availEq": self.state.cash, "demo": True}],
            )

    def position_snapshots(self) -> list[PositionSnapshot]:
        with self._lock:
            out: list[PositionSnapshot] = []
            now = int(time.time() * 1000)
            for p in self.state.positions:
                mark = self.state.tickers.get(p.instId, p.entry_px)
                if p.side == "long":
                    upnl = (mark - p.entry_px) * p.sz
                else:
                    upnl = (p.entry_px - mark) * p.sz
                out.append(
                    PositionSnapshot(
                        instId=p.instId,
                        side=p.side,
                        sz=p.sz,
                        entry_px=p.entry_px,
                        mark_px=mark,
                        liq_px=None,
                        margin=p.margin,
                        leverage=p.leverage,
                        unrealized_pnl=upnl,
                        age_ms=max(0, now - p.opened_ts),
                    )
                )
            return out

    def to_public_dict(self) -> dict[str, Any]:
        with self._lock:
            positions = []
            for p in self.position_snapshots():
                positions.append(
                    {
                        "instId": p.instId,
                        "side": p.side,
                        "sz": p.sz,
                        "entry_px": p.entry_px,
                        "mark_px": p.mark_px,
                        "leverage": p.leverage,
                        "margin": p.margin,
                        "unrealized_pnl": p.unrealized_pnl,
                    }
                )
            return {
                "mode": "demo",
                "starting_equity": self.state.starting_equity,
                "equity": self.equity(),
                "available": self.state.cash,
                "margin_used": self.margin_used(),
                "unrealized_pnl": self.unrealized_pnl(),
                "realized_pnl": self.state.realized_pnl,
                "universe_count": self.state.universe_count,
                "last_tick": self.state.last_tick,
                "updated_at": self.state.updated_at,
                "positions": positions,
                "open_positions": len(positions),
            }

    def place_order(
        self,
        inst_id: str,
        side: str,
        sz: str,
        ord_type: str,
        td_mode: str,
        px: str | None = None,
        cl_ord_id: str | None = None,
        leverage: int | None = None,
        stop_loss: str | None = None,
        take_profit: str | None = None,
        *,
        action: str = "open",
    ) -> dict:
        """Simulate a market fill at last mark. `action` comes from Decision."""
        del td_mode, stop_loss, take_profit  # unused in paper fills
        with self._lock:
            qty = abs(float(sz))
            if qty <= 0:
                raise ValueError("sz must be positive")
            mark = self.state.tickers.get(inst_id)
            if ord_type == "limit" and px:
                fill_px = float(px)
            else:
                fill_px = float(mark or px or 0)
            if fill_px <= 0:
                raise ValueError(f"no mark price for {inst_id}")
            lev = max(1, int(leverage or 1))
            action_l = (action or "open").lower()
            side_l = side.lower()

            # Map buy/sell + action into position changes.
            if action_l in {"close", "reduce"}:
                pnl, fill_px = self._close_or_reduce(inst_id, side_l, qty, fill_px)
                self._save()
                return {"ordId": cl_ord_id or f"paper-{int(time.time()*1000)}", "avgPx": str(fill_px), "pnl": pnl, "demo": True}

            # open / add / cancel_and_replace → open long on buy, short on sell
            pos_side = "long" if side_l == "buy" else "short"
            notional = qty * fill_px
            margin = notional / lev
            # Auto-shrink opens that exceed free cash (LLM / lot rounding).
            if margin > self.state.cash + 1e-9:
                affordable_notional = self.state.cash * lev * 0.98
                affordable_qty = affordable_notional / fill_px if fill_px > 0 else 0.0
                if affordable_qty <= 0:
                    raise ValueError(
                        f"insufficient paper cash: need {margin:.4f}, have {self.state.cash:.4f}"
                    )
                # Keep same magnitude scale; caller should pass lot-snapped sizes,
                # but we still floor to a safer qty when overspending.
                qty = float(f"{affordable_qty:.12f}")
                # Drop fractional dust below 1e-8 coins.
                if qty < 1e-8:
                    raise ValueError(
                        f"insufficient paper cash: need {margin:.4f}, have {self.state.cash:.4f}"
                    )
                notional = qty * fill_px
                margin = notional / lev
                if margin > self.state.cash + 1e-9:
                    raise ValueError(
                        f"insufficient paper cash: need {margin:.4f}, have {self.state.cash:.4f}"
                    )
                logger.info(
                    "paper size clamped %s %s -> sz=%.8f margin=%.4f (cash=%.4f)",
                    action_l,
                    inst_id,
                    qty,
                    margin,
                    self.state.cash,
                )
            self.state.cash -= margin
            # Merge into existing same-side position if present.
            existing = next((p for p in self.state.positions if p.instId == inst_id and p.side == pos_side), None)
            now = int(time.time() * 1000)
            if existing:
                total_sz = existing.sz + qty
                existing.entry_px = (existing.entry_px * existing.sz + fill_px * qty) / total_sz
                existing.sz = total_sz
                existing.margin += margin
                existing.leverage = lev
            else:
                self.state.positions.append(
                    PaperPosition(
                        instId=inst_id,
                        side=pos_side,
                        sz=qty,
                        entry_px=fill_px,
                        leverage=lev,
                        margin=margin,
                        opened_ts=now,
                    )
                )
            self._save()
            logger.info("paper fill %s %s %s sz=%s px=%.6f lev=%s margin=%.4f", action_l, side_l, inst_id, qty, fill_px, lev, margin)
            return {"ordId": cl_ord_id or f"paper-{now}", "avgPx": str(fill_px), "demo": True}

    def _close_or_reduce(self, inst_id: str, side: str, qty: float, fill_px: float) -> tuple[float, float]:
        # Closing a long sells; closing a short buys.
        target_side = "long" if side == "sell" else "short"
        pos = next((p for p in self.state.positions if p.instId == inst_id and p.side == target_side), None)
        if pos is None:
            # Try opposite interpretation: reduce whatever we hold on inst
            pos = next((p for p in self.state.positions if p.instId == inst_id), None)
        if pos is None:
            raise ValueError(f"no paper position to close for {inst_id}")
        close_sz = min(qty, pos.sz)
        if pos.side == "long":
            pnl = (fill_px - pos.entry_px) * close_sz
        else:
            pnl = (pos.entry_px - fill_px) * close_sz
        frac = close_sz / pos.sz if pos.sz else 1.0
        margin_back = pos.margin * frac
        self.state.cash += margin_back + pnl
        self.state.realized_pnl += pnl
        pos.sz -= close_sz
        pos.margin -= margin_back
        if pos.sz <= 1e-12:
            self.state.positions = [p for p in self.state.positions if p is not pos]
        return float(pnl), float(fill_px)

    def get_order(self, inst_id: str, ord_id: str | None = None, cl_ord_id: str | None = None) -> dict:
        return {"instId": inst_id, "ordId": ord_id or cl_ord_id, "avgPx": self.state.tickers.get(inst_id), "state": "filled", "demo": True}


def load_paper_public(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
