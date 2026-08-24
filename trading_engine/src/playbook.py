from __future__ import annotations

from typing import Any

BASELINE_PLAYBOOK = """Baseline optimized playbook summary:
- Regime: breakout + ROC momentum on 1H bars.
- Bias: long and short both allowed; prefer longs in positive funding, shorts in negative funding.
- Risk: 10x leverage, ~3% stop, ~25% target.
- Execution: market orders on high-conviction breakouts; limit orders only when retest confirmed.
- Filters: prefer top-20 by 24h quote volume; ignore illiquid symbols with wide spreads.
- Journal-backed adjustments: reduce size after two consecutive realized losses; close after hit TP/SL within 10 candles."""


def build_playbook_prompt(existing_summary: str | None) -> str:
    if existing_summary:
        return f"{BASELINE_PLAYBOOK}\n\nYour compressed journal memory:\n{existing_summary}"
    return BASELINE_PLAYBOOK
