from __future__ import annotations

import json
import os
from typing import List

from .ai_summary import extract_text_snippet
from .ai_provider import AIProviderClient, AIProviderError


class TaggingError(RuntimeError):
    """Raised when AI tagging fails or is unavailable."""


class AITagger:
    def __init__(
        self,
        api_key: str,
        provider: str = "openai",
        model: str = "gpt-4.1-mini",
        *,
        max_chars: int = 6000,
        timeout: float | None = 45.0,
        max_tags: int = 6,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required for AI tagging.")
        try:
            self._client = AIProviderClient(
                provider=provider,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )
        except AIProviderError as exc:
            raise TaggingError(str(exc)) from exc
        self._model = model
        self._max_chars = max(2000, int(max_chars))
        self._max_tags = max(3, int(max_tags))

    def suggest_tags(self, path: str, existing: List[str] | None = None) -> List[str]:
        snippet = extract_text_snippet(path, limit=self._max_chars)
        if not snippet.strip():
            raise TaggingError("Unable to extract readable text for tagging.")
        filename = os.path.basename(path) or os.path.basename(os.path.dirname(path)) or path
        return self._generate_tags(snippet, filename, existing or [])

    def _generate_tags(self, text: str, filename: str, existing: List[str]) -> List[str]:
        payload = {
            "document_name": filename,
            "text_excerpt": text,
            "existing_tags": existing,
            "instructions": (
                "Suggest between 3 and {max_tags} concise tags that describe the key topics, "
                "entities, or formats in the excerpt. "
                "Avoid duplicates with existing tags and keep each tag under 3 words."
            ).format(max_tags=self._max_tags),
            "requested_format": {"tags": "list of lowercase strings"},
        }
        system_prompt = (
            "You analyze documents to create metadata tags. "
            "Only emit valid JSON with a 'tags' array of lowercase strings. "
            "Each tag should be short and meaningful, e.g., 'financial-report' or 'machine-learning'."
        )
        raw = self._call_openai(system_prompt, payload)
        return _parse_tags_payload(raw)

    def _call_openai(self, system_prompt: str, payload: dict) -> str:
        body = json.dumps(payload, ensure_ascii=False)
        try:
            return self._client.generate_text(
                system_prompt=system_prompt,
                user_prompt=body,
                json_mode=True,
                temperature=0.2,
            )
        except AIProviderError as exc:  # pragma: no cover - network dependent
            raise TaggingError(str(exc)) from exc


def _parse_tags_payload(raw: str) -> List[str]:
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise TaggingError(f"Invalid AI tagging response: {exc}") from exc
    tags = data.get("tags") if isinstance(data, dict) else None
    if not isinstance(tags, list):
        raise TaggingError("AI tagging response missing 'tags'.")
    cleaned = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        trimmed = tag.strip().lower()
        if trimmed:
            cleaned.append(trimmed.replace(" ", "-"))
    unique = []
    for tag in cleaned:
        if tag not in unique:
            unique.append(tag)
    return unique[:12]


__all__ = ["AITagger", "TaggingError"]
