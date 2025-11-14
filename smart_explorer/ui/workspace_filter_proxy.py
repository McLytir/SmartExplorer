from __future__ import annotations

from typing import List

from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, Qt, QRegularExpression


class WorkspaceFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, pane: "WorkspacePane") -> None:  # type: ignore[name-defined]
        super().__init__(pane)
        self._pane = pane
        self._search_regex = QRegularExpression()
        self._tag_query: List[str] = []
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_search_text(self, text: str) -> None:
        text = text.strip()
        if text:
            self._search_regex = QRegularExpression(text, QRegularExpression.CaseInsensitiveOption)
        else:
            self._search_regex = QRegularExpression()
        super().setFilterRegularExpression(self._search_regex)

    def set_tag_query(self, tags: List[str]) -> None:
        self._tag_query = [tag.strip().lower() for tag in tags if tag.strip()]
        self.invalidateFilter()

    def tag_query(self) -> List[str]:
        return list(self._tag_query)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        if not self._tag_query:
            return True
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        path = self._pane._path_for_source_index(index)  # noqa: SLF001
        if not path:
            return False
        kind = self._pane.definition.kind
        tags = self._pane.tag_store.get_tags(kind, path) if hasattr(self._pane, "tag_store") else []
        if not tags:
            return False
        tags_lower = {tag.lower() for tag in tags}
        return any(tag in tags_lower for tag in self._tag_query)
