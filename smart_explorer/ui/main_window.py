from __future__ import annotations

import base64
import os
import sys
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QMenu,
    QSplitter,
    QToolBar,
    QWidget,
    QVBoxLayout,
    QDialog,
)

from ..api.backend_client import BackendClient
from ..services.rename_service import apply_rename
from ..settings import AppConfig, load_config, save_config
from ..translation_cache import TranslationCache
from ..translators.backend_translator import BackendTranslator
from ..translators.base import IdentityTranslator, Translator
from ..translators.openai_translator import OpenAITranslator
from ..workspaces import WorkspaceDefinition, WorkspaceManager, ensure_workspaces
from .settings_dialog import SettingsDialog
from .sharepoint_selector import SharePointSelectorDialog
from .translation_dialog import TranslationWorkspaceDialog
from .workspace_pane import WorkspacePane


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SmartExplorer — Workspaces")
        self.resize(1400, 820)

        self._cfg: AppConfig = load_config()
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        self._workspace_manager: WorkspaceManager = ensure_workspaces(self._cfg)

        self._translator: Translator = self._create_translator()
        self._translation_cache = TranslationCache()
        self._ignore_patterns = self._cfg.ignore_patterns or []

        self._workspace_panes: Dict[str, WorkspacePane] = {}
        self._active_workspace_id: Optional[str] = None
        self._clipboard: Dict[str, dict] = {}  # workspace_id -> clipboard payload
        self._selection_sync_block: set[str] = set()
        self._shortcuts: List[QShortcut] = []

        self._container = QWidget(self)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        self._splitter: Optional[QSplitter] = None
        self._toolbar = self._build_toolbar()
        self.addToolBar(Qt.TopToolBarArea, self._toolbar)

        self._workspace_holder = QWidget(self._container)
        self._workspace_layout = QVBoxLayout(self._workspace_holder)
        self._workspace_layout.setContentsMargins(0, 0, 0, 0)
        self._workspace_layout.setSpacing(0)
        self._container_layout.addWidget(self._workspace_holder, 1)

        self.setCentralWidget(self._container)

        self._rebuild_workspace_area()
        self.statusBar().showMessage("Ready")
        self._setup_shortcuts()

    # ------------------------------------------------------------------ UI --
    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar("Workspaces", self)
        tb.setMovable(False)

        add_local = QAction("Add Local Pane…", self)
        add_local.triggered.connect(self._add_local_workspace)
        tb.addAction(add_local)

        add_sharepoint = QAction("Add SharePoint Pane…", self)
        add_sharepoint.triggered.connect(self._add_sharepoint_workspace)
        tb.addAction(add_sharepoint)

        add_translation = QAction("Add Translation Pane…", self)
        add_translation.triggered.connect(self._add_translation_workspace)
        tb.addAction(add_translation)

        remove_ws = QAction("Remove Active Pane", self)
        remove_ws.triggered.connect(self._remove_active_workspace)
        tb.addAction(remove_ws)

        tb.addSeparator()

        rename_action = QAction("Apply Translation Rename", self)
        rename_action.triggered.connect(self._apply_translated_rename)
        tb.addAction(rename_action)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(lambda: self._clipboard_copy(False))
        tb.addAction(copy_action)
        self.addAction(copy_action)

        cut_action = QAction("Cut", self)
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.triggered.connect(lambda: self._clipboard_copy(True))
        tb.addAction(cut_action)
        self.addAction(cut_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self._clipboard_paste)
        tb.addAction(paste_action)
        self.addAction(paste_action)

        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self._delete_selected_items)
        tb.addAction(delete_action)
        self.addAction(delete_action)

        tb.addSeparator()

        share_link = QAction("Copy Share Link", self)
        share_link.triggered.connect(self._copy_share_link)
        tb.addAction(share_link)

        open_browser = QAction("Open in SharePoint", self)
        open_browser.triggered.connect(self._open_in_sharepoint)
        tb.addAction(open_browser)

        tb.addSeparator()

        settings = QAction("Settings…", self)
        settings.triggered.connect(self._open_settings)
        tb.addAction(settings)

        return tb

    # ------------------------------------------------------------- workspaces
    def _setup_shortcuts(self) -> None:
        for seq, offset in (("Ctrl+Shift+Left", -1), ("Ctrl+Shift+Right", 1), ("Ctrl+Shift+Up", -1), ("Ctrl+Shift+Down", 1)):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(lambda checked=False, o=offset: self._move_active_workspace(o))
            self._shortcuts.append(shortcut)

    def _rebuild_workspace_area(self, focus_workspace_id: Optional[str] = None) -> None:
        # Capture state before rebuilding
        prev_states: Dict[str, dict] = {
            wid: pane.snapshot_state()
            for wid, pane in self._workspace_panes.items()
        }

        # Remove existing widgets
        for pane in self._workspace_panes.values():
            pane.setParent(None)
        self._workspace_panes.clear()

        panes_in_order: List[WorkspacePane] = []
        base_lookup: Dict[str, WorkspacePane] = {}

        defs = self._workspace_manager.definitions()
        base_defs = [d for d in defs if d.kind != "translation"]
        translation_defs = [d for d in defs if d.kind == "translation"]

        for definition in base_defs:
            pane = self._create_workspace_pane(definition, base_lookup)
            self._workspace_panes[definition.id] = pane
            base_lookup[definition.id] = pane
            panes_in_order.append(pane)

        for definition in translation_defs:
            try:
                pane = self._create_workspace_pane(definition, base_lookup)
            except Exception as exc:
                QMessageBox.warning(self, "Workspace", f"Failed to create translation workspace '{definition.name}': {exc}")
                continue
            self._workspace_panes[definition.id] = pane
            panes_in_order.append(pane)

        if not panes_in_order:
            QMessageBox.information(self, "Workspace", "No workspaces defined. Adding a default local pane.")
            self._workspace_manager.ensure_unique_id("ws-local")
            default_ws = WorkspaceDefinition(
                id="ws-local",
                kind="local",
                name="Local",
                root_path=self._cfg.root_path or os.path.expanduser("~"),
            )
            self._workspace_manager.add(default_ws)
            self._cfg.workspaces = self._workspace_manager.to_config()
            save_config(self._cfg)
            self._rebuild_workspace_area(focus_workspace_id=default_ws.id)
            return

        if self._splitter:
            self._workspace_layout.removeWidget(self._splitter)
            self._splitter.deleteLater()

        self._splitter = self._build_splitter_layout(panes_in_order)
        self._normalize_splitter(self._splitter)
        self._workspace_layout.addWidget(self._splitter, 1)
        target_focus = focus_workspace_id or self._active_workspace_id or (panes_in_order[0].id if panes_in_order else None)
        self._focus_workspace(target_focus)

        # Restore state where possible
        for wid, pane in self._workspace_panes.items():
            pane.restore_state(prev_states.get(wid, {}))

    def _build_splitter_layout(self, panes: List[WorkspacePane]) -> QSplitter:
        count = len(panes)
        if count <= 1:
            split = QSplitter(Qt.Horizontal, self)
            split.addWidget(panes[0])
            return split
        if count == 2:
            split = QSplitter(Qt.Horizontal, self)
            split.addWidget(panes[0])
            split.addWidget(panes[1])
            return split
        if count <= 4:
            main_split = QSplitter(Qt.Horizontal, self)
            left = QSplitter(Qt.Vertical, main_split)
            right = QSplitter(Qt.Vertical, main_split)
            main_split.addWidget(left)
            main_split.addWidget(right)
            left.addWidget(panes[0])
            if count > 2:
                left.addWidget(panes[2])
            right.addWidget(panes[1])
            if count > 3:
                right.addWidget(panes[3])
            return main_split
        # Fallback: single horizontal line with all panes
        split = QSplitter(Qt.Horizontal, self)
        for pane in panes:
            split.addWidget(pane)
        return split

    def _normalize_splitter(self, splitter: QSplitter) -> None:
        count = splitter.count()
        if count:
            splitter.setSizes([1] * count)
        for i in range(count):
            child = splitter.widget(i)
            if isinstance(child, QSplitter):
                self._normalize_splitter(child)

    def _focus_workspace(self, workspace_id: Optional[str]) -> None:
        for wid, pane in self._workspace_panes.items():
            pane.set_active(wid == workspace_id)
        if workspace_id and workspace_id in self._workspace_panes:
            self._workspace_panes[workspace_id].setFocus()
            self._active_workspace_id = workspace_id
        else:
            self._active_workspace_id = None

    def _translation_dependents(self, base_workspace_id: str) -> List[WorkspacePane]:
        return [
            pane
            for pane in self._workspace_panes.values()
            if pane.definition.kind == "translation" and pane.definition.base_workspace_id == base_workspace_id
        ]

    def _move_active_workspace(self, offset: int) -> None:
        if not self._active_workspace_id or offset == 0:
            return
        self._workspace_manager.move_by_offset(self._active_workspace_id, offset)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=self._active_workspace_id)

    def _convert_workspace_to_local(self, definition: WorkspaceDefinition) -> None:
        dependents = self._translation_dependents(definition.id)
        if definition.kind == "translation" and dependents:
            QMessageBox.warning(self, "Workspace", "Cannot convert a translation workspace that has dependents.")
            return
        path = QFileDialog.getExistingDirectory(self, "Choose local folder", definition.root_path or os.path.expanduser("~"))
        if not path:
            return
        definition.kind = "local"
        definition.root_path = path
        definition.site_relative_url = None
        definition.server_relative_url = None
        definition.base_workspace_id = None
        definition.language = None
        definition.name = os.path.basename(path) or "Local"
        self._workspace_manager.update(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _convert_workspace_to_sharepoint(self, definition: WorkspaceDefinition) -> None:
        dependents = self._translation_dependents(definition.id)
        if definition.kind == "translation" and dependents:
            QMessageBox.warning(self, "Workspace", "Cannot convert a translation workspace that has dependents.")
            return
        dlg = SharePointSelectorDialog(self._backend, self)
        if dlg.exec() != QDialog.Accepted:
            return
        selection = dlg.selected()
        if not selection:
            QMessageBox.warning(self, "SharePoint", "Please choose a library with a valid server path.")
            return
        definition.kind = "sharepoint"
        definition.root_path = None
        definition.site_relative_url = selection.get("site_relative_url")
        definition.server_relative_url = selection.get("server_relative_url")
        definition.base_workspace_id = None
        definition.language = None
        definition.name = f"{selection.get('site_title', 'SharePoint')} - {selection.get('library_title', 'Library')}"
        self._workspace_manager.update(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _convert_workspace_to_translation(self, definition: WorkspaceDefinition) -> None:
        if definition.kind != "translation" and self._translation_dependents(definition.id):
            QMessageBox.warning(self, "Workspace", "Cannot convert a workspace that other translations depend on.")
            return
        base_options = [
            (ws.id, ws.name)
            for ws in self._workspace_manager.definitions()
            if ws.id != definition.id and ws.kind in ("local", "sharepoint")
        ]
        if not base_options:
            QMessageBox.information(self, "Translation", "Create a local or SharePoint workspace first.")
            return
        dlg = TranslationWorkspaceDialog(base_options, self._cfg.target_language or "English", self)
        if dlg.exec() != QDialog.Accepted:
            return
        base_id = dlg.base_workspace_id
        language = dlg.language
        if base_id == definition.id:
            QMessageBox.warning(self, "Translation", "A workspace cannot translate itself.")
            return
        definition.kind = "translation"
        definition.base_workspace_id = base_id
        definition.language = language
        definition.root_path = None
        definition.site_relative_url = None
        definition.server_relative_url = None
        base_name = dict(base_options).get(base_id, "Workspace")
        definition.name = f"{base_name} ({language})"
        self._workspace_manager.update(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _create_workspace_pane(self, definition: WorkspaceDefinition, base_panes: Dict[str, WorkspacePane]) -> WorkspacePane:
        pane = WorkspacePane(
            definition,
            backend_client=self._backend,
            translator=self._translator,
            translation_cache=self._translation_cache,
            ignore_patterns=self._ignore_patterns,
            base_panes=base_panes,
        )
        pane.activated.connect(self._on_workspace_item_activated)
        pane.drop_request.connect(self._on_workspace_drop_request)
        self._register_workspace_signals(pane)
        self._attach_context_menu(pane)
        return pane

    def _register_workspace_signals(self, pane: WorkspacePane) -> None:
        pane.selection_changed.connect(self._on_workspace_selection_changed)
        pane.expanded_path.connect(self._on_workspace_expanded)
        pane.collapsed_path.connect(self._on_workspace_collapsed)
        if hasattr(pane, "header"):
            pane.header.reorder_requested.connect(self._on_header_reorder)
            pane.header.context_menu_requested.connect(self._on_header_context_menu)

    def _mirror_selection(self, workspace_id: str) -> None:
        base_pane = self._workspace_panes.get(workspace_id)
        if not base_pane or base_pane.definition.kind == "translation":
            return
        dependents = self._translation_dependents(workspace_id)
        if not dependents:
            return
        if workspace_id in self._selection_sync_block:
            return
        self._selection_sync_block.add(workspace_id)
        try:
            source_indexes = base_pane.current_source_indexes()
            paths: List[str] = []
            for idx in source_indexes:
                path = base_pane.path_for_source_index(idx)
                if path:
                    paths.append(path)
            for pane in dependents:
                pane.select_paths(paths)
        finally:
            self._selection_sync_block.discard(workspace_id)

    def _on_workspace_expanded(self, workspace_id: str, path: str) -> None:
        for pane in self._translation_dependents(workspace_id):
            pane.expand_path(path)

    def _on_workspace_collapsed(self, workspace_id: str, path: str) -> None:
        for pane in self._translation_dependents(workspace_id):
            pane.collapse_path(path)

    def _attach_context_menu(self, pane: WorkspacePane) -> None:
        menu_actions = {
            "Rename…": self._apply_translated_rename,
            "Copy": lambda: self._clipboard_copy(False),
            "Cut": lambda: self._clipboard_copy(True),
            "Paste": self._clipboard_paste,
            "Delete": self._delete_selected_items,
            "Copy Share Link": self._copy_share_link,
            "Open in SharePoint": self._open_in_sharepoint,
        }
        for text, handler in menu_actions.items():
            action = QAction(text, pane)
            action.triggered.connect(handler)
            pane.addAction(action)
        close_action = QAction("Close Pane", pane)
        close_action.triggered.connect(lambda _, ws_id=pane.id: self._remove_workspace(ws_id))
        pane.addAction(close_action)

    def _on_workspace_drop_request(self, target_workspace_id: str, payload: dict, target_path: str, move: bool, site: Optional[str]) -> None:
        source_workspace_id = payload.get("source_workspace")
        items = payload.get("items") or []
        source_pane = self._workspace_panes.get(source_workspace_id)
        target_pane = self._workspace_panes.get(target_workspace_id)
        if not source_pane or not target_pane or not items:
            return
        if target_pane.definition.kind == "local":
            self._paste_local(items, source_pane, target_pane, move, dest_dir=target_path)
        elif target_pane.definition.kind == "sharepoint":
            self._paste_sharepoint(items, source_pane, target_pane, move, dest_root=target_path, target_site_override=site)
        else:
            # translation panes do not accept drops; ignore
            return

    def _on_header_reorder(self, source_id: str, target_id: Optional[str]) -> None:
        if source_id == target_id:
            return
        self._workspace_manager.reorder_before(source_id, target_id or None)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=source_id)

    def _on_header_context_menu(self, workspace_id: str, global_pos) -> None:
        pane = self._workspace_panes.get(workspace_id)
        definition = self._workspace_manager.get(workspace_id)
        if not pane or not definition:
            return
        menu = QMenu(self)
        local_action = menu.addAction("Switch to Local…")
        sharepoint_action = menu.addAction("Switch to SharePoint…")
        translation_label = "Configure Translation…" if definition.kind == "translation" else "Switch to Translation…"
        translation_action = menu.addAction(translation_label)
        if definition.kind == "local":
            local_action.setEnabled(False)
        if definition.kind == "sharepoint":
            sharepoint_action.setEnabled(False)
        if definition.kind != "translation" and not any(ws.kind in ("local", "sharepoint") and ws.id != workspace_id for ws in self._workspace_manager.definitions()):
            translation_action.setEnabled(False)
        if definition.kind != "translation" and self._translation_dependents(definition.id):
            translation_action.setEnabled(False)

        action = menu.exec(global_pos)
        if not action:
            return
        if action is local_action:
            self._convert_workspace_to_local(definition)
        elif action is sharepoint_action:
            self._convert_workspace_to_sharepoint(definition)
        elif action is translation_action:
            self._convert_workspace_to_translation(definition)

    # ------------------------------------------------------------- workspace ops
    def _on_workspace_selection_changed(self, workspace_id: str) -> None:
        self._focus_workspace(workspace_id)
        pane = self._workspace_panes.get(workspace_id)
        if not pane:
            return
        selected = pane.current_items()
        self.statusBar().showMessage(f"{pane.definition.name}: {len(selected)} selected")
        self._mirror_selection(workspace_id)

    def _on_workspace_item_activated(self, workspace_id: str, path: str) -> None:
        self.statusBar().showMessage(f"Opened: {path}", 4000)

    def _add_local_workspace(self) -> None:
        start_dir = self._cfg.root_path if os.path.isdir(self._cfg.root_path) else os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select folder", start_dir)
        if not directory:
            return
        name, ok = QInputDialog.getText(self, "Workspace Name", "Name:", text=os.path.basename(directory) or "Local")
        if not ok or not name.strip():
            return
        definition = WorkspaceDefinition(
            id=self._workspace_manager.ensure_unique_id("ws"),
            kind="local",
            name=name.strip(),
            root_path=directory,
        )
        self._workspace_manager.add(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _add_sharepoint_workspace(self) -> None:
        dlg = SharePointSelectorDialog(self._backend, self)
        if dlg.exec() != QDialog.Accepted:
            return
        selection = dlg.selected()
        if not selection:
            QMessageBox.warning(self, "SharePoint", "Please select a library with a valid server path.")
            return
        suggested_name = f"{selection.get('site_title', 'SharePoint')} - {selection.get('library_title', selection.get('name', 'Library'))}"
        name, ok = QInputDialog.getText(self, "Workspace Name", "Name:", text=suggested_name)
        if not ok or not name.strip():
            return
        definition = WorkspaceDefinition(
            id=self._workspace_manager.ensure_unique_id("ws-sp"),
            kind="sharepoint",
            name=name.strip(),
            site_relative_url=selection.get("site_relative_url"),
            server_relative_url=selection.get("server_relative_url"),
        )
        self._workspace_manager.add(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _add_translation_workspace(self) -> None:
        base_options = [(ws.id, ws.name) for ws in self._workspace_manager.definitions() if ws.kind in ("local", "sharepoint")]
        if not base_options:
            QMessageBox.information(self, "Translation", "Create a base workspace (local or SharePoint) first.")
            return
        dlg = TranslationWorkspaceDialog(base_options, self._cfg.target_language or "English", self)
        if dlg.exec() != QDialog.Accepted:
            return
        base_id = dlg.base_workspace_id
        language = dlg.language
        name, ok = QInputDialog.getText(
            self,
            "Workspace Name",
            "Name:",
            text=f"{dict(base_options).get(base_id, 'Workspace')} ({language})",
        )
        if not ok or not name.strip():
            return
        definition = WorkspaceDefinition(
            id=self._workspace_manager.ensure_unique_id("ws-tr"),
            kind="translation",
            name=name.strip(),
            base_workspace_id=base_id,
            language=language,
        )
        self._workspace_manager.add(definition)
        self._persist_workspaces()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _remove_active_workspace(self) -> None:
        if not self._active_workspace_id:
            QMessageBox.information(self, "Workspace", "Select a workspace first.")
            return
        self._remove_workspace(self._active_workspace_id)

    def _remove_workspace(self, workspace_id: str) -> None:
        if len(self._workspace_manager.definitions()) <= 1:
            QMessageBox.information(self, "Workspace", "At least one workspace must exist.")
            return
        reply = QMessageBox.question(
            self,
            "Remove Workspace",
            "Remove this workspace (and any translations depending on it)?",
        )
        if reply != QMessageBox.Yes:
            return
        self._workspace_manager.remove(workspace_id)
        if self._active_workspace_id == workspace_id:
            self._active_workspace_id = None
        self._persist_workspaces()
        self._rebuild_workspace_area()

    def _persist_workspaces(self) -> None:
        self._cfg.workspaces = self._workspace_manager.to_config()
        save_config(self._cfg)

    # ----------------------------------------------------- file operations --
    def _active_pane(self) -> Optional[WorkspacePane]:
        if not self._active_workspace_id:
            return None
        return self._workspace_panes.get(self._active_workspace_id)

    def _apply_translated_rename(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        if pane.definition.kind != "translation":
            QMessageBox.information(self, "Rename", "Select a translation workspace to apply renames.")
            return
        items = pane.current_items()
        if not items:
            return
        base_id = pane.definition.base_workspace_id
        base_pane = self._workspace_panes.get(base_id) if base_id else None
        if not base_pane:
            QMessageBox.warning(self, "Rename", "Base workspace missing; cannot apply rename.")
            return
        errors = 0
        for item in items:
            path = item["path"]
            current_name = item.get("display") or os.path.basename(path)
            translated_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_name)
            if not ok or not translated_name.strip():
                continue
            translated_name = translated_name.strip()
            if base_pane.definition.kind == "local":
                try:
                    apply_rename(path, translated_name)
                except Exception:
                    errors += 1
            else:
                try:
                    self._backend.sp_rename(
                        server_relative_url=path,
                        new_name=translated_name,
                        is_folder=item["is_dir"],
                        site_relative_url=base_pane.definition.site_relative_url,
                    )
                except Exception:
                    errors += 1
        if errors:
            QMessageBox.warning(self, "Rename", f"Some items failed to rename ({errors}).")
        else:
            QMessageBox.information(self, "Rename", "Renamed successfully.")
        if base_pane:
            base_pane.refresh()
        pane.refresh()

    def _clipboard_copy(self, cut: bool) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        op_type = "cut" if cut else "copy"
        self._clipboard = {
            "workspace_id": pane.id,
            "items": items,
            "operation": op_type,
        }
        self.statusBar().showMessage(f"{op_type.title()} {len(items)} item(s).", 3000)

    def _clipboard_paste(self) -> None:
        if not self._clipboard:
            return
        target_pane = self._active_pane()
        if not target_pane:
            return
        source_workspace_id = self._clipboard.get("workspace_id")
        source_pane = self._workspace_panes.get(source_workspace_id)
        if not source_pane:
            QMessageBox.warning(self, "Paste", "Source workspace no longer available.")
            return
        items = self._clipboard.get("items", [])
        operation = self._clipboard.get("operation")
        if target_pane.definition.kind == "local":
            self._paste_local(items, source_pane, target_pane, move=(operation == "cut"))
        else:
            self._paste_sharepoint(items, source_pane, target_pane, move=(operation == "cut"))
        if operation == "cut":
            self._clipboard.clear()

    def _paste_local(self, items: List[dict], source: WorkspacePane, target: WorkspacePane, move: bool, dest_dir: Optional[str] = None) -> None:
        if target.definition.kind != "local":
            QMessageBox.warning(self, "Paste", "Local paste only supported into local workspaces.")
            return
        if dest_dir is None:
            dest_dir = target.definition.root_path or os.path.expanduser("~")
            selection = target.current_items()
            if selection:
                first = selection[0]
                if first["is_dir"]:
                    dest_dir = first["path"]
                else:
                    dest_dir = os.path.dirname(first["path"])
        if not os.path.isdir(dest_dir):
            QMessageBox.warning(self, "Paste", "Target directory unavailable.")
            return
        import shutil

        errors = 0
        source_site = source.definition.site_relative_url
        if source.definition.kind == "translation" and source.definition.base_workspace_id:
            base_pane = self._workspace_panes.get(source.definition.base_workspace_id)
            if base_pane and base_pane.definition.kind == "sharepoint":
                source_site = base_pane.definition.site_relative_url

        for item in items:
            src = item["path"]
            base_name = os.path.basename(src)
            dest = os.path.join(dest_dir, base_name)
            try:
                if source.definition.kind == "local":
                    if move:
                        shutil.move(src, dest)
                    else:
                        if item["is_dir"]:
                            shutil.copytree(src, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src, dest)
                else:
                    if item["is_dir"]:
                        os.makedirs(dest, exist_ok=True)
                        continue
                    content = self._backend.sp_download(src, site_relative_url=source_site)
                    with open(dest, "wb") as fh:
                        fh.write(content)
                    if move:
                        try:
                            self._backend.sp_delete(src, is_folder=False, site_relative_url=source_site, recycle=True)
                        except Exception:
                            pass
            except Exception:
                errors += 1
        if errors:
            QMessageBox.warning(self, "Paste", f"Some items failed ({errors}).")
        target.refresh()
        if move:
            source.refresh()

    def _paste_sharepoint(
        self,
        items: List[dict],
        source: WorkspacePane,
        target: WorkspacePane,
        move: bool,
        dest_root: Optional[str] = None,
        target_site_override: Optional[str] = None,
    ) -> None:
        target_def = target.definition
        target_site = target_site_override or target_def.site_relative_url
        if dest_root is None:
            dest_root = target_def.server_relative_url
            if target_def.kind == "translation" and target_def.base_workspace_id:
                base_pane = self._workspace_panes.get(target_def.base_workspace_id)
                if base_pane and base_pane.definition.kind == "sharepoint":
                    target_site = target_site_override or base_pane.definition.site_relative_url
                    dest_root = base_pane.definition.server_relative_url
            selection = target.current_items()
            if selection:
                first = selection[0]
                if first["is_dir"]:
                    dest_root = first["path"]
                else:
                    dest_root = first["path"].rsplit('/', 1)[0]
        if not dest_root:
            QMessageBox.warning(self, "Paste", "Target SharePoint workspace missing root.")
            return
        errors = 0
        source_site = source.definition.site_relative_url
        if source.definition.kind == "translation" and source.definition.base_workspace_id:
            base_pane = self._workspace_panes.get(source.definition.base_workspace_id)
            if base_pane and base_pane.definition.kind == "sharepoint":
                source_site = base_pane.definition.site_relative_url

        for item in items:
            src = item["path"]
            name = os.path.basename(src)
            dest = f"{dest_root.rstrip('/')}/{name}"
            try:
                if source.definition.kind in ("sharepoint", "translation"):
                    if move:
                        self._backend.sp_move(
                            src,
                            dest,
                            is_folder=item["is_dir"],
                            overwrite=False,
                            site_relative_url=source_site,
                        )
                    else:
                        self._backend.sp_copy(
                            src,
                            dest,
                            is_folder=item["is_dir"],
                            overwrite=False,
                            site_relative_url=source_site,
                        )
                else:
                    if item["is_dir"]:
                        self._backend.sp_create_folder(dest_root, name, site_relative_url=target_site)
                        continue
                    try:
                        with open(src, "rb") as fh:
                            data = fh.read()
                    except Exception:
                        errors += 1
                        continue
                    payload = base64.b64encode(data).decode("ascii")
                    self._backend.sp_upload(dest_root, name, payload, site_relative_url=target_site, overwrite=False)
                    if move:
                        try:
                            os.remove(src)
                        except Exception:
                            pass
            except Exception:
                errors += 1
        if errors:
            QMessageBox.warning(self, "Paste", f"Some SharePoint items failed ({errors}).")
        target.refresh()
        if move:
            source.refresh()

    def _delete_selected_items(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        reply = QMessageBox.question(self, "Delete", f"Delete {len(items)} item(s)?")
        if reply != QMessageBox.Yes:
            return
        errors = 0
        if pane.definition.kind == "local":
            import shutil

            for item in items:
                try:
                    if item["is_dir"]:
                        shutil.rmtree(item["path"])
                    else:
                        os.remove(item["path"])
                except Exception:
                    errors += 1
        else:
            site = pane.definition.site_relative_url
            if pane.definition.kind == "translation" and pane.definition.base_workspace_id:
                base_pane = self._workspace_panes.get(pane.definition.base_workspace_id)
                if base_pane and base_pane.definition.kind == "sharepoint":
                    site = base_pane.definition.site_relative_url
            for item in items:
                try:
                    self._backend.sp_delete(
                        item["path"],
                        is_folder=item["is_dir"],
                        site_relative_url=site,
                        recycle=True,
                    )
                except Exception:
                    errors += 1
        if errors:
            QMessageBox.warning(self, "Delete", f"Some items failed to delete ({errors}).")
        pane.refresh()

    def _copy_share_link(self) -> None:
        pane = self._active_pane()
        if not pane or pane.definition.kind not in ("sharepoint", "translation"):
            return
        if pane.definition.kind == "translation":
            base_id = pane.definition.base_workspace_id
            base_pane = self._workspace_panes.get(base_id) if base_id else None
            if not base_pane or base_pane.definition.kind != "sharepoint":
                QMessageBox.information(self, "Share Link", "Translation must reference a SharePoint workspace.")
                return
            share_site = base_pane.definition.site_relative_url
        else:
            base_pane = pane
            share_site = pane.definition.site_relative_url
        items = pane.current_items()
        if not items:
            return
        item = items[0]
        try:
            resp = self._backend.sp_share_link(
                item["path"],
                site_relative_url=share_site,
            )
            url = resp.get("url")
            if url:
                QApplication.clipboard().setText(url)
                self.statusBar().showMessage("Share link copied.", 4000)
            else:
                QMessageBox.information(self, "Share Link", "No share link available.")
        except Exception as exc:
            QMessageBox.warning(self, "Share Link", f"Failed to get share link: {exc}")

    def _open_in_sharepoint(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        import webbrowser

        if pane.definition.kind == "local":
            import subprocess

            path = items[0]["path"]
            target = path if os.path.isdir(path) else os.path.dirname(path)
            try:
                if os.name == "nt":
                    os.startfile(target)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", target])
                else:
                    subprocess.Popen(["xdg-open", target])
            except Exception as exc:
                QMessageBox.warning(self, "Open", f"Failed to open location: {exc}")
            return

        share_site = pane.definition.site_relative_url
        if pane.definition.kind == "translation":
            base_id = pane.definition.base_workspace_id
            base_pane = self._workspace_panes.get(base_id) if base_id else None
            if not base_pane:
                return
            share_site = base_pane.definition.site_relative_url
            item_path = items[0]["path"]
        else:
            item_path = items[0]["path"]
        try:
            resp = self._backend.sp_share_link(item_path, site_relative_url=share_site)
            url = resp.get("url")
            if url:
                webbrowser.open(url)
        except Exception as exc:
            QMessageBox.warning(self, "Open in SharePoint", f"Failed to open item: {exc}")

    # ------------------------------------------------------------- settings --
    def _create_translator(self) -> Translator:
        api_key = (self._cfg.api_key or "").strip()
        if api_key:
            return OpenAITranslator(api_key=api_key, model=self._cfg.model)
        try:
            info = self._backend.get_settings()
            if info.get("has_api_key"):
                return BackendTranslator(self._backend.base_url)
        except Exception:
            pass
        return IdentityTranslator()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._cfg, self)
        dlg.exec()
        self._cfg = load_config()
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        self._translator = self._create_translator()
        for pane in self._workspace_panes.values():
            pane.set_translator(self._translator)

    # ---------------------------------------------------------------- misc ---
    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_workspaces()
        super().closeEvent(event)
