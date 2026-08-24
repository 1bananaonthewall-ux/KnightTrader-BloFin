"""OpenAI-compatible client for Nous Portal.

This is the OpenAI-compatible path. Do NOT use Emirald Agent's
legacy internal path. NousPortal issues such as
https://github.com/NousResearch/emirald-agent/issues/39124 are
avoided by using the standard OpenAI SDK against the portal base URL.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


def _is_rate_limit(exc: BaseException) -> bool:
    msg = str(exc)
    if "429" in msg or "rate limit" in msg.lower():
        return True
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status == 429:
            return True
    return False


class LLMUnavailable(Exception):
    pass


class NousClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        *,
        timeout_seconds: int = 45,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 2000,
    ) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens

    def decide(self, user_prompt: str, system_prompt: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=self.timeout_seconds,
                    extra_body={
                        "reasoning_effort": self.reasoning_effort,
                        "max_output_tokens": self.max_output_tokens,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < 3 and _is_rate_limit(exc):
                    wait = min(2 ** attempt, 20)
                    logger.warning("LLM rate-limited, backing off %ss: %s", wait, exc)
                    time.sleep(wait)
                    continue
                logger.exception("LLM decide failed: %s", exc)
                raise LLMUnavailable(str(exc)) from exc
            message = response.choices[0].message if response.choices else None
            content = message.content if message else None
            if content:
                return content
        raise LLMUnavailable("Empty LLM response") from last_exc

    def cheap_call(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(str(exc)) from exc
        message = response.choices[0].message if response.choices else None
        content = message.content if message else None
        if not content:
            raise LLMUnavailable("Empty LLM response")
        return content


class NousClientPool:
    def __init__(self, keys: list[str], **client_kwargs: Any) -> None:
        if not keys:
            raise ValueError("NousClientPool requires at least one API key")
        self.clients = [NousClient(api_key=k, **client_kwargs) for k in keys]
        self._idx = 0
        self._lock = threading.Lock()

    def _current(self) -> NousClient:
        with self._lock:
            return self.clients[self._idx]

    def _rotate(self) -> None:
        with self._lock:
            self._idx = (self._idx + 1) % len(self.clients)

    def decide(self, user_prompt: str, system_prompt: str) -> str:
        last_exc: Exception | None = None
        for _ in range(len(self.clients)):
            client = self._current()
            try:
                return client.decide(user_prompt, system_prompt)
            except LLMUnavailable as e:
                last_exc = e
                msg = str(e)
                if "429" in msg or "rate limit" in msg.lower():
                    logger.warning("Rotating Nous key after rate limit: %s", e)
                    self._rotate()
                    continue
                raise
        raise LLMUnavailable(f"All Nous keys unavailable: {last_exc}")

    def cheap_call(self, prompt: str) -> str:
        last_exc: Exception | None = None
        for _ in range(len(self.clients)):
            client = self._current()
            try:
                return client.cheap_call(prompt)
            except LLMUnavailable as e:
                last_exc = e
                msg = str(e)
                if "429" in msg or "rate limit" in msg.lower():
                    logger.warning("Rotating Nous key after rate limit: %s", e)
                    self._rotate()
                    continue
                raise
        raise LLMUnavailable(f"All Nous keys unavailable: {last_exc}")
