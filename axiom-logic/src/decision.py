from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import settings

VALID_ACTIONS = {"open", "add", "reduce", "close", "cancel_and_replace"}
VALID_SIDES = {"buy", "sell"}
VALID_ORDER_TYPES = {"market", "limit"}


class Decision(BaseModel):
    instId: str = ""
    action: str = "open"
    side: str = "buy"
    orderType: str = "market"
    sz: str = "0"
    px: str = ""
    leverage: int = Field(default=settings.risk.leverage, ge=1, le=100)
    stopLoss: str = ""
    takeProfit: str = ""
    rationale: str = ""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        v = (v or "").lower().strip()
        if v not in VALID_ACTIONS:
            raise ValueError("invalid action")
        return v

    @field_validator("side")
    @classmethod
    def valid_side(cls, v: str) -> str:
        v = (v or "").lower().strip()
        if v not in VALID_SIDES:
            raise ValueError("invalid side")
        return v

    @field_validator("orderType")
    @classmethod
    def valid_order_type(cls, v: str) -> str:
        v = (v or "").lower().strip()
        if v not in VALID_ORDER_TYPES:
            raise ValueError("invalid orderType")
        return v

    @model_validator(mode="after")
    def limit_requires_px(self) -> "Decision":
        if self.orderType == "limit" and not self.px:
            raise ValueError("limit requires px")
        if self.orderType == "market" and self.px:
            raise ValueError("market must not include px")
        return self


class CycleDecision(BaseModel):
    thesis: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    no_trade_reason: str = ""

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def empty(cls, reason: str = "empty") -> "CycleDecision":
        return cls(thesis="", decisions=[], no_trade_reason=reason)

    @property
    def is_empty(self) -> bool:
        return not bool(self.decisions)


def _extract_json_candidate(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def parse_decision(raw_text: str) -> CycleDecision:
    candidate = _extract_json_candidate(raw_text or "")
    if not candidate:
        return CycleDecision.empty("no_json_candidate")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return CycleDecision.empty("invalid_json")
    if not isinstance(data, dict):
        return CycleDecision.empty("invalid_structure")
    thesis = str(data.get("thesis", ""))
    decisions_raw = data.get("decisions", [])
    if not isinstance(decisions_raw, list):
        return CycleDecision.empty("decisions_not_list")
    decisions: list[Decision] = []
    for idx, item in enumerate(decisions_raw):
        if not isinstance(item, dict):
            continue
        try:
            decisions.append(Decision(**item))
        except Exception:
            continue
    no_trade_reason = str(data.get("no_trade_reason", ""))
    return CycleDecision(thesis=thesis, decisions=decisions[:5], no_trade_reason=no_trade_reason)
