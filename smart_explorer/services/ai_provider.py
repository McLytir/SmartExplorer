from __future__ import annotations

import os
from typing import Any, Optional


DEFAULT_AI_PROVIDER = "openai"
DEFAULT_AI_MODELS = {
    "openai": "gpt-4.1-mini",
    "claude": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
}
AI_MODEL_PRESETS = {
    "openai": [
        "gpt-5.2",
        "gpt-5.2-pro",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
    ],
    "claude": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-7-sonnet-latest",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    ],
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
}
PROVIDER_SECRET_KEYS = {
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}
PROVIDER_PACKAGE_HINTS = {
    "openai": "pip install openai",
    "claude": "pip install anthropic",
    "gemini": "pip install google-genai",
}


class AIProviderError(RuntimeError):
    pass


def normalize_ai_provider(provider: Optional[str]) -> str:
    value = str(provider or "").strip().lower()
    if value in {"anthropic", "claude"}:
        return "claude"
    if value in {"google", "gemini"}:
        return "gemini"
    if value == "openai":
        return "openai"
    return DEFAULT_AI_PROVIDER


def default_model_for_provider(provider: Optional[str]) -> str:
    normalized = normalize_ai_provider(provider)
    return DEFAULT_AI_MODELS.get(normalized, DEFAULT_AI_MODELS[DEFAULT_AI_PROVIDER])


def model_presets_for_provider(provider: Optional[str]) -> list[str]:
    normalized = normalize_ai_provider(provider)
    presets = list(AI_MODEL_PRESETS.get(normalized, []))
    default_model = default_model_for_provider(normalized)
    if default_model not in presets:
        presets.insert(0, default_model)
    return presets


def effective_ai_provider(cfg: Any) -> str:
    return normalize_ai_provider(getattr(cfg, "ai_provider", None))


def effective_ai_model(cfg: Any) -> str:
    provider = effective_ai_provider(cfg)
    explicit = str(
        getattr(cfg, "ai_model", None)
        or getattr(cfg, "model", None)
        or ""
    ).strip()
    return explicit or default_model_for_provider(provider)


def provider_secret_name(provider: Optional[str]) -> str:
    return PROVIDER_SECRET_KEYS.get(normalize_ai_provider(provider), "OPENAI_API_KEY")


def provider_install_hint(provider: Optional[str]) -> str:
    return PROVIDER_PACKAGE_HINTS.get(normalize_ai_provider(provider), "Install the provider SDK.")


def get_provider_api_key(provider: Optional[str], *, cfg: Any = None) -> str:
    normalized = normalize_ai_provider(provider)
    secret_name = provider_secret_name(normalized)
    env_names = [secret_name]
    if normalized == "gemini":
        env_names.append("GOOGLE_API_KEY")
    for name in env_names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    if normalized == "openai" and cfg is not None:
        fallback = str(getattr(cfg, "api_key", None) or "").strip()
        if fallback:
            return fallback
    try:
        from . import secret_store

        for name in env_names:
            value = (secret_store.get_secret(name) or "").strip()
            if value:
                return value
    except Exception:
        pass
    return ""


def has_provider_api_key(provider: Optional[str], *, cfg: Any = None) -> bool:
    return bool(get_provider_api_key(provider, cfg=cfg))


