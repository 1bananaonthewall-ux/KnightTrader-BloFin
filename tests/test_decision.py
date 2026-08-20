import json
from unittest.mock import MagicMock

import pytest

from hermes_trader.decision import CycleDecision, _extract_json, _round_sz_to_lot, parse
from hermes_trader.market_data import (
    AccountSnapshot,
    Instrument,
    MarketSnapshot,
    PositionSnapshot,
    TickerSnapshot,
)


@pytest.fixture()
def snapshot() -> MarketSnapshot:
    instrument = Instrument(instId="BTC-USDT", tickSz=0.1, lotSz=0.001, minSz=0.001, state="live")
    return MarketSnapshot(
        account=AccountSnapshot(equity=1000.0, available=1000.0, margin_used=0.0, unrealized_pnl=0.0, details=[]),
        positions=[],
        open_orders=[],
        instruments={"BTC-USDT": instrument},
        tickers={
            "BTC-USDT": TickerSnapshot(
                instId="BTC-USDT",
                last=50000.0,
                change_24h_pct=1.0,
                change_1h_pct=0.0,
                vol_24h_quote=1000.0,
                vol_24h_base=0.01,
                funding_rate=None,
                oi=None,
                oi_change_24h_pct=None,
            )
        },
        candles={"BTC-USDT": []},
        top_n=20,
    )


def test_extract_json_from_fenced_response():
    text = "Here:\n```json\n{\"thesis\":\"x\",\"decisions\":[]}\n```\nBye"
    assert json.loads(_extract_json(text))["thesis"] == "x"


def test_extract_json_with_surrounding_prose():
    text = "Start {\"thesis\":\"1\",\"decisions\":[]} End"
    assert json.loads(_extract_json(text))["thesis"] == "1"


def test_extract_json_returns_none_when_missing():
    assert _extract_json("No JSON here.") is None


def test_parse_returns_empty_on_empty_input(snapshot: MarketSnapshot):
    result = parse("", snapshot)
    assert result == CycleDecision.empty("llm_returned_empty")


def test_parse_returns_empty_when_no_json_found(snapshot: MarketSnapshot):
    result = parse("I decline.", snapshot)
    assert result == CycleDecision.empty("llm_output_no_json_found")


def test_parse_rejects_unknown_instrument(snapshot: MarketSnapshot):
    payload = json.dumps({
        "thesis": "unknown",
        "decisions": [{"instId": "UNKNOWN", "action": "open", "side": "buy", "orderType": "market", "sz": "0.001", "leverage": 1}],
    })
    result = parse(payload, snapshot)
    assert result == CycleDecision.empty("all_decisions_rejected: #0: unknown instId 'UNKNOWN'")


def test_parse_snaps_size_down_to_lot(snapshot: MarketSnapshot):
    instrument = snapshot.instruments["BTC-USDT"]
    assert _round_sz_to_lot("0.00123", instrument) == "0.001"
    assert _round_sz_to_lot("9.999e-10", instrument) == "0"
    assert _round_sz_to_lot("abc", instrument) == "abc"


def test_parse_keeps_limit_decision_with_price(snapshot: MarketSnapshot):
    payload = json.dumps({
        "thesis": "limit long",
        "decisions": [
            {
                "instId": "BTC-USDT",
                "action": "open",
                "side": "buy",
                "orderType": "limit",
                "sz": "0.002",
                "px": "50100.0",
                "leverage": 3,
            }
        ],
    })
    result = parse(payload, snapshot)
    assert result.thesis == "limit long"
    assert len(result.decisions) == 1
    assert result.decisions[0].orderType == "limit"
    assert result.decisions[0].px == "50100.0"


def test_parse_rejects_limit_decision_without_price(snapshot: MarketSnapshot):
    payload = json.dumps({
        "decisions": [
            {
                "instId": "BTC-USDT",
                "action": "open",
                "side": "buy",
                "orderType": "limit",
                "sz": "0.001",
            }
        ],
    })
    result = parse(payload, snapshot)
    assert result.no_trade_reason.startswith("all_decisions_rejected:")
