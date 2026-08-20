"""Deterministic demo fallback when the LLM returns no usable JSON.

Uses playbook stop-based sizing (NOT all-in cash/slots).
"""
from __future__ import annotations

import logging
from typing import Any

from .decision import CycleDecision, Decision
from .market_data import MarketSnapshot
from .paper_broker import PaperBroker
from .sizing import format_sz, load_playbook_risk, plan_open, stop_take_prices

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
    if cash < risk.min_margin_usdt:
        return CycleDecision(
            thesis="Demo fallback: insufficient cash.",
            decisions=[],
            no_trade_reason="insufficient_cash",
        )

    ranked = sorted(
        snapshot.tickers.values(),
        key=lambda t: (t.change_24h_pct, t.vol_24h_quote),
        reverse=True,
    )
    picks: list[Any] = []
    for t in ranked:
        if t.instId in open_ids:
            continue
        if t.last <= 0 or t.change_24h_pct < 1.0:
            continue
        inst = snapshot.instruments.get(t.instId)
        if not inst or inst.state != "live":
            continue
        picks.append(t)
        if len(picks) >= slots:
            break

    if not picks:
        return CycleDecision(
            thesis="Demo fallback: no momentum candidates above threshold.",
            decisions=[],
            no_trade_reason="no_momentum_candidates",
        )

    decisions: list[Decision] = []
    sim_cash = cash
    sim_open = open_count
    sim_margin = margin_used
    for t in picks:
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
        if plan is None:
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
                leverage=leverage,
                stopLoss=sl or None,
                takeProfit=tp or None,
                rationale=(
                    f"[PLAYBOOK RISK] risk~${plan.risk_usd:.2f} margin~${plan.margin:.2f} "
                    f"lev={leverage}x SL={risk.stop_loss_pct*100:.0f}% "
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
            f"1% equity risk/trade, max_pos={max_positions}, lev={leverage}x."
        ),
        decisions=decisions,
        no_trade_reason="",
    )
