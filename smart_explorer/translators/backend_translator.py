from __future__ import annotations

from typing import List, Optional

from ..api.backend_client import BackendClient
from .base import Translator


class BackendTranslator(Translator):
    def __init__(self, base_url: str = "http://127.0.0.1:5001") -> None:
        self.client = BackendClient(base_url)
        self._base_url = self.client.base_url

    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        try:
            resp = self.client.post(
                "/api/translate",
                json={"language": target_language, "items": [{"name": title}]},
            )
            arr = resp.get("translations", [])
            if arr and isinstance(arr[0], str) and arr[0]:
                return arr[0]
        except Exception:
            return None
        return None

    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        try:
            items = [{"name": t} for t in titles]
            resp = self.client.post(
                "/api/translate",
                json={"language": target_language, "items": items},
            )
            arr = resp.get("translations", [])
            out: List[Optional[str]] = []
            for i in range(len(titles)):
                v = arr[i] if i < len(arr) else None
                out.append(v if isinstance(v, str) and v else None)
            return out
        except Exception:
            return [None] * len(titles)

    def cache_namespace(self) -> str:
        return f"backend:{self._base_url}"

    def translate_texts(self, texts: List[str], target_language: str) -> List[str]:
        try:
            resp = self.client.post(
                "/api/translate/text",
                json={"language": target_language, "texts": texts},
            )
            arr = resp.get("translations", []) if isinstance(resp, dict) else []
            if isinstance(arr, list) and len(arr) == len(texts):
                return [
                    item.strip() if isinstance(item, str) and item.strip() else orig
                    for item, orig in zip(arr, texts)
                ]
            return list(texts)
        except Exception:
            return list(texts)
