"""Intelligent position sizing from the offline playbook winner.

Best book (data/backtest_best.json): breakout+roc_momentum AND,
leverage=10, max_positions=3, stop_loss=3%, take_profit=25%,
~$40 -> ~$124 in ~1 month of 1H bars (max DD was large offline).

IMPORTANT: the search engine deployed cash/remaining_slots all-in. That is a
backtest artifact, NOT live sizing. Live/demo uses stop-based risk:

    risk_usd = equity * risk_per_trade_pct
    # price stop of stop_loss_pct at `leverage` moves equity by
    #   margin * leverage * stop_loss_pct
    margin   = risk_usd / (leverage * stop_loss_pct)
    notional = margin * leverage
    sz       = notional / price   (lot-snapped)

Defaults: risk 1% equity per open, max 3 opens, so ~3% portfolio heat if
every stop hits. Caps total margin so a $40 book never locks ~$39.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .playbook import load_backtest_best

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybookRisk:
    leverage: int = 10
    max_positions: int = 3
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.25
    starting_equity: float = 40.0
    target_equity: float = 120.0
    # Live risk controls (not all-in cash/slots).
    risk_per_trade_pct: float = 0.01      # 1% equity risked to the stop
    max_portfolio_heat_pct: float = 0.03  # sum of open risks
    max_margin_util_pct: float = 0.35     # never lock >35% equity as margin
    min_margin_usdt: float = 0.05


@dataclass(frozen=True)
class SizePlan:
    sz: float
    margin: float
    notional: float
    leverage: int
    risk_usd: float = 0.0


def load_playbook_risk(best: dict[str, Any] | None = None) -> PlaybookRisk:
    data = best if best is not None else load_backtest_best()
    params = (data or {}).get("params") or {}
    # Optional overrides from config-shaped keys if present in best JSON later.
    return PlaybookRisk(
        leverage=max(1, int(float(params.get("leverage", 10)))),
        max_positions=max(1, int(float(params.get("max_positions", 3)))),
        stop_loss_pct=max(0.005, float(params.get("stop_loss_pct", 0.03))),
        take_profit_pct=float(params.get("take_profit_pct", 0.25)),
        starting_equity=40.0,
        target_equity=120.0,
        risk_per_trade_pct=float(params.get("risk_per_trade_pct", 0.01)),
        max_portfolio_heat_pct=float(params.get("max_portfolio_heat_pct", 0.03)),
        max_margin_util_pct=float(params.get("max_margin_util_pct", 0.35)),
        min_margin_usdt=float(params.get("min_margin_usdt", 0.05)),
    )


def floor_to_lot(raw_sz: float, lot: float, min_sz: float) -> float:
    lot = max(float(lot), 1e-12)
    min_sz = max(float(min_sz), lot)
    if raw_sz < min_sz:
        return 0.0
    steps = int(raw_sz / lot)
    sz = steps * lot
    if sz < min_sz:
        return 0.0
    return float(f"{sz:.12f}")


def margin_for_sz(sz: float, price: float, leverage: int) -> float:
    lev = max(1, int(leverage))
    return (abs(sz) * float(price)) / lev


def risk_budget_usd(equity: float, open_count: int, risk: PlaybookRisk) -> float:
    """How many dollars of equity this next open may risk to its stop."""
    equity = max(0.0, float(equity))
    # Tiny accounts need a higher risk fraction to clear exchange min sizes.
    pct = float(risk.risk_per_trade_pct)
    if equity < 20.0:
        pct = max(pct, 0.05)  # 5% on sub-$20 books
    if equity < 5.0:
        pct = max(pct, 0.08)  # 8% on sub-$5 books
    per = equity * pct
    used_heat = max(0, int(open_count)) * pct * equity
    heat_cap = float(risk.max_portfolio_heat_pct)
    if equity < 20.0:
        heat_cap = max(heat_cap, pct * risk.max_positions)
    room = max(0.0, equity * heat_cap - used_heat)
    return min(per, room)


def margin_from_risk(
    *,
    equity: float,
    cash: float,
    open_count: int,
    margin_already_used: float = 0.0,
    risk: PlaybookRisk | None = None,
) -> float:
    """Stop-based margin for one new open (intelligent, not cash/slots)."""
    risk = risk or load_playbook_risk()
    if open_count >= risk.max_positions:
        return 0.0
    risk_usd = risk_budget_usd(equity, open_count, risk)
    if risk_usd <= 0:
        return 0.0
    denom = max(1e-9, float(risk.leverage) * float(risk.stop_loss_pct))
    margin = risk_usd / denom
    # Margin utilization cap across the book.
    max_total = max(0.0, float(equity) * float(risk.max_margin_util_pct))
    room_margin = max(0.0, max_total - float(margin_already_used))
    margin = min(margin, room_margin, float(cash) * 0.95)
    if margin < float(risk.min_margin_usdt):
        return 0.0
    return float(margin)


def size_from_margin(
    *,
    margin_budget: float,
    price: float,
    leverage: int,
    lot: float,
    min_sz: float,
    contract_value: float | None = None,
    haircut: float = 0.997,
    risk_usd: float = 0.0,
) -> SizePlan | None:
    """Margin budget -> lot-snapped CONTRACT size (BloFin `size` units).

    notional = margin * leverage
    contracts = notional / (price * contract_value)
    """
    price = float(price)
    if price <= 0 or margin_budget <= 0:
        return None
    lev = max(1, int(leverage))
    cv = float(contract_value) if contract_value and float(contract_value) > 0 else 1.0
    usable = max(0.0, float(margin_budget) * float(haircut))
    raw_contracts = (usable * lev) / (price * cv)
    sz = floor_to_lot(raw_contracts, lot, min_sz)
    if sz <= 0:
        return None
    notional = sz * price * cv
    margin = notional / lev
    while sz > 0 and margin > margin_budget + 1e-9:
        sz = floor_to_lot(sz - max(float(lot), 1e-12), lot, min_sz)
        if sz <= 0:
            return None
        notional = sz * price * cv
        margin = notional / lev
    return SizePlan(
        sz=sz,
        margin=margin,
        notional=notional,
        leverage=lev,
        risk_usd=float(risk_usd),
    )


def format_sz(sz: float, lot: float) -> str:
    lot = max(float(lot), 1e-12)
    text = f"{lot:.12f}".rstrip("0")
    decimals = len(text.split(".")[1]) if "." in text else 0
    if decimals <= 0:
        return str(int(sz))
    return f"{sz:.{decimals}f}".rstrip("0").rstrip(".")


def plan_open(
    *,
    equity: float,
    cash: float,
    open_count: int,
    price: float,
    lot: float,
    min_sz: float,
    contract_value: float | None = None,
    margin_already_used: float = 0.0,
    risk: PlaybookRisk | None = None,
) -> SizePlan | None:
    """Size one new open with stop-based risk from playbook params."""
    risk = risk or load_playbook_risk()
    if open_count >= risk.max_positions:
        return None
    risk_usd = risk_budget_usd(equity, open_count, risk)
    margin = margin_from_risk(
        equity=equity,
        cash=cash,
        open_count=open_count,
        margin_already_used=margin_already_used,
        risk=risk,
    )
    if margin <= 0:
        return None
    return size_from_margin(
        margin_budget=margin,
        price=price,
        leverage=risk.leverage,
        lot=lot,
        min_sz=min_sz,
        contract_value=contract_value,
        risk_usd=risk_usd,
    )


def stop_take_prices(entry: float, side: str, risk: PlaybookRisk | None = None) -> tuple[str, str]:
    risk = risk or load_playbook_risk()
    entry = float(entry)
    if entry <= 0:
        return "", ""
    side_l = (side or "buy").lower()
    if side_l == "buy":
        sl = entry * (1.0 - risk.stop_loss_pct)
        tp = entry * (1.0 + risk.take_profit_pct)
    else:
        sl = entry * (1.0 + risk.stop_loss_pct)
        tp = entry * (1.0 - risk.take_profit_pct)
    return f"{sl:.8f}".rstrip("0").rstrip("."), f"{tp:.8f}".rstrip("0").rstrip(".")


def apply_playbook_sizing(
    decisions: list[Any],
    *,
    snapshot: Any,
    cash: float,
    equity: float,
    open_count: int,
    margin_already_used: float = 0.0,
    risk: PlaybookRisk | None = None,
) -> list[Any]:
    """Rewrite open/add sizes to stop-based playbook risk; drop extras past max_positions."""
    from .decision import Decision

    risk = risk or load_playbook_risk()
    out: list[Any] = []
    sim_cash = float(cash)
    sim_equity = float(equity)
    sim_open = int(open_count)
    sim_margin_used = float(margin_already_used)
    for d in decisions:
        action = (getattr(d, "action", "") or "").lower()
        if action not in {"open", "add"}:
            out.append(d)
            continue
        if sim_open >= risk.max_positions:
            logger.info(
                "playbook size: dropping %s %s - book full (%d/%d)",
                action,
                d.instId,
                sim_open,
                risk.max_positions,
            )
            continue
        inst = snapshot.instruments.get(d.instId) if snapshot is not None else None
        ticker = snapshot.tickers.get(d.instId) if snapshot is not None else None
        price = float(getattr(ticker, "last", 0) or 0) if ticker else 0.0
        if price <= 0 and getattr(d, "px", None):
            try:
                price = float(d.px)
            except Exception:
                price = 0.0
        if not inst or price <= 0:
            continue
        plan = plan_open(
            equity=sim_equity,
            cash=sim_cash,
            open_count=sim_open,
            price=price,
            lot=inst.lotSz,
            min_sz=inst.minSz,
            contract_value=getattr(inst, "contract_value", None),
            margin_already_used=sim_margin_used,
            risk=risk,
        )
        if plan is None:
            logger.info("playbook size: skip %s - risk/margin budget empty", d.instId)
            continue
        sl, tp = stop_take_prices(price, getattr(d, "side", "buy"), risk)
        sim_cash -= plan.margin
        sim_margin_used += plan.margin
        sim_open += 1
        note = (
            f" [size risk~${plan.risk_usd:.2f} margin~${plan.margin:.2f} "
            f"lev={risk.leverage}x SL={risk.stop_loss_pct*100:.0f}%]"
        )
        rationale = ((getattr(d, "rationale", None) or "") + note)[:400]
        out.append(
            Decision(
                instId=d.instId,
                action=d.action,
                side=d.side,
                orderType=d.orderType,
                sz=format_sz(plan.sz, inst.lotSz),
                px=d.px,
                leverage=risk.leverage,
                stopLoss=getattr(d, "stopLoss", None) or sl or None,
                takeProfit=getattr(d, "takeProfit", None) or tp or None,
                rationale=rationale,
            )
        )
    return out
