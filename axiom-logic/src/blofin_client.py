from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import settings, blofin_sign


def _request_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


class Ticker(BaseModel):
    instId: str = ""
    last: str = ""
    open24h: str = ""
    high24h: str = ""
    low24h: str = ""
    quoteVolume: str = ""
    openInterest: str = ""


class Candle(BaseModel):
    ts: str = ""
    o: str = ""
    h: str = ""
    l: str = ""
    c: str = ""
    vol: str = ""


class Instrument(BaseModel):
    instId: str = ""
    base_ccy: str = ""
    quote_ccy: str = ""
    ct_val: str = ""
    lot_sz: str = "1"
    min_sz: str = "1"
    ct_mult: str = "1"
    state: str = ""


class Position(BaseModel):
    instId: str = ""
    side: str = ""
    sz: str = ""
    avail_sz: str = ""
    entry_px: str = ""
    mark_px: str = ""
    leverage: str = ""
    liq_px: str = ""
    unrealized_pnl: str = ""


class Balance(BaseModel):
    ccy: str = ""
    eq: str = ""
    avail_eq: str = ""
    frozen: str = ""


class OrderResponse(BaseModel):
    ordId: str = ""
    clientOrderId: str = ""
    code: str = ""
    msg: str = ""
    data: dict[str, Any] | None = None


class BlofinClient:
    def __init__(self) -> None:
        self.creds = settings.credentials()
        self.cfg = settings.blofin
        self.broker_id = self.cfg.broker_id
        self.base = self.cfg.base_url.rstrip("/")
        self.client = httpx.Client(timeout=httpx.Timeout(10.0), http2=True, follow_redirects=True)
        self._universe_cache: list[str] = []
        self._universe_ts = 0.0

    def close(self) -> None:
        self.client.close()

    def _headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        sign = blofin_sign(self.creds.secret, ts, method, path, body)
        return {
            "ACCESS-KEY": self.creds.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.creds.passphrase,
            "brokerId": self.broker_id,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> httpx.Response:
        params = params or {}
        qs = ("?" + urlencode(params)) if params else ""
        body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        headers = self._headers(method, path + qs, body_text)
        if method == "GET":
            resp = self.client.get(self.base + path + qs, headers=headers)
        else:
            resp = self.client.post(self.base + path, headers=headers, content=body_text)
        if resp.status_code >= 400:
            raise RuntimeError(f"Blofin API error {resp.status_code}: {resp.text[:300]}")
        return resp

    def get_tickers(self, inst_type: str = "SWAP") -> list[Ticker]:
        r = self._request("GET", self.cfg.rest.tickers, params={"instType": inst_type, "instFamily": "USDT"})
        data = r.json().get("data") or r.json().get("data") or []
        return [Ticker(**{k: item.get(k, "") for k in Ticker.model_fields}) for item in data]

    def get_candles(self, instId: str, bar: str = "1m", limit: int = 100) -> list[Candle]:
        params = {"instId": instId, "bar": bar, "limit": str(limit)}
        r = self._request("GET", self.cfg.rest.candles, params=params)
        raw = r.json().get("data", [])
        candles: list[Candle] = []
        for row in raw:
            if not row:
                continue
            candles.append(
                Candle(
                    ts=row[0],
                    o=row[1],
                    h=row[2],
                    l=row[3],
                    c=row[4],
                    vol=row[5] if len(row) > 5 else "",
                )
            )
        return candles

    def get_instruments(self, inst_type: str = "SWAP", inst_family: str = "USDT") -> list[Instrument]:
        params = {"instType": inst_type, "instFamily": inst_family}
        r = self._request("GET", "/api/v1/public/instruments", params=params)
        raw = r.json().get("data", [])
        return [Instrument(**{k: item.get(k, "") for k in Instrument.model_fields}) for item in raw]

    def get_positions(self) -> list[Position]:
        r = self._request("GET", self.cfg.rest.positions)
        raw = r.json().get("data", [])
        return [Position(**{k: item.get(k, "") for k in Position.model_fields}) for item in raw]

    def get_balances(self, ccy: str = "USDT") -> list[Balance]:
        r = self._request("GET", self.cfg.rest.balances, params={"ccy": ccy})
        raw = r.json().get("data", [])
        return [Balance(**{k: item.get(k, "") for k in Balance.model_fields}) for item in raw]

    def place_order(self, payload: dict[str, Any]) -> OrderResponse:
        path = self.cfg.rest.order
        payload.setdefault("brokerId", self.broker_id)
        payload.setdefault("clientOrderId", _request_id())
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        sign = blofin_sign(self.creds.secret, ts, "POST", path, body)
        headers = {
            "ACCESS-KEY": self.creds.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.creds.passphrase,
            "brokerId": self.broker_id,
            "Content-Type": "application/json",
        }
        resp = self.client.post(self.base + path, headers=headers, content=body)
        if resp.status_code >= 400:
            return OrderResponse(code=str(resp.status_code), msg=resp.text[:500])
        return OrderResponse(**resp.json())

    def universe(self, max_age_seconds: float = 3600.0) -> list[str]:
        now = datetime.now(timezone.utc).timestamp()
        if self._universe_cache and (now - self._universe_ts) < max_age_seconds:
            return self._universe_cache
        tickers = self.get_tickers()
        active = [t.instId for t in tickers if getattr(t, "instId", "")]
        self._universe_cache = active
        self._universe_ts = now
        return active
