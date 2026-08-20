import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hermes_trader.config import AppConfig, JournalConfig, LLMConfig, LoggingConfig, LoopConfig
from hermes_trader.loop import HermesLoop


def _config(tmp_path: Path, *, summary_every: int = 60) -> AppConfig:
    return AppConfig(
        exchange="blofin",
        mode="isolated",
        universe="all_usdt_perps",
        loop=LoopConfig(interval_seconds=60, jitter_seconds=5),
        llm=LLMConfig(timeout_seconds=45),
        journal=JournalConfig(
            db_path=str(tmp_path / "journal.sqlite"),
            summary_refresh_every_ticks=summary_every,
            verbatim_window=30,
        ),
        logging=LoggingConfig(level="INFO", file=str(tmp_path / "hermes.log")),
    )


def _loop(tmp_path: Path, *, summary_every: int = 60):
    config = _config(tmp_path, summary_every=summary_every)
    secrets = SimpleNamespace(blofin_api_key="k", blofin_api_secret="s", nous_portal_key="p")
    loop = HermesLoop(secrets, config)
    loop.blofin = MagicMock()
    loop.journal = MagicMock()
    loop.journal.pnl_today.return_value = 0.0
    loop.instruments = {"BTC-USDT": MagicMock()}
    return loop


def test_prompt_build_crash_logs_and_skips_tick(tmp_path, caplog: pytest.LogCaptureFixture):
    loop = _loop(tmp_path)
    loop.llm = MagicMock()
    loop.journal.get_verbatim.side_effect = RuntimeError("prompt builder blew up")

    caplog.set_level(logging.ERROR)
    loop.run_one_tick()

    assert any("prompt build crashed" in record.getMessage() for record in caplog.records if record.levelname == "ERROR")
    loop.llm.decide.assert_not_called()
