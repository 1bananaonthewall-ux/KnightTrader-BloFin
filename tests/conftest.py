import json
import time
from pathlib import Path

import pytest

from hermes_trader.decision import CycleDecision
from hermes_trader.journal import Journal
from hermes_trader.market_data import (
    AccountSnapshot,
    Instrument,
    MarketSnapshot,
    PositionSnapshot,
    TickerSnapshot,
)


@pytest.fixture()
def journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "journal.sqlite")


@pytest.fixture()
def sample_instrument() -> Instrument:
    return Instrument(
        instId="BTC-USDT",
        tickSz=0.1,
        lotSz=0.001,
        minSz=0.001,
        contract_value=100.0,
        state="live",
    )


@pytest.fixture()
def snapshot(sample_instrument: Instrument) -> MarketSnapshot:
    return MarketSnapshot(
        account=AccountSnapshot(
            equity=1000.0,
            available=950.0,
            margin_used=50.0,
            unrealized_pnl=10.0,
            details=[]
        ),
        positions=[
            PositionSnapshot(
                instId="BTC-USDT",
                side="long",
                sz=0.01,
                entry_px=50000.0,
                mark_px=51000.0,
                liq_px=45000.0,
                margin=50.0,
                leverage=5,
                unrealized_pnl=10.0,
                age_ms=int(time.time() * 1000),
                cl_ord_id="cl-1",
            )
        ],
        open_orders=[],
        instruments={"BTC-USDT": sample_instrument},
        tickers={
            "BTC-USDT": TickerSnapshot(
                instId="BTC-USDT",
                last=51000.0,
                change_24h_pct=1.5,
                change_1h_pct=0.3,
                vol_24h_quote=5000000.0,
                vol_24h_base=100.0,
                funding_rate=0.0001,
                oi=1000000.0,
                oi_change_24h_pct=2.0,
            )
        },
        candles={"BTC-USDT": [{"ts": 0, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "vol": 10}]},
        top_n=20,
    )


@pytest.fixture()
def valid_decision() -> dict:
    return {
        "thesis": "backend warmth",
        "decisions": [
            {
                "instId": "BTC-USDT",
                "action": "open",
                "side": "buy",
                "orderType": "market",
                "sz": "0.012",
                "leverage": 5,
                "rationale": "warm",
            }
        ],
        "no_trade_reason": "",
    }
