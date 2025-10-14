from __future__ import annotations

import fnmatch
import os
from typing import Dict, Optional

from PySide6.QtCore import QIdentityProxyModel, QModelIndex, Qt, QThreadPool, QRunnable, QObject, Signal

from ..translators.base import Translator
from ..translation_cache import TranslationCache

# Optional role used by non-QFileSystemModel sources to provide a path
PATH_ROLE = Qt.UserRole + 1


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
                 ignore_patterns: Optional[list[str]] = None):
        super().__init__(parent)
        self._translator = translator
        self._target_language = target_language
        self._cache: Dict[str, str] = {}
        self._pending: Dict[str, bool] = {}
        self._pool = QThreadPool.globalInstance()
        self._disk_cache = cache
        self._ignore_patterns = ignore_patterns or []

        self._signals = _TranslateJobSignals()
        self._signals.done.connect(self._on_done)
        self._signals.fail.connect(self._on_fail)

    def set_target_language(self, language: str) -> None:
        if language != self._target_language:
            self._target_language = language
            self._cache.clear()
            self._pending.clear()
            # Refresh all visible rows
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount() - 1, 0)
            self.dataChanged.emit(top_left, bottom_right)

    def set_translator(self, translator: Translator) -> None:
        self._translator = translator
        self._cache.clear()
        self._pending.clear()
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, 0)
        self.dataChanged.emit(top_left, bottom_right)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return super().data(index, role)
        if role == Qt.DisplayRole:
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

            if path in self._cache:
                return self._cache[path]

            # Skip translating ignored paths
            if self._is_ignored(path, name):
                return name

            # Try disk cache first
            mtime = 0.0
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                pass
            if self._disk_cache:
                cached = self._disk_cache.get(self._target_language, path, name, mtime)
                if not cached:
                    # Fallback to name-only cache (common names across locations)
                    cached = self._disk_cache.get_by_name(self._target_language, name)
                if cached:
                    self._cache[path] = cached
                    return cached

            # Queue translation if not pending
            if path not in self._pending:
                self._pending[path] = True
                job = _TranslateJob(path, name, self._target_language, self._translator, self._signals)
                self._pool.start(job)

            # Fallback: show original name while loading
            return name

        return super().data(index, role)

    def _on_done(self, path: str, translated: str) -> None:
        self._cache[path] = translated
        self._pending.pop(path, None)
        if self._disk_cache:
            name = os.path.basename(path)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = 0.0
            self._disk_cache.set(self._target_language, path, name, mtime, translated)
            self._disk_cache.set_by_name(self._target_language, name, translated)
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
