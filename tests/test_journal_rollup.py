"""Journal tests: FIFO P&L matching, verbatim window, summary cache."""
from __future__ import annotations

import tempfile
from pathlib import Path

from hermes_trader.journal import Journal


def _tmp_journal() -> Journal:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    return Journal(Path(tmp.name))


def test_add_trade_opens_lot_with_no_pnl() -> None:
    j = _tmp_journal()
    t = j.add_trade(
        tick=1, inst_id="BTC-USDT", side="buy", action="open",
        sz="0.01", px="60000", leverage=2, rationale="entry", decision_raw=None,
    )
    assert t.pnl_usdt is None
    trades = j.get_verbatim(10)
    assert len(trades) == 1
    assert trades[0].instId == "BTC-USDT"


def test_close_realizes_long_pnl() -> None:
    j = _tmp_journal()
    j.add_trade(tick=1, inst_id="BTC-USDT", side="buy", action="open",
                sz="0.01", px="60000", leverage=1, rationale="entry", decision_raw=None)
    # Close 0.01 at 61000 -> +0.01 * 1000 = +10 USDT
    close = j.add_trade(tick=2, inst_id="BTC-USDT", side="sell", action="close",
                        sz="0.01", px="61000", leverage=1, rationale="exit", decision_raw=None)
    assert close.pnl_usdt == pytest.approx(10.0, rel=1e-6)


def test_close_realizes_short_pnl() -> None:
    j = _tmp_journal()
    j.add_trade(tick=1, inst_id="BTC-USDT", side="sell", action="open",
                sz="0.01", px="60000", leverage=1, rationale="short", decision_raw=None)
    # Cover at 59000 -> +0.01 * 1000 = +10 USDT
    close = j.add_trade(tick=2, inst_id="BTC-USDT", side="buy", action="close",
                        sz="0.01", px="59000", leverage=1, rationale="cover", decision_raw=None)
    assert close.pnl_usdt == pytest.approx(10.0, rel=1e-6)


def test_verbatim_window_chronological() -> None:
    j = _tmp_journal()
    for i in range(5):
        j.add_trade(tick=i, inst_id="BTC-USDT", side="hold", action="hold",
                    sz="0", px=None, leverage=None, rationale=f"t{i}", decision_raw=None)
    last3 = j.get_verbatim(3)
    assert [t.tick for t in last3] == [2, 3, 4]


def test_summary_cache_roundtrip() -> None:
    j = _tmp_journal()
    assert j.get_summary() == ""
    j.set_summary("worked: small caps. failed: 50x leverage on sunday.")
    assert "small caps" in j.get_summary()
    j.set_summary("v2: even smaller caps.")
    assert "v2" in j.get_summary()


def test_should_refresh_summary_tick() -> None:
    assert Journal.should_refresh_summary_tick(0, 60) is False
    assert Journal.should_refresh_summary_tick(60, 60) is True
    assert Journal.should_refresh_summary_tick(120, 60) is True
    assert Journal.should_refresh_summary_tick(61, 60) is False


# We import pytest only inside the test that needs the approx matcher, so the
# file is importable without pytest installed (matters for the runtime app).
import pytest  # noqa: E402
