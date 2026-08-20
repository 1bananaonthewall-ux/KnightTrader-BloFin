"""Nous Portal LLM client.

Talks to https://inference-api.nousresearch.com/v1 via the OpenAI Python SDK.
This is the OpenAI-compatible path. Do NOT use Hermes Agent's
`api_mode: anthropic_messages` for `step-3.7-flash`: there's a known bug
(https://github.com/NousResearch/hermes-agent/issues/39124) where Anthropic
`thinking` blocks get injected and then stripped on replay, which breaks
multi-turn tool calls.

We don't use Anthropic-style thinking at all here. We do set `reasoning_effort`
via `extra_body` per StepFun's docs — that's the server-side reasoning control.
"""
from __future__ import annotations

import logging
import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """Raised when the LLM call fails in a way the bot should skip the tick for."""


class NousClient:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "stepfun/step-3.7-flash:free",
        base_url: str = "https://inference-api.nousresearch.com/v1",
        timeout_seconds: int = 45,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 2000,
    ):
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def decide(self, system_prompt: str, user_prompt: str) -> str:
        """Returns the assistant's text content. Raises LLMUnavailable on
        transient failure (the loop should skip the tick in that case).
        """
        start = time.time()
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.max_output_tokens,
                # Do NOT send reasoning_effort for trading decisions: StepFun
                # then leaves message.content empty and only fills `reasoning`
                # with chain-of-thought (no final JSON). We need content.
            )
        except (APITimeoutError, APIConnectionError) as e:
            raise LLMUnavailable(f"timeout/connection: {e}") from e
        except RateLimitError as e:
            # Caller's job to back off; we just signal unavailability.
            raise LLMUnavailable(f"rate limit: {e}") from e
        except AuthenticationError as e:
            # Auth errors are NOT transient — re-raise so the loop dies loudly
            # rather than silently burning ticks.
            raise

        elapsed_ms = int((time.time() - start) * 1000)
        if not resp.choices:
            raise LLMUnavailable("empty choices in response")
        msg = resp.choices[0].message
        content = (msg.content or "").strip()
        if not content:
            # StepFun/Nous sometimes leaves content empty and puts the answer
            # in the reasoning channel when reasoning_effort is enabled.
            reasoning = getattr(msg, "reasoning", None) or ""
            if not reasoning:
                dumped = msg.model_dump() if hasattr(msg, "model_dump") else {}
                reasoning = dumped.get("reasoning") or ""
                details = dumped.get("reasoning_details") or []
                if not reasoning and isinstance(details, list):
                    parts = []
                    for d in details:
                        if isinstance(d, dict) and d.get("text"):
                            parts.append(str(d["text"]))
                    reasoning = "\n".join(parts)
            content = (reasoning or "").strip()
        logger.info("LLM call ok in %d ms, %d chars returned", elapsed_ms, len(content))
        return content

    def cheap_call(self, prompt: str) -> str:
        """Used by first_run_check and the summary-refresh LLM. Same rules,
        no system prompt.
        """
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=min(self.max_output_tokens, 500),
                extra_body={"reasoning_effort": self.reasoning_effort},
            )
        except (APITimeoutError, APIConnectionError) as e:
            raise LLMUnavailable(str(e)) from e
        return resp.choices[0].message.content or ""