class AIProviderClient:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        model: str,
        timeout: float | None = None,
    ) -> None:
        self.provider = normalize_ai_provider(provider)
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip() or default_model_for_provider(self.provider)
        self.timeout = timeout
        if not self.api_key:
            raise AIProviderError(f"{self.provider} API key is required.")
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if self.provider == "openai":
            try:
                from openai import OpenAI  # type: ignore
            except Exception as exc:
                raise AIProviderError(
                    f"OpenAI support requires the openai package. {provider_install_hint(self.provider)}"
                ) from exc
            kwargs = {"api_key": self.api_key}
            if self.timeout:
                kwargs["timeout"] = self.timeout
            try:
                self._client = OpenAI(**kwargs)
            except TypeError:
                kwargs.pop("timeout", None)
                self._client = OpenAI(**kwargs)
            return self._client
        if self.provider == "claude":
            try:
                from anthropic import Anthropic  # type: ignore
            except Exception as exc:
                raise AIProviderError(
                    f"Claude support requires the anthropic package. {provider_install_hint(self.provider)}"
                ) from exc
            kwargs = {"api_key": self.api_key}
            if self.timeout:
                kwargs["timeout"] = self.timeout
            try:
                self._client = Anthropic(**kwargs)
            except TypeError:
                kwargs.pop("timeout", None)
                self._client = Anthropic(**kwargs)
            return self._client
        if self.provider == "gemini":
            try:
                from google import genai  # type: ignore
            except Exception as exc:
                raise AIProviderError(
                    f"Gemini support requires the google-genai package. {provider_install_hint(self.provider)}"
                ) from exc
            kwargs = {"api_key": self.api_key}
            try:
                self._client = genai.Client(**kwargs)
            except TypeError as exc:
                raise AIProviderError(
                    f"Gemini client initialization failed. {provider_install_hint(self.provider)}"
                ) from exc
            return self._client
        raise AIProviderError(f"Unsupported AI provider: {self.provider}")

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        temperature: float | None = 0.2,
        max_output_tokens: int | None = None,
    ) -> str:
        client = self._ensure_client()
        if self.provider == "openai":
            return self._generate_openai(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=json_mode,
                temperature=temperature,
            )
        if self.provider == "claude":
            return self._generate_claude(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        if self.provider == "gemini":
            return self._generate_gemini(
                client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=json_mode,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
        raise AIProviderError(f"Unsupported AI provider: {self.provider}")

    def _generate_openai(
        self,
        client: Any,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        temperature: float | None,
    ) -> str:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            response = client.responses.create(**kwargs)
            text = str(getattr(response, "output_text", "") or "").strip()
            if text:
                return text
        except Exception:
            pass
        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            chat = client.chat.completions.create(**kwargs)
            content = chat.choices[0].message.content if getattr(chat, "choices", None) else ""
            return str(content or "").strip()
        except Exception as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc

    def _generate_claude(
        self,
        client: Any,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None,
        max_output_tokens: int | None,
    ) -> str:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": max_output_tokens or 4096,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            message = client.messages.create(**kwargs)
            parts = []
            for item in getattr(message, "content", []) or []:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
            content = "\n".join(parts).strip()
            if content:
                return content
            raise AIProviderError("Claude returned an empty response.")
        except Exception as exc:
            raise AIProviderError(f"Claude request failed: {exc}") from exc

    def _generate_gemini(
        self,
        client: Any,
        *,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool,
        temperature: float | None,
        max_output_tokens: int | None,
    ) -> str:
        try:
            from google.genai import types  # type: ignore
        except Exception as exc:
            raise AIProviderError(
                f"Gemini support requires the google-genai package. {provider_install_hint(self.provider)}"
            ) from exc
        try:
            config_kwargs: dict[str, Any] = {
                "system_instruction": system_prompt,
            }
            if temperature is not None:
                config_kwargs["temperature"] = temperature
            if max_output_tokens:
                config_kwargs["max_output_tokens"] = max_output_tokens
            if json_mode:
                config_kwargs["response_mime_type"] = "application/json"
            response = client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = str(getattr(response, "text", "") or "").strip()
            if text:
                return text
            candidates = getattr(response, "candidates", None) or []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None) or []
                collected = []
                for part in parts:
                    piece = getattr(part, "text", None)
                    if piece:
                        collected.append(str(piece))
                if collected:
                    return "\n".join(collected).strip()
            raise AIProviderError("Gemini returned an empty response.")
        except Exception as exc:
            raise AIProviderError(f"Gemini request failed: {exc}") from exc
