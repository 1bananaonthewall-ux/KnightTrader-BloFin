"""Deterministic demo fallback when the LLM returns no usable JSON.

Uses playbook stop-based sizing (NOT all-in cash/slots).
"""
from __future__ import annotations

import logging
from typing import Any

from .decision import CycleDecision, Decision
from .market_data import MarketSnapshot
from .paper_broker import PaperBroker
from .sizing import SizePlan, format_sz, load_playbook_risk, plan_open, stop_take_prices

logger = logging.getLogger(__name__)


def demo_fallback_decisions(
    snapshot: MarketSnapshot,
    paper: PaperBroker | None,
    *,
    max_positions: int | None = None,
    leverage: int | None = None,
) -> CycleDecision:
    risk = load_playbook_risk()
    max_positions = int(max_positions or risk.max_positions)
    leverage = int(leverage or risk.leverage)

    positions = paper.position_snapshots() if paper else snapshot.positions
    open_ids = {p.instId for p in positions}
    open_count = len(open_ids)
    slots = max(0, max_positions - open_count)
    if slots <= 0:
        return CycleDecision(
            thesis="Demo fallback: book full; holding.",
            decisions=[],
            no_trade_reason="max_positions_reached",
        )

    cash = float(paper.state.cash if paper else snapshot.account.available)
    equity = float(paper.equity() if paper else snapshot.account.equity)
    margin_used = float(paper.margin_used() if paper else snapshot.account.margin_used)
    if cash < risk.min_margin_usdt or equity < 1.0:
        return CycleDecision(
            thesis="Demo fallback: insufficient account size to size safely.",
            decisions=[],
            no_trade_reason="insufficient_account_size",
        )

    tickers = list(snapshot.tickers.values())
    tickers.sort(key=lambda t: t.vol_24h_quote, reverse=True)
    picks: list[Any] = []
    max_picks = min(slots, 2)
    logger.info("FALLBACK_DIAG top_tickers=%s", [t.instId for t in tickers[:5]])
    for t in tickers:
        if t.instId in open_ids:
            continue
        if t.last <= 0 or t.change_24h_pct < 1.0:
            continue
        inst = snapshot.instruments.get(t.instId)
        if not inst or inst.state != "live":
            continue
        lot = float(inst.lotSz or 0)
        min_sz = float(inst.minSz or 0)
        cv = getattr(inst, "contract_value", None)
        if lot <= 0 or min_sz <= 0 or not cv or float(cv) <= 0:
            continue
        picks.append(t)
        if len(picks) >= max_picks:
            break

    if not picks:
        return CycleDecision(
            thesis="Demo fallback: no liquid momentum candidates above threshold.",
            decisions=[],
            no_trade_reason="no_momentum_candidates",
        )

    live_leverage = leverage
    if equity < 20.0:
        live_leverage = min(live_leverage, 5)
    if equity < 12.0:
        live_leverage = min(live_leverage, 3)
    if equity < 7.0:
        live_leverage = min(live_leverage, 2)
    if live_leverage < 1:
        live_leverage = 1

    # Never increase exposure when the book already has any live positions for
    # small accounts. Without `reduce_only` support, opening more can trap margin
    # and block closes on Blofin.
    max_new_positions = 0 if open_count > 0 else max(1, slots)
    decisions: list[Decision] = []
    sim_cash = cash
    sim_open = open_count
    sim_margin = margin_used
    for t in picks[:max_new_positions]:
        inst = snapshot.instruments[t.instId]
        plan = plan_open(
            equity=equity,
            cash=sim_cash,
            open_count=sim_open,
            price=t.last,
            lot=inst.lotSz,
            min_sz=inst.minSz,
            contract_value=getattr(inst, "contract_value", None),
            margin_already_used=sim_margin,
            risk=risk,
        )
        if plan is None or plan.sz <= 0:
            min_sz = float(inst.minSz or 0)
            if min_sz > 0:
                min_margin = min_sz * t.last / live_leverage
                if min_margin <= sim_cash * 0.99 and min_margin <= sim_cash:
                    plan = SizePlan(sz=min_sz, margin=min_margin, notional=min_sz * t.last, leverage=live_leverage, risk_usd=0.0)
            if plan is None or plan.sz <= 0:
                continue
        if plan.margin > sim_cash * 0.99:
            continue
        sl, tp = stop_take_prices(t.last, "buy", risk)
        sim_cash -= plan.margin
        sim_margin += plan.margin
        sim_open += 1
        decisions.append(
            Decision(
                instId=t.instId,
                action="open",
                side="buy",
                orderType="market",
                sz=format_sz(plan.sz, inst.lotSz),
                px=None,
                leverage=live_leverage,
                stopLoss=sl or None,
                takeProfit=tp or None,
                rationale=(
                    f"[PLAYBOOK RISK] risk~${plan.risk_usd:.2f} margin~${plan.margin:.2f} "
                    f"lev={live_leverage}x SL={risk.stop_loss_pct*100:.0f}% "
                    f"24h={t.change_24h_pct:+.2f}%"
                ),
            )
        )

    if not decisions:
        return CycleDecision(
            thesis="Demo fallback: risk budget empty or lots too large.",
            decisions=[],
            no_trade_reason="size_below_lot",
        )

    return CycleDecision(
        thesis=(
            f"Playbook risk-sized fallback: {len(decisions)} open(s), "
            f"1% equity risk/trade, max_pos={max_positions}, lev={live_leverage}x."
        ),
        decisions=decisions,
        no_trade_reason="",
    )
