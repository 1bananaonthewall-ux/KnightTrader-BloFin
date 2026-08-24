from __future__ import annotations

from typing import Any

from .config import settings
from .llm_client import AxiomLLM
from .journal import AxiomJournal


BASELINE = """Baseline playbook summary:
- Breakout and ROC momentum on 1H USDT-margined perps.
- Prefer 10x leverage with ~3% stop loss and ~25% take profit.
- Trade high-conviction setups only; if tape does not support thesis, size down or skip.
- Use tight stop placement and avoid oversized notional for low-liquidity symbols.
- Re-evaluate after each trade and let journal evidence override playbook preference.
"""


class AxiomPlaybook:
    def __init__(self, journal: AxiomJournal, llm: AxiomLLM | None = None) -> None:
        self.journal = journal
        self.llm = llm or AxiomLLM()

    def summary(self) -> str:
        cached = self.journal.summary()
        if cached.summary:
            return f"{BASELINE}\nCompressed journal summary:\n{cached.summary}"
        return BASELINE

    def maybe_refresh(self, tick: int) -> None:
        if tick <= 0:
            return
        if tick % settings.journal.summary_refresh_ticks != 0:
            return
        trades = self.journal.trades_since_tick(tick - settings.journal.summary_window_trades - 1)
        if not trades:
            return
        text = "\n".join(
            f"#{t.id} tick={t.tick} {t.instId} {t.side} {t.action} sz={t.sz} px={t.px} lev={t.leverage} pnl={t.pnl_usdt} | {t.rationale}"
            for t in trades
        )
        prompt = f"Summarize these trades into what worked, what failed, and how to improve: \n{text}\n"
        try:
            summary = self.llm.cheap_call(prompt)
        except Exception:
            summary = "Summary compression failed."
        self.journal.set_summary(summary)
