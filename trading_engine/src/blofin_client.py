from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

import requests

from src.config import AppConfig


def _parse_credential_file(path: str) -> dict[str, str]:
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return {}
    out: dict[str, str] = {}
    with open(p, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def _sign(secret: str, timestamp: str, method: str, path: str, body: str = "") -> str:
    payload = timestamp + method.upper() + path + body
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


class BlofinClient:
    def __init__(self, cfg: AppConfig, *, demo: bool | None = None) -> None:
        self.cfg = cfg
        self.demo = demo if demo is not None else cfg.trading.mode != "live"
        self.rest_base = cfg.blofin.rest_base
        self.broker_id = cfg.blofin.broker_id
        creds = _parse_credential_file(cfg.blofin.credential_file)
        self.api_key = cfg.blofin.api_key or creds.get("api key", "")
        self.secret = cfg.blofin.secret_key or creds.get("secret key", "")
        self.passphrase = cfg.blofin.passphrase or creds.get("passphrase", "")
        if not all([self.api_key, self.secret, self.passphrase]):
            raise RuntimeError("Missing Blofin credentials")

    def _headers(self, path: str, body: str = "", method: str = "GET") -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        sign = _sign(self.secret, ts, method, path, body)
        hdrs = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.passphrase,
            "brokerId": self.broker_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.demo:
            hdrs["x-simulated-trading"] = "1"
        return hdrs

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = self.rest_base + path
        hdrs = self._headers(path)
        r = requests.get(url, headers=hdrs, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict[str, Any]) -> Any:
        url = self.rest_base + path
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        hdrs = self._headers(path, body=payload, method="POST")
        r = requests.post(url, headers=hdrs, data=payload, timeout=15)
        text = r.text
        try:
            data = r.json()
        except ValueError:
            data = {"raw": text}
        if not r.ok:
            raise RuntimeError(f"Blofin POST {path} failed: {data}")
        return data

    def get_tickers(self) -> Any:
        return self.get("/api/v1/market/tickers", {"instType": "SWAP"})

    def get_candles(self, inst_id: str, bar: str = "1m", limit: int = 100) -> Any:
        path = f"/api/v1/market/candles"
        params = {"instId": inst_id, "bar": bar, "limit": str(limit)}
        return self.get(path, params)

    def get_balances(self) -> Any:
        return self.get("/api/v1/asset/balances", {"ccy": "USDT"})

    def get_positions(self) -> Any:
        return self.get("/api/v1/account/positions", {"instType": "SWAP"})

    def place_order(self, order: dict[str, Any]) -> Any:
        order.setdefault("brokerId", self.broker_id)
        if "clOrdId" not in order:
            order["clOrdId"] = f"hermes-{int(time.time()*1000)}"
        return self.post("/api/v1/trade/order", order)
