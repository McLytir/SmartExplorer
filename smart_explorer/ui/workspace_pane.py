from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from PySide6.QtCore import QModelIndex, Qt, QSortFilterProxyModel, Signal, QMimeData, QItemSelectionModel
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QLineEdit, QSizePolicy, QTreeView, QVBoxLayout

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
        self.setMargin(4)
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

    def __init__(
        self,
        definition: WorkspaceDefinition,
        *,
        backend_client,
        translator: Translator,
        translation_cache: TranslationCache,
        ignore_patterns: List[str],
        base_panes: Dict[str, "WorkspacePane"],
    ) -> None:
        super().__init__()
        self.definition = definition
        self.backend = backend_client
        self._translator = translator
        self._translation_cache = translation_cache
        self._ignore_patterns = ignore_patterns
        self._base_panes = base_panes

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.header)
        layout.addWidget(self._search)
        layout.addWidget(self._view, 1)

        self._source_model = None
        self._filter_model: Optional[QSortFilterProxyModel] = None
        self._translated_model: Optional[TranslatedProxyModel] = None
        self._root_source_index: Optional[QModelIndex] = None
        self._root_view_index: Optional[QModelIndex] = None
        self._suppress_selection_signal = False
        self._suppress_expand_signal = False

        self._build_models()
        self._search.textChanged.connect(self._on_search_text_changed)
        self.set_active(False)

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
        if active:
            self.setStyleSheet(
                "WorkspacePane { border: 2px solid #1a5fb4; border-radius: 6px; }"
            )
        else:
            self.setStyleSheet(
                "WorkspacePane { border: 1px solid palette(mid); border-radius: 6px; }"
            )
        self.header.setStyleSheet(
            "font-weight: bold; color: #1a5fb4;" if active else "font-weight: normal; color: palette(text);"
        )

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

    # --- interactions -------------------------------------------------------
    def set_translator(self, translator: Translator) -> None:
        self._translator = translator
        if self._translated_model:
            self._translated_model.set_translator(translator)

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
        src_idx = self._map_to_source(index)
        if src_idx and src_idx.isValid():
            model = src_idx.model()
            if hasattr(model, "filePath"):
                path = model.filePath(src_idx)  # type: ignore[attr-defined]
            else:
                path = model.data(src_idx, PATH_ROLE)
        if path:
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

    def set_root_to_path(self, path: str) -> None:
        src_idx = self.source_index_for_path(path)
        view_idx = self._map_source_to_view(src_idx)
        self._set_root_indexes(src_idx if src_idx and src_idx.isValid() else None, view_idx)

    def source_index_for_path(self, path: str) -> Optional[QModelIndex]:
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
                    return model.filePath(source_idx)  # type: ignore[attr-defined]
                except Exception:
                    return ""
            value = model.data(source_idx, PATH_ROLE)
            return value or ""
        if self.definition.kind == "local":
            return self.definition.root_path or ""
        if self.definition.kind == "sharepoint":
            return self.definition.server_relative_url or ""
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
            self.set_root_to_path(root_path)
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
