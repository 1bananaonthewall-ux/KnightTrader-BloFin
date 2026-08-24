"""Emirald risk_none module.

The user explicitly chose to run Emirald with no guardrails. This module is
an identity function so execution still works. To add real guardrails later:
1. implement `emirald/risk.py`
2. In `emirald/loop.py`, change the import.
"""

from __future__ import annotations

from typing import Any

from .decision import CycleDecision


def apply(decisions: list[CycleDecision], snapshot: Any = None, **kwargs: Any) -> list[CycleDecision]:
    return decisions
