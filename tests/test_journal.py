import time

import pytest

from hermes_trader.journal import Journal


def test_add_open_trade_sets_open_pnl(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    trade = journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.01",
        px="50000.0",
        leverage=5,
        rationale="open long",
        decision_raw="raw1",
    )
    assert trade.pnl_usdt is None
    assert journal.total_trades() == 1
    rows = journal.get_verbatim(1)
    assert rows[0].action == "open"
    assert rows[0].pnl_usdt is None


def test_close_computes_fifo_pnl(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.02",
        px="50000.0",
        leverage=5,
        rationale="open",
        decision_raw="raw1",
    )
    trade = journal.add_trade(
        tick=2,
        inst_id="BTC-USDT",
        side="sell",
        action="close",
        sz="0.01",
        px="51000.0",
        leverage=5,
        rationale="close half",
        decision_raw="raw2",
    )
    assert trade.pnl_usdt == pytest.approx(10.0)


def test_reduce_partially_closes_and_leaves_remainder(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.02",
        px="50000.0",
        leverage=5,
        rationale="",
        decision_raw="raw",
    )
    trade = journal.add_trade(
        tick=2,
        inst_id="BTC-USDT",
        side="sell",
        action="reduce",
        sz="0.015",
        px="52000.0",
        leverage=5,
        rationale="",
        decision_raw="raw",
    )
    assert trade.pnl_usdt == pytest.approx(30.0)
    remaining = journal._connect().execute(
        "SELECT sz FROM open_lots WHERE instId='BTC-USDT' AND side='buy'"
    ).fetchone()["sz"]
    assert remaining == pytest.approx(0.005)


def test_update_fill_backfills_market_fill(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    trade = journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.01",
        px=None,
        leverage=2,
        rationale="mkt",
        decision_raw="raw",
    )
    journal.update_fill(trade.id, "50250.0", "0.01", None)
    filled = journal.get_verbatim(1)[0]
    assert filled.px == "50250.0"
    assert filled.sz == "0.01"


def test_verbatim_returns_oldest_first(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    for tick in range(4):
        journal.add_trade(
            tick=tick + 1,
            inst_id="BTC-USDT",
            side="buy",
            action="open",
            sz="0.01",
            px="1000.0",
            leverage=2,
            rationale=f"t{tick}",
            decision_raw=f"raw{tick}",
        )
    rows = [row.tick for row in journal.get_verbatim(3)]
    assert rows == [2, 3, 4]


def test_no_trade_heartbeat_is_included_in_total_and_verbatim(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    for tick in range(3):
        journal.add_trade(
            tick=tick + 1,
            inst_id="BTC-USDT",
            side="buy",
            action="open",
            sz="0.01",
            px="1000.0",
            leverage=2,
            rationale="",
            decision_raw="",
        )
    journal.add_trade(
        tick=4,
        inst_id="(no_trade)",
        side="hold",
        action="hold",
        sz="0",
        px=None,
        leverage=None,
        rationale="",
        decision_raw="",
    )
    assert journal.total_trades() == 4
    last = [row.instId for row in journal.get_verbatim(10)]
    assert last[-1] == "(no_trade)"


def test_pnl_today_counts_from_utc_midnight_and_ignores_unrealized(tmp_path, monkeypatch: pytest.MonkeyPatch):
    journal = Journal(tmp_path / "journal.sqlite")
    fixed_now = 1_725_000_000 + 18 * 3600

    class FakeTime:
        @staticmethod
        def time():
            return fixed_now

    monkeypatch.setattr("hermes_trader.journal.time", FakeTime)
    journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.01",
        px="30000.0",
        leverage=2,
        rationale="open",
        decision_raw="raw",
    )
    assert journal.pnl_today() == 0.0


def test_open_lots_are_isolated_by_instrument_and_side(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    journal.add_trade(
        tick=1,
        inst_id="BTC-USDT",
        side="buy",
        action="open",
        sz="0.01",
        px="30000.0",
        leverage=2,
        rationale="",
        decision_raw="",
    )
    journal.add_trade(
        tick=2,
        inst_id="ETH-USDT",
        side="sell",
        action="reduce",
        sz="1.0",
        px="2000.0",
        leverage=2,
        rationale="",
        decision_raw="",
    )

    rows = journal._connect().execute(
        "SELECT instId, side, sz FROM open_lots WHERE instId IN ('BTC-USDT', 'ETH-USDT') ORDER BY instId, side"
    ).fetchall()
    assert {tuple(row) for row in rows} == {("BTC-USDT", "buy", 0.01), ("ETH-USDT", "sell", 1.0)}
