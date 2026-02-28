from __future__ import annotations

import json
import os
import posixpath
import re
from dataclasses import dataclass
from typing import List, Sequence

from .ai_summary import extract_text_snippet

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional
    OpenAI = None  # type: ignore


class RenamePlanningError(RuntimeError):
    """Raised when AI rename planning fails or is unavailable."""


@dataclass(frozen=True)
class RenamePlannerItem:
    source_path: str
    current_relative_path: str
    name: str
    is_dir: bool
    parent_relative_path: str = ""
    text_excerpt: str = ""


class AIRenamePlanner:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        max_chars: int = 1200,
        timeout: float | None = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("API key is required for rename planning.")
        if OpenAI is None:
            raise RenamePlanningError("openai package is not available.")
        client_kwargs = {"api_key": api_key}
        if timeout:
            client_kwargs["timeout"] = timeout
        try:
            self._client = OpenAI(**client_kwargs)
        except TypeError:
            client_kwargs.pop("timeout", None)
            self._client = OpenAI(**client_kwargs)
        self._model = model
        self._max_chars = max(200, int(max_chars))

    def plan(
        self,
        items: Sequence[RenamePlannerItem],
        *,
        instruction: str,
        root_name: str = "",
    ) -> dict:
        if not items:
            raise RenamePlanningError("At least one item is required.")
        payload = {
            "goal": instruction.strip() or "Rename items consistently and group related content into clear folders.",
            "root_name": root_name,
            "items": [
                {
                    "source_path": item.source_path,
                    "current_relative_path": item.current_relative_path,
                    "name": item.name,
                    "is_folder": item.is_dir,
                    "parent_relative_path": item.parent_relative_path,
                    "text_excerpt": item.text_excerpt,
                }
                for item in items
            ],
            "rules": [
                "Return one operation for every input item.",
                "Use relative paths only for target_relative_path.",
                "Do not use .. segments or absolute paths.",
                "Preserve file extensions.",
                "Group related items into folders when that improves organization, for example by series and season.",
                "If an item is already well placed, keep its current_relative_path.",
                "Be conservative when the name pattern is ambiguous.",
            ],
            "requested_format": {
                "summary": "short string",
                "warnings": ["list of strings"],
                "operations": [
                    {
                        "source_path": "original source_path value",
                        "target_relative_path": "safe relative path under the selected root",
                        "reason": "short explanation",
                    }
                ],
            },
        }
        system_prompt = (
            "You organize messy file collections. "
            "Return valid JSON only. "
            "Your job is to normalize names and folder structure without inventing facts. "
            "When you see TV-series style filenames, group them under a series folder and Season NN folders. "
            "Keep folder names concise and stable."
        )
        raw = self._call_openai(system_prompt, payload)
        return _parse_plan_payload(raw, items)

    def build_item(
        self,
        *,
        source_path: str,
        current_relative_path: str,
        is_dir: bool,
        text_source_path: str | None = None,
    ) -> RenamePlannerItem:
        rel_path = _normalize_relative(current_relative_path)
        name = posixpath.basename(rel_path) or os.path.basename(source_path.rstrip("/")) or source_path
        parent = posixpath.dirname(rel_path) if "/" in rel_path else ""
        excerpt = ""
        sample_path = text_source_path or source_path
        if not is_dir and sample_path and os.path.exists(sample_path):
            excerpt = extract_text_snippet(sample_path, limit=self._max_chars)
        return RenamePlannerItem(
            source_path=source_path,
            current_relative_path=rel_path,
            name=name,
            is_dir=is_dir,
            parent_relative_path="" if parent == "." else parent,
            text_excerpt=excerpt,
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
            raise RenamePlanningError(f"OpenAI request failed: {exc}") from exc


def _normalize_relative(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/").lstrip("/")
    value = posixpath.normpath(value) if value else ""
    if value in {"", "."}:
        return ""
    if value.startswith("../") or value == "..":
        return ""
    return value


def _clean_model_payload(payload: str) -> str:
    data = (payload or "").strip()
    if not data:
        return ""
    if data.startswith("```"):
        parts = data.split("```")
        if len(parts) >= 3:
            data = parts[1]
            if data.strip().startswith("json"):
                data = data.split("\n", 1)[1] if "\n" in data else ""
        data = data.strip("` \n")
    first = data.find("{")
    last = data.rfind("}")
    if first != -1 and last != -1 and last >= first:
        data = data[first : last + 1]
    return data.strip()


def _split_name_ext(name: str) -> tuple[str, str]:
    base, ext = posixpath.splitext(name or "")
    return base or name, ext


def _sanitize_target_relative(target_relative_path: str, current_relative_path: str) -> str:
    target = _normalize_relative(target_relative_path)
    if not target:
        return current_relative_path
    target = re.sub(r"[<>:\"|?*]", "-", target)
    target = re.sub(r"/{2,}", "/", target).strip("/")
    if not target or target.startswith("../") or "/../" in f"/{target}/":
        return current_relative_path
    current_name = posixpath.basename(current_relative_path)
    target_name = posixpath.basename(target)
    _, current_ext = _split_name_ext(current_name)
    _, target_ext = _split_name_ext(target_name)
    if current_ext and current_ext.lower() != target_ext.lower():
        target = posixpath.join(posixpath.dirname(target), target_name + current_ext)
    return _normalize_relative(target) or current_relative_path


def _parse_plan_payload(raw: str, items: Sequence[RenamePlannerItem]) -> dict:
    cleaned = _clean_model_payload(raw)
    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise RenamePlanningError(f"Invalid JSON returned by the model: {exc}") from exc
    if not isinstance(data, dict):
        raise RenamePlanningError("Rename planner returned an invalid payload.")

    item_map = {item.source_path: item for item in items}
    operations = data.get("operations")
    if not isinstance(operations, list):
        raise RenamePlanningError("Rename planner response is missing 'operations'.")

    normalized_ops: List[dict] = []
    seen_sources: set[str] = set()
    for entry in operations:
        if not isinstance(entry, dict):
            continue
        source_path = str(entry.get("source_path") or "").strip()
        item = item_map.get(source_path)
        if not item:
            continue
        target_relative_path = _sanitize_target_relative(
            str(entry.get("target_relative_path") or ""),
            item.current_relative_path,
        )
        normalized_ops.append(
            {
                "source_path": source_path,
                "target_relative_path": target_relative_path,
                "reason": str(entry.get("reason") or "").strip(),
            }
        )
        seen_sources.add(source_path)

    for item in items:
        if item.source_path in seen_sources:
            continue
        normalized_ops.append(
            {
                "source_path": item.source_path,
                "target_relative_path": item.current_relative_path,
                "reason": "No change suggested.",
            }
        )

    warnings = data.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
    normalized_warnings = [str(value).strip() for value in warnings if str(value).strip()]
    summary = str(data.get("summary") or "").strip() or "AI generated an organization plan."
    return {
        "summary": summary,
        "warnings": normalized_warnings[:20],
        "operations": normalized_ops,
    }


__all__ = ["AIRenamePlanner", "RenamePlannerItem", "RenamePlanningError"]
