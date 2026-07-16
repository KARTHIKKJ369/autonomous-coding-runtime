from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from config.credentials import load_credentials


class LLMClient(Protocol):
    """Minimal interface every provider adapter implements.
    Skills/Executive only depend on this, never on a specific SDK.
    """

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        ...


@dataclass
class ProviderConfig:
    provider: str  # "anthropic" | "openai" | "openrouter"
    model: str
    api_key: str
    base_url: str | None = None


def _resolve_config(model: str | None = None, provider: str | None = None) -> ProviderConfig:
    """Resolves provider settings from explicit args, then env vars, then the saved
    /connect credentials file (~/.autonomous_runtime/credentials.json).

    Priority per field, highest first: explicit function arg > env var > saved file > default.

    Env vars:
      LLM_PROVIDER          -> "anthropic" | "openai" | "openrouter" (default: anthropic)
      LLM_MODEL             -> model id override for any provider
      ANTHROPIC_API_KEY     -> used when provider == anthropic
      OPENAI_API_KEY        -> used when provider == openai
      OPENROUTER_API_KEY    -> used when provider == openrouter
      OPENROUTER_BASE_URL   -> override (default https://openrouter.ai/api/v1)
    """
    saved = load_credentials()

    resolved_provider = (
        provider or os.environ.get("LLM_PROVIDER") or saved.get("provider") or "anthropic"
    ).lower()

    default_models = {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4.1",
        "openrouter": "anthropic/claude-sonnet-4.6",
    }
    resolved_model = (
        model or os.environ.get("LLM_MODEL") or saved.get("model") or default_models.get(resolved_provider, "")
    )

    if resolved_provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or saved.get("anthropic_api_key")
        if not api_key:
            raise RuntimeError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY, or run: /connect anthropic <api_key>"
            )
        return ProviderConfig("anthropic", resolved_model, api_key)

    if resolved_provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or saved.get("openai_api_key")
        if not api_key:
            raise RuntimeError(
                "No OpenAI API key found. Set OPENAI_API_KEY, or run: /connect openai <api_key>"
            )
        return ProviderConfig("openai", resolved_model, api_key)

    if resolved_provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY") or saved.get("openrouter_api_key")
        if not api_key:
            raise RuntimeError(
                "No OpenRouter API key found. Set OPENROUTER_API_KEY, or run: /connect openrouter <api_key>"
            )
        base_url = (
            os.environ.get("OPENROUTER_BASE_URL")
            or saved.get("openrouter_base_url")
            or "https://openrouter.ai/api/v1"
        )
        return ProviderConfig("openrouter", resolved_model, api_key, base_url=base_url)

    raise ValueError(f"Unknown provider: {resolved_provider!r} (expected anthropic/openai/openrouter)")


class AnthropicAdapter:
    def __init__(self, cfg: ProviderConfig) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=cfg.api_key)
        self._model = cfg.model

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if block.type == "text")


class OpenAICompatibleAdapter:
    """Handles both native OpenAI and OpenRouter, which share the OpenAI SDK/API shape."""

    def __init__(self, cfg: ProviderConfig) -> None:
        from openai import OpenAI

        kwargs = {"api_key": cfg.api_key}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        self._client = OpenAI(**kwargs)
        self._model = cfg.model
        self._provider = cfg.provider

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        extra_headers = {}
        if self._provider == "openrouter":
            # Optional but recommended by OpenRouter for attribution/rate-limit tiers.
            extra_headers = {
                "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
                "X-Title": os.environ.get("OPENROUTER_APP_NAME", "autonomous-coding-runtime"),
            }
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            extra_headers=extra_headers or None,
        )
        return response.choices[0].message.content or ""


def get_llm_client(model: str | None = None, provider: str | None = None) -> LLMClient:
    """Factory: returns a ready-to-use LLMClient for whichever provider is configured.
    Resolves the API key immediately - raises if it's missing. Use SharedLazyLLMClient
    instead when construction shouldn't require an API key to already be present.
    """
    cfg = _resolve_config(model=model, provider=provider)
    if cfg.provider == "anthropic":
        return AnthropicAdapter(cfg)
    return OpenAICompatibleAdapter(cfg)


class SharedLazyLLMClient:
    """Defers provider/API-key resolution until the first .complete() call.

    Lets Runtime wire up Executive + CodeSkill with "the same client" without requiring
    an API key at construction time - only when an LLM call is actually attempted.
    """

    def __init__(self, model: str | None = None, provider: str | None = None) -> None:
        self._model = model
        self._provider = provider
        self._delegate: LLMClient | None = None

    def complete(self, system: str, user: str, max_tokens: int = 2048) -> str:
        if self._delegate is None:
            self._delegate = get_llm_client(model=self._model, provider=self._provider)
        return self._delegate.complete(system, user, max_tokens=max_tokens)
