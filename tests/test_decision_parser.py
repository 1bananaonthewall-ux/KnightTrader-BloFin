"""Parser tests: canned LLM outputs into a fake MarketSnapshot."""
from __future__ import annotations

from hermes_trader.decision import parse
from hermes_trader.market_data import (
    AccountSnapshot,
    Instrument,
    MarketSnapshot,
)


def _snap() -> MarketSnapshot:
    insts = {
        "BTC-USDT": Instrument(instId="BTC-USDT", tickSz=0.1, lotSz=0.001, minSz=0.001),
        "ETH-USDT": Instrument(instId="ETH-USDT", tickSz=0.01, lotSz=0.01, minSz=0.01),
    }
    return MarketSnapshot(
        account=AccountSnapshot(equity=1000.0, available=900.0, margin_used=100.0, unrealized_pnl=0.0),
        positions=[],
        open_orders=[],
        instruments=insts,
        tickers={},
        candles={},
        top_n=2,
    )


def test_valid_open_market() -> None:
    raw = '{"thesis":"trend up","decisions":[{"instId":"BTC-USDT","action":"open","side":"buy","orderType":"market","sz":"0.012","leverage":3,"rationale":"trend"}]}'
    d = parse(raw, _snap())
    assert d.decisions
    assert d.decisions[0].instId == "BTC-USDT"
    # sz snapped down to lotSz 0.001
    assert d.decisions[0].sz == "0.012"


def test_sz_snapped_to_lot() -> None:
    raw = '{"decisions":[{"instId":"BTC-USDT","action":"open","side":"buy","orderType":"market","sz":"0.0123","leverage":1}]}'
    d = parse(raw, _snap())
    # 0.0123 / 0.001 = 12 lots -> 0.012
    assert d.decisions[0].sz == "0.012"


def test_unknown_instId_rejected() -> None:
    raw = '{"decisions":[{"instId":"DOGE-USDT","action":"open","side":"buy","orderType":"market","sz":"1"}]}'
    d = parse(raw, _snap())
    assert d.decisions == []
    assert "unknown instId" in d.no_trade_reason


def test_leverage_out_of_range() -> None:
    raw = '{"decisions":[{"instId":"BTC-USDT","action":"open","side":"buy","orderType":"market","sz":"0.01","leverage":250}]}'
    d = parse(raw, _snap())
    assert d.decisions == []
    assert "rejected" in d.no_trade_reason


def test_limit_order_missing_px() -> None:
    raw = '{"decisions":[{"instId":"BTC-USDT","action":"open","side":"buy","orderType":"limit","sz":"0.01","leverage":1}]}'
    d = parse(raw, _snap())
    assert d.decisions == []


def test_fenced_json_extraction() -> None:
    raw = 'Here is my decision:\n```json\n{"decisions":[],"no_trade_reason":"choppy"}\n```'
    d = parse(raw, _snap())
    assert d.decisions == []
    assert d.no_trade_reason == "choppy"


def test_prose_around_json() -> None:
    raw = 'I think we should hold. {"decisions":[],"no_trade_reason":"flat"} That is all.'
    d = parse(raw, _snap())
    assert d.no_trade_reason == "flat"


def test_more_than_5_decisions_truncated_by_schema() -> None:
    decisions = [
        {"instId": "BTC-USDT", "action": "open", "side": "buy", "orderType": "market", "sz": "0.001", "leverage": 1}
        for _ in range(10)
    ]
    raw = '{"decisions":' + str(decisions).replace("'", '"') + '}'
    d = parse(raw, _snap())
    # Pydantic enforces max_length=5 on the list.
    assert len(d.decisions) <= 5


def test_invalid_json_returns_empty() -> None:
    d = parse("not json at all", _snap())
    assert d.decisions == []
    assert "invalid" in d.no_trade_reason or "no_json" in d.no_trade_reason
