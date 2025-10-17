from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from PySide6.QtCore import QModelIndex, Qt, QSortFilterProxyModel, Signal, QMimeData, QItemSelectionModel, QEvent, QSize
from PySide6.QtGui import QDrag, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSizePolicy,
    QStackedLayout,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..models.sharepoint_tree_model import SharePointTreeModel, IS_DIR_ROLE, PATH_ROLE
from ..models.translated_fs_model import TranslatedProxyModel
from ..translation_cache import TranslationCache
from ..translators.base import Translator, IdentityTranslator
from ..workspaces import WorkspaceDefinition


DRAG_MIME_TYPE = "application/x-smartexplorer-items"
PANE_DRAG_MIME = "application/x-smartexplorer-pane"


class WorkspaceTreeView(QTreeView):
    def __init__(self, pane: "WorkspacePane") -> None:
        super().__init__(pane)
        self._pane = pane
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.viewport().setAcceptDrops(True)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:  # type: ignore[override]
        self._pane._start_drag(supportedActions)

    def dragEnterEvent(self, event):  # type: ignore[override]
        if self._pane._accepts_drag(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # type: ignore[override]
        if self._pane._accepts_drag(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # type: ignore[override]
        if self._pane._handle_drop_event(event):
            event.acceptProposedAction()
        else:
            event.ignore()


class WorkspaceHeader(QLabel):
    reorder_requested = Signal(str, str)  # source_id, target_id
    context_menu_requested = Signal(str, object)

    def __init__(self, pane: "WorkspacePane") -> None:
        super().__init__(pane)
        self._pane = pane
        self._workspace_id = pane.definition.id
        self.setAcceptDrops(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setMargin(0)
        self.setAlignment(Qt.AlignCenter)
        self._drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_start_pos is not None:
            if (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self._start_drag()
                self._drag_start_pos = None
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def _start_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(PANE_DRAG_MIME, self._workspace_id.encode("utf-8"))
        drag.setMimeData(mime)
        self.setCursor(Qt.ClosedHandCursor)
        drag.exec(Qt.MoveAction)
        self.setCursor(Qt.OpenHandCursor)

    def dragEnterEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasFormat(PANE_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasFormat(PANE_DRAG_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # type: ignore[override]
        mime = event.mimeData()
        if not mime.hasFormat(PANE_DRAG_MIME):
            event.ignore()
            return
        source_id = bytes(mime.data(PANE_DRAG_MIME)).decode("utf-8")
        if source_id == self._workspace_id:
            event.ignore()
            return
        self.reorder_requested.emit(source_id, self._workspace_id)
        event.acceptProposedAction()

    def contextMenuEvent(self, event):  # type: ignore[override]
        self.context_menu_requested.emit(self._workspace_id, event.globalPos())

class WorkspacePane(QFrame):
    """
    Encapsulates a single workspace tree view. Handles local filesystem,
    SharePoint, or translation views.
    """

    selection_changed = Signal(str)  # workspace_id
    activated = Signal(str, str)     # workspace_id, path
    expanded_path = Signal(str, str)
    collapsed_path = Signal(str, str)
    drop_request = Signal(str, dict, str, bool, object)  # target_workspace, payload, target_path, move, site
    path_changed = Signal(str, str)  # workspace_id, path
    pane_clicked = Signal(str)       # workspace_id

    def __init__(
        self,
        definition: WorkspaceDefinition,
        *,
        backend_client,
        translator: Translator,
        translation_cache: TranslationCache,
        ignore_patterns: List[str],
        base_panes: Dict[str, "WorkspacePane"],
        header_color: str,
        header_active_color: str,
    ) -> None:
        super().__init__()
        self.definition = definition
        self.backend = backend_client
        self._translator = translator
        self._translation_cache = translation_cache
        self._ignore_patterns = ignore_patterns
        self._base_panes = base_panes
        self._header_color = header_color
        self._header_active_color = header_active_color
        self._history: List[str] = []
        self._history_index: int = -1
        self._suspend_history = False
        self._base_root_path: str = ""
        self._sharepoint_mode = definition.kind == "sharepoint"
        if definition.kind == "translation" and definition.base_workspace_id:
            base = base_panes.get(definition.base_workspace_id)
            if base is not None:
                self._sharepoint_mode = base.definition.kind == "sharepoint"
        self._is_active = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName(f"WorkspacePane::{definition.id}")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(220, 220)

        self.header = WorkspaceHeader(self)
        self.header.setText(definition.name)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search…")

        self._view = WorkspaceTreeView(self)
        self._view.setSortingEnabled(True)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionMode(QTreeView.ExtendedSelection)
        self._view.setContextMenuPolicy(Qt.ActionsContextMenu)
        self._view.expanded.connect(lambda _: self._view.resizeColumnToContents(0))
        self._view.doubleClicked.connect(self._on_activated)
        self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._view.expanded.connect(self._on_expanded)
        self._view.collapsed.connect(self._on_collapsed)

        self._icon_view = QListView(self)
        self._icon_view.setViewMode(QListView.IconMode)
        self._icon_view.setIconSize(QSize(48, 48))
        self._icon_view.setResizeMode(QListView.Adjust)
        self._icon_view.setWordWrap(True)
        self._icon_view.setUniformItemSizes(False)
        self._icon_view.setSelectionMode(QListView.ExtendedSelection)
        self._icon_view.setSpacing(12)
        self._icon_view.setWrapping(True)
        self._icon_view.setContextMenuPolicy(Qt.ActionsContextMenu)
        self._icon_view.doubleClicked.connect(self._on_activated)

        self._supports_icon_mode = not self._sharepoint_mode
        self._icon_mode = False

        self._view_container = QWidget(self)
        self._view_stack = QStackedLayout(self._view_container)
        self._view_stack.setContentsMargins(0, 0, 0, 0)
        self._view_stack.addWidget(self._view)
        self._view_stack.addWidget(self._icon_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.header)
        layout.addLayout(self._build_nav_bar())
        layout.addWidget(self._search)
        layout.addWidget(self._view_container, 1)

        self.installEventFilter(self)
        self.header.installEventFilter(self)
        self._view.viewport().installEventFilter(self)
        self._icon_view.viewport().installEventFilter(self)
        self._search.installEventFilter(self)

        self._source_model = None
        self._filter_model: Optional[QSortFilterProxyModel] = None
        self._translated_model: Optional[TranslatedProxyModel] = None
        self._root_source_index: Optional[QModelIndex] = None
        self._root_view_index: Optional[QModelIndex] = None
        self._suppress_selection_signal = False
        self._suppress_expand_signal = False

        self._build_models()
        self._base_root_path = self._determine_base_root()
        self._initialize_history()
        self._search.textChanged.connect(self._on_search_text_changed)
        self._update_style(False)

    # --- properties ---------------------------------------------------------
    @property
    def id(self) -> str:
        return self.definition.id

    def source_model(self):
        return self._source_model

    def display_model(self):
        return self._view.model()

    def site_relative_url(self) -> Optional[str]:
        return self.definition.site_relative_url

    def root_source_index(self) -> Optional[QModelIndex]:
        return self._root_source_index

    def view_root_index(self) -> QModelIndex:
        if isinstance(self._root_view_index, QModelIndex) and self._root_view_index.isValid():
            return self._root_view_index
        return self._view.rootIndex()

    def set_title(self, name: str) -> None:
        self.header.setText(name)

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._update_style(active)

    def map_view_to_source(self, index: QModelIndex) -> Optional[QModelIndex]:
        return self._map_to_source(index)

    # --- model setup --------------------------------------------------------
    def _build_models(self) -> None:
        kind = self.definition.kind
        if kind == "local":
            self._build_local_model()
        elif kind == "sharepoint":
            self._build_sharepoint_model()
        elif kind == "translation":
            self._build_translation_model()
        else:
            raise ValueError(f"Unknown workspace kind: {kind}")

    def _build_local_model(self) -> None:
        from PySide6.QtWidgets import QFileSystemModel

        fs_model = QFileSystemModel(self)
        root = self.definition.root_path or ""
        fs_model.setRootPath(root)
        self._source_model = fs_model
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(fs_model)
        proxy.setRecursiveFilteringEnabled(True)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model = proxy
        self._view.setModel(proxy)
        idx = fs_model.index(root) if root else fs_model.index("/")
        view_idx = proxy.mapFromSource(idx)
        self._set_root_indexes(idx, view_idx)
        for column in range(1, fs_model.columnCount()):
            self._view.setColumnHidden(column, True)
        self._connect_selection()
        self._sync_icon_model()

    def _build_sharepoint_model(self) -> None:
        if not (self.definition.site_relative_url and self.definition.server_relative_url):
            raise RuntimeError("SharePoint workspace requires site and library information.")
        sp_model = SharePointTreeModel(
            self.backend,
            self.definition.site_relative_url,
            self.definition.server_relative_url,
            self,
        )
        self._source_model = sp_model
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(sp_model)
        proxy.setRecursiveFilteringEnabled(True)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model = proxy
        self._view.setModel(proxy)
        self._set_root_indexes(None, QModelIndex())
        self._connect_selection()
        self._sync_icon_model()

    def _build_translation_model(self) -> None:
        if not self.definition.base_workspace_id:
            raise RuntimeError("Translation workspace requires base workspace reference.")
        base = self._base_panes.get(self.definition.base_workspace_id)
        if not base:
            raise RuntimeError(f"Base workspace '{self.definition.base_workspace_id}' missing.")
        source = base.source_model()
        if source is None:
            raise RuntimeError("Base workspace has no source model.")
        translator = self._translator or IdentityTranslator()
        language = self.definition.language or "English"
        translated = TranslatedProxyModel(
            translator,
            language,
            self,
            cache=self._translation_cache,
            ignore_patterns=self._ignore_patterns,
        )
        translated.setSourceModel(source)
        self._translated_model = translated
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(translated)
        proxy.setRecursiveFilteringEnabled(True)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model = proxy
        self._view.setModel(proxy)
        self._source_model = source
        base_root_source = base.root_source_index() if hasattr(base, "root_source_index") else None
        base_view_root = base.view_root_index() if hasattr(base, "view_root_index") else QModelIndex()
        if (not base_root_source or not base_root_source.isValid()) and isinstance(base_view_root, QModelIndex) and base_view_root.isValid():
            base_root_source = base.map_view_to_source(base_view_root)
        if isinstance(base_root_source, QModelIndex) and base_root_source.isValid():
            translated_root = translated.mapFromSource(base_root_source)
            view_root = proxy.mapFromSource(translated_root)
            self._set_root_indexes(base_root_source, view_root)
        else:
            self._set_root_indexes(None, QModelIndex())
        self._connect_selection()
        self._sync_icon_model()

    def _build_nav_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 0, 6, 0)
        bar.setSpacing(6)

        self._back_btn = QToolButton(self)
        self._back_btn.setText("←")
        self._back_btn.setToolTip("Back")
        self._back_btn.setAutoRaise(True)
        self._back_btn.clicked.connect(lambda checked=False: self._navigate_history(-1))

        self._forward_btn = QToolButton(self)
        self._forward_btn.setText("→")
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.setAutoRaise(True)
        self._forward_btn.clicked.connect(lambda checked=False: self._navigate_history(1))

        self._up_btn = QToolButton(self)
        self._up_btn.setText("↑")
        self._up_btn.setToolTip("Up one level")
        self._up_btn.setAutoRaise(True)
        self._up_btn.clicked.connect(lambda checked=False: self.navigate_up())

        self._view_mode_btn = QToolButton(self)
        self._view_mode_btn.setText("☰")
        self._view_mode_btn.setCheckable(True)
        self._view_mode_btn.setToolTip("Toggle icon view")
        self._view_mode_btn.setAutoRaise(True)
        self._view_mode_btn.toggled.connect(self._toggle_view_mode)
        self._view_mode_btn.setEnabled(self._supports_icon_mode)
        self._view_mode_btn.setVisible(self._supports_icon_mode)

        for btn in (self._back_btn, self._forward_btn, self._up_btn):
            btn.setEnabled(False)
            btn.installEventFilter(self)
            bar.addWidget(btn)

        bar.addStretch(1)
        bar.addWidget(self._view_mode_btn)
        return bar

    def _update_style(self, active: bool) -> None:
        palette = self.palette()
        base_color = palette.color(QPalette.Base).name()
        highlight = palette.color(QPalette.Highlight).name()
        mid = palette.color(QPalette.Mid).name()
        if mid.lower() == base_color.lower():
            mid = palette.color(QPalette.AlternateBase).name()
        if mid.lower() == base_color.lower():
            mid = "#aab3c3" if not self._sharepoint_mode else "#44525d"

        border_color = highlight if active else mid
        border_width = 2 if active else 1
        self.setStyleSheet(
            f"WorkspacePane {{ border: {border_width}px solid {border_color}; border-radius: 6px; background-color: {base_color}; }}"
        )
        self._apply_header_style(active)

    def _apply_header_style(self, active: bool) -> None:
        color = self._header_active_color if active else self._header_color
        weight = "600" if active else "500"
        text_color = self._preferred_text_color(color)
        shadow = "rgba(0, 0, 0, 0.20)" if active else "rgba(0, 0, 0, 0.08)"
        self.header.setStyleSheet(
            f"QLabel {{ background-color: {color}; color: {text_color}; padding: 6px 10px; margin: 0px; "
            f"font-weight: {weight}; border-top-left-radius: 6px; border-top-right-radius: 6px; "
            f"border-bottom: 1px solid {shadow}; }}"
        )

    def update_header_palette(self, header_color: str, header_active_color: str) -> None:
        self._header_color = header_color
        self._header_active_color = header_active_color
        self._apply_header_style(self._is_active)

    @staticmethod
    def _preferred_text_color(color: str) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return "#1f2b3a"
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#1f2b3a" if luminance >= 0.6 else "#f6fbff"

    def _toggle_view_mode(self, checked: bool) -> None:
        if not self._supports_icon_mode:
            blocker = self._view_mode_btn.blockSignals(True)
            self._view_mode_btn.setChecked(False)
            self._view_mode_btn.blockSignals(blocker)
            return
        self._icon_mode = checked
        self._view_stack.setCurrentIndex(1 if checked else 0)
        self._view_mode_btn.setText("🗂" if checked else "☰")
        self._view_mode_btn.setToolTip("Show tree view" if checked else "Show icon view")
        self._sync_icon_model()
        if checked:
            self._icon_view.setFocus()
        else:
            self._view.setFocus()

    # --- interactions -------------------------------------------------------
    def set_translator(self, translator: Translator) -> None:
        self._translator = translator
        if self._translated_model:
            self._translated_model.set_translator(translator)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                self._emit_pane_clicked()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
            self._emit_pane_clicked()
        super().mousePressEvent(event)

    def _emit_pane_clicked(self) -> None:
        self.pane_clicked.emit(self.definition.id)

    def set_language(self, language: str) -> None:
        if self.definition.kind == "translation" and self._translated_model:
            self.definition.language = language
            self._translated_model.set_target_language(language)

    def refresh(self) -> None:
        if isinstance(self._source_model, SharePointTreeModel):
            self._source_model.beginResetModel()
            self._source_model.root.children.clear()
            self._source_model.root.loaded = False
            self._source_model.endResetModel()
        elif isinstance(self._source_model, TranslatedProxyModel):
            self._source_model._cache.clear()  # type: ignore[attr-defined]

    # --- navigation --------------------------------------------------------
    def current_path(self) -> str:
        return self._normalize_path(self._path_for_source_index(self.root_source_index()))

    def navigate_back(self) -> None:
        self._navigate_history(-1)

    def navigate_forward(self) -> None:
        self._navigate_history(1)

    def navigate_up(self) -> None:
        current = self.current_path()
        parent = self._parent_path(current)
        if not parent or parent == current:
            return
        if self._base_root_path and not self._is_within_base(parent):
            return
        self.go_to_path(parent)

    def go_to_path(self, path: str, *, record: bool = True, emit: bool = True) -> bool:
        target = self._normalize_path(path)
        if not target:
            return False
        src_idx: Optional[QModelIndex] = None
        root_idx: Optional[QModelIndex] = None
        if self.definition.kind == "local":
            fs_target = os.path.abspath(os.path.expanduser(target))
            if not os.path.isdir(fs_target):
                return False
            target = os.path.normpath(fs_target)
            try:
                if hasattr(self._source_model, "setRootPath"):
                    root_idx = self._source_model.setRootPath(target)  # type: ignore[attr-defined]
            except Exception:
                return False
            target = self._normalize_path(target)
        elif self._sharepoint_mode and hasattr(self._source_model, "set_root_path"):
            try:
                self._source_model.set_root_path(target)  # type: ignore[attr-defined]
            except Exception:
                return False
        if src_idx is None:
            src_idx = root_idx if isinstance(root_idx, QModelIndex) and root_idx.isValid() else self.source_index_for_path(target)
        if src_idx is None and not self._allow_empty_index(target):
            return False
        view_idx = self._map_source_to_view(src_idx) if isinstance(src_idx, QModelIndex) else QModelIndex()
        self._set_root_indexes(src_idx if isinstance(src_idx, QModelIndex) and src_idx.isValid() else None, view_idx)
        if self._suspend_history:
            return True
        if record:
            self._record_history(target, emit=emit)
        elif emit:
            self.path_changed.emit(self.definition.id, target)
            self._update_navigation_buttons()
        else:
            self._update_navigation_buttons()
        return True

    def navigate_to_path(self, path: str) -> bool:
        return self.go_to_path(path, record=True, emit=True)

    def _allow_empty_index(self, path: str) -> bool:
        normalized = self._normalize_path(path)
        base = self._normalize_path(self._base_root_path)
        return normalized == base

    def _navigate_history(self, delta: int) -> None:
        if not self._history:
            return
        target = self._history_index + delta
        if 0 <= target < len(self._history):
            self._apply_history_index(target)

    def _apply_history_index(self, index: int) -> None:
        if index == self._history_index or not (0 <= index < len(self._history)):
            return
        path = self._history[index]
        self._suspend_history = True
        try:
            self.go_to_path(path, record=False, emit=False)
        finally:
            self._suspend_history = False
        self._history_index = index
        self.path_changed.emit(self.definition.id, path)
        self._update_navigation_buttons()

    def _record_history(self, path: str, *, emit: bool) -> None:
        if self._suspend_history:
            return
        normalized = self._normalize_path(path)
        if not normalized:
            return
        if self._history_index >= 0 and self._history[self._history_index] == normalized:
            if emit:
                self.path_changed.emit(self.definition.id, normalized)
            self._update_navigation_buttons()
            return
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(normalized)
        self._history_index = len(self._history) - 1
        if emit:
            self.path_changed.emit(self.definition.id, normalized)
        self._update_navigation_buttons()

    def _initialize_history(self) -> None:
        current = self.current_path()
        if current:
            self._history = [current]
            self._history_index = 0
        else:
            self._history = []
            self._history_index = -1
        self._update_navigation_buttons()

    def _determine_base_root(self) -> str:
        if self.definition.kind == "local":
            base = self.definition.root_path or ""
        elif self.definition.kind == "sharepoint":
            base = self.definition.server_relative_url or "/"
        elif self.definition.kind == "translation":
            base = ""
            if self.definition.base_workspace_id:
                base_pane = self._base_panes.get(self.definition.base_workspace_id)
                if base_pane is not None:
                    base = base_pane._base_root_path or base_pane.current_path()
            if not base:
                base = self.current_path()
        else:
            base = self.current_path()
        return self._normalize_path(base)

    def _normalize_path(self, path: Optional[str]) -> str:
        if not path:
            return ""
        path = str(path).strip()
        if not path:
            return ""
        if path.startswith("/"):
            normalized = os.path.normpath(path)
            if self._sharepoint_mode:
                return normalized if normalized != "" else "/"
            return normalized
        if self._sharepoint_mode:
            normalized = "/" + path.lstrip("/")
            return normalized if normalized != "//" else "/"
        expanded = os.path.expanduser(path)
        if not os.path.isabs(expanded):
            expanded = os.path.abspath(expanded)
        return os.path.normpath(expanded)

    def _parent_path(self, path: str) -> str:
        normalized = self._normalize_path(path)
        if not normalized:
            return ""
        if normalized.startswith("/"):
            trimmed = normalized.rstrip("/")
            if not trimmed or trimmed == "/":
                return "/"
            parent = trimmed.rsplit("/", 1)[0]
            return parent or "/"
        return os.path.normpath(os.path.dirname(os.path.normpath(normalized)))

    def _is_within_base(self, path: str) -> bool:
        if self.definition.kind == "local" or (self.definition.kind == "translation" and not self._sharepoint_mode):
            return True
        if not self._base_root_path:
            return True
        if self._sharepoint_mode:
            base = self._normalize_path(self._base_root_path) or "/"
            target = self._normalize_path(path)
            if base in ("", "/"):
                return True
            base = base.rstrip("/")
            return target == base or target.startswith(base + "/")
        base_abs = os.path.abspath(self._normalize_path(self._base_root_path))
        target_abs = os.path.abspath(self._normalize_path(path))
        try:
            return os.path.commonpath([target_abs, base_abs]) == base_abs
        except Exception:
            return True

    def _update_navigation_buttons(self) -> None:
        if hasattr(self, "_back_btn"):
            self._back_btn.setEnabled(self._history_index > 0)
        if hasattr(self, "_forward_btn"):
            self._forward_btn.setEnabled(0 <= self._history_index < len(self._history) - 1)
        if hasattr(self, "_up_btn"):
            self._up_btn.setEnabled(self._can_navigate_up())

    def _can_navigate_up(self) -> bool:
        current = self.current_path()
        parent = self._parent_path(current)
        if not parent or parent == current:
            return False
        if self._base_root_path:
            if not self._is_within_base(parent):
                return False
        return True

    def current_paths(self) -> List[str]:
        indexes = self._view.selectionModel().selectedIndexes() if self._view.selectionModel() else []
        paths: List[str] = []
        for idx in indexes:
            if idx.column() != 0:
                continue
            src_idx = self._map_to_source(idx)
            if src_idx is None or not src_idx.isValid():
                continue
            model = src_idx.model()
            if hasattr(model, "filePath"):
                try:
                    paths.append(model.filePath(src_idx))  # type: ignore[attr-defined]
                except Exception:
                    continue
            else:
                path = model.data(src_idx, PATH_ROLE)
                if path:
                    paths.append(path)
        return paths

    def current_items(self) -> List[dict]:
        items: List[dict] = []
        selection = self._view.selectionModel().selectedIndexes() if self._view.selectionModel() else []
        seen = set()
        for idx in selection:
            if idx.column() != 0:
                continue
            src_idx = self._map_to_source(idx)
            if src_idx is None or not src_idx.isValid():
                continue
            model = src_idx.model()
            path = None
            is_dir = False
            if hasattr(model, "filePath"):
                path = model.filePath(src_idx)  # type: ignore[attr-defined]
                is_dir = model.isDir(src_idx)  # type: ignore[attr-defined]
            else:
                path = model.data(src_idx, PATH_ROLE)
                is_dir = bool(model.data(src_idx, IS_DIR_ROLE))
            if not path or path in seen:
                continue
            seen.add(path)
            display_name = idx.data(Qt.DisplayRole) if idx.isValid() else os.path.basename(path)
            items.append({"path": path, "is_dir": is_dir, "display": display_name})
        return items

    # --- helpers ------------------------------------------------------------
    def _on_search_text_changed(self, text: str) -> None:
        if self._filter_model:
            self._filter_model.setFilterFixedString(text)

    def _connect_selection(self) -> None:
        sel_model = self._view.selectionModel()
        if sel_model:
            sel_model.selectionChanged.connect(self._on_selection_changed)
        if self._icon_view.model() is not None and self._view.selectionModel() is not None:
            self._icon_view.setSelectionModel(self._view.selectionModel())

    def _sync_icon_model(self) -> None:
        if not self._supports_icon_mode:
            return
        if self._filter_model is None:
            self._icon_view.setModel(None)
            return
        self._icon_view.setModel(self._filter_model)
        sel_model = self._view.selectionModel()
        if sel_model:
            self._icon_view.setSelectionModel(sel_model)
        root_index = self._view.rootIndex()
        self._icon_view.setRootIndex(root_index)

    def _on_selection_changed(self, *_args) -> None:
        if self._suppress_selection_signal:
            return
        self.selection_changed.emit(self.definition.id)

    def _on_expanded(self, index: QModelIndex) -> None:
        if self._suppress_expand_signal:
            return
        src_idx = self._map_to_source(index)
        path = self._path_for_source_index(src_idx)
        if path:
            self.expanded_path.emit(self.definition.id, path)

    def _on_collapsed(self, index: QModelIndex) -> None:
        if self._suppress_expand_signal:
            return
        src_idx = self._map_to_source(index)
        path = self._path_for_source_index(src_idx)
        if path:
            self.collapsed_path.emit(self.definition.id, path)

    def _on_activated(self, index: QModelIndex) -> None:
        path = None
        is_dir = False
        src_idx = self._map_to_source(index)
        if src_idx and src_idx.isValid():
            model = src_idx.model()
            if hasattr(model, "filePath"):
                path = model.filePath(src_idx)  # type: ignore[attr-defined]
                if hasattr(model, "isDir"):
                    try:
                        is_dir = bool(model.isDir(src_idx))  # type: ignore[attr-defined]
                    except Exception:
                        is_dir = False
            else:
                path = model.data(src_idx, PATH_ROLE)
                is_dir = bool(model.data(src_idx, IS_DIR_ROLE))
        if not path and index.isValid():
            path = index.data(PATH_ROLE)
        if path:
            if is_dir:
                self.go_to_path(path)
            else:
                self.activated.emit(self.definition.id, path)

    def _map_to_source(self, index: QModelIndex) -> Optional[QModelIndex]:
        model = self._view.model()
        idx = index
        if self._filter_model:
            idx = self._filter_model.mapToSource(idx)
        if self._translated_model and idx.model() is self._translated_model:
            idx = self._translated_model.mapToSource(idx)
        return idx

    def _map_source_to_view(self, source_idx: Optional[QModelIndex]) -> QModelIndex:
        if not isinstance(source_idx, QModelIndex) or not source_idx.isValid():
            return QModelIndex()
        idx = source_idx
        if self._translated_model:
            idx = self._translated_model.mapFromSource(idx)
        if self._filter_model:
            idx = self._filter_model.mapFromSource(idx)
        return idx

    def current_source_indexes(self) -> List[QModelIndex]:
        indexes: List[QModelIndex] = []
        sel_model = self._view.selectionModel()
        if not sel_model:
            return indexes
        for idx in sel_model.selectedIndexes():
            if idx.column() != 0:
                continue
            src_idx = self._map_to_source(idx)
            if src_idx and src_idx.isValid():
                indexes.append(src_idx)
        return indexes

    def path_for_source_index(self, source_idx: Optional[QModelIndex]) -> str:
        return self._path_for_source_index(source_idx)

    def select_paths(self, paths: List[str]) -> None:
        source_indexes = [self.source_index_for_path(p) for p in paths if p]
        source_indexes = [idx for idx in source_indexes if idx and idx.isValid()]
        self.select_source_indexes(source_indexes)

    def select_source_indexes(self, source_indexes: List[QModelIndex]) -> None:
        sel_model = self._view.selectionModel()
        if not sel_model:
            return
        self._suppress_selection_signal = True
        try:
            sel_model.clearSelection()
            last_view = QModelIndex()
            for src in source_indexes:
                view_idx = self._map_source_to_view(src)
                if view_idx and view_idx.isValid():
                    sel_model.select(view_idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)
                    last_view = view_idx
            if last_view and last_view.isValid():
                self._view.scrollTo(last_view)
        finally:
            self._suppress_selection_signal = False

    def expand_path(self, path: str) -> None:
        src_idx = self.source_index_for_path(path)
        view_idx = self._map_source_to_view(src_idx)
        if view_idx and view_idx.isValid():
            self._suppress_expand_signal = True
            self._view.expand(view_idx)
            self._suppress_expand_signal = False

    def collapse_path(self, path: str) -> None:
        src_idx = self.source_index_for_path(path)
        view_idx = self._map_source_to_view(src_idx)
        if view_idx and view_idx.isValid():
            self._suppress_expand_signal = True
            self._view.collapse(view_idx)
            self._suppress_expand_signal = False

    def set_root_to_path(self, path: str, *, record: bool = True, emit: bool = True) -> None:
        self.go_to_path(path, record=record, emit=emit)

    def source_index_for_path(self, path: str) -> Optional[QModelIndex]:
        path = self._normalize_path(path)
        if not path:
            return None
        if hasattr(self._source_model, "filePath"):
            try:
                return self._source_model.index(path)  # type: ignore[attr-defined]
            except Exception:
                return None
        if isinstance(self._source_model, SharePointTreeModel):
            return self._source_model.index_for_path(path)
        if self._translated_model and self.definition.base_workspace_id:
            base = self._base_panes.get(self.definition.base_workspace_id)
            if base:
                return base.source_index_for_path(path)
        return None

    def _path_for_source_index(self, source_idx: Optional[QModelIndex]) -> str:
        if isinstance(source_idx, QModelIndex) and source_idx.isValid():
            model = source_idx.model()
            if hasattr(model, "filePath"):
                try:
                    value = model.filePath(source_idx)  # type: ignore[attr-defined]
                except Exception:
                    value = ""
            else:
                value = model.data(source_idx, PATH_ROLE)
            return self._normalize_path(value or "")
        if self.definition.kind == "local":
            return self._normalize_path(self.definition.root_path or "")
        if self.definition.kind == "sharepoint":
            return self._normalize_path(self.definition.server_relative_url or "")
        if self.definition.kind == "translation" and self.definition.base_workspace_id:
            base = self._base_panes.get(self.definition.base_workspace_id)
            if base:
                return base._path_for_source_index(base.root_source_index())
        return ""

    def snapshot_state(self) -> dict:
        state: dict = {}
        root_idx = self.root_source_index()
        root_path = self._path_for_source_index(root_idx)
        if root_path:
            state["root_path"] = root_path
        selection = [self._path_for_source_index(idx) for idx in self.current_source_indexes()]
        selection = [p for p in selection if p]
        if selection:
            state["selection"] = selection
        return state

    def restore_state(self, state: dict) -> None:
        if not state:
            return
        root_path = state.get("root_path")
        if root_path:
            if self.go_to_path(root_path, record=False, emit=False):
                current = self.current_path()
                if current:
                    self._history = [current]
                    self._history_index = 0
                else:
                    self._history = []
                    self._history_index = -1
                self._update_navigation_buttons()
        selection = state.get("selection") or []
        if selection:
            self.select_paths(selection)

    def _set_root_indexes(self, source_idx: Optional[QModelIndex], view_idx: QModelIndex) -> None:
        if isinstance(source_idx, QModelIndex) and not source_idx.isValid():
            source_idx = None
        self._root_source_index = source_idx
        if not isinstance(view_idx, QModelIndex) or not view_idx.isValid():
            view_idx = QModelIndex()
        self._root_view_index = view_idx
        self._view.setRootIndex(view_idx)
        if self._supports_icon_mode and self._icon_view.model() is not None:
            self._icon_view.setRootIndex(view_idx)
        self._update_navigation_buttons()

    # --- drag/drop ----------------------------------------------------------
    def _start_drag(self, supported_actions: Qt.DropAction) -> None:
        items = self.current_items()
        if not items:
            return
        payload = {
            "source_workspace": self.definition.id,
            "items": items,
        }
        mime = QMimeData()
        mime.setData(DRAG_MIME_TYPE, json.dumps(payload).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        default_action = Qt.MoveAction
        drag.exec(Qt.CopyAction | Qt.MoveAction, default_action)

    def _accepts_drag(self, mime: QMimeData) -> bool:
        if not mime or not mime.hasFormat(DRAG_MIME_TYPE):
            return False
        if self.definition.kind == "translation":
            return False
        return True

    def _handle_drop_event(self, event) -> bool:
        if self.definition.kind == "translation":
            return False
        mime = event.mimeData()
        if not self._accepts_drag(mime):
            return False
        payload = self._decode_payload(mime)
        if not payload:
            return False
        target_index = self._view.indexAt(event.position().toPoint()) if hasattr(event, "position") else self._view.indexAt(event.pos())
        target_path, target_site = self._target_directory_for_index(target_index)
        if target_path is None:
            return False
        move = event.dropAction() == Qt.MoveAction
        self.drop_request.emit(self.definition.id, payload, target_path, move, target_site)
        return True

    def _decode_payload(self, mime: QMimeData) -> Optional[dict]:
        try:
            raw = bytes(mime.data(DRAG_MIME_TYPE)).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    def _target_directory_for_index(self, index: QModelIndex) -> Tuple[Optional[str], Optional[str]]:
        if self.definition.kind == "local":
            root = self.definition.root_path or os.path.expanduser("~")
            if not index or not index.isValid():
                return root, None
            src_idx = self._map_to_source(index)
            if not src_idx or not src_idx.isValid():
                return root, None
            model = src_idx.model()
            if hasattr(model, "filePath"):
                path = model.filePath(src_idx)  # type: ignore[attr-defined]
                is_dir = model.isDir(src_idx)  # type: ignore[attr-defined]
                if is_dir:
                    return path, None
                return os.path.dirname(path), None
            return root, None
        if self.definition.kind == "sharepoint":
            site = self.definition.site_relative_url
            root = self.definition.server_relative_url or "/"
            if not index or not index.isValid():
                return root, site
            src_idx = self._map_to_source(index)
            if not src_idx or not src_idx.isValid():
                return root, site
            model = src_idx.model()
            path = model.data(src_idx, PATH_ROLE) if model else None
            is_dir = bool(model.data(src_idx, IS_DIR_ROLE)) if model else False
            if not path:
                return root, site
            if is_dir:
                return path, site
            return path.rsplit('/', 1)[0], site
        return None, None
