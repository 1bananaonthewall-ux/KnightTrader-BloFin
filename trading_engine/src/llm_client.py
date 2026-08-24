from __future__ import annotations

from typing import Any

from openai import OpenAI

from src.config import AppConfig


class LLMClient:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.client = OpenAI(
            api_key=cfg.model.api_key,
            base_url=cfg.model.base_url,
            timeout=cfg.model.timeout_seconds,
        )
        self.model = cfg.model.model
        self.cheap_model = cfg.model.cheap_model or self.model

    def decide(self, system_prompt: str, user_prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        msg = completion.choices[0].message if completion.choices else None
        if not msg:
            return ""
        content = getattr(msg, "content", None) or ""
        if content:
            return content
        reasoning = getattr(msg, "reasoning", "") or ""
        if not reasoning:
            reasoning = ""
        if hasattr(msg, "model_dump"):
            dumped = msg.model_dump()
            reasoning = reasoning or dumped.get("reasoning_details") or ""
        return reasoning

    def cheap_call(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.cheap_model,
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": prompt},
            ],
        )
        msg = completion.choices[0].message if completion.choices else None
        if not msg:
            return ""
        content = getattr(msg, "content", None) or ""
        if content:
            return content
        return getattr(msg, "reasoning", "") or ""
