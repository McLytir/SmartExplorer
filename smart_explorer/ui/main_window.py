from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QTreeView,
    QFileSystemModel,
    QVBoxLayout,
    QSplitter,
    QToolBar,
    QFileDialog,
    QLineEdit,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QSortFilterProxyModel, QModelIndex

from ..models.translated_fs_model import TranslatedProxyModel, PATH_ROLE
from ..settings import AppConfig, load_config, save_config
from ..translators.base import IdentityTranslator
from ..translators.openai_translator import OpenAITranslator
from ..translators.backend_translator import BackendTranslator
from ..services.rename_service import apply_rename
from ..translation_cache import TranslationCache
from ..models.sharepoint_tree_model import SharePointTreeModel, IS_DIR_ROLE
from ..api.backend_client import BackendClient
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartExplorer — Translation Mirror")
        self.resize(1200, 700)

        self._cfg: AppConfig = load_config()
        # Use configured backend URL if present
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        self._fs_model = QFileSystemModel(self)
        self._fs_model.setRootPath(self._cfg.root_path)

        self._translator = self._create_translator()
        self._cache = TranslationCache()
        self._proxy = TranslatedProxyModel(
            self._translator,
            self._cfg.target_language,
            self,
            cache=self._cache,
            ignore_patterns=self._cfg.ignore_patterns,
        )
        self._proxy.setSourceModel(self._fs_model)

        # Add filter proxies for search
        self._left_filter = QSortFilterProxyModel(self)
        self._left_filter.setSourceModel(self._fs_model)
        self._left_filter.setRecursiveFilteringEnabled(True)
        self._left_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._right_filter = QSortFilterProxyModel(self)
        self._right_filter.setSourceModel(self._proxy)
        self._right_filter.setRecursiveFilteringEnabled(True)
        self._right_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._left = QTreeView(self)
        self._left.setModel(self._left_filter)
        self._left.setRootIndex(self._left_filter.mapFromSource(self._fs_model.index(self._cfg.root_path)))
        self._left.setSortingEnabled(True)
        self._left.setAlternatingRowColors(True)
        self._left.setSelectionMode(QTreeView.ExtendedSelection)
        self._left.setContextMenuPolicy(Qt.ActionsContextMenu)

        self._right = QTreeView(self)
        self._right.setModel(self._right_filter)
        self._right.setRootIndex(self._right_filter.mapFromSource(self._proxy.mapFromSource(self._fs_model.index(self._cfg.root_path))))
        self._right.setSortingEnabled(True)
        self._right.setAlternatingRowColors(True)
        self._right.setSelectionMode(QTreeView.ExtendedSelection)

        # Keep columns aligned
        for view in (self._left, self._right):
            self._hide_extra_columns(view)

        splitter = QSplitter(self)
        splitter.addWidget(self._left)
        splitter.addWidget(self._right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        self._build_toolbar()
        self._wire_selection_sync()
        self._wire_expand_sync()
        self.statusBar().showMessage("Ready")

        # Default to Local source on startup
        self._source_combo.setCurrentText("Local")

    def _hide_extra_columns(self, view: QTreeView) -> None:
        # Show only Name and let user enable others if needed
        for c in range(1, 4):
            view.setColumnHidden(c, True)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        self.addToolBar(tb)

        # Choose root folder
        pick_dir = QAction("Choose Folder", self)
        pick_dir.triggered.connect(self._choose_root)
        tb.addAction(pick_dir)

        # Source selector (Local / SharePoint)
        from PySide6.QtWidgets import QComboBox
        self._source_combo = QComboBox(self)
        self._source_combo.addItems(["Local", "SharePoint"])
        self._source_combo.currentTextChanged.connect(self._on_source_changed)
        tb.addWidget(self._source_combo)

        # Target language entry
        self._lang_edit = QLineEdit(self)
        self._lang_edit.setPlaceholderText("Target language (e.g., English, French)")
        self._lang_edit.setText(self._cfg.target_language)
        self._lang_edit.editingFinished.connect(self._on_lang_changed)
        tb.addWidget(self._lang_edit)

        # Search box
        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search (original or translated)")
        self._search_edit.textChanged.connect(self._on_search_changed)
        tb.addWidget(self._search_edit)

        # Apply rename
        apply_act = QAction("Apply Rename (Selected)", self)
        apply_act.triggered.connect(self._apply_selected_renames)
        tb.addAction(apply_act)

        # Settings (API key)
        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(self._open_settings)
        tb.addAction(settings_act)

        # Context menu action on left tree
        left_apply = QAction("Apply Translated Name", self._left)
        left_apply.triggered.connect(self._apply_selected_renames)
        self._left.addAction(left_apply)

    def _wire_selection_sync(self) -> None:
        # Sync expansions and root path changes where possible
        self._left.selectionModel().selectionChanged.connect(self._sync_selection)

    def _sync_selection(self):
        # Map left selection to right
        sel = self._left.selectionModel().selectedIndexes()
        if not sel:
            return
        # Use first column only
        left_name_indexes = [i for i in sel if i.column() == 0]
        if not left_name_indexes:
            return
        left_first = left_name_indexes[0]
        if self._source_combo.currentText() == "Local":
            fs_idx = self._left_filter.mapToSource(left_first)
            tr_idx = self._proxy.mapFromSource(fs_idx)
            right_idx = self._right_filter.mapFromSource(tr_idx)
        else:
            fs_idx = self._sp_left_filter.mapToSource(left_first)
            tr_idx = self._sp_proxy.mapFromSource(fs_idx)
            right_idx = self._sp_right_filter.mapFromSource(tr_idx)
        if right_idx.isValid():
            self._right.setCurrentIndex(right_idx)

    def _wire_expand_sync(self) -> None:
        self._left.expanded.connect(self._on_left_expanded)
        self._left.collapsed.connect(self._on_left_collapsed)

    def _on_left_expanded(self, left_idx):
        if self._source_combo.currentText() == "Local":
            fs_idx = self._left_filter.mapToSource(left_idx)
            tr_idx = self._proxy.mapFromSource(fs_idx)
            right_idx = self._right_filter.mapFromSource(tr_idx)
        else:
            fs_idx = self._sp_left_filter.mapToSource(left_idx)
            tr_idx = self._sp_proxy.mapFromSource(fs_idx)
            right_idx = self._sp_right_filter.mapFromSource(tr_idx)
        if right_idx.isValid():
            self._right.expand(right_idx)

    def _on_left_collapsed(self, left_idx):
        if self._source_combo.currentText() == "Local":
            fs_idx = self._left_filter.mapToSource(left_idx)
            tr_idx = self._proxy.mapFromSource(fs_idx)
            right_idx = self._right_filter.mapFromSource(tr_idx)
        else:
            fs_idx = self._sp_left_filter.mapToSource(left_idx)
            tr_idx = self._sp_proxy.mapFromSource(fs_idx)
            right_idx = self._sp_right_filter.mapFromSource(tr_idx)
        if right_idx.isValid():
            self._right.collapse(right_idx)

    def _create_translator(self):
        api_key = (self._cfg.api_key or "").strip()
        if api_key:
            return OpenAITranslator(api_key=api_key, model=self._cfg.model)
        # Try backend translator when local key absent
        try:
            info = self._backend.get_settings()
            if info.get("has_api_key"):
                return BackendTranslator(self._backend.base_url)
        except Exception:
            pass
        return IdentityTranslator()

    def _choose_root(self) -> None:
        start = self._cfg.root_path if os.path.isdir(self._cfg.root_path) else os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Choose root folder", start)
        if path:
            self._cfg.root_path = path
            save_config(self._cfg)
            self._fs_model.setRootPath(path)
            self._left.setRootIndex(self._left_filter.mapFromSource(self._fs_model.index(path)))
            self._right.setRootIndex(self._right_filter.mapFromSource(self._proxy.mapFromSource(self._fs_model.index(path))))

    def _on_source_changed(self, text: str) -> None:
        # Persist selection
        try:
            setattr(self._cfg, "last_source", text)
            save_config(self._cfg)
        except Exception:
            pass
        if text == "Local":
            self._left.setModel(self._left_filter)
            self._right.setModel(self._right_filter)
            self._left.setRootIndex(self._left_filter.mapFromSource(self._fs_model.index(self._cfg.root_path)))
            self._right.setRootIndex(self._right_filter.mapFromSource(self._proxy.mapFromSource(self._fs_model.index(self._cfg.root_path))))
        else:
            # Build SharePoint model using settings
            sp_base = getattr(self._cfg, "sp_base_url", None) or ""
            if not sp_base:
                QMessageBox.information(self, "SharePoint", "Please set SharePoint Site URL in Settings.")
                self._source_combo.setCurrentText("Local")
                return
            # Derive site_relative_url from base URL (path part)
            from urllib.parse import urlparse
            parsed = urlparse(sp_base)
            site_rel = parsed.path
            # Pick library root: prefer explicit override if provided
            root_folder = getattr(self._cfg, "sp_library_root", None)
            if not root_folder:
                # Ask backend for default document library when not explicitly set
                try:
                    info = self._backend.sp_default_doclib()
                    root_folder = info.get("server_relative_url") or (site_rel.rstrip("/") + "/Shared%20Documents")
                except Exception:
                    # Fallback to common default library name
                    root_folder = site_rel.rstrip("/") + "/Shared%20Documents"
            # Ensure spaces are encoded to match backend's expectations
            if " " in root_folder and "%20" not in root_folder:
                root_folder = root_folder.replace(" ", "%20")
            self._sp_model = SharePointTreeModel(self._backend, site_rel, root_folder, self)
            self._sp_proxy = TranslatedProxyModel(self._translator, self._cfg.target_language, self, cache=self._cache, ignore_patterns=self._cfg.ignore_patterns)
            self._sp_proxy.setSourceModel(self._sp_model)
            # Filters for SP
            self._sp_left_filter = QSortFilterProxyModel(self)
            self._sp_left_filter.setSourceModel(self._sp_model)
            self._sp_left_filter.setRecursiveFilteringEnabled(True)
            self._sp_left_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self._sp_right_filter = QSortFilterProxyModel(self)
            self._sp_right_filter.setSourceModel(self._sp_proxy)
            self._sp_right_filter.setRecursiveFilteringEnabled(True)
            self._sp_right_filter.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self._left.setModel(self._sp_left_filter)
            self._right.setModel(self._sp_right_filter)
            self._left.setRootIndex(self._sp_left_filter.mapFromSource(QModelIndex()))
            self._right.setRootIndex(self._sp_right_filter.mapFromSource(self._sp_proxy.mapFromSource(QModelIndex())))

    def _on_lang_changed(self) -> None:
        new_lang = self._lang_edit.text().strip() or "English"
        self._cfg.target_language = new_lang
        save_config(self._cfg)
        self._proxy.set_target_language(new_lang)
        if hasattr(self, "_sp_proxy"):
            self._sp_proxy.set_target_language(new_lang)

    def _on_search_changed(self, text: str) -> None:
        self._left_filter.setFilterFixedString(text)
        self._right_filter.setFilterFixedString(text)
        if hasattr(self, "_sp_left_filter"):
            self._sp_left_filter.setFilterFixedString(text)
        if hasattr(self, "_sp_right_filter"):
            self._sp_right_filter.setFilterFixedString(text)

    def _apply_selected_renames(self) -> None:
        indexes = [i for i in self._left.selectionModel().selectedIndexes() if i.column() == 0]
        if not indexes:
            return

        # Confirm action
        resp = QMessageBox.question(
            self,
            "Confirm Rename",
            "Apply translated names to selected files/folders? This will rename on disk.",
        )
        if resp != QMessageBox.Yes:
            return

        errors = 0
        if self._source_combo.currentText() == "Local":
            for idx in indexes:
                src_idx = self._left_filter.mapToSource(idx)
                path = self._fs_model.filePath(src_idx)
                original_name = self._fs_model.fileName(src_idx)
                tr_idx = self._proxy.mapFromSource(src_idx)
                translated_name = self._proxy.data(tr_idx, Qt.DisplayRole)
                if not isinstance(translated_name, str) or not translated_name or translated_name == original_name:
                    continue
                try:
                    new_path = apply_rename(path, translated_name)
                    parent = os.path.dirname(new_path)
                    self._fs_model.setRootPath(parent)
                    self._proxy._cache.pop(path, None)
                except Exception:
                    errors += 1
        else:
            # SharePoint rename via backend
            for idx in indexes:
                src_idx = self._sp_left_filter.mapToSource(idx)
                tr_idx = self._sp_proxy.mapFromSource(src_idx)
                translated_name = self._sp_proxy.data(tr_idx, Qt.DisplayRole)
                path = self._sp_model.data(src_idx, PATH_ROLE)
                name = self._sp_model.data(src_idx, Qt.DisplayRole)
                if not isinstance(translated_name, str) or not translated_name or translated_name == name:
                    continue
                try:
                    is_folder = bool(self._sp_model.data(src_idx, IS_DIR_ROLE))
                    self._backend.sp_rename(server_relative_url=path, new_name=translated_name, is_folder=is_folder)
                except Exception:
                    errors += 1

        if errors:
            QMessageBox.warning(self, "Rename", f"Completed with {errors} errors.")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._cfg, self)
        dlg.exec()
        # Reload cfg from disk in case dialog saved
        self._cfg = load_config()
        # Update backend base URL
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        # Swap translator if needed
        self._translator = self._create_translator()
        self._proxy.set_translator(self._translator)
        if hasattr(self, "_sp_proxy"):
            self._sp_proxy.set_translator(self._translator)
