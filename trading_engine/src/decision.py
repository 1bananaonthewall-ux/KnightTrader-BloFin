from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class Decision(BaseModel):
    instId: str = Field(min_length=1)
    action: str = Field(pattern="^(open|add|reduce|close|cancel_and_replace)$")
    side: str = Field(pattern="^(buy|sell)$")
    orderType: str = Field(pattern="^(market|limit)$")
    sz: str = Field(min_length=1)
    px: str | None = None
    leverage: int = Field(ge=1, le=100)
    stopLoss: str | None = None
    takeProfit: str | None = None
    rationale: str = Field(min_length=1)


class CycleDecision(BaseModel):
    thesis: str = ""
    decisions: list[Decision] = Field(default_factory=list, max_length=5)
    no_trade_reason: str = ""

    @classmethod
    def empty(cls, reason: str) -> CycleDecision:
        return cls(thesis="", decisions=[], no_trade_reason=reason)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    match = _JSON_OBJECT_RE.search(text)
    return match.group(0) if match else text


def parse_decision(text: str, valid_universe: set[str]) -> CycleDecision:
    cleaned = _extract_json(text or "").strip()
    if not cleaned:
        return CycleDecision.empty("parse_failed")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return CycleDecision.empty("parse_failed")
    if not isinstance(data, dict):
        return CycleDecision.empty("parse_failed")
    try:
        cd = CycleDecision(**data)
    except ValidationError:
        return CycleDecision.empty("parse_failed")
    normalized: list[Decision] = []
    for d in cd.decisions:
        if d.instId not in valid_universe:
            continue
        if d.orderType == "limit" and not d.px:
            continue
        if d.orderType == "market" and d.px:
            d = d.model_copy(update={"px": None})
        normalized.append(d)
    return cd.model_copy(update={"decisions": normalized[:5]})
