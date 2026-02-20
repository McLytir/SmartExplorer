from __future__ import annotations

import atexit
import json
import os
import threading
import time
from typing import Optional, Dict


CACHE_FILENAME = "smart_explorer_cache.json"


class TranslationCache:
    def __init__(self, path: Optional[str] = None, *, save_interval_seconds: float = 1.0) -> None:
        self._path = os.path.abspath(path or CACHE_FILENAME)
        self._lock = threading.Lock()
        self._save_interval = max(0.0, float(save_interval_seconds))
        self._dirty = False
        self._last_save_monotonic = 0.0
        # by_path: namespace -> composite_key -> translated
        self._data_by_path: Dict[str, Dict[str, str]] = {}
        # by_name: namespace -> name -> translated (fallback when path/mtime unknown)
        self._data_by_name: Dict[str, Dict[str, str]] = {}
        self._load()
        atexit.register(self.flush)

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Backward compatibility: older versions stored only by_path in root
                if isinstance(raw, dict) and ("by_path" in raw or "by_name" in raw):
                    self._data_by_path = dict(raw.get("by_path", {}))
                    self._data_by_name = dict(raw.get("by_name", {}))
                else:
                    # Assume raw is old by_path mapping
                    self._data_by_path = dict(raw or {})
        except Exception:
            self._data_by_path = {}
            self._data_by_name = {}

    def _save(self, *, force: bool = False) -> None:
        payload = None
        now = time.monotonic()
        with self._lock:
            if not self._dirty:
                return
            if not force and (now - self._last_save_monotonic) < self._save_interval:
                return
            payload = {
                "by_path": self._data_by_path,
                "by_name": self._data_by_name,
            }
            self._dirty = False
            self._last_save_monotonic = now
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            with self._lock:
                self._dirty = True

    @staticmethod
    def _key(namespace: str, file_path: str, name: str, mtime: float) -> str:
        # Store by namespace + path + mtime + current name to keep it stable
        return f"{namespace}\n{file_path}\n{mtime}\n{name}"

    def get(self, namespace: str, file_path: str, name: str, mtime: float) -> Optional[str]:
        key = self._key(namespace, file_path, name, mtime)
        with self._lock:
            return self._data_by_path.get(namespace, {}).get(key)

    def set(self, namespace: str, file_path: str, name: str, mtime: float, translated: str) -> None:
        key = self._key(namespace, file_path, name, mtime)
        with self._lock:
            bucket = self._data_by_path.setdefault(namespace, {})
            bucket[key] = translated
            self._dirty = True
        self._save()

    # Name-only fallback cache
    def get_by_name(self, namespace: str, name: str) -> Optional[str]:
        with self._lock:
            return self._data_by_name.get(namespace, {}).get(name)

    def set_by_name(self, namespace: str, name: str, translated: str) -> None:
        with self._lock:
            bucket = self._data_by_name.setdefault(namespace, {})
            bucket[name] = translated
            self._dirty = True
        self._save()

    def flush(self) -> None:
        self._save(force=True)
