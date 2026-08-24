from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict

from .config import settings


class SizingResult(BaseModel):
    instId: str = ""
    side: str = "buy"
    leverage: int = settings.risk.leverage
    risk_usd: float = 0.0
    margin: float = 0.0
    notional: float = 0.0
    sz: str = "0"
    stop_loss_pct: float = settings.risk.stop_loss_pct
    take_profit_pct: float = settings.risk.take_profit_pct
    stop_loss: str | None = None
    take_profit: str | None = None
    price: float = 0.0

    model_config = ConfigDict(frozen=False)


def _floor_to_lot(value: float, lot_sz: float, min_sz: float) -> float:
    if lot_sz <= 0:
        return max(min_sz, value)
    snapped = math.floor(value / lot_sz) * lot_sz
    return max(0.0, snapped)


def compute_size(
    inst: Any,
    price: float,
    side: str = "buy",
    leverage: int | None = None,
    equity: float | None = None,
) -> SizingResult:
    risk = settings.risk
    leverage = leverage or risk.leverage
    equity = equity if equity is not None else 0.0
    risk_usd = equity * risk.risk_per_trade_pct
    margin = risk_usd / (leverage * risk.stop_loss_pct) if leverage and risk.stop_loss_pct else 0.0
    notional = margin * leverage if margin and leverage else 0.0
    contract_value = float(getattr(inst, "ct_val", 1.0) or 1.0) * float(getattr(inst, "ct_mult", 1.0) or 1.0)
    raw_sz = notional / (price * contract_value) if price and contract_value else 0.0
    lot_sz = float(getattr(inst, "lot_sz", 1.0) or 1.0)
    min_sz = float(getattr(inst, "min_sz", 0.0) or 0.0)
    sz = _floor_to_lot(raw_sz, lot_sz, min_sz)
    if sz < min_sz:
        sz = 0.0
    stop_loss = None
    take_profit = None
    if price:
        if side == "buy":
            stop_loss = round(price * (1 - risk.stop_loss_pct), 8)
            take_profit = round(price * (1 + risk.take_profit_pct), 8)
        else:
            stop_loss = round(price * (1 + risk.stop_loss_pct), 8)
            take_profit = round(price * (1 - risk.take_profit_pct), 8)
    return SizingResult(
        instId=getattr(inst, "instId", ""),
        side=side,
        leverage=leverage,
        risk_usd=risk_usd,
        margin=margin,
        notional=notional,
        sz=repr(sz) if sz == 0 else f"{sz:.8f}".rstrip("0").rstrip(".") or "0",
        stop_loss_pct=risk.stop_loss_pct,
        take_profit_pct=risk.take_profit_pct,
        stop_loss=str(stop_loss) if stop_loss is not None else None,
        take_profit=str(take_profit) if take_profit is not None else None,
        price=price,
    )
