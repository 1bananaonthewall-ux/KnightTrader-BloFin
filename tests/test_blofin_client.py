import base64
import hashlib
import hmac
import json
import time

import pytest

from hermes_trader.blofin_client import BlofinAPIError, BlofinClient, _sign


class _FakeResp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method.upper(), "url": url, **kwargs})
        payload = self.responses[len(self.requests) - 1]
        if isinstance(payload, Exception):
            raise payload
        return payload


def _make_client(responses):
    client = BlofinClient(api_key="test-key", api_secret="test-secret")
    client._session = _FakeSession(responses)
    client._last_time_sync = 0.0
    client._server_time_offset_ms = 0
    return client


def test_sign_reproduces_blofin_signature_pattern():
    secret = "secret"
    timestamp = "1"
    nonce = "uuid"
    body_json = '{"a":"b"}'
    sign = _sign(secret, timestamp, nonce, "POST", "/api/v1/trade/order", body_json)
    message = f"{timestamp}{nonce}POST/api/v1/trade/order{body_json}".encode("utf-8")
    expected = base64.b64encode(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()).decode("utf-8")
    assert sign == expected


def test_request_sends_compact_json_body():
    body = {"instId": "BTC-USDT", "sz": "0.01"}
    client = _make_client([_FakeResp(200, {"code": "0", "data": [{"instId": "BTC-USDT"}]})])
    client._request("POST", "/api/v1/trade/order", body=body)
    request = client._session.requests[-1]
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["headers"]["ACCESS-KEY"] == "test-key"
    assert request["data"] == json.dumps(body, separators=(",", ":"))


def test_request_retries_transient_429_once():
    client = _make_client([
        _FakeResp(429, "too many"),
        _FakeResp(200, {"code": "0", "data": {"ok": True}}),
    ])
    data = client._request("GET", "/api/v1/market/tickers")
    assert data == {"ok": True}
    assert len(client._session.requests) == 2


def test_request_raises_api_error_for_bad_status():
    client = _make_client([_FakeResp(400, {"code": "60012", "msg": "bad order"})])
    with pytest.raises(BlofinAPIError) as exc_info:
        client._request("POST", "/api/v1/trade/order", body={})
    assert exc_info.value.status == 400
    assert exc_info.value.code == "60012"


def test_list_usdt_perps_filters_by_usdt_swaps():
    client = _make_client([
        _FakeResp(
            200,
            {"code": "0", "data": [
                {"instId": "BTC-USDT", "state": "live"},
                {"instId": "ETH-USDT", "state": "suspended"},
                {"instId": "ETH-USD", "state": "live"},
            ]},
        )
    ])
    instruments = client.list_usdt_perps()
    assert [item["instId"] for item in instruments] == ["BTC-USDT", "ETH-USDT"]


def test_get_candles_returns_chronological_bars():
    newest = {"ts": "30", "o": "1", "h": "2", "l": "0.5", "c": "1.5", "vol": "10"}
    oldest = {"ts": "0", "o": "0.9", "h": "1.9", "l": "0.4", "c": "1.4", "vol": "9"}
    client = _make_client([_FakeResp(200, {"code": "0", "data": [newest, oldest]})])
    candles = client.get_candles("BTC-USDT", bar="1m", limit=2)
    assert [candle["ts"] for candle in candles] == ["0", "30"]


def test_get_tickers_batch_chunks_on_length():
    responses = []
    for chunk_start in range(0, 80, 20):
        ids = [f"{idx:02d}-USDT" for idx in range(chunk_start, chunk_start + 20)]
        responses.append(_FakeResp(200, {"code": "0", "data": [{"instId": iid, "last": "1"} for iid in ids]}))
    client = _make_client(responses)
    instruments = [f"{idx:02d}-USDT" for idx in range(80)]
    result = client.get_tickers_batch(instruments)
    assert len(result) == 80
    assert client._session.requests[-1]["url"].endswith("78-USDT,79-USDT")


def test_time_sync_updates_offset_and_is_cached():
    client = _make_client([])
    client._last_time_sync = 0
    client._server_time_offset_ms = 0
    future_server_ms = int(time.time() * 1000) + 250
    client._session = _FakeSession([_FakeResp(200, {"code": "0", "data": {"ts": str(future_server_ms)}})])
    client._ensure_time_sync()
    server_ms = int(client._timestamp())
    local_ms = int(time.time() * 1000)
    assert future_server_ms - 250 <= server_ms <= future_server_ms + 250

    client._last_time_sync = time.time() - 100
    client._session.requests.clear()
    client._ensure_time_sync()
    assert not client._session.requests
