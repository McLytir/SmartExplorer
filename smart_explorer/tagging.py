from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


_DEFAULT_FILENAME = ".smart_tags.json"


@dataclass
class TagEntry:
    tags: List[str]
    missing: bool = False

    def to_dict(self) -> dict:
        return {"tags": list(self.tags), "missing": self.missing}

    @staticmethod
    def from_dict(data: dict) -> "TagEntry":
        tags = [str(t).strip() for t in data.get("tags", []) if str(t).strip()]
        missing = bool(data.get("missing", False))
        return TagEntry(tags=tags, missing=missing)


class TagStore:
    """Simple per-root tag repository stored in a hidden JSON sidecar."""

    VERSION = 1

    def __init__(self, root_path: str, filename: str = _DEFAULT_FILENAME) -> None:
        self.root_path = os.path.abspath(root_path)
        self.filename = filename
        self.sidecar_path = os.path.join(self.root_path, self.filename)
        self._entries: Dict[str, TagEntry] = {}
        self._dirty = False
        self._load()

    # ------------------------------------------------------------------ basics
    def _load(self) -> None:
        if not os.path.isdir(self.root_path):
            return
        if not os.path.exists(self.sidecar_path):
            return
        try:
            with open(self.sidecar_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception:
            payload = {}
        entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
        for rel, data in entries.items():
            if isinstance(rel, str) and isinstance(data, dict):
                entry = TagEntry.from_dict(data)
                if entry.tags:
                    self._entries[rel] = entry
        # drop empties automatically
        if len(self._entries) != len(entries):
            self._dirty = True
            self._save()

    def _save(self) -> None:
        if not self._dirty:
            return
        if not os.path.isdir(self.root_path):
            try:
                os.makedirs(self.root_path, exist_ok=True)
            except Exception:
                return
        data = {
            "version": self.VERSION,
            "entries": {rel: entry.to_dict() for rel, entry in self._entries.items()},
        }
        try:
            with open(self.sidecar_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            pass
        self._dirty = False

    # ---------------------------------------------------------------- helpers
    def _rel(self, path: str) -> str | None:
        if not path:
            return None
        try:
            rel = os.path.relpath(os.path.abspath(path), self.root_path)
        except Exception:
            return None
        if rel.startswith(".."):
            return None
        rel = os.path.normpath(rel)
        return rel.replace(os.sep, "/")

    def _abs(self, rel: str) -> str:
        return os.path.join(self.root_path, rel.replace("/", os.sep))

    def _normalize_tags(self, tags: Iterable[str]) -> List[str]:
        seen = set()
        clean: List[str] = []
        for tag in tags:
            t = str(tag).strip()
            if not t:
                continue
            key = t.lower()
            if key not in seen:
                seen.add(key)
                clean.append(t)
        return clean

    def _set_entry(self, rel: str, tags: List[str], missing: bool | None = None) -> None:
        if not tags:
            if rel in self._entries:
                self._entries.pop(rel, None)
                self._dirty = True
            return
        entry = self._entries.get(rel)
        if not entry:
            entry = TagEntry(tags=list(tags), missing=bool(missing))
            self._entries[rel] = entry
            self._dirty = True
            return
        if entry.tags != tags or (missing is not None and entry.missing != missing):
            entry.tags = list(tags)
            if missing is not None:
                entry.missing = bool(missing)
            self._dirty = True

    # ----------------------------------------------------------------- public
    def reconcile(self) -> Tuple[List[Tuple[str, str]], List[str]]:
        """Ensure stored entries still point to existing files.

        Returns (relocations, orphans).
        """
        if not os.path.isdir(self.root_path):
            return ([], list(self._entries.keys()))
        missing = [rel for rel in list(self._entries.keys()) if not os.path.exists(self._abs(rel))]
        if not missing:
            return ([], [])
        name_targets = {os.path.basename(rel): rel for rel in missing}
        lower_targets = {name.lower(): name for name in name_targets}
        found: Dict[str, str] = {}
        remaining = set(lower_targets.keys())
        if remaining:
            for dirpath, _, filenames in os.walk(self.root_path):
                for fname in filenames:
                    key = fname.lower()
                    if key not in remaining:
                        continue
                    rel = self._rel(os.path.join(dirpath, fname))
                    if rel is None:
                        continue
                    original_name = lower_targets[key]
                    if original_name not in found:
                        found[original_name] = rel
                    remaining.discard(key)
                if not remaining:
                    break
        relocations: List[Tuple[str, str]] = []
        orphans: List[str] = []
        for original_name, old_rel in name_targets.items():
            new_rel = found.get(original_name)
            entry = self._entries.get(old_rel)
            if entry is None:
                continue
            if new_rel and new_rel != old_rel:
                self._entries[new_rel] = entry
                self._entries.pop(old_rel, None)
                entry.missing = False
                relocations.append((old_rel, new_rel))
            else:
                entry.missing = True
                orphans.append(old_rel)
        if relocations or orphans:
            self._dirty = True
            self._save()
        return relocations, orphans

    def tags_for(self, path: str) -> List[str]:
        rel = self._rel(path)
        if rel is None:
            return []
        entry = self._entries.get(rel)
        return list(entry.tags) if entry else []

    def set_tags(self, path: str, tags: Iterable[str]) -> None:
        rel = self._rel(path)
        if rel is None:
            return
        clean = self._normalize_tags(tags)
        self._set_entry(rel, clean, missing=False)
        self._save()

    def add_tag(self, path: str, tag: str) -> None:
        rel = self._rel(path)
        if rel is None:
            return
        entry = self._entries.get(rel)
        if not entry:
            self.set_tags(path, [tag])
            return
        tags = self._normalize_tags(entry.tags + [tag])
        self._set_entry(rel, tags, missing=False)
        self._save()

    def remove_tag(self, path: str, tag: str) -> None:
        rel = self._rel(path)
        if rel is None:
            return
        entry = self._entries.get(rel)
        if not entry:
            return
        tags = [t for t in entry.tags if t.lower() != tag.lower()]
        self._set_entry(rel, tags, missing=entry.missing)
        self._save()

    def clear(self, path: str, is_dir: bool = False) -> None:
        rel = self._rel(path)
        if rel is None:
            return
        removed = False
        if is_dir:
            prefix = rel + "/"
            for key in list(self._entries.keys()):
                if key == rel or key.startswith(prefix):
                    self._entries.pop(key, None)
                    removed = True
        else:
            if rel in self._entries:
                self._entries.pop(rel, None)
                removed = True
        if removed:
            self._dirty = True
            self._save()

    def move(self, old_path: str, new_path: str, is_dir: bool = False) -> None:
        old_rel = self._rel(old_path)
        new_rel = self._rel(new_path)
        if old_rel is None or new_rel is None or old_rel == new_rel:
            return
        changed = False
        if is_dir:
            prefix = old_rel + "/"
            for key in list(self._entries.keys()):
                if key == old_rel or key.startswith(prefix):
                    entry = self._entries.pop(key)
                    suffix = key[len(old_rel):]
                    new_key = new_rel + suffix
                    entry.missing = False
                    self._entries[new_key] = entry
                    changed = True
        else:
            entry = self._entries.pop(old_rel, None)
            if entry:
                entry.missing = False
                self._entries[new_rel] = entry
                changed = True
        if changed:
            self._dirty = True
            self._save()

    def duplicate(self, source_path: str, new_path: str, is_dir: bool = False) -> None:
        src_rel = self._rel(source_path)
        new_rel = self._rel(new_path)
        if src_rel is None or new_rel is None:
            return
        added = False
        if is_dir:
            prefix = src_rel + "/"
            for key, entry in list(self._entries.items()):
                if key == src_rel or key.startswith(prefix):
                    suffix = key[len(src_rel):]
                    new_key = new_rel + suffix
                    if new_key not in self._entries:
                        self._entries[new_key] = TagEntry(tags=list(entry.tags), missing=False)
                        added = True
        else:
            entry = self._entries.get(src_rel)
            if entry and new_rel not in self._entries:
                self._entries[new_rel] = TagEntry(tags=list(entry.tags), missing=False)
                added = True
        if added:
            self._dirty = True
            self._save()

    def entries_under(self, path: str, is_dir: bool = False) -> List[Tuple[str, List[str]]]:
        rel = self._rel(path)
        if rel is None:
            return []
        results: List[Tuple[str, List[str]]] = []
        if is_dir:
            prefix = rel + "/"
            for key, entry in self._entries.items():
                if key == rel or key.startswith(prefix):
                    suffix = key[len(rel):].lstrip('/')
                    results.append((suffix, list(entry.tags)))
        else:
            entry = self._entries.get(rel)
            if entry:
                results.append(("", list(entry.tags)))
        return results

    def remove_if_missing(self, path: str) -> None:
        self.clear(path)

    def all_tags(self) -> List[str]:
        seen = set()
        out: List[str] = []
        for entry in self._entries.values():
            for tag in entry.tags:
                key = tag.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(tag)
        return out

    def tagged_paths(self) -> List[Tuple[str, List[str]]]:
        return [(rel, list(entry.tags)) for rel, entry in self._entries.items()]

    def __len__(self) -> int:
        return len(self._entries)
