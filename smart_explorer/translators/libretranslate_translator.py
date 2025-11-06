from __future__ import annotations

import re
from typing import List, Optional

import httpx

from .base import Translator


_EXT_RE = re.compile(r"^(?P<stem>.*?)(?P<ext>\.[^./\\]+)?$")


class LibreTranslateTranslator(Translator):
    """
    Translator using a LibreTranslate-compatible server.

    Default base URL is a common public instance, but it is recommended to
    self-host or configure a trusted endpoint via settings.
    """

    def __init__(self, base_url: str = "https://libretranslate.de", api_key: Optional[str] = None, source_language: str = "auto") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.source_language = source_language

    def cache_namespace(self) -> str:
        return f"libretranslate:{self.base_url}"

    def _post(self, path: str, json_body: dict) -> Optional[dict]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=json_body)
                if resp.status_code != 200:
                    return None
                return resp.json()
        except Exception:
            return None

    def _translate_stem(self, stem: str, target_language: str) -> Optional[str]:
        if not stem:
            return None
        body = {
            "q": stem,
            "source": self.source_language,
            "target": target_language,
            "format": "text",
        }
        if self.api_key:
            body["api_key"] = self.api_key
        data = self._post("/translate", body)
        if not data:
            return None
        # API returns {"translatedText": "..."}
        text = data.get("translatedText") if isinstance(data, dict) else None
        if not isinstance(text, str):
            return None
        s = text.replace("/", "-").replace("\\", "-").strip()
        return s or None

    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        m = _EXT_RE.match(title)
        if not m:
            stem, ext = title, ""
        else:
            stem = m.group("stem") or ""
            ext = m.group("ext") or ""
        s = self._translate_stem(stem, target_language)
        return (s + ext) if s else None

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        if not titles:
            return []
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

        # Try batch: many LT servers accept array for q and return list
        body = {
            "q": stems,
            "source": self.source_language,
            "target": target_language,
            "format": "text",
        }
        if self.api_key:
            body["api_key"] = self.api_key
        data = self._post("/translate", body)
        out: List[Optional[str]] = [None] * len(stems)
        if isinstance(data, list):
            # Some servers return list of { translatedText }
            for i, item in enumerate(data[: len(stems)]):
                txt = item.get("translatedText") if isinstance(item, dict) else None
                if isinstance(txt, str):
                    s = txt.replace("/", "-").replace("\\", "-").strip()
                    out[i] = (s + (exts[i] or "")) if s else None
            return out
        if isinstance(data, dict) and isinstance(data.get("translatedText"), str) and len(stems) == 1:
            s = data["translatedText"].replace("/", "-").replace("\\", "-").strip()
            out[0] = (s + (exts[0] or "")) if s else None
            return out

        # Fallback: per-item requests
        for i, stem in enumerate(stems):
            out[i] = self._translate_stem(stem, target_language)
            if isinstance(out[i], str):
                out[i] = out[i] + (exts[i] or "")
        return out

    def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        if not texts:
            return []

        body = {
            "q": texts,
            "source": self.source_language,
            "target": target_language,
            "format": "text",
        }
        if self.api_key:
            body["api_key"] = self.api_key

        data = self._post("/translate", body)
        out: List[str] = list(texts)
        if isinstance(data, list):
            for idx, item in enumerate(data[: len(texts)]):
                txt = item.get("translatedText") if isinstance(item, dict) else None
                if isinstance(txt, str) and txt.strip():
                    out[idx] = txt.strip()
            return out
        if isinstance(data, dict) and isinstance(data.get("translatedText"), str) and len(texts) == 1:
            txt = data["translatedText"].strip()
            return [txt or texts[0]]

        # Fallback per-item
        for idx, txt in enumerate(texts):
            translated = self._translate_stem(txt, target_language)
            out[idx] = translated if isinstance(translated, str) and translated else txt
        return out
