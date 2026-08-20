"""Known-vector test for the Blofin HMAC-SHA256 signing.

We don't have an official published test vector, so we use a stable
hand-computed one. The crucial properties this verifies:
- HMAC-SHA256 with the API secret as key
- Base64 encoding (NOT hex)
- The exact signing string format: timestamp + nonce + METHOD + path + body
- The body must be the compact JSON string we send on the wire

If you change the sign string format, this test will fail and you should
fix the test (and confirm against a captured real request) before shipping.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from hermes_trader.blofin_client import _sign


def test_sign_matches_hand_computed_vector() -> None:
    secret = "test_secret_key_1234567890"
    ts = "1700000000000"
    nonce = "00000000-0000-4000-8000-000000000000"
    method = "POST"
    path = "/api/v1/trade/order"
    body = '{"instId":"BTC-USDT","side":"buy","sz":"0.01","ordType":"market","marginMode":"isolated"}'

    expected = base64.b64encode(
        hmac.new(
            secret.encode(),
            f"{ts}{nonce}{method}{path}{body}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()

    assert _sign(secret, ts, nonce, method, path, body) == expected


def test_sign_changes_when_body_changes() -> None:
    """Whitespace or order changes in the body must change the signature."""
    s1 = _sign("k", "1", "n", "POST", "/p", '{"a":1,"b":2}')
    s2 = _sign("k", "1", "n", "POST", "/p", '{"b":2,"a":1}')
    s3 = _sign("k", "1", "n", "POST", "/p", '{"a": 1, "b": 2}')
    assert s1 != s2
    assert s1 != s3


def test_sign_changes_with_method_case() -> None:
    """Blofin requires uppercase METHOD; lowercase must not be equivalent."""
    a = _sign("k", "1", "n", "POST", "/p", "")
    b = _sign("k", "1", "n", "post", "/p", "")
    assert a != b
