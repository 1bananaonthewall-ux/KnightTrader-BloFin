"""Order execution: turns validated Decisions into Blofin orders (live) or
paper fills (demo), then records them into the journal.
"""
from __future__ import annotations

import logging

from .blofin_client import BlofinAPIError, BlofinClient
from .decision import Decision
from .journal import Journal
from .paper_broker import PaperBroker

logger = logging.getLogger(__name__)


def _cl_ord_id(tick: int, inst_id: str, seq: int) -> str:
    # clOrdId max length is typically 32 chars; keep it short.
    safe_iid = inst_id.replace("-", "")
    return f"emirald_{tick}_{safe_iid}_{seq}"[:32]


def execute_decisions(
    decisions: list[Decision],
    *,
    tick: int,
    client: BlofinClient | PaperBroker,
    journal: Journal,
    td_mode: str,
    decision_raw: str | None = None,
    demo: bool = False,
) -> list[dict]:
    """Place each decision sequentially. Returns a list of per-decision
    outcome dicts: {"instId", "clOrdId", "status": "filled"|"rejected"|"error",
    "message": ...}.
    """
    outcomes: list[dict] = []
    for seq, d in enumerate(decisions):
        clid = _cl_ord_id(tick, d.instId, seq)
        outcome: dict = {
            "instId": d.instId,
            "clOrdId": clid,
            "status": "pending",
            "message": "",
        }
        try:
            if demo or isinstance(client, PaperBroker):
                resp = client.place_order(
                    inst_id=d.instId,
                    side=d.side,
                    sz=d.sz,
                    ord_type=d.orderType,
                    td_mode=td_mode,
                    px=d.px,
                    cl_ord_id=clid,
                    leverage=d.leverage,
                    stop_loss=d.stopLoss,
                    take_profit=d.takeProfit,
                    action=d.action,
                )
            else:
                body = {
                "instId": d.instId,
                "marginMode": td_mode,
                "side": d.side,
                "orderType": d.orderType,
                "size": str(d.sz),
            }
            if getattr(client, "position_mode", "net") == "hedge":
                action_l = (getattr(d, "action", "") or "").lower()
                if action_l in {"close", "reduce", "cancel_and_replace"}:
                    body["positionSide"] = "short" if d.side == "buy" else "long"
                else:
                    body["positionSide"] = "long" if d.side == "buy" else "short"
            if getattr(client, "broker_id", ""):
                body["brokerId"] = client.broker_id
            if d.stopLoss:
                body["slTriggerPrice"] = str(d.stopLoss)
                body["slOrderPrice"] = "-1"
                body["slTriggerPriceType"] = "last"
            if d.takeProfit:
                body["tpTriggerPrice"] = str(d.takeProfit)
                body["tpOrderPrice"] = "-1"
                body["tpTriggerPriceType"] = "last"
            logger.info("live order body: %s", body)
            resp = client.place_order(
                    inst_id=d.instId,
                    side=d.side,
                    sz=d.sz,
                    ord_type=d.orderType,
                    td_mode=td_mode,
                    px=d.px,
                    cl_ord_id=clid,
                    stop_loss=d.stopLoss,
                    take_profit=d.takeProfit,
                    position_side=body.get("positionSide") if getattr(client, "position_mode", "net") == "hedge" else None,
                )
            ord_id = (resp or {}).get("ordId") if isinstance(resp, dict) else None

            fill_px: str | None = None
            if isinstance(resp, dict) and resp.get("avgPx"):
                fill_px = str(resp.get("avgPx"))
            elif ord_id and not demo and not isinstance(client, PaperBroker):
                try:
                    detail = client.get_order(d.instId, ord_id=ord_id)
                    fill_px = str(detail.get("avgPx") or detail.get("px") or "")
                except BlofinAPIError as e:
                    logger.debug("order detail fetch failed (non-fatal): %s", e)

            trade = journal.add_trade(
                tick=tick,
                inst_id=d.instId,
                side=d.side,
                action=d.action,
                sz=d.sz,
                px=fill_px or (d.px if d.orderType == "limit" else None),
                leverage=d.leverage,
                rationale=(("[DEMO] " if demo else "") + (d.rationale or ""))[:500],
                decision_raw=decision_raw,
            )
            outcome.update({
                "status": "submitted",
                "ordId": ord_id,
                "trade_id": trade.id,
                "demo": bool(demo),
            })
            logger.info(
                "%ssubmitted %s %s %s sz=%s px=%s lev=%s clOrdId=%s ordId=%s",
                "demo " if demo else "",
                d.action, d.side, d.instId, d.sz, fill_px or d.px, d.leverage, clid, ord_id,
            )
        except BlofinAPIError as e:
            outcome.update({"status": "rejected", "message": f"{e.code} {e.message}"})
            journal.add_trade(
                tick=tick,
                inst_id=d.instId,
                side=d.side,
                action=d.action,
                sz=d.sz,
                px=None,
                leverage=d.leverage,
                rationale=(d.rationale or "") + f" [REJECTED: {e.code} {e.message}]",
                decision_raw=decision_raw,
            )
            logger.warning("rejected %s %s: %s", d.instId, d.action, e)
        except Exception as e:  # noqa: BLE001
            outcome.update({"status": "rejected", "message": str(e)})
            journal.add_trade(
                tick=tick,
                inst_id=d.instId,
                side=d.side,
                action=d.action,
                sz=d.sz,
                px=None,
                leverage=d.leverage,
                rationale=(d.rationale or "") + f" [REJECTED: {e}]",
                decision_raw=decision_raw,
            )
            logger.warning("paper/live order failed %s %s: %s", d.instId, d.action, e)
        outcomes.append(outcome)
    return outcomes
