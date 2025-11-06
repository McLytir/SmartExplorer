from __future__ import annotations

from functools import lru_cache
from typing import Iterable, List

try:
    from deep_translator import GoogleTranslator  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    GoogleTranslator = None  # type: ignore


def _normalize_language(lang: str) -> str:
    if not lang:
        return lang
    low = lang.strip().lower()
    # handle common aliases manually
    aliases = {
        "chinese (simplified)": "zh-CN",
        "chinese (traditional)": "zh-TW",
        "mandarin": "zh-CN",
        "cantonese": "zh-TW",
        "english": "en",
        "japanese": "ja",
        "korean": "ko",
        "german": "de",
        "french": "fr",
        "spanish": "es",
        "portuguese": "pt",
        "italian": "it",
        "russian": "ru",
    }
    if low in aliases:
        return aliases[low]
    return low


@lru_cache(maxsize=48)
def _translator_for(source: str, target: str):
    if GoogleTranslator is None:
        return None
    try:
        norm_source = _normalize_language(source or "auto")
        norm_target = _normalize_language(target or "english")
        return GoogleTranslator(source=norm_source, target=norm_target)
    except Exception:
        return None


def translate_texts(texts: Iterable[str], target_language: str, *, source_language: str = "auto") -> List[str]:
    """
    Translate an iterable of texts to the target language.

    Uses deep-translator's Google backend (best-effort, unofficial).
    Returns original text if translation fails or dependency missing.
    """
    sequence = list(texts)
    if not sequence:
        return []

    translator = _translator_for(source_language, target_language)
    if translator is None:
        return list(sequence)

    out: List[str] = ["" for _ in sequence]

    # Attempt batch translate first (if supported by installed version)
    try:
        batch = translator.translate_batch(sequence)  # type: ignore[attr-defined]
        if isinstance(batch, list) and len(batch) == len(sequence):
            for idx, value in enumerate(batch):
                if isinstance(value, str) and value.strip():
                    out[idx] = value.strip()
                else:
                    out[idx] = sequence[idx]
            return out
    except Exception:
        pass

    # Fallback to per-item translation
    for idx, text in enumerate(sequence):
        stripped = text.strip()
        if not stripped:
            out[idx] = ""
            continue
        try:
            value = translator.translate(stripped)
            out[idx] = value.strip() if isinstance(value, str) and value.strip() else stripped
        except Exception:
            out[idx] = stripped

    return out
