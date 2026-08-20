"""LLM-output → typed Decision parser with validation.

The LLM is told to return a single JSON object. We:
1. Try to extract the JSON (handle ```json fences and surrounding prose).
2. Parse into a Pydantic model.
3. Validate each decision against the known instrument universe.
4. If anything is off, return an empty CycleDecision with a no_trade_reason
   so the loop skips this tick. We do NOT place orders from unvalidated
   output. This is the one piece of "safety" in the system — but it's
   safety against crashes and obviously-wrong inputs (unknown ticker, lot
   size that doesn't divide), not safety against bad strategy choices.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from .market_data import Instrument, MarketSnapshot

logger = logging.getLogger(__name__)


class Decision(BaseModel):
    instId: str
    action: str                    # "open" | "add" | "reduce" | "close" | "cancel_and_replace"
    side: str                      # "buy" | "sell"
    orderType: str                 # "market" | "limit"
    sz: str
    px: str | None = None
    leverage: int | None = None
    stopLoss: str | None = None
    takeProfit: str | None = None
    rationale: str | None = None

    @field_validator("action")
    @classmethod
    def _v_action(cls, v: str) -> str:
        allowed = {"open", "add", "reduce", "close", "cancel_and_replace"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}, got {v!r}")
        return v

    @field_validator("side")
    @classmethod
    def _v_side(cls, v: str) -> str:
        if v not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got {v!r}")
        return v

    @field_validator("orderType")
    @classmethod
    def _v_orderType(cls, v: str) -> str:
        if v not in ("market", "limit"):
            raise ValueError(f"orderType must be 'market' or 'limit', got {v!r}")
        return v

    @field_validator("leverage")
    @classmethod
    def _v_lev(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if not (1 <= v <= 100):
            raise ValueError(f"leverage must be 1..100, got {v}")
        return v

    @field_validator("sz")
    @classmethod
    def _v_sz(cls, v: str) -> str:
        try:
            f = float(v)
        except ValueError as e:
            raise ValueError(f"sz must be numeric, got {v!r}") from e
        if f <= 0:
            raise ValueError(f"sz must be > 0, got {f}")
        return v


class CycleDecision(BaseModel):
    thesis: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    no_trade_reason: str = ""

    @field_validator("no_trade_reason", mode="before")
    @classmethod
    def _coerce_no_trade_reason(cls, v: object) -> str:
        return "" if v is None else str(v)

    @classmethod
    def empty(cls, reason: str) -> "CycleDecision":
        return cls(decisions=[], no_trade_reason=reason)

    @field_validator("decisions")
    @classmethod
    def _cap_decisions(cls, v: list[Decision]) -> list[Decision]:
        # The system prompt says max 5. We truncate rather than raise so a
        # 6-item response from a hot LLM doesn't crash the bot.
        return v[:5]


# --- Extraction & parsing -------------------------------------------------- #


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_BARE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str | None:
    """Pull a JSON object out of an LLM response, even if it has prose around
    it or a code fence. Returns the candidate string, or None if nothing
    plausible was found.
    """
    m = _JSON_FENCE.search(text)
    if m:
        return m.group(1)
    # Try the largest balanced-looking {...} region
    candidates = _JSON_BARE.findall(text)
    if not candidates:
        return None
    # Prefer the longest candidate (most likely to be the real payload).
    return max(candidates, key=len)


def _round_sz_to_lot(sz: str, inst: Instrument) -> str:
    """Snap sz down to the nearest lot increment, never up."""
    try:
        x = float(sz)
    except ValueError:
        return sz
    if inst.lotSz <= 0:
        return sz
    lots = int(x / inst.lotSz)
    snapped = lots * inst.lotSz
    if snapped < inst.minSz:
        snapped = 0.0
    # Blofin wants sz as a string with no trailing zeros.
    if snapped == 0:
        return "0"
    return ("%." + str(_decimal_places(inst.lotSz)) + "f") % snapped


def _decimal_places(lot: float) -> int:
    s = f"{lot:.10f}".rstrip("0")
    if "." in s:
        return len(s.split(".")[1])
    return 0


def parse(raw_output: str, snapshot: MarketSnapshot) -> CycleDecision:
    """Parse LLM output against the live snapshot. Returns an empty decision
    (with a no_trade_reason explaining what went wrong) if anything fails.
    Never raises — the loop should always be able to proceed to the next tick.
    """
    if not raw_output or not raw_output.strip():
        return CycleDecision.empty("llm_returned_empty")

    js = _extract_json(raw_output)
    if js is None:
        return CycleDecision.empty("llm_output_no_json_found")

    try:
        data = json.loads(js)
    except json.JSONDecodeError as e:
        return CycleDecision.empty(f"llm_output_invalid_json: {e.msg}")

    if not isinstance(data, dict):
        return CycleDecision.empty("llm_output_not_object")

    # Coerce: if LLM returned `decisions` as a string or missing, recover gracefully.
    raw_decisions = data.get("decisions", [])
    if isinstance(raw_decisions, str):
        try:
            raw_decisions = json.loads(raw_decisions)
        except json.JSONDecodeError:
            raw_decisions = []

    valid: list[Decision] = []
    rejected: list[str] = []
    for idx, d in enumerate(raw_decisions):
        if not isinstance(d, dict):
            rejected.append(f"#{idx}: not an object")
            continue
        try:
            inst_id = str(d.get("instId", "")).strip()
            if not inst_id:
                rejected.append(f"#{idx}: missing instId")
                continue
            inst = snapshot.instruments.get(inst_id)
            if inst is None:
                rejected.append(f"#{idx}: unknown instId {inst_id!r}")
                continue
            if inst.state != "live":
                rejected.append(f"#{idx}: {inst_id} not live (state={inst.state})")
                continue

            sz_in = str(d.get("sz", "0"))
            sz_out = _round_sz_to_lot(sz_in, inst)
            if float(sz_out) <= 0:
                rejected.append(f"#{idx}: sz {sz_in} < minSz {inst.minSz}")
                continue

            cleaned = {
                "instId": inst_id,
                "action": d.get("action", "open"),
                "side": d.get("side", "buy"),
                "orderType": d.get("orderType", "market"),
                "sz": sz_out,
                "px": str(d["px"]) if d.get("px") is not None else None,
                "leverage": d.get("leverage"),
                "stopLoss": str(d["stopLoss"]) if d.get("stopLoss") is not None else None,
                "takeProfit": str(d["takeProfit"]) if d.get("takeProfit") is not None else None,
                "rationale": d.get("rationale"),
            }
            decision = Decision.model_validate(cleaned)
            if decision.orderType == "limit" and not decision.px:
                rejected.append(f"#{idx}: limit order missing px")
                continue
            valid.append(decision)
        except (ValidationError, ValueError) as e:
            rejected.append(f"#{idx}: {e}")
            continue

    if not valid and rejected:
        return CycleDecision.empty("all_decisions_rejected: " + "; ".join(rejected[:3]))

    return CycleDecision(
        thesis=str(data.get("thesis", "")).strip(),
        decisions=valid,
        no_trade_reason=(
            str(data.get("no_trade_reason", "")).strip()
            if not valid else ""
        ),
    )
