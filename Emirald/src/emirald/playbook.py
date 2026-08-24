"""Load the offline backtest winner into Emirald's live prompt / journal memory.

Emirald is still an LLM agent — this does not force signal execution. It makes
the strongest known historical setup available inside the LLM context.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config import load_all
from .journal import Journal, SummaryCache

logger = logging.getLogger(__name__)


def _backtest_path() -> Path:
    return Path("data/backtest_best.json")


def load_backtest_best() -> dict[str, Any]:
    path = _backtest_path()
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def format_playbook() -> str:
    data = load_backtest_best()
    if not data:
        return ""
    mix = data.get("mix") or data.get("mix_name") or ""
    best = data.get("best") or {}
    return f"Optimized playbook: mix={mix} best={best}"


def seed_journal_playbook(journal: Journal) -> bool:
    data = load_backtest_best()
    if not data:
        return False
    summary = format_playbook()
    cache = SummaryCache(generated_at=int(__import__("time").time()), summary=summary)
    try:
        journal.upsert_summary(cache)
        return True
    except Exception:
        return False


def merge_summary_with_playbook(summary: str | None) -> str:
    base = format_playbook()
    extra = (summary or "").strip()
    if not base:
        return extra
    if not extra:
        return base
    return base + "\n\n" + extra
