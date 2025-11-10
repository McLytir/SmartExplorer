from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

try:  # Optional dependency for PDFs
    import fitz  # type: ignore
except Exception:  # pragma: no cover - optional
    fitz = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    OpenAI = None  # type: ignore


class SummaryError(RuntimeError):
    """Raised when summarization fails or is unavailable."""


@dataclass(frozen=True)
class SummaryResult:
    preset: str
    tone: str
    summary: str
    key_risks: List[str]
    action_items: List[str]


SUMMARY_PRESETS: Dict[str, Dict[str, str]] = {
    "tweet": {
        "label": "Tweet (<=280 chars)",
        "instruction": (
            "Write a single snappy statement no longer than 280 characters. "
            "Prefer plain language over jargon."
        ),
    },
    "paragraph": {
        "label": "Paragraph (~120 words)",
        "instruction": (
            "Write one well-structured paragraph (80-140 words) that captures the core points, "
            "audience, and outcome."
        ),
    },
    "executive": {
        "label": "Executive Brief (bullets)",
        "instruction": (
            "Provide 3-4 bullet sentences covering purpose, current status, and next milestones."
        ),
    },
}

SUMMARY_TONES: Dict[str, Dict[str, str]] = {
    "neutral": {"label": "Neutral", "instruction": "Maintain an objective, matter-of-fact voice."},
    "friendly": {"label": "Friendly", "instruction": "Sound encouraging and collaborative."},
    "urgent": {"label": "Urgent", "instruction": "Highlight deadlines and consequences succinctly."},
}

TEXT_LIKE_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".log",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cs",
    ".c",
    ".cpp",
    ".h",
    ".html",
    ".htm",
}


def available_presets() -> List[Tuple[str, str]]:
    return [(key, data["label"]) for key, data in SUMMARY_PRESETS.items()]


def available_tones() -> List[Tuple[str, str]]:
    return [(key, data["label"]) for key, data in SUMMARY_TONES.items()]


class AISummarizer:
    """
    Lightweight wrapper around OpenAI's Responses API with a fallback to Chat Completions.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        max_chars: int = 8000,
        timeout: float | None = 45.0,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required for summarization.")
        if OpenAI is None:
            raise SummaryError("openai package is not available.")
        client_kwargs = {"api_key": api_key}
        if timeout:
            client_kwargs["timeout"] = timeout
        try:
            self._client = OpenAI(**client_kwargs)
        except TypeError:
            # Older SDKs may not accept timeout
            client_kwargs.pop("timeout", None)
            self._client = OpenAI(**client_kwargs)
        self._model = model
        self._max_chars = max(2000, int(max_chars))

    def summarize_file(self, path: str, *, preset: str, tone: str) -> SummaryResult:
        text = extract_text_snippet(path, limit=self._max_chars)
        if not text.strip():
            raise SummaryError("Unable to extract readable text from the selected file.")
        return self._summarize_text(text, os.path.basename(path), preset, tone)

    def _summarize_text(self, text: str, filename: str, preset: str, tone: str) -> SummaryResult:
        preset_key = preset if preset in SUMMARY_PRESETS else "paragraph"
        tone_key = tone if tone in SUMMARY_TONES else "neutral"

        preset_instruction = SUMMARY_PRESETS[preset_key]["instruction"]
        tone_instruction = SUMMARY_TONES[tone_key]["instruction"]

        payload = {
            "document_name": filename,
            "summary_style": preset_instruction,
            "tone_instruction": tone_instruction,
            "text_excerpt": text,
            "requested_format": {
                "summary": "string",
                "key_risks": "array of up to 3 concise bullet sentences highlighting risks/unknowns.",
                "action_items": "array of up to 3 bullet sentences describing next steps.",
            },
        }
        system_prompt = (
            "You condense long documents for busy professionals. "
            "Always respond with valid JSON using the schema provided by the user."
        )

        raw = self._call_openai(system_prompt, payload)
        summary, risks, actions = _parse_summary_payload(raw)
        return SummaryResult(
            preset=preset_key,
            tone=tone_key,
            summary=summary,
            key_risks=risks,
            action_items=actions,
        )

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
                temperature=0.2,
            )
            content = chat.choices[0].message.content if chat.choices else ""
            return (content or "").strip()
        except Exception as exc:  # pragma: no cover - network dependent
            raise SummaryError(f"OpenAI request failed: {exc}") from exc


def extract_text_snippet(path: str, *, limit: int = 8000) -> str:
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    text = ""
    if ext == ".pdf":
        text = _extract_pdf_text(path, limit)
    elif ext in TEXT_LIKE_EXTENSIONS:
        text = _read_text_file(path, limit * 2)
    else:
        text = _read_text_file(path, limit * 2)
        if not text and fitz and ext in {".xps", ".oxps"}:
            text = _extract_pdf_text(path, limit)
    return _normalize_excerpt(text, limit)


def _extract_pdf_text(path: str, limit: int) -> str:
    if not fitz:
        return ""
    try:
        doc = fitz.open(path)  # type: ignore[arg-type]
    except Exception:
        return ""
    collected: List[str] = []
    remaining = max(limit, 1000)
    try:
        for page_index in range(min(doc.page_count, 20)):
            try:
                page = doc.load_page(page_index)
                chunk = page.get_text("text") or ""
            except Exception:
                continue
            if not chunk.strip():
                continue
            collected.append(chunk)
            remaining -= len(chunk)
            if remaining <= 0:
                break
    finally:
        try:
            doc.close()
        except Exception:
            pass
    return "\n".join(collected)


def _read_text_file(path: str, limit: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except Exception:
        return ""


def _normalize_excerpt(text: str, limit: int) -> str:
    snippet = (text or "").strip()
    if not snippet:
        return ""
    snippet = re.sub(r"\r\n?", "\n", snippet)
    snippet = re.sub(r"[ \t]+", " ", snippet)
    snippet = re.sub(r"\n{3,}", "\n\n", snippet)
    return snippet[:limit].strip()


def _parse_summary_payload(payload: str) -> Tuple[str, List[str], List[str]]:
    summary = ""
    risks: List[str] = []
    actions: List[str] = []
    try:
        data = json.loads(payload)
    except Exception as exc:
        raise SummaryError(f"Invalid JSON returned by the model: {exc}") from exc

    if isinstance(data, dict):
        summary = str(data.get("summary") or "").strip()
        risks_data = data.get("key_risks")
        actions_data = data.get("action_items")
        if isinstance(risks_data, list):
            risks = [str(item).strip() for item in risks_data if str(item).strip()]
        if isinstance(actions_data, list):
            actions = [str(item).strip() for item in actions_data if str(item).strip()]
    if not summary:
        raise SummaryError("Model returned an empty summary.")
    return summary, risks[:3], actions[:3]


__all__ = [
    "AISummarizer",
    "SummaryResult",
    "SummaryError",
    "SUMMARY_PRESETS",
    "SUMMARY_TONES",
    "available_presets",
    "available_tones",
    "extract_text_snippet",
]
