from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def _default_store_path() -> Path:
    base = os.getenv("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    root = Path(base) / "smart_explorer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "tags.json"


class TagStore:
    def __init__(self, store_path: Optional[Path] = None) -> None:
        self._path = store_path or _default_store_path()
        self._data: Dict[str, Dict[str, List[str]]] = {"local": {}, "sharepoint": {}}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._data["local"] = data.get("local", {})
                self._data["sharepoint"] = data.get("sharepoint", {})
        except Exception:
            self._data = {"local": {}, "sharepoint": {}}

    def _save(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def _normalize(kind: str, identifier: str) -> str:
        if kind == "local":
            return os.path.abspath(os.path.expanduser(identifier))
        return identifier.strip()

    def get_tags(self, kind: str, identifier: str) -> List[str]:
        kind_key = "sharepoint" if kind == "sharepoint" else "local"
        key = self._normalize(kind_key, identifier)
        tags = self._data.get(kind_key, {}).get(key, [])
        return list(tags)

    def set_tags(self, kind: str, identifier: str, tags: List[str]) -> None:
        kind_key = "sharepoint" if kind == "sharepoint" else "local"
        key = self._normalize(kind_key, identifier)
        cleaned = sorted({tag.strip().lower() for tag in tags if tag.strip()})
        if not cleaned:
            self._data.get(kind_key, {}).pop(key, None)
        else:
            self._data.setdefault(kind_key, {})[key] = cleaned
        self._save()

    def search(self, kind: str, tag: str) -> List[str]:
        kind_key = "sharepoint" if kind == "sharepoint" else "local"
        tag_lower = tag.strip().lower()
        matches: List[str] = []
        if not tag_lower:
            return matches
        for key, tags in self._data.get(kind_key, {}).items():
            if tag_lower in tags:
                matches.append(key)
        return matches

    def all_tags(self, kind: Optional[str] = None) -> List[str]:
        kinds = []
        if kind is None:
            kinds = ["local", "sharepoint"]
        else:
            kinds = ["sharepoint" if kind == "sharepoint" else "local"]
        tags: set[str] = set()
        for k in kinds:
            for entries in self._data.get(k, {}).values():
                for tag in entries:
                    tags.add(tag)
        return sorted(tags)

    def tag_stats(self, kind: Optional[str] = None) -> List[tuple[str, int]]:
        kinds = []
        if kind is None:
            kinds = ["local", "sharepoint"]
        else:
            kinds = ["sharepoint" if kind == "sharepoint" else "local"]
        counts: dict[str, int] = {}
        for k in kinds:
            for entries in self._data.get(k, {}).values():
                for tag in entries:
                    counts[tag] = counts.get(tag, 0) + 1
        return sorted(counts.items(), key=lambda item: item[0])

    def remove_tag_everywhere(self, kind: str, tag: str) -> bool:
        kind_key = "sharepoint" if kind == "sharepoint" else "local"
        tag_lower = tag.strip().lower()
        if not tag_lower:
            return False
        changed = False
        kind_data = self._data.get(kind_key, {})
        for key in list(kind_data.keys()):
            tags = kind_data.get(key, [])
            if tag_lower in tags:
                remaining = [t for t in tags if t != tag_lower]
                if remaining:
                    kind_data[key] = remaining
                else:
                    kind_data.pop(key, None)
                changed = True
        if changed:
            self._save()
        return changed

    def find_paths_for_tags(self, kind: str, tags: List[str]) -> List[dict]:
        kind_key = "sharepoint" if kind == "sharepoint" else "local"
        query = [segment.strip().lower() for segment in tags if segment.strip()]
        if not query:
            return []
        results: list[dict] = []
        for path, tag_list in self._data.get(kind_key, {}).items():
            matched = [tag for tag in query if tag in tag_list]
            if not matched:
                continue
            results.append(
                {
                    "path": path,
                    "matched": sorted(matched),
                    "tags": list(tag_list),
                }
            )
        results.sort(key=lambda item: item["path"].lower())
        return results


__all__ = ["TagStore"]
