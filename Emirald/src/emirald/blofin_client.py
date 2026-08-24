"""Signed REST client for Blofin.

Signature pattern (BloFin docs):
    prehash    = requestPath + METHOD + timestamp + nonce + body
    hexdigest  = hmac_sha256(api_secret, prehash).hexdigest()
    signature  = base64(utf8_bytes(hexdigest))

Notes that bite if you get them wrong:
- `body` is the EXACT raw JSON string sent on the wire (compact separators).
- `timestamp` is Unix epoch in milliseconds (a string).
- `nonce` is a UUID4 string, NOT an integer.
- `METHOD` is uppercase ("GET", "POST", "DELETE").
- `requestPath` is the path component only, including any query string
  (e.g. "/api/v1/market/candles?instId=BTC-USDT&bar=1m&limit=60").
- ACCESS-PASSPHRASE is required when the key was created with one.

Reference: https://docs.blofin.com/ (Authentication / Signing Messages)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover
    curl_requests = None  # type: ignore

logger = logging.getLogger(__name__)

BASE_URL = "https://openapi.blofin.com"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_IMPERSONATE_CANDIDATES = ("chrome", "safari17_0", "edge101")


# --- Signing ---------------------------------------------------------------- #


def _sign(secret: str, timestamp: str, nonce: str, method: str, path: str, body: str) -> str:
    """BloFin ACCESS-SIGN.

    Docs: prehash = path + method + timestamp + nonce + body
    Then HMAC-SHA256 -> hex digest string -> UTF-8 bytes -> Base64.
    (Not raw-digest Base64 like many other exchanges.)
    """
    prehash = f"{path}{method.upper()}{timestamp}{nonce}{body or ''}"
    hex_digest = hmac.new(
        secret.encode("utf-8"),
        prehash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return base64.b64encode(hex_digest.encode("utf-8")).decode("utf-8")


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def _split_path(full_path: str) -> str:
    """Path including query string, exactly as it appears after the host."""
    if full_path.startswith(BASE_URL):
        return full_path[len(BASE_URL):]
    return full_path


# --- Client ----------------------------------------------------------------- #


class BlofinAPIError(Exception):
    def __init__(self, status: int, code: str | None, message: str, payload: Any = None):
        super().__init__(f"Blofin API error {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.payload = payload


class _TransientBlofinError(Exception):
    """Internal signal for tenacity to retry on 429/5xx."""


class BlofinClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str = "",
        broker_id: str = "",
        position_mode: str = "net",
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase or ""
        self.broker_id = (broker_id or "").strip()
        self.position_mode = (position_mode or "net").strip().lower()
        if self.position_mode not in {"net", "hedge"}:
            self.position_mode = "net"
        self._server_time_offset_ms: int = 0
        self._last_time_sync: float = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": _BROWSER_UA,
                "Accept": "application/json",
            }
        )
        self._curl = None
        self._impersonate = "chrome"
        if curl_requests is not None:
            self._curl = curl_requests.Session()

    def _is_geo_block_html(self, status: int, text: str) -> bool:
        if status != 403:
            return False
        low = (text or "").lower()
        return "restricted" in low or "<!doctype html>" in low or "just a moment" in low

    def _transport_get(self, url: str, headers: dict | None = None, timeout: int = 20):
        """GET with Chrome TLS impersonation when available (VPN/WAF bypass)."""
        hdrs = {"User-Agent": _BROWSER_UA, "Accept": "application/json"}
        if headers:
            hdrs.update(headers)
        last_exc: Exception | None = None
        if self._curl is not None:
            for imp in (self._impersonate, *_IMPERSONATE_CANDIDATES):
                try:
                    resp = self._curl.get(url, headers=hdrs, impersonate=imp, timeout=timeout)
                    if self._is_geo_block_html(resp.status_code, getattr(resp, "text", "") or ""):
                        last_exc = BlofinAPIError(resp.status_code, None, "geo/WAF block html")
                        continue
                    self._impersonate = imp
                    return resp
                except Exception as e:  # noqa: BLE001
                    last_exc = e
                    continue
        try:
            return self._session.get(url, headers=hdrs, timeout=timeout)
        except requests.RequestException as e:
            if last_exc:
                raise _TransientBlofinError(str(last_exc)) from e
            raise

    def _transport_request(
        self,
        method: str,
        url: str,
        headers: dict,
        data: str | None = None,
        timeout: int = 15,
    ):
        last_exc: Exception | None = None
        if self._curl is not None:
            for imp in (self._impersonate, *_IMPERSONATE_CANDIDATES):
                try:
                    resp = self._curl.request(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        data=data,
                        impersonate=imp,
                        timeout=timeout,
                    )
                    if self._is_geo_block_html(resp.status_code, getattr(resp, "text", "") or ""):
                        last_exc = BlofinAPIError(resp.status_code, None, "geo/WAF block html")
                        continue
                    self._impersonate = imp
                    return resp
                except Exception as e:  # noqa: BLE001
                    last_exc = e
                    continue
        try:
            return self._session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                data=data,
                timeout=timeout,
            )
        except requests.RequestException as e:
            if last_exc:
                raise _TransientBlofinError(str(last_exc)) from e
            raise

    # --- public: time sync ------------------------------------------------- #

    def _ensure_time_sync(self) -> None:
        """BloFin public /time currently returns 401; skip noisy sync attempts."""
        self._last_time_sync = time.time()
        return

    def _timestamp(self) -> str:
        return str(int(time.time() * 1000) + self._server_time_offset_ms)

    # --- low-level request ------------------------------------------------- #

    def _public_get(self, path_with_query: str) -> Any:
        """Unsigned public market GET (preferred; avoids WAF trips on VPN IPs)."""
        url = f"{BASE_URL}{path_with_query}"
        last_err: Exception | None = None
        for attempt in range(5):
            resp = self._transport_get(url, timeout=20)
            status = getattr(resp, "status_code", 0)
            text = getattr(resp, "text", "") or ""
            if status == 429 or 500 <= status < 600:
                last_err = _TransientBlofinError(f"status {status}: {text[:200]}")
                time.sleep(min(30.0, 2.0 ** attempt))
                continue
            if status != 200:
                if self._is_geo_block_html(status, text):
                    # rotate impersonation and retry
                    last_err = BlofinAPIError(
                        status,
                        None,
                        "Blofin WAF/geo HTML block. VPN datacenter IPs are often filtered; "
                        "Chrome TLS impersonation failed for this request.",
                    )
                    time.sleep(1.0 + attempt)
                    continue
                try:
                    payload = resp.json()
                    code = str(payload.get("code", ""))
                    msg = payload.get("msg") or payload.get("message") or text
                except ValueError:
                    code, msg, payload = "", text, None
                raise BlofinAPIError(status, code, msg, payload)
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("code") not in (None, "0", 0, "200"):
                raise BlofinAPIError(
                    status,
                    str(payload.get("code")),
                    str(payload.get("msg") or "unknown"),
                    payload,
                )
            return payload.get("data") if isinstance(payload, dict) else payload
        if last_err:
            raise last_err
        raise BlofinAPIError(0, None, f"public GET failed for {path_with_query}")

    @retry(
        retry=retry_if_exception_type(_TransientBlofinError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    def _request(self, method: str, path_with_query: str, body: dict | None = None) -> Any:
        self._ensure_time_sync()

        ts = self._timestamp()
        nonce = str(uuid.uuid4())
        # Compact separators: no spaces. We use the same string in body & sign.
        body_str = json.dumps(body, separators=(",", ":")) if body else ""

        signature = _sign(
            secret=self.api_secret,
            timestamp=ts,
            nonce=nonce,
            method=method.upper(),
            path=path_with_query,
            body=body_str,
        )

        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-NONCE": nonce,
            "Content-Type": "application/json",
            "User-Agent": _BROWSER_UA,
            "Accept": "application/json",
        }
        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase

        url = f"{BASE_URL}{path_with_query}"
        try:
            resp = self._transport_request(
                method=method.upper(),
                url=url,
                headers=headers,
                data=body_str if body else None,
                timeout=15,
            )
        except Exception as e:  # noqa: BLE001
            raise _TransientBlofinError(str(e)) from e

        status = getattr(resp, "status_code", 0)
        text = getattr(resp, "text", "") or ""
        if status == 429 or 500 <= status < 600:
            raise _TransientBlofinError(f"status {status}: {text[:200]}")

        if status != 200:
            if self._is_geo_block_html(status, text):
                raise BlofinAPIError(
                    status,
                    None,
                    "Blofin WAF/geo HTML block on signed request.",
                )
            try:
                payload = resp.json()
                code = str(payload.get("code", ""))
                msg = payload.get("msg") or payload.get("message") or text
            except ValueError:
                code, msg, payload = "", text, None
            raise BlofinAPIError(status, code, msg, payload)

        try:
            payload = resp.json()
        except ValueError as e:
            raise BlofinAPIError(status, None, f"non-JSON response: {e}") from e

        # Blofin wraps responses in {code, msg, data}. Surface non-zero codes.
        if isinstance(payload, dict) and payload.get("code") not in (None, "0", 0, "200"):
            raise BlofinAPIError(
                status,
                str(payload.get("code")),
                str(payload.get("msg") or "unknown"),
                payload,
            )
        return payload.get("data") if isinstance(payload, dict) else payload

    # --- market endpoints (public) ---------------------------------------- #

    def list_usdt_perps(self) -> list[dict]:
        """List all USDT-margined swap (perpetual) instruments on Blofin."""
        data = self._public_get("/api/v1/market/instruments?instType=SWAP")
        return [x for x in (data or []) if x.get("instId", "").endswith("-USDT")]

    def get_candles(self, inst_id: str, bar: str = "1m", limit: int = 60) -> list[dict]:
        """Recent candles. Returns list of dicts with ts/o/h/l/c/vol/etc.
        Note: Blofin returns candles in descending order (newest first).
        """
        path = f"/api/v1/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
        data = self._public_get(path) or []
        # Normalize and return in chronological (ascending) order for the LLM.
        return list(reversed(data))

    def get_ticker(self, inst_id: str) -> dict:
        path = f"/api/v1/market/tickers?instId={inst_id}"
        data = self._public_get(path) or []
        return data[0] if data else {}

    def get_tickers_batch(self, inst_ids: list[str] | None = None) -> dict[str, dict]:
        """Fetch tickers for many instruments.

        Blofin rejects comma-separated instId lists (error 152002), so we pull
        the full ticker book once and filter client-side.
        """
        data = self._public_get("/api/v1/market/tickers?instType=SWAP") or []
        wanted = set(inst_ids) if inst_ids else None
        out: dict[str, dict] = {}
        for t in data:
            iid = t.get("instId")
            if not iid:
                continue
            if wanted is not None and iid not in wanted:
                continue
            out[iid] = t
        return out

    # --- account / private endpoints -------------------------------------- #

    def get_balance(self) -> dict:
        """Account balance. Returns Blofin's nested structure (details: [{ccy,
        eq, availEq, ...}])."""
        return self._request("GET", "/api/v1/account/balance") or {}

    def get_positions(self) -> list[dict]:
        return self._request("GET", "/api/v1/account/positions") or []

    def get_open_orders(self) -> list[dict]:
        return self._request("GET", "/api/v1/trade/orders-pending") or []

    def get_order(self, inst_id: str, ord_id: str | None = None, cl_ord_id: str | None = None) -> dict:
        q = f"instId={inst_id}"
        if ord_id:
            q += f"&orderId={ord_id}"
        if cl_ord_id:
            q += f"&clientOrderId={cl_ord_id}"
        return self._request("GET", f"/api/v1/trade/order?{q}") or {}

    def set_leverage(self, inst_id: str, leverage: int, margin_mode: str = "isolated", position_mode: str | None = None, side: str | None = None) -> dict:
        body: dict[str, Any] = {
            "instId": inst_id,
            "leverage": str(int(leverage)),
            "marginMode": margin_mode,
        }
        mode = (position_mode or self.position_mode or "net").strip().lower()
        if mode == "hedge":
            body["positionSide"] = "long" if side == "buy" else "short"
        return self._request("POST", "/api/v1/account/set-leverage", body) or {}

    # --- trading ---------------------------------------------------------- #

    def place_order(
        self,
        inst_id: str,
        side: str,            # "buy" | "sell"
        sz: str,              # contracts (string) per BloFin
        ord_type: str,        # "market" | "limit"
        td_mode: str,         # "isolated" | "cross" | "cash"
        px: str | None = None,
        cl_ord_id: str | None = None,
        leverage: int | None = None,
        stop_loss: str | None = None,
        take_profit: str | None = None,
        position_side: str | None = None,
    ) -> dict:
        body = {
            "instId": inst_id,
            "marginMode": td_mode,
            "side": side,
            "orderType": ord_type,
            "size": str(sz),
        }
        if self.position_mode == "hedge":
            body["positionSide"] = position_side or ("long" if side == "buy" else "short")
        if self.broker_id:
            body["brokerId"] = self.broker_id
        if ord_type == "limit":
            if px is None:
                raise ValueError("limit order requires px")
            body["price"] = str(px)
        if cl_ord_id:
            body["clientOrderId"] = cl_ord_id
        if stop_loss:
            body["slTriggerPrice"] = str(stop_loss)
            body["slOrderPrice"] = "-1"
            body["slTriggerPriceType"] = "last"
        if take_profit:
            body["tpTriggerPrice"] = str(take_profit)
            body["tpOrderPrice"] = "-1"
            body["tpTriggerPriceType"] = "last"

        raw = self._request("POST", "/api/v1/trade/order", body)
        # Normalize response shape for executor (data may be a list).
        if isinstance(raw, list) and raw:
            row = raw[0] if isinstance(raw[0], dict) else {"orderId": raw[0]}
            return {
                "ordId": row.get("orderId") or row.get("ordId"),
                "clOrdId": row.get("clientOrderId") or row.get("clOrdId"),
                "raw": row,
            }
        if isinstance(raw, dict):
            return {
                "ordId": raw.get("orderId") or raw.get("ordId"),
                "clOrdId": raw.get("clientOrderId") or raw.get("clOrdId"),
                "raw": raw,
            }
        return {"raw": raw}

    def cancel_order(self, inst_id: str, ord_id: str | None = None, cl_ord_id: str | None = None) -> dict:
        body: dict[str, Any] = {"instId": inst_id}
        if ord_id:
            body["orderId"] = ord_id
        if cl_ord_id:
            body["clientOrderId"] = cl_ord_id
        if not body.get("orderId") and not body.get("clientOrderId"):
            raise ValueError("cancel_order requires orderId or clientOrderId")
        return self._request("POST", "/api/v1/trade/cancel-order", body)
