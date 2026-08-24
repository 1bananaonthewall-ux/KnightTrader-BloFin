from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import settings


@dataclass
class PaperPosition:
    instId: str
    side: str
    sz: float
    entry_px: float
    leverage: int
    liq_px: float = 0.0
    mark_px: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaperOrder:
    ordId: str
    clientOrderId: str
    instId: str
    side: str
    orderType: str
    sz: str
    px: str
    leverage: int | None = None
    status: str = "new"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperBroker:
    def __init__(self, equity: float = 1000.0) -> None:
        self.equity = equity
        self.available_balance = equity
        self.margin_used = 0.0
        self.positions: dict[str, PaperPosition] = {}
        self.orders: list[PaperOrder] = []
        self.starting_equity = equity

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        instId = payload.get("instId", "")
        side = payload.get("side", "buy")
        order_type = payload.get("orderType", "market")
        sz = float(payload.get("sz", 0) or 0)
        px = float(payload.get("px", 0) or 0)
        leverage = int(payload.get("leverage", settings.risk.leverage) or settings.risk.leverage)
        margin = (sz * (px if px > 0 else 0)) / leverage if px > 0 else 0.0
        if margin > self.available_balance:
            return {"code": "20101", "msg": "Insufficient available balance", "data": None, "ordId": "", "clientOrderId": ""}
        if order_type == "market":
            position = self.positions.get(instId)
            if position:
                if position.side == side:
                    position.sz += sz
                    position.leverage = leverage
                else:
                    realized = 0.0
                    if side == "buy":
                        realized = (position.entry_px - (px if px > 0 else position.entry_px)) * min(sz, position.sz)
                    else:
                        realized = ((px if px > 0 else position.entry_px) - position.entry_px) * min(sz, position.sz)
                    self.equity += realized
                    self.available_balance += realized
                    position.sz = abs(position.sz - sz)
                    if position.sz <= 1e-12:
                        del self.positions[instId]
            else:
                self.positions[instId] = PaperPosition(
                    instId=instId,
                    side=side,
                    sz=sz,
                    entry_px=px if px > 0 else 0.0,
                    leverage=leverage,
                )
            self.margin_used = sum((p.sz * p.mark_px) / p.leverage for p in self.positions.values()) if self.positions else 0.0
            return {"code": "0", "msg": "Order placed", "data": None, "ordId": f"paper-{len(self.orders)+1}", "clientOrderId": payload.get("clientOrderId", "")}
        ord_id = f"paper-{len(self.orders)+1}"
        self.orders.append(PaperOrder(ordId=ord_id, clientOrderId=str(payload.get("clientOrderId", "")), instId=instId, side=side, orderType=order_type, sz=str(sz), px=str(px), leverage=leverage))
        return {"code": "0", "msg": "Order accepted", "data": None, "ordId": ord_id, "clientOrderId": str(payload.get("clientOrderId", ""))}

    def close_position(self, instId: str, side: str, sz: str, px: float) -> dict[str, float, str]:
        position = self.positions.get(instId)
        if not position:
            return {"realized_pnl": 0.0, "note": "no_position"}
        close_sz = float(sz)
        realized = 0.0
        if side == position.side:
            realized = 0.0
        else:
            if side == "buy":
                realized = (position.entry_px - px) * min(close_sz, position.sz)
            else:
                realized = (px - position.entry_px) * min(close_sz, position.sz)
        self.equity += realized
        self.available_balance += realized
        position.sz = max(0.0, position.sz - close_sz)
        if position.sz <= 1e-12:
            del self.positions[instId]
        self.margin_used = sum((p.sz * p.mark_px) / p.leverage for p in self.positions.values()) if self.positions else 0.0
        return {"realized_pnl": realized, "note": f"closed {close_sz} of {instId}"}

    def snapshot(self) -> dict[str, Any]:
        unrealized = 0.0
        for p in self.positions.values():
            if p.side == "buy":
                p.unrealized_pnl = (p.mark_px - p.entry_px) * p.sz if p.mark_px else 0.0
            else:
                p.unrealized_pnl = (p.entry_px - p.mark_px) * p.sz if p.mark_px else 0.0
            unrealized += p.unrealized_pnl
        return {
            "equity": self.equity + unrealized,
            "available_balance": self.available_balance,
            "margin_used": self.margin_used,
            "unrealized_pnl": unrealized,
            "positions": list(self.positions.values()),
            "orders": self.orders[-20:],
        }
