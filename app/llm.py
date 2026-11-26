"""Provider adapter. Groq and Gemini both expose an OpenAI-compatible chat API,
so one small client covers both. Swapping providers is a config change."""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from .config import Settings

PROVIDERS = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


class LLMError(RuntimeError):
    pass


class RateLimitedError(LLMError):
    pass


class LLM(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> dict: ...


class OpenAICompatibleLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float, name: str):
        if not api_key:
            raise LLMError(f"missing API key for provider '{name}'")
        self.name = f"{name}:{model}"
        self._model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete_json(self, system: str, user: str) -> dict:
        body = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": 900,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            r = self._client.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise LLMError(f"LLM request failed: {e.__class__.__name__}") from e
        if r.status_code == 429:
            raise RateLimitedError("LLM provider free-tier limit reached; try again shortly")
        if r.status_code >= 400:
            raise LLMError(f"LLM provider returned HTTP {r.status_code}")
        try:
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError("LLM returned malformed JSON") from e


def build_llm(settings: Settings) -> LLM:
    p = settings.llm_provider.lower()
    if p == "groq":
        return OpenAICompatibleLLM(
            PROVIDERS["groq"], settings.groq_api_key, settings.groq_model, settings.llm_timeout_s, "groq"
        )
    if p == "gemini":
        return OpenAICompatibleLLM(
            PROVIDERS["gemini"], settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_s, "gemini"
        )
    if p == "fake":
        from .fake_llm import FakeLLM

        return FakeLLM()
    raise LLMError(f"unknown LLM provider: {settings.llm_provider}")
