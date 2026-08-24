from __future__ import annotations

from typing import Sequence

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from .config import settings


class AxiomLLM:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, timeout: float | None = None) -> None:
        self.api_key = api_key or settings.api_key()
        self.base_url = base_url or settings.model.base_url
        self.model = model or settings.model.model
        self.timeout = timeout or float(settings.model.timeout_seconds)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    def decide(self, system_prompt: str, user_prompt: str) -> ChatCompletion:
        return self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

    def decide_stream(self, system_prompt: str, user_prompt: str) -> Stream[ChatCompletionChunk]:
        return self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

    def cheap_call(self, prompt: str, model: str | None = None) -> str:
        resp = self.client.chat.completions.create(
            model=model or settings.model.summary_model,
            temperature=0.1,
            max_tokens=220,
            messages=[
                {"role": "system", "content": "Compress the user's provided notes into a concise trading summary under 250 words."},
                {"role": "user", "content": prompt},
            ],
        )
        content = resp.choices[0].message.content or ""
        return content.strip()

    def extract_content(self, msg) -> str:
        if not msg:
            return ""
        content = getattr(msg, "content", None) or ""
        if content:
            return content
        reasoning = getattr(msg, "reasoning", None)
        if reasoning:
            if isinstance(reasoning, str):
                return reasoning
            if hasattr(reasoning, "content"):
                return reasoning.content or ""
        dump = msg.model_dump() if hasattr(msg, "model_dump") else {}
        for key in ("reasoning", "reasoning_content", "reasoning_details"):
            val = dump.get(key)
            if isinstance(val, str) and val:
                return val
            if isinstance(val, dict):
                inner = val.get("content") or val.get("text") or ""
                if isinstance(inner, str) and inner:
                    return inner
        return ""

    def chat_completion_text(self, system_prompt: str, user_prompt: str) -> str:
        resp = self.decide(system_prompt, user_prompt)
        msg = resp.choices[0].message if resp.choices else None
        return self.extract_content(msg)

    def chat_completion_stream_text(self, system_prompt: str, user_prompt: str) -> str:
        text = ""
        stream = self.decide_stream(system_prompt, user_prompt)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            if getattr(delta, "content", None):
                text += delta.content
            content = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if content and not text:
                text += content
        return text.strip()
