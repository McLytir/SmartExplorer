from __future__ import annotations

import fnmatch
import os
from typing import Dict, Optional

from PySide6.QtCore import QIdentityProxyModel, QModelIndex, Qt, QThreadPool, QRunnable, QObject, Signal

from ..translators.base import Translator
from ..translation_cache import TranslationCache

# Optional role used by non-QFileSystemModel sources to provide a path
PATH_ROLE = Qt.UserRole + 1
TRANSLATION_ROLE = Qt.UserRole + 2


class _TranslateJobSignals(QObject):
    done = Signal(str, str)  # path, translated_name
    fail = Signal(str)       # path


class _TranslateJob(QRunnable):
    def __init__(self, path: str, title: str, lang: str, translator: Translator, signals: _TranslateJobSignals) -> None:
        super().__init__()
        self.path = path
        self.title = title
        self.lang = lang
        self.translator = translator
        self.signals = signals

    def run(self) -> None:
        try:
            res = self.translator.translate_title(self.title, self.lang)
            if res:
                self.signals.done.emit(self.path, res)
            else:
                self.signals.fail.emit(self.path)
        except Exception:
            self.signals.fail.emit(self.path)


class TranslatedProxyModel(QIdentityProxyModel):
    def __init__(self, translator: Translator, target_language: str, parent=None, *,
                 cache: Optional[TranslationCache] = None,
                 ignore_patterns: Optional[list[str]] = None,
                 display_mode: str = "replace",
                 enabled: bool = True):
        super().__init__(parent)
        self._translator = translator
        self._target_language = target_language
        self._display_mode = display_mode
        self._enabled = enabled
        self._cache: Dict[str, str] = {}
        self._pending: Dict[str, bool] = {}
        self._pool = QThreadPool.globalInstance()
        self._disk_cache = cache
        self._ignore_patterns = ignore_patterns or []
        # Translation scope: by default we translate everything; once a root is
        # set we restrict automatic translations to that folder (and optionally
        # any user-added scopes).
        self._scope_limits: Dict[str, Optional[int]] = {}  # path -> max depth from scope (None = unlimited)
        self._active_root: Optional[str] = None

        self._signals = _TranslateJobSignals()
        self._signals.done.connect(self._on_done)
        self._signals.fail.connect(self._on_fail)

    def _cache_namespace(self) -> str:
        key = "default"
        if hasattr(self._translator, "cache_namespace"):
            try:
                key = self._translator.cache_namespace()
            except Exception:
                key = self._translator.__class__.__name__
        return f"{self._target_language}|{key}"

    def set_target_language(self, language: str) -> None:
        if language != self._target_language:
            self._target_language = language
            self._cache.clear()
            self._pending.clear()
            # Refresh all visible rows
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount() - 1, 0)
            self.dataChanged.emit(top_left, bottom_right)

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self._refresh_all_rows()

    def set_display_mode(self, mode: str) -> None:
        mode = mode or "replace"
        if mode == self._display_mode:
            return
        self._display_mode = mode
        self._refresh_all_rows()

    def set_translator(self, translator: Translator) -> None:
        self._translator = translator
        self._cache.clear()
        self._pending.clear()
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, 0)
        self.dataChanged.emit(top_left, bottom_right)

    def set_active_root(self, path: Optional[str]) -> None:
        """
        Restrict automatic translations to the current folder. Depth is limited
        to the immediate children of the root (distance <= 1). Users can extend
        scope with add_scope().
        """
        normalized = self._normalize_path(path)
        if normalized == self._active_root and self._scope_limits:
            return
        self._active_root = normalized
        self._scope_limits = {normalized: 1} if normalized else {}
        self._refresh_all_rows()

    def add_scope(self, path: str, *, depth_limit: Optional[int] = None) -> None:
        """
        Allow translations for an additional subtree (e.g., user-requested).
        depth_limit=None means translate recursively; otherwise distance limit
        from the scope root.
        """
        normalized = self._normalize_path(path)
        if not normalized:
            return
        existing = self._scope_limits.get(normalized)
        if existing is not None and depth_limit is not None and depth_limit <= existing:
            return
        self._scope_limits[normalized] = depth_limit
        self._refresh_all_rows()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return super().data(index, role)
        if index.column() != 0:
            return super().data(index, role)
        if role in (Qt.DisplayRole, TRANSLATION_ROLE):
            src_idx = self.mapToSource(index)
            # Try QFileSystemModel-style API first
            path = None
            name = None
            src_model = self.sourceModel()
            if hasattr(src_model, "filePath") and hasattr(src_model, "fileName"):
                try:
                    path = src_model.filePath(src_idx)  # type: ignore[attr-defined]
                    name = src_model.fileName(src_idx)  # type: ignore[attr-defined]
                except Exception:
                    path = None
                    name = None
            # Fallback to roles
            if path is None:
                path = src_model.data(src_idx, PATH_ROLE)
            if name is None:
                name = src_model.data(src_idx, Qt.DisplayRole)
            name = str(name or "")

            if role == TRANSLATION_ROLE:
                if not self._enabled or self._is_ignored(path, name) or not self._is_in_scope(path):
                    return ""
                translated = self._translated_value(path, name)
                return translated if translated and translated != name else ""

            # Skip translating ignored paths
            if self._is_ignored(path, name):
                return name

            if not self._is_in_scope(path):
                return name

            if not self._enabled:
                return name

            translated = self._translated_value(path, name)
            if not translated or translated == name:
                return name
            if self._display_mode == "below_name":
                return f"{name}\n{translated}"
            return translated
        return super().data(index, role)

    def _translated_value(self, path: str, name: str) -> str:
        if path in self._cache:
            return self._cache[path]

        mtime = 0.0
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            pass
        if self._disk_cache:
            namespace = self._cache_namespace()
            cached = self._disk_cache.get(namespace, path, name, mtime)
            if not cached:
                cached = self._disk_cache.get_by_name(namespace, name)
            if cached:
                self._cache[path] = cached
                return cached

        if path not in self._pending:
            self._pending[path] = True
            job = _TranslateJob(path, name, self._target_language, self._translator, self._signals)
            self._pool.start(job)
        return ""

    def _on_done(self, path: str, translated: str) -> None:
        self._cache[path] = translated
        self._pending.pop(path, None)
        if self._disk_cache:
            name = os.path.basename(path)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = 0.0
            namespace = self._cache_namespace()
            self._disk_cache.set(namespace, path, name, mtime, translated)
            self._disk_cache.set_by_name(namespace, name, translated)
        # Find the index and notify view
        src_model = self.sourceModel()
        if not hasattr(src_model, "index"):
            return
        # We can't easily find by path; trigger a light refresh
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, 0)
        self.dataChanged.emit(top_left, bottom_right)

    def _on_fail(self, path: str) -> None:
        self._pending.pop(path, None)
        # No update; keep original name

    def _is_ignored(self, path: str, name: str) -> bool:
        # Check each segment and full name against ignore patterns
        parts = os.path.normpath(path).split(os.sep)
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _normalize_path(self, path: Optional[str]) -> str:
        if path is None:
            return ""
        p = str(path).replace("\\", "/").strip()
        while "//" in p:
            p = p.replace("//", "/")
        return p.rstrip("/") if p not in ("/", "") else p

    def _is_in_scope(self, path: Optional[str]) -> bool:
        normalized = self._normalize_path(path)
        if not normalized:
            return False
        # If no scope set, allow translations everywhere (legacy behavior)
        if not self._scope_limits:
            return True
        for scope, depth_limit in self._scope_limits.items():
            if not scope:
                continue
            if self._is_descendant(normalized, scope):
                if depth_limit is None:
                    return True
                return self._distance_from_scope(normalized, scope) <= depth_limit
        return False

    def _is_descendant(self, path: str, scope: str) -> bool:
        p = self._normalize_path(path)
        s = self._normalize_path(scope)
        if not s:
            return False
        if s == "/":
            return True
        return p == s or p.startswith(s + "/")

    def _distance_from_scope(self, path: str, scope: str) -> int:
        p_parts = [seg for seg in self._normalize_path(path).split("/") if seg]
        s_parts = [seg for seg in self._normalize_path(scope).split("/") if seg]
        return max(0, len(p_parts) - len(s_parts))

    def _refresh_all_rows(self) -> None:
        rows = self.rowCount()
        if rows <= 0:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(rows - 1, 0)
        self.dataChanged.emit(top_left, bottom_right)
