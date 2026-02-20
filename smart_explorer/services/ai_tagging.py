from __future__ import annotations

import json
import os
from typing import List

from .ai_summary import extract_text_snippet

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    OpenAI = None  # type: ignore


class TaggingError(RuntimeError):
    """Raised when AI tagging fails or is unavailable."""


class AITagger:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        max_chars: int = 6000,
        timeout: float | None = 45.0,
        max_tags: int = 6,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required for AI tagging.")
        if OpenAI is None:
            raise TaggingError("openai package is not available.")
        client_kwargs = {"api_key": api_key}
        if timeout:
            client_kwargs["timeout"] = timeout
        try:
            self._client = OpenAI(**client_kwargs)
        except TypeError:
            client_kwargs.pop("timeout", None)
            self._client = OpenAI(**client_kwargs)
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
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": body},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            text = response.output_text.strip()
            if text:
                return text
        except Exception:
            pass

        try:
            chat = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": body},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = chat.choices[0].message.content if chat.choices else ""
            return (content or "").strip()
        except Exception as exc:  # pragma: no cover - network dependent
            raise TaggingError(f"OpenAI request failed: {exc}") from exc


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
