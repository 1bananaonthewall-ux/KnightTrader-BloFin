"""Risk module — INTENTIONALLY EMPTY.

The user explicitly chose to run Hermes with no guardrails. This module is
the off-switch. It is wired into loop.py via a single import; replacing
this file with a real `risk.py` (or renaming and switching the import) is
how future-you adds a kill-switch, position cap, daily loss limit, or
drawdown cap without touching the rest of the code.

To activate real risk controls:
  1. Implement a function `apply(decision, account_state) -> decision`
     in a new `hermes_trader/risk.py`.
  2. In `hermes_trader/loop.py`, change:
         from . import risk_none as risk
     to:
         from . import risk
  3. Set `risk.enabled: true` in config.yaml.

Until then, the bot does whatever the LLM says, including 100x leverage on
micro-cap alts with no stop. You accepted this.
"""
from __future__ import annotations

from typing import Any

from .decision import Decision, CycleDecision


def apply(decision: CycleDecision, account_state: Any) -> CycleDecision:
    """Identity. Returns the decision unchanged. No-op by design."""
    return decision
