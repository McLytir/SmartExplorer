from __future__ import annotations

import re
from typing import List, Optional

from .base import Translator

try:
    # deep-translator provides an unofficial Google Translate client
    from deep_translator import GoogleTranslator as _DGTranslator  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _DGTranslator = None  # type: ignore


_EXT_RE = re.compile(r"^(?P<stem>.*?)(?P<ext>\.[^./\\]+)?$")


class GoogleFreeTranslator(Translator):
    """
    Lightweight translator via deep-translator's Google backend.

    Notes:
    - This uses an unofficial Google Translate endpoint and may be brittle or
      subject to rate limits/ToS changes. Treat as best-effort.
    - Returns None on failure so callers can fall back gracefully.
    """

    def __init__(self, source_language: str = "auto") -> None:
        self.source_language = source_language

    def cache_namespace(self) -> str:
        return "google-free"

    def _translate_stem(self, stem: str, target_language: str) -> Optional[str]:
        if not stem:
            return None
        try:
            if _DGTranslator is None:
                return None
            translator = _DGTranslator(source=self.source_language, target=target_language)
            out = translator.translate(stem)
            if not isinstance(out, str):
                return None
            s = out.replace("/", "-").replace("\\", "-").strip()
            return s or None
        except Exception:
            return None

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

        out: List[Optional[str]] = [None] * len(stems)
        try:
            if _DGTranslator is None:
                # no dependency available; fall back to per-item None
                return out
            translator = _DGTranslator(source=self.source_language, target=target_language)
            # deep-translator supports batch translate, but we guard if it changes
            try:
                batch = translator.translate_batch(stems)
                if isinstance(batch, list):
                    for i, v in enumerate(batch[: len(stems)]):
                        if isinstance(v, str):
                            s = v.replace("/", "-").replace("\\", "-").strip()
                            out[i] = (s + (exts[i] or "")) if s else None
                    return out
            except Exception:
                pass
            # Fallback: translate one by one
            for i, stem in enumerate(stems):
                s = translator.translate(stem)
                if isinstance(s, str):
                    s = s.replace("/", "-").replace("\\", "-").strip()
                out[i] = (s + (exts[i] or "")) if (isinstance(s, str) and s) else None
            return out
        except Exception:
            return [None] * len(stems)

    def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        if not texts:
            return []
        out: List[str] = list(texts)
        try:
            if _DGTranslator is None:
                return out
            translator = _DGTranslator(source=self.source_language, target=target_language)
            try:
                batch = translator.translate_batch(texts)
                if isinstance(batch, list) and len(batch) == len(texts):
                    return [
                        item.strip() if isinstance(item, str) and item.strip() else orig
                        for item, orig in zip(batch, texts)
                    ]
            except Exception:
                pass
            for idx, txt in enumerate(texts):
                try:
                    res = translator.translate(txt)
                    out[idx] = res.strip() if isinstance(res, str) and res.strip() else txt
                except Exception:
                    out[idx] = txt
            return out
        except Exception:
            return list(texts)
