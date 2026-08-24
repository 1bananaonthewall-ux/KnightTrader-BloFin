from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN

from src.config import AppConfig


def _floor_to_lot(value: Decimal, lot_sz: Decimal, min_sz: Decimal) -> Decimal:
    if lot_sz <= 0:
        return Decimal("0")
    floored = (value // lot_sz) * lot_sz
    if floored < min_sz:
        return Decimal("0")
    return floored


def apply_risk_sizing(
    cfg: AppConfig, *, equity: Decimal, mark_price: Decimal, inst: dict[str, str], leverage: int | None = None
) -> dict[str, Any]:
    leverage = leverage or cfg.risk.leverage
    risk_usd = equity * Decimal(str(cfg.risk.risk_per_trade_pct))
    margin = risk_usd / (Decimal(str(leverage)) * Decimal(str(cfg.risk.stop_loss_pct)))
    notional = margin * Decimal(str(leverage))
    contract_value = Decimal(inst.get("ctVal", "1") or "1")
    price = mark_price * contract_value if contract_value != 1 else mark_price
    raw_sz = notional / price
    lot_sz = Decimal(inst.get("lotSz", "1") or "1")
    min_sz = Decimal(inst.get("minSz", "0") or "0")
    sz = _floor_to_lot(raw_sz, lot_sz, min_sz)
    stop_loss = float((mark_price * (Decimal("1") - Decimal(str(cfg.risk.stop_loss_pct)))).quantize(Decimal("0.0001")))
    take_profit = float((mark_price * (Decimal("1") + Decimal(str(cfg.risk.take_profit_pct)))).quantize(Decimal("0.0001")))
    return {
        "sz": f"{sz:.10f}".rstrip("0").rstrip("."),
        "leverage": leverage,
        "margin_usdt": float(margin.quantize(Decimal("0.0001"))),
        "notional_usdt": float(notional.quantize(Decimal("0.0001"))),
        "stopLoss": str(stop_loss),
        "takeProfit": str(take_profit),
        "risk_usdt": float(risk_usd.quantize(Decimal("0.0001"))),
    }
