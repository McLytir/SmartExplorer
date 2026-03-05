from __future__ import annotations

import json
import re
from typing import List, Optional

from ..services.ai_provider import AIProviderClient, AIProviderError, normalize_ai_provider
from .base import Translator


_EXT_RE = re.compile(r"^(?P<stem>.*?)(?P<ext>\.[^./\\]+)?$")


class AITranslator(Translator):
    def __init__(self, provider: str, api_key: str, model: str) -> None:
        self.provider = normalize_ai_provider(provider)
        self.model = model
        self.client = AIProviderClient(provider=self.provider, api_key=api_key, model=model, timeout=45.0)

    def cache_namespace(self) -> str:
        return f"{self.provider}:{self.model}"

    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        m = _EXT_RE.match(title)
        stem = (m.group("stem") if m else title) or ""
        ext = (m.group("ext") if m else "") or ""
        prompt = (
            "Translate the following filename stem into "
            f"{target_language}. Do not include any punctuation or quotes. "
            "Keep it concise and natural in the target language. "
            "Only return the translated stem, nothing else.\n\n"
            f"Stem: {stem}"
        )
        try:
            content = self.client.generate_text(
                system_prompt="You translate short filename stems.",
                user_prompt=prompt,
                json_mode=False,
                temperature=0.2,
            )
            content = content.replace("/", "-").replace("\\", "-").strip()
            if not content:
                return None
            return f"{content}{ext}"
        except AIProviderError:
            return None

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        if not titles:
            return []
        stems: List[str] = []
        exts: List[str] = []
        for title in titles:
            m = _EXT_RE.match(title)
            stems.append((m.group("stem") if m else title) or "")
            exts.append((m.group("ext") if m else "") or "")
        prompt = (
            "Translate each filename stem below into "
            f"{target_language}. Return ONLY a JSON array of strings where each element is the translated stem "
            "for the corresponding input. No extra text.\n\n"
            "Input stems as JSON array:\n" + json.dumps(stems, ensure_ascii=False)
        )
        try:
            content = self.client.generate_text(
                system_prompt="You translate short filename stems.",
                user_prompt=prompt,
                json_mode=True,
                temperature=0.2,
            )
        except AIProviderError:
            return [None] * len(stems)
        out: List[Optional[str]] = [None] * len(stems)
        try:
            arr = json.loads(content)
            if isinstance(arr, list):
                for i, value in enumerate(arr[: len(stems)]):
                    if isinstance(value, str):
                        clean = value.replace("/", "-").replace("\\", "-").strip()
                        out[i] = clean + (exts[i] or "")
                return out
        except Exception:
            pass
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        for i in range(min(len(lines), len(stems))):
            clean = lines[i].replace("/", "-").replace("\\", "-").strip()
            out[i] = clean + (exts[i] or "")
        return out

    def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        if not texts:
            return []
        request_payload = {
            "instruction": (
                "Translate each entry in the provided list into "
                f"{target_language}. Return a JSON object with a key 'translations' "
                "containing an array of translated strings aligned with the input order."
            ),
            "texts": texts,
        }
        try:
            content = self.client.generate_text(
                system_prompt=(
                    "You are a professional translator. Translate user provided text into the requested language. "
                    "Preserve meaning and formatting. Return only the translated text."
                ),
                user_prompt=json.dumps(request_payload, ensure_ascii=False),
                json_mode=True,
                temperature=0.2,
            )
        except AIProviderError:
            return list(texts)
        try:
            data = json.loads(content)
            items = data.get("translations") if isinstance(data, dict) else None
            if isinstance(items, list) and len(items) == len(texts):
                return [
                    (item or "").strip() if isinstance(item, str) and (item or "").strip() else original
                    for item, original in zip(items, texts)
                ]
        except Exception:
            pass
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        if len(lines) >= len(texts):
            return [lines[i] if lines[i] else original for i, original in enumerate(texts)]
        return list(texts)
