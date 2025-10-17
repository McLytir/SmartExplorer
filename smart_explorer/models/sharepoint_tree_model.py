from __future__ import annotations

from typing import List, Optional
from urllib.parse import unquote
from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from ..api.backend_client import BackendClient
from .translated_fs_model import PATH_ROLE

IS_DIR_ROLE = Qt.UserRole + 2


@dataclass
class SPItem:
    name: str
    path: str  # server-relative URL
    is_dir: bool
    loaded: bool = False
    parent: Optional['SPItem'] = None
    children: List['SPItem'] = field(default_factory=list)


class SharePointTreeModel(QAbstractItemModel):
    def __init__(self, backend: BackendClient, site_relative_url: str, root_server_relative_url: str, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.site_relative_url = site_relative_url
        self.root = SPItem(
            name=root_server_relative_url.rsplit('/', 1)[-1] or root_server_relative_url,
            path=root_server_relative_url,
            is_dir=True,
        )

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_item = self._item_from_index(parent)
        try:
            child = parent_item.children[row]
        except IndexError:
            return QModelIndex()
        return self.createIndex(row, column, child)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        item: SPItem = index.internalPointer()  # type: ignore[assignment]
        p = item.parent
        if p is None or p is self.root:
            return QModelIndex()
        gp = p.parent
        row = 0
        if gp:
            try:
                row = gp.children.index(p)
            except ValueError:
                row = 0
        return self.createIndex(row, 0, p)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        item = self._item_from_index(parent)
        if item.is_dir and not item.loaded:
            self._load_children(item)
        return len(item.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        item: SPItem = index.internalPointer()  # type: ignore[assignment]
        if role == Qt.DisplayRole:
            return item.name
        if role == PATH_ROLE:
            return item.path
        if role == IS_DIR_ROLE:
            return item.is_dir
        return None

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        item = self._item_from_index(parent)
        return item.is_dir

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    # Helpers
    def _item_from_index(self, index: QModelIndex) -> SPItem:
        if index.isValid():
            return index.internalPointer()  # type: ignore[return-value]
        return self.root

    def _load_children(self, item: SPItem) -> None:
        if item.loaded or not item.is_dir:
            return
        try:
            resp = self.backend.sp_list(self.site_relative_url, item.path)
            children: List[SPItem] = []
            for it in resp.get("items", []):
                child = SPItem(
                    name=it.get("name", ""),
                    path=it.get("path", ""),
                    is_dir=bool(it.get("isDir", False)),
                    parent=item,
                )
                children.append(child)
            item.children = children
            item.loaded = True
        except Exception:
            item.children = []
            item.loaded = True

    def set_root_path(self, server_relative_url: str) -> None:
        path = (server_relative_url or self.root.path or "/").strip()
        if not path.startswith("/"):
            path = "/" + path
        self.beginResetModel()
        self.root = SPItem(
            name=path.rstrip("/").rsplit('/', 1)[-1] or path,
            path=path,
            is_dir=True,
        )
        self.root.loaded = False
        self.endResetModel()

    def index_for_path(self, server_relative_url: str) -> Optional[QModelIndex]:
        path = (server_relative_url or "").strip()
        if not path:
            return QModelIndex()
        if not path.startswith("/"):
            path = "/" + path
        target = path.rstrip("/")
        root_path = (self.root.path or "").rstrip("/")
        if target == root_path:
            return QModelIndex()
        if not target.startswith(root_path):
            return None
        rel = target[len(root_path):].lstrip("/")
        if not rel:
            return QModelIndex()
        segments = rel.split("/")
        parent_item = self.root
        parent_index = QModelIndex()
        for seg in segments:
            self._load_children(parent_item)
            match = None
            for child in parent_item.children:
                child_name = child.path.rstrip("/").split("/")[-1]
                if child_name == seg or unquote(child_name) == seg:
                    match = child
                    break
            if not match:
                return None
            row = parent_item.children.index(match)
            parent_index = self.createIndex(row, 0, match)
            parent_item = match
        return parent_index
