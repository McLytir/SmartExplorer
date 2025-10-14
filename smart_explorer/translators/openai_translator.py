from __future__ import annotations

import re
from typing import Optional, List
import json

from openai import OpenAI

from .base import Translator


_EXT_RE = re.compile(r"^(?P<stem>.*?)(?P<ext>\.[^./\\]+)?$")


class OpenAITranslator(Translator):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        m = _EXT_RE.match(title)
        if not m:
            stem, ext = title, ""
        else:
            stem = m.group("stem") or ""
            ext = m.group("ext") or ""

        prompt = (
            "Translate the following filename stem into "
            f"{target_language}. Do not include any punctuation or quotes. "
            "Keep it concise and natural in the target language. "
            "Only return the translated stem, nothing else.\n\n"
            f"Stem: {stem}"
        )

        try:
            # Use Responses API if available in this SDK version
            try:
                resp = self.client.responses.create(
                    model=self.model,
                    input=prompt,
                )
                content = resp.output_text.strip()
            except Exception:
                # Fallback to chat.completions for older versions
                chat = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You translate short filename stems."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = chat.choices[0].message.content.strip()

            # Basic sanitization: avoid path separators, trim whitespace
            content = content.replace("/", "-").replace("\\", "-").strip()
            if not content:
                return None
            return f"{content}{ext}"
        except Exception:
            return None

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        if not titles:
            return []

        # Separate stems and extensions per title
        stems: List[str] = []
        exts: List[str] = []
        for t in titles:
            m = _EXT_RE.match(t)
            if not m:
                stems.append(t)
                exts.append("")
            else:
                stems.append(m.group("stem") or "")
                exts.append(m.group("ext") or "")

        sys_prompt = "You translate short filename stems into the requested language."
        user_prompt = (
            "Translate each filename stem below into "
            f"{target_language}. Return ONLY a JSON array of strings where each element is the translated stem for the corresponding input. "
            "Do not include quotes around the whole array except as JSON requires; no extra text. Keep translations concise and natural.\n\n"
            "Input stems as JSON array:\n" + json.dumps(stems, ensure_ascii=False)
        )

        try:
            try:
                resp = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = resp.output_text.strip()
            except Exception:
                chat = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                )
                content = chat.choices[0].message.content.strip()

            # Parse JSON array
            out: List[Optional[str]] = [None] * len(stems)
            try:
                arr = json.loads(content)
                if isinstance(arr, list):
                    for i, v in enumerate(arr[: len(stems)]):
                        if isinstance(v, str):
                            s = v.replace("/", "-").replace("\\", "-").strip()
                            out[i] = s + (exts[i] or "")
            except Exception:
                # Fallback: try line-splitting
                lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
                for i in range(min(len(lines), len(stems))):
                    s = lines[i].replace("/", "-").replace("\\", "-").strip()
                    out[i] = s + (exts[i] or "")

            # Fill any missing entries with None to signal fallback
            return out
        except Exception:
            return [None] * len(stems)
