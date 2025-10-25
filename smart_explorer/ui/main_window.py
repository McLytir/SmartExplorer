from __future__ import annotations

import base64
import colorsys
import os
import sys
import subprocess
import uuid
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QPalette, QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QCompleter,
    QLineEdit,
    QMessageBox,
    QMenu,
    QSplitter,
    QToolBar,
    QWidget,
    QVBoxLayout,
    QDialog,
    QTabBar,
)

from ..api.backend_client import BackendClient
from ..services.rename_service import apply_rename, safe_new_name
from ..settings import AppConfig, load_config, save_config
from ..translation_cache import TranslationCache
from ..translators.backend_translator import BackendTranslator
from ..translators.base import IdentityTranslator, Translator
from ..translators.openai_translator import OpenAITranslator
from ..translators.google_free_translator import GoogleFreeTranslator
from ..translators.libretranslate_translator import LibreTranslateTranslator
from ..workspaces import (
    FavoriteLocation,
    FavoritesManager,
    LayoutDefinition,
    LayoutManager,
    WorkspaceDefinition,
    WorkspaceManager,
    ensure_favorites,
    ensure_layouts,
    ensure_workspaces,
)
from .favorites_panel import FavoritesPanel
from .settings_dialog import SettingsDialog
from .sharepoint_selector import SharePointSelectorDialog
from .translation_dialog import TranslationWorkspaceDialog
from .workspace_pane import WorkspacePane
from .rename_preview_dialog import RenamePreviewDialog, RenameCandidate
from .preview_pane import PreviewPane


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SmartExplorer — Workspaces")
        self.resize(1400, 820)

        self._cfg: AppConfig = load_config()
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        self._workspace_manager: WorkspaceManager = ensure_workspaces(self._cfg)
        self._favorites_manager: FavoritesManager = ensure_favorites(self._cfg)
        self._layouts_manager: LayoutManager = ensure_layouts(self._cfg)

        self._translator: Translator = self._create_translator()
        self._translation_cache = TranslationCache()
        self._ignore_patterns = self._cfg.ignore_patterns or []

        self._workspace_panes: Dict[str, WorkspacePane] = {}
        self._active_workspace_id: Optional[str] = None
    # Preview pane is off by default; created on demand when user toggles it
    self._preview_enabled: bool = False
    self._preview_widget: Optional[PreviewPane] = None
        self._clipboard: Dict[str, dict] = {}
        self._selection_sync_block: set[str] = set()
        self._shortcuts: List[QShortcut] = []
        self._address_bar: Optional[QLineEdit] = None
        self._theme_specs = self._build_theme_specs()
        self._workspace_color_map: Dict[str, str] = {}
        self._base_color_palette: List[str] = self._theme_base_palette()
        self._rename_undo_stack: List[List[dict]] = []
        self._layout_tabs: Optional[QTabBar] = QTabBar(self)
        self._layout_tab_ids: List[str] = []
        self._layout_tabs.setExpanding(False)
        self._layout_tabs.setMovable(False)
        self._layout_tabs.setUsesScrollButtons(True)
        self._layout_tabs.setDocumentMode(True)
        self._layout_tabs.tabBarClicked.connect(self._on_layout_tab_clicked)

        self._container = QWidget(self)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        self._toolbar = self._build_toolbar()
        self.addToolBar(Qt.TopToolBarArea, self._toolbar)

        self._workspace_holder = QWidget()
        self._workspace_layout = QVBoxLayout(self._workspace_holder)
        self._workspace_layout.setContentsMargins(0, 0, 0, 0)
        self._workspace_layout.setSpacing(0)
        self._pane_splitter: Optional[QSplitter] = None

        self._favorites_panel = FavoritesPanel(self)
        self._favorites_panel.set_position(self._cfg.favorites_bar_position)
        self._favorites_panel.favorite_selected.connect(self._on_favorite_selected)
        self._favorites_panel.favorite_add_requested.connect(self._on_add_favorite)
        self._favorites_panel.favorite_remove_requested.connect(self._on_remove_favorite)
        self._favorites_panel.favorite_rename_requested.connect(self._on_rename_favorite)
        self._favorites_panel.favorite_move_requested.connect(self._on_move_favorite)
        self._favorites_panel.layout_save_requested.connect(self._on_save_layout)
        self._favorites_panel.layout_apply_requested.connect(self._on_apply_layout)
        self._favorites_panel.layout_remove_requested.connect(self._on_remove_layout)
        self._favorites_panel.layout_rename_requested.connect(self._on_rename_layout)
        self._favorites_panel.layout_move_requested.connect(self._on_move_layout)
        self._favorites_panel.position_changed.connect(self._change_favorites_position)

        self._main_splitter: Optional[QSplitter] = None
        self._favorites_index = 0
        self._updating_splitter = False
        self._apply_theme()
        self._arrange_favorites_panel()

        self.setCentralWidget(self._container)
        self._refresh_favorites_panel()
        self._rebuild_workspace_area()
        self.statusBar().showMessage("Ready")
        self._setup_shortcuts()
        self._refresh_layout_tabs()

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

    # Toggle preview pane (off by default to avoid clutter)
    toggle_preview = QAction("Preview Pane", self)
    toggle_preview.setCheckable(True)
    toggle_preview.setChecked(False)
    toggle_preview.setToolTip("Show/Hide the optional preview pane")
    toggle_preview.triggered.connect(self._toggle_preview_pane)
    tb.addAction(toggle_preview)

        tb.addSeparator()

        goto_action = QAction("Go To…", self)
        goto_action.setShortcut(QKeySequence("Ctrl+K"))
        goto_action.triggered.connect(self._open_go_to_palette)
        tb.addAction(goto_action)
        self.addAction(goto_action)
        # macOS-friendly alternative (⌘K)
        try:
            goto_action_mac = QShortcut(QKeySequence("Meta+K"), self)
            goto_action_mac.activated.connect(self._open_go_to_palette)
            self._shortcuts.append(goto_action_mac)
        except Exception:
            pass

        self._address_bar = QLineEdit(self)
        self._address_bar.setPlaceholderText("Path")
        self._address_bar.setClearButtonEnabled(True)
        self._address_bar.setMinimumWidth(320)
        self._address_bar.returnPressed.connect(self._on_address_bar_return)
        tb.addWidget(self._address_bar)

        # Local path autocompletion in address bar
        try:
            from PySide6.QtWidgets import QFileSystemModel
            fs_model = QFileSystemModel(self)
            # Use root of current drive or system root
            fs_model.setRootPath("")
            completer = QCompleter(self)
            completer.setModel(fs_model)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self._address_bar.setCompleter(completer)
        except Exception:
            pass

        # Focus address bar shortcut
        focus_addr = QShortcut(QKeySequence("Ctrl+L"), self)
        focus_addr.activated.connect(lambda: (self._address_bar.setFocus() if self._address_bar else None))
        self._shortcuts.append(focus_addr)
        try:
            focus_addr_mac = QShortcut(QKeySequence("Meta+L"), self)
            focus_addr_mac.activated.connect(lambda: (self._address_bar.setFocus() if self._address_bar else None))
            self._shortcuts.append(focus_addr_mac)
        except Exception:
            pass

        # Undo last rename batch
        undo_action = QAction("Undo Last Rename", self)
        undo_action.triggered.connect(self._undo_last_rename_batch)
        tb.addAction(undo_action)

        # Follow base toggle for translation panes
        self._follow_toggle = QAction("Follow Base", self)
        self._follow_toggle.setCheckable(True)
        self._follow_toggle.setChecked(True)
        self._follow_toggle.triggered.connect(self._toggle_follow_active)
        tb.addAction(self._follow_toggle)
        # Initially disabled until a translation pane is active
        self._follow_toggle.setEnabled(False)

        return tb

    # ------------------------------------------------------------- workspaces
    def _setup_shortcuts(self) -> None:
        for seq, offset in (("Ctrl+Shift+Left", -1), ("Ctrl+Shift+Right", 1), ("Ctrl+Shift+Up", -1), ("Ctrl+Shift+Down", 1)):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(lambda checked=False, o=offset: self._move_active_workspace(o))
            self._shortcuts.append(shortcut)
        for seq, action in (
            ("Alt+Left", "back"),
            ("Alt+Right", "forward"),
            ("Alt+Up", "up"),
            ("Meta+[", "back"),
            ("Meta+]", "forward"),
            ("Meta+Up", "up"),
        ):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(lambda checked=False, a=action: self._navigate_active_pane(a))
            self._shortcuts.append(shortcut)
        self._sync_address_bar()

    def _toggle_follow_active(self, checked: bool) -> None:
        pane = self._active_pane()
        if not pane or pane.definition.kind != "translation":
            return
        pane.set_follow_base(bool(checked))
        self._on_pane_link_toggled(pane.id, bool(checked))

    def _toggle_preview_pane(self, checked: bool) -> None:
        """Create/destroy the preview pane and rebuild the workspace layout."""
        try:
            self._preview_enabled = bool(checked)
            if self._preview_enabled and self._preview_widget is None:
                try:
                    self._preview_widget = PreviewPane(self)
                    # When user requests open from preview, reuse existing opening logic
                    self._preview_widget.open_requested.connect(lambda p: self._on_workspace_item_activated(self._active_workspace_id or "", p))
                except Exception:
                    self._preview_widget = None
            # Rebuild layout so splitter wraps the preview pane when enabled
            self._rebuild_workspace_area(focus_workspace_id=self._active_workspace_id)
        except Exception:
            pass

    def _navigate_active_pane(self, action: str) -> None:
        pane = self._active_pane()
        if not pane:
            return
        if action == "back":
            pane.navigate_back()
        elif action == "forward":
            pane.navigate_forward()
        elif action == "up":
            pane.navigate_up()

    def _on_address_bar_return(self) -> None:
        if not self._address_bar:
            return
        pane = self._active_pane()
        if not pane:
            return
        target = self._address_bar.text().strip()
        if not target:
            return
        if not pane.go_to_path(target):
            QMessageBox.warning(self, "Navigate", f"Unable to open '{target}'.")
            self._sync_address_bar()

    def _open_go_to_palette(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        from PySide6.QtWidgets import QInputDialog
        current = pane.current_path() or ""
        text, ok = QInputDialog.getText(self, "Go To", "Path:", text=current)
        if not ok:
            return
        target = (text or current).strip()
        if target:
            if not pane.go_to_path(target):
                QMessageBox.warning(self, "Go To", f"Unable to open '{target}'.")
            self._sync_address_bar()

    def _sync_address_bar(self) -> None:
        if not self._address_bar:
            return
        pane = self._active_pane()
        text = pane.current_path() if pane else ""
        self._update_address_bar_text(text)

    def _update_address_bar_text(self, text: str) -> None:
        if not self._address_bar:
            return
        blocker = self._address_bar.blockSignals(True)
        self._address_bar.setText(text)
        self._address_bar.blockSignals(blocker)

    def _on_workspace_path_changed(self, workspace_id: str, path: str) -> None:
        if workspace_id == self._active_workspace_id:
            self._update_address_bar_text(path)
        pane = self._workspace_panes.get(workspace_id)
        if pane:
            pane.set_title(self._display_name_for_pane(pane))
            # Keep translation panes mirrored to the base pane's path (if linked)
            if pane.definition.kind != "translation":
                for dep in self._translation_dependents(workspace_id):
                    try:
                        if getattr(dep.definition, "follow_base", True):
                            dep.set_root_to_path(path, record=False, emit=False)
                        dep.set_title(self._display_name_for_pane(dep))
                    except Exception:
                        pass
            else:
                for dep in self._translation_dependents(workspace_id):
                    dep.set_title(self._display_name_for_pane(dep))

    def _display_name_for_pane(self, pane: WorkspacePane) -> str:
        try:
            kind = pane.definition.kind
            # Manual override takes precedence
            override = getattr(pane.definition, "title_override", None)
            if override:
                return override
            if kind == "translation":
                base_id = pane.definition.base_workspace_id
                language = pane.definition.language or (getattr(self._cfg, "target_language", None) or "English")
                base_title = ""
                if base_id and base_id in self._workspace_panes:
                    base_title = self._display_name_for_pane(self._workspace_panes[base_id])
                else:
                    base_title = pane.definition.name or "Translation"
                return f"{base_title} → {language}"
            if kind == "local":
                p = pane.current_path() or pane.definition.root_path or ""
                if not p:
                    return pane.definition.name or "Local"
                drive, rest = os.path.splitdrive(p)
                tail = os.path.basename(p.rstrip("/\\"))
                if not tail:
                    return (drive + os.sep) if drive else os.sep
                return tail
            if kind == "sharepoint":
                p = pane.current_path() or pane.definition.server_relative_url or "/"
                if not p:
                    return pane.definition.name or "SharePoint"
                s = p.rstrip("/")
                if not s or s == "/":
                    return "SharePoint"
                label = s.split("/")[-1] or "SharePoint"
                return label
        except Exception:
            pass
        return pane.definition.name or "Pane"

    def _build_theme_specs(self) -> Dict[str, dict]:
        return {
            "light": {
                "palette": {
                    "Window": "#f5f6fa",
                    "WindowText": "#1f2b3a",
                    "Base": "#ffffff",
                    "AlternateBase": "#f0f3f9",
                    "ToolTipBase": "#ffffe0",
                    "ToolTipText": "#1f2b3a",
                    "Text": "#1f2b3a",
                    "Button": "#eef1f7",
                    "ButtonText": "#1f2b3a",
                    "BrightText": "#ff4c3b",
                    "Highlight": "#3d6dcc",
                    "HighlightedText": "#ffffff",
                    "Link": "#1d5fc1",
                    "LinkVisited": "#7b4bb7",
                    "PlaceholderText": "#8b97ab",
                    "Mid": "#c7d0de",
                    "Midlight": "#dde4f0",
                    "Shadow": "#a5afc3",
                    "Dark": "#b4bed0",
                    "DisabledText": "#aeb8c6",
                },
                "stylesheet": """
QToolBar { background-color: #edf1fb; border: none; spacing: 6px; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QTreeView {
    background-color: #ffffff;
    color: #1f2b3a;
    border: 1px solid #cbd5e3;
    selection-background-color: #3d6dcc;
    selection-color: #ffffff;
}
QTreeView {
    alternate-background-color: #f0f3f9;
}
QLabel { color: #1f2b3a; }
""",
                "base_colors": [
                    "#dde7ff",
                    "#ffe4c1",
                    "#dff2e3",
                    "#e6dbff",
                    "#ffd9e8",
                    "#d9f1f7",
                ],
                "translation_adjust": {"dh": 0.04, "dl": -0.05, "ds": 0.0},
                "active_adjust": {"dl": -0.07, "ds": 0.0},
            },
            "dark": {
                "palette": {
                    "Window": "#25292e",
                    "WindowText": "#e8e8e8",
                    "Base": "#1e2226",
                    "AlternateBase": "#2a3036",
                    "ToolTipBase": "#363c44",
                    "ToolTipText": "#f0f0f0",
                    "Text": "#e8e8e8",
                    "Button": "#2d3239",
                    "ButtonText": "#e8e8e8",
                    "BrightText": "#ff735c",
                    "Highlight": "#4669aa",
                    "HighlightedText": "#ffffff",
                    "Link": "#7aa7ff",
                    "LinkVisited": "#98b7ff",
                    "PlaceholderText": "#9aa4b0",
                    "Mid": "#3b4149",
                    "Midlight": "#434a52",
                    "Shadow": "#16181c",
                    "Dark": "#1a1c1f",
                    "DisabledText": "#6f7985",
                },
                "stylesheet": """
QToolBar { background-color: #2d3239; border: none; spacing: 6px; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QTreeView {
    background-color: #1e2226;
    color: #e8e8e8;
    border: 1px solid #474f5a;
    selection-background-color: #4669aa;
    selection-color: #ffffff;
}
QTreeView {
    alternate-background-color: #2a3036;
}
QLabel { color: #e8e8e8; }
""",
                "base_colors": [
                    "#425472",
                    "#6c4c7d",
                    "#4a6f59",
                    "#7a5a4a",
                    "#586b7f",
                    "#5a627d",
                ],
                "translation_adjust": {"dh": 0.05, "dl": 0.06, "ds": 0.02},
                "active_adjust": {"dl": 0.08, "ds": 0.0},
            },
            "solarized_light": {
                "palette": {
                    "Window": "#fdf6e3",
                    "WindowText": "#586e75",
                    "Base": "#fffdf5",
                    "AlternateBase": "#f3e6c6",
                    "ToolTipBase": "#fef9dd",
                    "ToolTipText": "#586e75",
                    "Text": "#586e75",
                    "Button": "#f2e6c5",
                    "ButtonText": "#586e75",
                    "BrightText": "#d33682",
                    "Highlight": "#268bd2",
                    "HighlightedText": "#fdf6e3",
                    "Link": "#2aa198",
                    "LinkVisited": "#6c71c4",
                    "PlaceholderText": "#8a9aa2",
                    "Mid": "#c7b99b",
                    "Midlight": "#e6d7b4",
                    "Shadow": "#b6a67d",
                    "Dark": "#b3a373",
                    "DisabledText": "#a8afaa",
                },
                "stylesheet": """
QToolBar { background-color: #f2e7c7; border: none; spacing: 6px; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QTreeView {
    background-color: #fffdf5;
    color: #586e75;
    border: 1px solid #d3c7a0;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
}
QTreeView {
    alternate-background-color: #f6edd0;
}
QLabel { color: #586e75; }
""",
                "base_colors": [
                    "#d7e8f2",
                    "#f0ddb2",
                    "#dcefe3",
                    "#ede1f4",
                    "#f8d9c6",
                    "#e3ecda",
                ],
                "translation_adjust": {"dh": 0.03, "dl": -0.04, "ds": 0.0},
                "active_adjust": {"dl": -0.06, "ds": 0.0},
            },
            "solarized_dark": {
                "palette": {
                    "Window": "#002b36",
                    "WindowText": "#eee8d5",
                    "Base": "#073642",
                    "AlternateBase": "#0c3a46",
                    "ToolTipBase": "#004051",
                    "ToolTipText": "#eee8d5",
                    "Text": "#eee8d5",
                    "Button": "#0c3a46",
                    "ButtonText": "#eee8d5",
                    "BrightText": "#cb4b16",
                    "Highlight": "#268bd2",
                    "HighlightedText": "#fdf6e3",
                    "Link": "#2aa198",
                    "LinkVisited": "#6c71c4",
                    "PlaceholderText": "#93a1a1",
                    "Mid": "#0f4a54",
                    "Midlight": "#165660",
                    "Shadow": "#001f27",
                    "Dark": "#00242d",
                    "DisabledText": "#68767a",
                },
                "stylesheet": """
QToolBar { background-color: #073642; border: none; spacing: 6px; }
QLineEdit, QTextEdit, QListWidget, QComboBox, QTreeView {
    background-color: #002b36;
    color: #eee8d5;
    border: 1px solid #586e75;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
}
QTreeView {
    alternate-background-color: #073642;
}
QLabel { color: #eee8d5; }
""",
                "base_colors": [
                    "#2f4550",
                    "#5c3f3f",
                    "#2d5047",
                    "#403d63",
                    "#5b4c2f",
                    "#2f5761",
                ],
                "translation_adjust": {"dh": 0.03, "dl": 0.06, "ds": 0.02},
                "active_adjust": {"dl": 0.08, "ds": 0.0},
            },
        }

    def _apply_palette_colors(self, palette: QPalette, colors: Dict[str, str]) -> None:
        role_map = {
            "Window": QPalette.Window,
            "WindowText": QPalette.WindowText,
            "Base": QPalette.Base,
            "AlternateBase": QPalette.AlternateBase,
            "ToolTipBase": QPalette.ToolTipBase,
            "ToolTipText": QPalette.ToolTipText,
            "Text": QPalette.Text,
            "Button": QPalette.Button,
            "ButtonText": QPalette.ButtonText,
            "BrightText": QPalette.BrightText,
            "Highlight": QPalette.Highlight,
            "HighlightedText": QPalette.HighlightedText,
            "Link": QPalette.Link,
            "LinkVisited": QPalette.LinkVisited,
            "PlaceholderText": QPalette.PlaceholderText,
            "Mid": QPalette.Mid,
            "Midlight": QPalette.Midlight,
            "Shadow": QPalette.Shadow,
            "Dark": QPalette.Dark,
        }

        for name, value in colors.items():
            if name == "DisabledText":
                qcolor = QColor(value)
                palette.setColor(QPalette.Disabled, QPalette.Text, qcolor)
                palette.setColor(QPalette.Disabled, QPalette.ButtonText, qcolor)
                palette.setColor(QPalette.Disabled, QPalette.WindowText, qcolor)
                palette.setColor(QPalette.Disabled, QPalette.PlaceholderText, qcolor)
                continue

            role = role_map.get(name)
            if role is None:
                continue
            qcolor = QColor(value)

            if role == QPalette.PlaceholderText:
                for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
                    palette.setColor(group, role, qcolor)
                continue

            for group in (QPalette.Active, QPalette.Inactive):
                palette.setColor(group, role, qcolor)

            if role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
                palette.setColor(QPalette.Disabled, role, QColor(value).lighter(150))
            elif role == QPalette.Highlight:
                palette.setColor(QPalette.Disabled, role, QColor(value).darker(170))
            elif role == QPalette.HighlightedText:
                palette.setColor(QPalette.Disabled, role, QColor(value).lighter(140))
            elif role == QPalette.Base:
                palette.setColor(QPalette.Disabled, role, QColor(value).darker(120))
            else:
                palette.setColor(QPalette.Disabled, role, qcolor)

    def _theme_spec(self, theme: Optional[str] = None) -> Dict[str, dict]:
        key = theme or getattr(self._cfg, "theme", "light")
        return self._theme_specs.get(key, self._theme_specs["light"])

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if not app:
            return
        spec = self._theme_spec()
        palette = QPalette()
        self._apply_palette_colors(palette, spec.get("palette", {}))
        app.setPalette(palette)
        stylesheet = spec.get("stylesheet")
        if stylesheet:
            app.setStyleSheet(stylesheet)
        else:
            app.setStyleSheet("")

        self._base_color_palette = list(spec.get("base_colors", []))
        self._workspace_color_map = {}

        if hasattr(self, "_container") and self._container is not None:
            self._container.setStyleSheet("background-color: palette(Window);")
        if hasattr(self, "_workspace_holder") and self._workspace_holder is not None:
            self._workspace_holder.setStyleSheet("background-color: palette(Window);")
        if hasattr(self, "_favorites_panel") and self._favorites_panel is not None:
            self._favorites_panel.setStyleSheet("background-color: palette(Base);")

        if hasattr(self, "_workspace_manager"):
            for definition in self._workspace_manager.definitions():
                header_color, active_color = self._header_colors_for(definition)
                pane = self._workspace_panes.get(definition.id)
                if not pane:
                    continue
                pane.update_header_palette(header_color, active_color)
                pane.set_active(definition.id == self._active_workspace_id)

    def _theme_base_palette(self) -> List[str]:
        spec = self._theme_spec()
        return list(spec.get("base_colors", []))

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

        if self._pane_splitter:
            self._workspace_layout.removeWidget(self._pane_splitter)
            self._pane_splitter.deleteLater()

        self._pane_splitter = self._build_splitter_layout(panes_in_order)
        self._normalize_splitter(self._pane_splitter)

        # If preview pane is enabled, place it to the right of the workspace panes
        try:
            if getattr(self, "_preview_enabled", False) and getattr(self, "_preview_widget", None):
                combined = QSplitter(Qt.Horizontal, self)
                combined.addWidget(self._pane_splitter)
                combined.addWidget(self._preview_widget)
                self._workspace_layout.addWidget(combined, 1)
            else:
                self._workspace_layout.addWidget(self._pane_splitter, 1)
        except Exception:
            # Fallback to just the pane splitter
            self._workspace_layout.addWidget(self._pane_splitter, 1)
        target_focus = focus_workspace_id or self._active_workspace_id or (panes_in_order[0].id if panes_in_order else None)
        self._focus_workspace(target_focus)

        # Restore state where possible
        for wid, pane in self._workspace_panes.items():
            pane.restore_state(prev_states.get(wid, {}))
            try:
                pane.set_title(self._display_name_for_pane(pane))
            except Exception:
                pass
        self._sync_address_bar()

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
        self._sync_address_bar()
        # Update follow toggle state/visibility
        try:
            if hasattr(self, "_follow_toggle") and self._follow_toggle:
                pane = self._workspace_panes.get(self._active_workspace_id) if self._active_workspace_id else None
                if pane and pane.definition.kind == "translation":
                    self._follow_toggle.setEnabled(True)
                    self._follow_toggle.setChecked(getattr(pane.definition, "follow_base", True))
                else:
                    self._follow_toggle.setEnabled(False)
        except Exception:
            pass

    def _translation_dependents(self, base_workspace_id: str) -> List[WorkspacePane]:
        return [
            pane
            for pane in self._workspace_panes.values()
            if pane.definition.kind == "translation" and pane.definition.base_workspace_id == base_workspace_id
        ]

    def _arrange_favorites_panel(self) -> None:
        if self._main_splitter is not None:
            try:
                self._main_splitter.splitterMoved.disconnect(self._on_favorites_splitter_moved)
            except Exception:
                pass
            self._main_splitter.setParent(None)
            self._main_splitter.deleteLater()
        position = getattr(self._cfg, "favorites_bar_position", "left") or "left"
        self._favorites_panel.set_position(position)
        orientation = Qt.Horizontal if position in {"left", "right"} else Qt.Vertical
        splitter = QSplitter(orientation, self)
        self._main_splitter = splitter
        if position in {"left", "top"}:
            splitter.addWidget(self._favorites_panel)
            splitter.addWidget(self._workspace_holder)
            self._favorites_index = 0
        else:
            splitter.addWidget(self._workspace_holder)
            splitter.addWidget(self._favorites_panel)
            self._favorites_index = 1
        splitter.splitterMoved.connect(self._on_favorites_splitter_moved)

        # Replace existing widgets in container layout
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        # Layout tabs (layouts as quick tabs)
        if self._layout_tabs is not None:
            self._container_layout.addWidget(self._layout_tabs)
        self._container_layout.addWidget(splitter, 1)
        self._update_splitter_sizes()

    # ---------------------------------------------------------- layout tabs --
    def _refresh_layout_tabs(self) -> None:
        if not self._layout_tabs:
            return
        self._layout_tabs.blockSignals(True)
        try:
            while self._layout_tabs.count():
                self._layout_tabs.removeTab(0)
            self._layout_tab_ids = []
            for layout in self._layouts_manager.all():
                self._layout_tabs.addTab(layout.name)
                self._layout_tab_ids.append(layout.id)
        finally:
            self._layout_tabs.blockSignals(False)

    def _on_layout_tab_clicked(self, index: int) -> None:
        if 0 <= index < len(self._layout_tab_ids):
            self._on_apply_layout(self._layout_tab_ids[index])

    def _update_splitter_sizes(self) -> None:
        if not self._main_splitter:
            return
        if self._updating_splitter:
            return
        orientation = self._main_splitter.orientation()
        fav_size = getattr(self._cfg, "favorites_bar_size", 240)
        fav_size = max(120, min(600, fav_size))
        self._updating_splitter = True
        try:
            if orientation == Qt.Horizontal:
                other = max(200, self.width() - fav_size)
            else:
                other = max(200, self.height() - fav_size)
            if self._favorites_index == 0:
                sizes = [fav_size, other]
            else:
                sizes = [other, fav_size]
            self._main_splitter.setSizes(sizes)
        finally:
            self._updating_splitter = False

    def _on_favorites_splitter_moved(self, pos: int, index: int) -> None:
        if self._updating_splitter:
            return
        if not self._main_splitter:
            return
        sizes = self._main_splitter.sizes()
        if not sizes:
            return
        fav_size = sizes[self._favorites_index if self._favorites_index < len(sizes) else 0]
        self._cfg.favorites_bar_size = fav_size
        self._persist_state(save_workspaces=False)

    def _change_favorites_position(self, position: str) -> None:
        if position not in {"left", "right", "top", "bottom"}:
            return
        if position == self._cfg.favorites_bar_position:
            return
        self._cfg.favorites_bar_position = position
        self._favorites_panel.set_position(position)
        self._arrange_favorites_panel()
        self._persist_state(save_workspaces=False)

    def _refresh_favorites_panel(self) -> None:
        self._favorites_panel.set_favorites([fav.to_config() for fav in self._favorites_manager.all()])
        self._favorites_panel.set_layouts([layout.to_config() for layout in self._layouts_manager.all()])

    # ------------------------------------------------------------- favorites/layouts
    def _on_favorite_selected(self, favorite_id: str) -> None:
        favorite = self._favorites_manager.get(favorite_id)
        if not favorite:
            return
        self._open_favorite(favorite)

    def _on_add_favorite(self) -> None:
        pane = self._active_pane()
        if not pane:
            QMessageBox.information(self, "Favorites", "Select a pane to add as a favorite.")
            return
        favorite = self._favorite_from_pane(pane)
        if not favorite:
            QMessageBox.warning(self, "Favorites", "Unable to determine location for this pane.")
            return
        favorite = self._favorites_manager.add(favorite)
        self._refresh_favorites_panel()
        self._favorites_panel.select_favorite(favorite.id)
        self._persist_state(save_workspaces=False)

    def _on_remove_favorite(self, favorite_id: str) -> None:
        favorite = self._favorites_manager.get(favorite_id)
        if not favorite:
            return
        if QMessageBox.question(self, "Favorites", f"Remove favorite '{favorite.name}'?") != QMessageBox.Yes:
            return
        self._favorites_manager.remove(favorite_id)
        self._refresh_favorites_panel()
        self._persist_state(save_workspaces=False)

    def _on_rename_favorite(self, favorite_id: str) -> None:
        favorite = self._favorites_manager.get(favorite_id)
        if not favorite:
            return
        name, ok = QInputDialog.getText(self, "Rename Favorite", "Name:", text=favorite.name)
        if not ok or not name.strip():
            return
        favorite.name = name.strip()
        self._favorites_manager.update(favorite)
        self._refresh_favorites_panel()
        self._favorites_panel.select_favorite(favorite.id)
        self._persist_state(save_workspaces=False)

    def _on_move_favorite(self, favorite_id: str, offset: int) -> None:
        self._favorites_manager.move_by_offset(favorite_id, offset)
        self._refresh_favorites_panel()
        self._favorites_panel.select_favorite(favorite_id)
        self._persist_state(save_workspaces=False)

    def _favorite_from_pane(self, pane: WorkspacePane) -> Optional[FavoriteLocation]:
        items = pane.current_items()
        path = items[0]["path"] if items else None
        if pane.definition.kind == "local":
            base_path = path or pane.definition.root_path
            if not base_path:
                return None
            base_path = os.path.abspath(base_path)
            name = os.path.basename(base_path.rstrip(os.sep)) or base_path
            return FavoriteLocation(
                id=f"fav-{uuid.uuid4().hex[:6]}",
                kind="local",
                name=name,
                root_path=base_path,
            )
        if pane.definition.kind == "sharepoint":
            base_path = path or pane.definition.server_relative_url
            if not base_path:
                return None
            if not base_path.startswith("/"):
                base_path = "/" + base_path
            site_rel = pane.definition.site_relative_url
            name = os.path.basename(base_path.rstrip("/")) or pane.definition.name or "SharePoint"
            return FavoriteLocation(
                id=f"fav-{uuid.uuid4().hex[:6]}",
                kind="sharepoint",
                name=name,
                site_relative_url=site_rel,
                server_relative_url=base_path,
            )
        return None

    def _open_favorite(self, favorite: FavoriteLocation) -> None:
        pane = self._active_pane()
        if pane and pane.definition.kind != "translation" and pane.definition.kind == favorite.kind:
            definition = pane.definition
        else:
            definition = WorkspaceDefinition(
                id=self._workspace_manager.ensure_unique_id("ws"),
                kind="local",
                name=favorite.name,
            )
            pane = None
        if favorite.kind == "local":
            definition.kind = "local"
            definition.name = favorite.name
            definition.root_path = favorite.root_path
            definition.site_relative_url = None
            definition.server_relative_url = None
            definition.base_workspace_id = None
            definition.language = None
        elif favorite.kind == "sharepoint":
            definition.kind = "sharepoint"
            definition.name = favorite.name
            definition.site_relative_url = favorite.site_relative_url
            definition.server_relative_url = favorite.server_relative_url
            definition.root_path = None
            definition.base_workspace_id = None
            definition.language = None
        if definition.id in [ws.id for ws in self._workspace_manager.definitions()]:
            self._workspace_manager.update(definition)
        else:
            self._workspace_manager.add(definition)
        self._persist_state()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)
        if favorite.kind == "sharepoint" and favorite.server_relative_url:
            pane = self._workspace_panes.get(definition.id)
            if pane:
                pane.set_root_to_path(favorite.server_relative_url)

    def _on_save_layout(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Layout", "Layout name:", text=f"Layout {len(self._layouts_manager.all()) + 1}")
        if not ok or not name.strip():
            return
        layout = LayoutDefinition(
            id=f"layout-{uuid.uuid4().hex[:6]}",
            name=name.strip(),
            workspaces=self._workspace_manager.to_config(),
        )
        self._layouts_manager.add(layout)
        self._refresh_favorites_panel()
        self._favorites_panel.select_layout(layout.id)
        self._persist_state(save_workspaces=False)
        self._refresh_layout_tabs()

    def _on_apply_layout(self, layout_id: str) -> None:
        layout = self._layouts_manager.get(layout_id)
        if not layout:
            return
        if QMessageBox.question(self, "Layouts", f"Apply layout '{layout.name}'? This will replace current panes.") != QMessageBox.Yes:
            return
        self._cfg.workspaces = list(layout.workspaces)
        self._workspace_manager = ensure_workspaces(self._cfg)
        self._persist_state()
        self._rebuild_workspace_area()
        self._refresh_layout_tabs()

    def _on_remove_layout(self, layout_id: str) -> None:
        layout = self._layouts_manager.get(layout_id)
        if not layout:
            return
        if QMessageBox.question(self, "Layouts", f"Remove layout '{layout.name}'?") != QMessageBox.Yes:
            return
        self._layouts_manager.remove(layout_id)
        self._refresh_favorites_panel()
        self._persist_state(save_workspaces=False)
        self._refresh_layout_tabs()

    def _on_rename_layout(self, layout_id: str) -> None:
        layout = self._layouts_manager.get(layout_id)
        if not layout:
            return
        name, ok = QInputDialog.getText(self, "Rename Layout", "Name:", text=layout.name)
        if not ok or not name.strip():
            return
        layout.name = name.strip()
        self._layouts_manager.update(layout)
        self._refresh_favorites_panel()
        self._favorites_panel.select_layout(layout.id)
        self._persist_state(save_workspaces=False)
        self._refresh_layout_tabs()

    def _on_move_layout(self, layout_id: str, offset: int) -> None:
        self._layouts_manager.move_by_offset(layout_id, offset)
        self._refresh_favorites_panel()
        self._favorites_panel.select_layout(layout_id)
        self._persist_state(save_workspaces=False)
        self._refresh_layout_tabs()

    def _move_active_workspace(self, offset: int) -> None:
        if not self._active_workspace_id or offset == 0:
            return
        self._workspace_manager.move_by_offset(self._active_workspace_id, offset)
        self._persist_state()
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
        self._persist_state()
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
        self._persist_state()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _convert_workspace_to_translation(self, definition: WorkspaceDefinition) -> None:
        if definition.kind != "translation" and self._translation_dependents(definition.id):
            QMessageBox.warning(self, "Workspace", "Cannot convert a workspace that other translations depend on.")
            return
        base_options = []
        for ws in self._workspace_manager.definitions():
            if ws.id == definition.id or ws.kind not in ("local", "sharepoint"):
                continue
            pane2 = self._workspace_panes.get(ws.id)
            display2 = self._display_name_for_pane(pane2) if pane2 else (getattr(ws, "title_override", None) or ws.name)
            base_options.append((ws.id, display2))
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
        definition.follow_base = True
        definition.root_path = None
        definition.site_relative_url = None
        definition.server_relative_url = None
        base_name = dict(base_options).get(base_id, "Workspace")
        definition.name = f"{base_name} ({language})"
        self._workspace_manager.update(definition)
        self._persist_state()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _header_colors_for(self, definition: WorkspaceDefinition) -> Tuple[str, str]:
        base_key = definition.id if definition.kind != "translation" else (definition.base_workspace_id or definition.id)
        base_color = self._workspace_color_map.get(base_key)
        if not base_color:
            base_color = self._generate_base_color(len(self._workspace_color_map))
            self._workspace_color_map[base_key] = base_color
        spec = self._theme_spec()
        trans_adjust = spec.get("translation_adjust", {})
        active_adjust = spec.get("active_adjust", {})
        if definition.kind == "translation":
            header_color = self._adjust_color(
                base_color,
                dh=trans_adjust.get("dh", 0.0),
                dl=trans_adjust.get("dl", 0.0),
                ds=trans_adjust.get("ds", 0.0),
            )
        else:
            header_color = base_color
        active_color = self._adjust_color(
            header_color,
            dh=active_adjust.get("dh", 0.0),
            dl=active_adjust.get("dl", 0.0),
            ds=active_adjust.get("ds", 0.0),
        )
        return header_color, active_color

    def _generate_base_color(self, index: int) -> str:
        if self._base_color_palette:
            seed = self._base_color_palette[index % len(self._base_color_palette)]
            rotation = index // len(self._base_color_palette)
            if rotation:
                return self._adjust_color(seed, dh=0.08 * rotation, dl=0.02 * ((rotation % 2) * 2 - 1) * 0.5)
            return seed
        # fallback
        hue = (index * 0.61803398875) % 1.0
        return self._hls_to_hex(hue, 0.82, 0.4)

    @staticmethod
    def _adjust_color(color: str, dh: float = 0.0, dl: float = 0.0, ds: float = 0.0) -> str:
        h, l, s = MainWindow._hex_to_hls(color)
        h = (h + dh) % 1.0
        l = max(0.0, min(1.0, l + dl))
        s = max(0.0, min(1.0, s + ds))
        return MainWindow._hls_to_hex(h, l, s)

    @staticmethod
    def _hex_to_hls(color: str) -> Tuple[float, float, float]:
        color = color.lstrip("#")
        if len(color) != 6:
            color = "cccccc"
        r = int(color[0:2], 16) / 255.0
        g = int(color[2:4], 16) / 255.0
        b = int(color[4:6], 16) / 255.0
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return h, l, s

    @staticmethod
    def _hls_to_hex(h: float, l: float, s: float) -> str:
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    def _create_workspace_pane(self, definition: WorkspaceDefinition, base_panes: Dict[str, WorkspacePane]) -> WorkspacePane:
        header_color, header_active_color = self._header_colors_for(definition)
        pane = WorkspacePane(
            definition,
            backend_client=self._backend,
            translator=self._translator,
            translation_cache=self._translation_cache,
            ignore_patterns=self._ignore_patterns,
            base_panes=base_panes,
            header_color=header_color,
            header_active_color=header_active_color,
        )
        pane.activated.connect(self._on_workspace_item_activated)
        pane.drop_request.connect(self._on_workspace_drop_request)
        pane.path_changed.connect(self._on_workspace_path_changed)
        self._register_workspace_signals(pane)
        self._attach_context_menu(pane)
        return pane

    def _register_workspace_signals(self, pane: WorkspacePane) -> None:
        pane.selection_changed.connect(self._on_workspace_selection_changed)
        pane.expanded_path.connect(self._on_workspace_expanded)
        pane.collapsed_path.connect(self._on_workspace_collapsed)
        pane.pane_clicked.connect(self._on_pane_clicked)
        if hasattr(pane, "link_toggled"):
            pane.link_toggled.connect(self._on_pane_link_toggled)
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
        def add_action(text, handler=None, *, separator=False):
            act = QAction(text, pane)
            if separator:
                act.setSeparator(True)
            elif handler:
                act.triggered.connect(handler)
            pane.addAction(act)
            try:
                if hasattr(pane, "_view"):
                    pane._view.addAction(act)
                if hasattr(pane, "_icon_view"):
                    pane._icon_view.addAction(act)
            except Exception:
                pass
            return act

        # Open group
        add_action("Open", self._open_selected_items)
        add_action("Open With…", self._open_with_selected_items)
        add_action("Reveal in File Manager", self._reveal_in_file_manager)
        add_action("", separator=True)
        # Clipboard group
        add_action("Copy", lambda: self._clipboard_copy(False))
        add_action("Cut", lambda: self._clipboard_copy(True))
        add_action("Paste", self._clipboard_paste)
        add_action("Copy Path", self._copy_paths_to_clipboard)
        add_action("", separator=True)
        # Edit group
        add_action("Rename", self._rename_selected_item)
        add_action("New Folder", self._new_folder)
        add_action("Delete", self._delete_selected_items)
        add_action("", separator=True)
        # Translation group
        add_action("Apply Translation Rename", self._apply_translated_rename)
        add_action("", separator=True)
        # SharePoint group
        add_action("Copy Share Link", self._copy_share_link)
        add_action("Open in SharePoint", self._open_in_sharepoint)
        add_action("", separator=True)
        # Properties
        add_action("Properties", self._show_properties)
        close_action = QAction("Close Pane", pane)
        close_action.triggered.connect(lambda _, ws_id=pane.id: self._remove_workspace(ws_id))
        pane.addAction(close_action)
        try:
            reveal_label = "Reveal in Explorer" if sys.platform.startswith("win") else ("Reveal in Finder" if sys.platform == "darwin" else "Reveal in Files")
        except Exception:
            reveal_label = "Reveal in File Manager"
        reveal_action = QAction(reveal_label, pane)
        reveal_action.triggered.connect(self._reveal_in_file_manager)
        pane.addAction(reveal_action)
        copy_path_action = QAction("Copy Path", pane)
        copy_path_action.triggered.connect(self._copy_paths_to_clipboard)
        pane.addAction(copy_path_action)
        sp_reveal = QAction("Reveal in SharePoint (Web)", pane)
        sp_reveal.triggered.connect(self._open_in_sharepoint)
        pane.addAction(sp_reveal)

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
        self._persist_state()
        self._rebuild_workspace_area(focus_workspace_id=source_id)

    def _reveal_in_file_manager(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        path = items[0].get("path")
        if not path:
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer.exe", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                folder = os.path.dirname(path) if not items[0].get("is_dir") else path
                if folder:
                    try:
                        subprocess.Popen(["xdg-open", folder])
                    except Exception:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        except Exception:
            pass

    def _copy_paths_to_clipboard(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        text = "\n".join([it.get("path") for it in items if it.get("path")])
        if text:
            QGuiApplication.clipboard().setText(text)

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
        menu.addSeparator()
        rename_action = menu.addAction("Rename Pane…")
        reset_title_action = menu.addAction("Reset Auto Title")
        if definition.kind == "local":
            local_action.setEnabled(False)
        if definition.kind == "sharepoint":
            sharepoint_action.setEnabled(False)
        if definition.kind != "translation" and not any(ws.kind in ("local", "sharepoint") and ws.id != workspace_id for ws in self._workspace_manager.definitions()):
            translation_action.setEnabled(False)
        if definition.kind != "translation" and self._translation_dependents(definition.id):
            translation_action.setEnabled(False)
        if not getattr(definition, "title_override", None):
            reset_title_action.setEnabled(False)

        # Add link/unlink toggle for translation panes
        link_action = None
        if definition.kind == "translation":
            link_action = menu.addAction("Link to Base Navigation")
            link_action.setCheckable(True)
            try:
                link_action.setChecked(getattr(definition, "follow_base", True))
            except Exception:
                link_action.setChecked(True)

        action = menu.exec(global_pos)
        if not action:
            return
        if action is local_action:
            self._convert_workspace_to_local(definition)
        elif action is sharepoint_action:
            self._convert_workspace_to_sharepoint(definition)
        elif action is translation_action:
            self._convert_workspace_to_translation(definition)
        elif link_action is not None and action is link_action:
            new_state = not getattr(definition, "follow_base", True)
            definition.follow_base = new_state
            self._workspace_manager.update(definition)
            self._persist_state()
            if new_state and definition.base_workspace_id and definition.base_workspace_id in self._workspace_panes:
                base = self._workspace_panes[definition.base_workspace_id]
                pane.set_root_to_path(base.current_path(), record=False, emit=False)
        elif 'rename_action' in locals() and action is rename_action:
            current_title = self._display_name_for_pane(pane)
            new_name, ok = QInputDialog.getText(self, "Rename Pane", "Title:", text=current_title)
            if ok and new_name.strip():
                definition.title_override = new_name.strip()
                self._workspace_manager.update(definition)
                self._persist_state()
                pane.set_title(definition.title_override)
        elif 'reset_title_action' in locals() and action is reset_title_action:
            definition.title_override = None
            self._workspace_manager.update(definition)
            self._persist_state()
            pane.set_title(self._display_name_for_pane(pane))

    # ------------------------------------------------------------- workspace ops
    def _on_workspace_selection_changed(self, workspace_id: str) -> None:
        self._focus_workspace(workspace_id)
        pane = self._workspace_panes.get(workspace_id)
        if not pane:
            return
        selected = pane.current_items()
        try:
            title = self._display_name_for_pane(pane)
        except Exception:
            title = pane.definition.name
        self.statusBar().showMessage(f"{title}: {len(selected)} selected")
        self._mirror_selection(workspace_id)
        # keep toolbar follow toggle in sync
        try:
            if hasattr(self, "_follow_toggle") and self._follow_toggle:
                if pane.definition.kind == "translation":
                    self._follow_toggle.setEnabled(True)
                    self._follow_toggle.setChecked(getattr(pane.definition, "follow_base", True))
                else:
                    self._follow_toggle.setEnabled(False)
        except Exception:
            pass
        # Update preview pane (if enabled) with the selected paths from the active pane
        try:
            if getattr(self, "_preview_enabled", False) and getattr(self, "_preview_widget", None):
                paths = [it.get("path") for it in selected if it.get("path")]
                paths = [p for p in paths if p]
                if not paths:
                    self._preview_widget.preview_paths([])
                else:
                    # If this pane (or its base) is SharePoint, download file in background then preview
                    effective_kind = pane.definition.kind
                    effective_site = getattr(pane.definition, "site_relative_url", None)
                    if pane.definition.kind == "translation" and pane.definition.base_workspace_id:
                        base = self._workspace_panes.get(pane.definition.base_workspace_id)
                        if base:
                            effective_kind = base.definition.kind
                            effective_site = getattr(base.definition, "site_relative_url", None)

                    first = paths[0]
                    if effective_kind == "sharepoint":
                        # download asynchronously and preview when ready
                        try:
                            self._download_and_preview(first, effective_site)
                        except Exception:
                            # fallback: show no preview
                            self._preview_widget.preview_paths([])
                    else:
                        # local file: preview directly
                        self._preview_widget.preview_paths(paths[:10])
        except Exception:
            pass

    def _download_and_preview(self, path: str, site: Optional[str]) -> None:
        """Download SharePoint file in a background thread and preview it when finished.

        Writes to the OS temp dir and schedules the preview on the Qt main thread.
        """
        if not getattr(self, "_preview_widget", None):
            return

        # If an existing download is running, cancel it
        try:
            if getattr(self, "_active_download_worker", None):
                try:
                    self._active_download_worker.cancel()
                except Exception:
                    pass
                self._active_download_worker = None
        except Exception:
            pass

        # Define a cancellable worker that streams the download and reports progress
        class DownloadWorker:
            def __init__(self, outer: "MainWindow", server_path: str, site_rel: Optional[str]):
                self.outer = outer
                self.server_path = server_path
                self.site_rel = site_rel
                self._cancel_event = threading.Event()

            def cancel(self) -> None:
                self._cancel_event.set()

            def run(self) -> None:
                try:
                    from ..services.preview_cache import cached_download_path, save_existing_file
                    import httpx
                    import tempfile

                    # Check cache first
                    cached = cached_download_path(self.server_path)
                    if cached and os.path.exists(cached):
                        final_path = cached
                        # schedule show
                        from PySide6.QtCore import QTimer

                        def show():
                            try:
                                if getattr(self.outer, "_preview_widget", None):
                                    self.outer._preview_widget.preview_paths([final_path])
                                    self.outer._preview_widget.hide_progress()
                            except Exception:
                                pass

                        QTimer.singleShot(0, show)
                        return

                    url = self.outer._backend.base_url + "/api/sp/download"
                    params = {"server_relative_url": self.server_path}
                    if self.site_rel:
                        params["site_relative_url"] = self.site_rel

                    # Stream the response
                    with httpx.Client(timeout=None) as client:
                        with client.stream("GET", url, params=params) as r:
                            r.raise_for_status()
                            total = None
                            try:
                                total = int(r.headers.get("content-length"))
                            except Exception:
                                total = None
                            # write to a temp file
                            tf = tempfile.NamedTemporaryFile(delete=False)
                            temp_path = tf.name
                            downloaded = 0
                            chunk_size = 64 * 1024
                            for chunk in r.iter_bytes(chunk_size=chunk_size):
                                if self._cancel_event.is_set():
                                    try:
                                        tf.close()
                                    except Exception:
                                        pass
                                    try:
                                        os.remove(temp_path)
                                    except Exception:
                                        pass
                                    # notify UI to hide progress
                                    from PySide6.QtCore import QTimer

                                    QTimer.singleShot(0, lambda: getattr(self.outer, "_preview_widget", None).hide_progress() if getattr(self.outer, "_preview_widget", None) else None)
                                    return
                                tf.write(chunk)
                                downloaded += len(chunk)
                                # report progress (0-100) if total known
                                if total:
                                    pct = int(downloaded / total * 100)
                                else:
                                    pct = 0
                                from PySide6.QtCore import QTimer

                                QTimer.singleShot(0, lambda p=pct: getattr(self.outer, "_preview_widget", None).show_progress(p) if getattr(self.outer, "_preview_widget", None) else None)
                            try:
                                tf.close()
                            except Exception:
                                pass

                    # Move temp file into cache
                    final_cached = save_existing_file(self.server_path, temp_path)

                    # schedule UI update to show the cached file
                    from PySide6.QtCore import QTimer

                    def show_final():
                        try:
                            if getattr(self.outer, "_preview_widget", None):
                                self.outer._preview_widget.preview_paths([final_cached])
                                self.outer._preview_widget.hide_progress()
                        except Exception:
                            pass

                    QTimer.singleShot(0, show_final)
                except Exception as exc:
                    from PySide6.QtCore import QTimer
                    from PySide6.QtWidgets import QMessageBox

                    def warn():
                        try:
                            if getattr(self.outer, "_preview_widget", None):
                                self.outer._preview_widget.hide_progress()
                            QMessageBox.warning(self.outer, "Preview", f"Download failed: {exc}")
                        except Exception:
                            pass

                    QTimer.singleShot(0, warn)

        import threading

        worker = DownloadWorker(self, path, site)
        t = threading.Thread(target=worker.run, daemon=True)
        # store active worker so it can be cancelled
        self._active_download_worker = worker
        # when preview cancel requested, stop the worker
        try:
            self._preview_widget.cancel_requested.connect(lambda: worker.cancel())
        except Exception:
            pass
        # show initial progress UI
        try:
            self._preview_widget.show_progress(0)
        except Exception:
            pass
        t.start()

    def _on_pane_clicked(self, workspace_id: str) -> None:
        self._focus_workspace(workspace_id)

    def _on_pane_link_toggled(self, workspace_id: str, follow: bool) -> None:
        definition = self._workspace_manager.get(workspace_id)
        pane = self._workspace_panes.get(workspace_id)
        if not definition or not pane:
            return
        try:
            definition.follow_base = bool(follow)
            self._workspace_manager.update(definition)
            self._persist_state()
        except Exception:
            pass
        # update toolbar state
        try:
            if hasattr(self, "_follow_toggle") and self._active_workspace_id == workspace_id:
                self._follow_toggle.setEnabled(True)
                self._follow_toggle.setChecked(bool(follow))
        except Exception:
            pass
        # if linking now, sync path to base
        try:
            if follow and definition.base_workspace_id and definition.base_workspace_id in self._workspace_panes:
                base = self._workspace_panes[definition.base_workspace_id]
                pane.set_follow_base(True)
                pane.set_root_to_path(base.current_path(), record=False, emit=False)
        except Exception:
            pass

    def _on_workspace_item_activated(self, workspace_id: str, path: str) -> None:
        pane = self._workspace_panes.get(workspace_id)
        if not pane:
            return
        effective_kind = pane.definition.kind
        effective_site = pane.definition.site_relative_url
        if pane.definition.kind == "translation" and pane.definition.base_workspace_id:
            base = self._workspace_panes.get(pane.definition.base_workspace_id)
            if base:
                effective_kind = base.definition.kind
                effective_site = base.definition.site_relative_url
        try:
            if effective_kind == "local":
                if os.path.exists(path):
                    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                else:
                    QMessageBox.warning(self, "Open", f"File not found: {path}")
            elif effective_kind == "sharepoint":
                try:
                    data = self._backend.sp_download(path, site_relative_url=effective_site)
                except Exception as exc:
                    QMessageBox.warning(self, "Open", f"Download failed: {exc}")
                    return
                try:
                    import tempfile
                    import uuid as _uuid
                    name = os.path.basename(path) or f"download-{_uuid.uuid4().hex}"
                    # Use configured download dir if provided, else temp
                    target_dir = getattr(self._cfg, "sp_download_dir", None) or tempfile.gettempdir()
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                    except Exception:
                        target_dir = tempfile.gettempdir()
                    temp_path = os.path.join(target_dir, name)
                    with open(temp_path, "wb") as f:
                        f.write(data)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(temp_path))
                except Exception as exc:
                    QMessageBox.warning(self, "Open", f"Failed to open file: {exc}")
            else:
                self.statusBar().showMessage(f"Opened: {path}", 4000)
        except Exception as exc:
            QMessageBox.warning(self, "Open", f"Failed to open: {exc}")

    def _open_selected_items(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        for it in items:
            p = it.get("path") or ""
            if not p:
                continue
            if it.get("is_dir"):
                pane.go_to_path(p)
            else:
                self._on_workspace_item_activated(pane.id, p)
    def _open_with_selected_items(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        files = [it.get("path") for it in items if it.get("path") and not it.get("is_dir")]
        if not files:
            return
        try:
            if sys.platform.startswith("win"):
                for p in files:
                    subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", p])
            elif sys.platform == "darwin":
                try:
                    app, _ = QFileDialog.getOpenFileName(self, "Choose Application", "/Applications")
                except Exception:
                    app = ''
                for p in files:
                    if app:
                        subprocess.Popen(["open", "-a", app, p])
                    else:
                        subprocess.Popen(["open", p])
            else:
                try:
                    cmd, ok = QInputDialog.getText(self, "Open With", "Application (command):", text="xdg-open")
                    if not ok:
                        return
                    parts = (cmd or "").strip().split()
                    if not parts:
                        parts = ["xdg-open"]
                except Exception:
                    parts = ["xdg-open"]
                for p in files:
                    subprocess.Popen(parts + [p])
        except Exception as exc:
            QMessageBox.warning(self, "Open With", f"Failed: {exc}")

    def _rename_selected_item(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        it = items[0]
        path = it.get("path") or ""
        if not path:
            return
        current_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current_name)
        if not ok or not (new_name or "").strip():
            return
        new_name = new_name.strip()
        target_pane = pane
        if pane.definition.kind == "translation" and pane.definition.base_workspace_id:
            target_pane = self._workspace_panes.get(pane.definition.base_workspace_id) or pane
        try:
            if target_pane.definition.kind == "local":
                from ..services.rename_service import apply_rename
                apply_rename(path, new_name)
            elif target_pane.definition.kind == "sharepoint":
                self._backend.sp_rename(
                    server_relative_url=path,
                    new_name=new_name,
                    is_folder=bool(it.get("is_dir")),
                    site_relative_url=target_pane.definition.site_relative_url,
                )
        except Exception as exc:
            QMessageBox.warning(self, "Rename", f"Failed to rename item: {exc}")
        try:
            target_pane.refresh()
            pane.refresh()
        except Exception:
            pass

    def _new_folder(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        target_dir = pane.current_path()
        if not target_dir:
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:", text="New Folder")
        if not ok or not (name or "").strip():
            return
        name = name.strip()
        target_pane = pane
        if pane.definition.kind == "translation" and pane.definition.base_workspace_id:
            target_pane = self._workspace_panes.get(pane.definition.base_workspace_id) or pane
        try:
            if target_pane.definition.kind == "local":
                os.makedirs(os.path.join(target_dir, name), exist_ok=False)
            elif target_pane.definition.kind == "sharepoint":
                self._backend.sp_create_folder(
                    parent_server_relative_url=target_dir,
                    name=name,
                    site_relative_url=target_pane.definition.site_relative_url,
                )
        except Exception as exc:
            QMessageBox.warning(self, "New Folder", f"Failed to create folder: {exc}")
        try:
            target_pane.refresh()
            pane.refresh()
        except Exception:
            pass

    def _show_properties(self) -> None:
        pane = self._active_pane()
        if not pane:
            return
        items = pane.current_items()
        if not items:
            return
        it = items[0]
        path = it.get("path") or ""
        is_dir = bool(it.get("is_dir"))
        info_lines = [
            "Path: " + path,
            "Type: " + ("Folder" if is_dir else "File"),
        ]
        # For translation panes, use the base pane kind/site
        eff = pane
        if pane.definition.kind == 'translation' and pane.definition.base_workspace_id:
            eff = self._workspace_panes.get(pane.definition.base_workspace_id) or pane
        try:
            if eff.definition.kind == 'local':
                st = os.stat(path)
                info_lines.append("Size: " + str(st.st_size) + " bytes")
                from datetime import datetime
                info_lines.append("Modified: " + datetime.fromtimestamp(st.st_mtime).isoformat(sep=' ', timespec='seconds'))
                try:
                    import pwd
                    info_lines.append("Owner: " + pwd.getpwuid(st.st_uid).pw_name)
                except Exception:
                    pass
            elif eff.definition.kind == 'sharepoint':
                try:
                    props = self._backend.sp_properties(path, is_folder=is_dir, site_relative_url=eff.definition.site_relative_url)
                    sz = props.get('size')
                    if isinstance(sz, int):
                        info_lines.append("Size: " + str(sz) + " bytes")
                    if props.get('mtime'):
                        info_lines.append("Modified: " + str(props.get('mtime')))
                    if props.get('author'):
                        info_lines.append("Author: " + str(props.get('author')))
                    if props.get('modifiedBy'):
                        info_lines.append("Modified By: " + str(props.get('modifiedBy')))
                except Exception:
                    pass
        except Exception:
            pass
        QMessageBox.information(self, "Properties", "\n".join(info_lines))

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
        self._persist_state()
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
        self._persist_state()
        self._rebuild_workspace_area(focus_workspace_id=definition.id)

    def _add_translation_workspace(self) -> None:
        base_options = []
        for ws in self._workspace_manager.definitions():
            if ws.kind not in ("local", "sharepoint"):
                continue
            pane = self._workspace_panes.get(ws.id)
            display = self._display_name_for_pane(pane) if pane else (getattr(ws, "title_override", None) or ws.name)
            base_options.append((ws.id, display))
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
        self._persist_state()
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
        self._persist_state()
        self._rebuild_workspace_area()

    def _persist_state(self, save_workspaces: bool = True) -> None:
        if save_workspaces:
            self._cfg.workspaces = self._workspace_manager.to_config()
        self._cfg.favorites = self._favorites_manager.to_config()
        self._cfg.saved_layouts = self._layouts_manager.to_config()
        self._cfg.favorites_bar_position = getattr(self._cfg, "favorites_bar_position", "left")
        try:
            self._cfg.favorites_bar_size = int(getattr(self._cfg, "favorites_bar_size", 240))
        except Exception:
            self._cfg.favorites_bar_size = 240
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
        # Build candidates using original and translated display names
        candidates: List[RenameCandidate] = []
        for it in items:
            path = it["path"]
            orig = os.path.basename(path)
            trans = (it.get("display") or orig).strip()
            candidates.append(RenameCandidate(path, it["is_dir"], orig, trans))

        # Conflict checker per backend
        if base_pane.definition.kind == "local":
            def checker(parent_dir: str, new_name: str, is_dir: bool):
                # If exists, propose a safe new name; flag conflict only if identical exists
                exists = os.path.exists(os.path.join(parent_dir, new_name))
                suggestion = safe_new_name(parent_dir, new_name) if exists else None
                return (exists, suggestion)
        else:
            def checker(parent_server_relative_url: str, new_name: str, is_dir: bool):
                try:
                    # List children and check name collision
                    data = self._backend.sp_list(
                        base_pane.definition.site_relative_url or "",
                        parent_server_relative_url,
                    )
                    items = data.get("items") or []
                    names = [(it.get("name") or it.get("Name") or "") for it in items]
                    names = [n for n in names if n]
                    conflict = new_name in names
                    return (conflict, None)
                except Exception:
                    return (False, None)

        dlg = RenamePreviewDialog(candidates, parent=self, conflict_checker=checker)
        if dlg.exec() != QDialog.Accepted:
            return

        ops = dlg.selected_operations()
        if not ops:
            return

        # Apply in batch and record for undo
        undo_batch: List[dict] = []
        errors = 0
        self.statusBar().showMessage("Renaming items…", 3000)
        if base_pane.definition.kind == "local":
            for old_path, new_name, is_dir in ops:
                try:
                    new_path = apply_rename(old_path, new_name)
                    undo_batch.append({
                        "type": "local",
                        "old_path": old_path,
                        "new_path": new_path,
                        "is_dir": is_dir,
                    })
                except Exception:
                    errors += 1
        else:
            site = base_pane.definition.site_relative_url
            for old_path, new_name, is_dir in ops:
                try:
                    # Compute new server-relative path for undo
                    parent = old_path.rsplit("/", 1)[0]
                    new_path = f"{parent}/{new_name}"
                    try:
                        resp = self._backend.sp_rename(
                            server_relative_url=old_path,
                            new_name=new_name,
                            is_folder=is_dir,
                            site_relative_url=site,
                        )
                        if isinstance(resp, dict) and resp.get("newPath"):
                            new_path = resp["newPath"]
                    except Exception:
                        raise
                    undo_batch.append({
                        "type": "sp",
                        "old_path": old_path,
                        "new_path": new_path,
                        "is_dir": is_dir,
                        "site": site,
                    })
                except Exception:
                    errors += 1

        if undo_batch:
            self._rename_undo_stack.append(undo_batch)

        if errors:
            QMessageBox.warning(self, "Rename", f"Some items failed to rename ({errors}).")
        else:
            QMessageBox.information(self, "Rename", "Renamed successfully.")
        if base_pane:
            base_pane.refresh()
        pane.refresh()

    def _undo_last_rename_batch(self) -> None:
        if not self._rename_undo_stack:
            QMessageBox.information(self, "Undo", "No rename to undo.")
            return
        batch = self._rename_undo_stack.pop()
        errors = 0
        # Undo in reverse order
        for op in reversed(batch):
            try:
                if op["type"] == "local":
                    if os.path.exists(op["new_path"]):
                        os.rename(op["new_path"], op["old_path"])
                else:
                    # SharePoint: rename new_path back to original name
                    new_path = op["new_path"]
                    old_path = op["old_path"]
                    site = op.get("site")
                    name = os.path.basename(old_path)
                    self._backend.sp_rename(
                        server_relative_url=new_path,
                        new_name=name,
                        is_folder=op.get("is_dir", False),
                        site_relative_url=site,
                    )
            except Exception:
                errors += 1
        if errors:
            QMessageBox.warning(self, "Undo", f"Some items failed to undo ({errors}).")
        else:
            QMessageBox.information(self, "Undo", "Undo completed.")
        # Refresh all panes
        for p in self._workspace_panes.values():
            try:
                p.refresh()
            except Exception:
                pass

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
        provider = getattr(self._cfg, "translator_provider", "auto") or "auto"
        # Secrets
        try:
            from ..services import secret_store
        except Exception:
            secret_store = None  # type: ignore

        def openai_instance() -> Optional[Translator]:
            key = (self._cfg.api_key or "").strip()
            if not key and secret_store:
                try:
                    key = secret_store.get_secret("OPENAI_API_KEY") or ""
                except Exception:
                    key = ""
            return OpenAITranslator(api_key=key, model=self._cfg.model) if key else None

        def backend_instance() -> Optional[Translator]:
            try:
                info = self._backend.get_settings()
                if info.get("has_api_key"):
                    return BackendTranslator(self._backend.base_url)
            except Exception:
                return None
            return None

        def google_free_instance() -> Optional[Translator]:
            try:
                return GoogleFreeTranslator()
            except Exception:
                return None

        def libretranslate_instance() -> Optional[Translator]:
            try:
                base = getattr(self._cfg, "libretranslate_url", None) or "https://libretranslate.de"
                lt_key = None
                if secret_store:
                    try:
                        lt_key = secret_store.get_secret("LIBRETRANSLATE_API_KEY") or None
                    except Exception:
                        lt_key = None
                return LibreTranslateTranslator(base_url=base, api_key=lt_key)
            except Exception:
                return None

        if provider == "openai":
            return openai_instance() or IdentityTranslator()
        if provider == "backend":
            return backend_instance() or IdentityTranslator()
        if provider == "google_free":
            return google_free_instance() or IdentityTranslator()
        if provider == "libretranslate":
            return libretranslate_instance() or IdentityTranslator()
        if provider == "identity":
            return IdentityTranslator()

        # auto: prefer OpenAI → Backend → LibreTranslate → GoogleFree → Identity
        return (
            openai_instance()
            or backend_instance()
            or libretranslate_instance()
            or google_free_instance()
            or IdentityTranslator()
        )

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._cfg, self)
        dlg.exec()
        self._cfg = load_config()
        self._backend = BackendClient(getattr(self._cfg, "backend_url", None) or "http://127.0.0.1:5001")
        self._translator = self._create_translator()
        self._ignore_patterns = self._cfg.ignore_patterns or []
        self._apply_theme()
        for pane in self._workspace_panes.values():
            pane.set_translator(self._translator)

    # ---------------------------------------------------------------- misc ---
    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_state()
        super().closeEvent(event)
