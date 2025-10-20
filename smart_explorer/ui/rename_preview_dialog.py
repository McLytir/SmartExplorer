from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)


class RenameCandidate:
    def __init__(self, path: str, is_dir: bool, original_name: str, translated_name: str) -> None:
        self.path = path
        self.is_dir = is_dir
        self.original_name = original_name
        self.translated_name = translated_name
        self.include = True
        self.status = ""
        self.conflict = False


class RenamePreviewDialog(QDialog):
    """Bulk rename preview dialog.

    Shows original names and suggested translated names.
    Performs basic conflict checks and allows selection of which items to apply.
    """

    COL_CHECK = 0
    COL_OLD = 1
    COL_NEW = 2
    COL_STATUS = 3

    def __init__(
        self,
        candidates: List[RenameCandidate],
        *,
        parent: Optional[QWidget] = None,
        conflict_checker: Optional[callable] = None,
        title: str = "Apply Translation Rename",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._candidates = candidates
        self._conflict_checker = conflict_checker

        self._table = QTableWidget(self)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "Original", "New name", "Status"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self._table.setSortingEnabled(False)

        self._select_all = QCheckBox("Select all", self)
        self._select_all.stateChanged.connect(self._on_select_all)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._select_all)
        layout.addWidget(self._table, 1)
        layout.addWidget(btns)

        self._populate()
        self._recompute_statuses()

    # ---------------------------------------------------------------- populate
    def _populate(self) -> None:
        self._table.setRowCount(len(self._candidates))
        for row, cand in enumerate(self._candidates):
            chk = QTableWidgetItem("")
            chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Checked if cand.include else Qt.Unchecked)
            self._table.setItem(row, self.COL_CHECK, chk)

            old_item = QTableWidgetItem(cand.original_name)
            old_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self._table.setItem(row, self.COL_OLD, old_item)

            new_item = QTableWidgetItem(cand.translated_name)
            new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self._table.setItem(row, self.COL_NEW, new_item)

            status_item = QTableWidgetItem("")
            status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self._table.setItem(row, self.COL_STATUS, status_item)

        self._table.resizeColumnsToContents()
        self._table.itemChanged.connect(self._on_item_changed)

    def _on_select_all(self, state: int) -> None:
        checked = state == Qt.Checked
        for row in range(self._table.rowCount()):
            it = self._table.item(row, self.COL_CHECK)
            if it:
                it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        # candidates will be synced by _on_item_changed or on accept

    # --------------------------------------------------------------- computation
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        row = item.row()
        cand = self._candidates[row]
        if item.column() == self.COL_CHECK:
            cand.include = item.checkState() == Qt.Checked
        elif item.column() == self.COL_NEW:
            cand.translated_name = (item.text() or cand.original_name).strip()
            self._update_row_status(row)

    def _recompute_statuses(self) -> None:
        for row in range(self._table.rowCount()):
            self._update_row_status(row)

    def _update_row_status(self, row: int) -> None:
        cand = self._candidates[row]
        status = ""
        conflict = False
        if not cand.translated_name or cand.translated_name == cand.original_name:
            status = "No change"
        else:
            # Parent folder path
            parent = os.path.dirname(cand.path)
            conflict, suggestion = (False, None)
            if self._conflict_checker:
                try:
                    conflict, suggestion = self._conflict_checker(parent, cand.translated_name, cand.is_dir)
                except Exception:
                    conflict, suggestion = (False, None)
            if conflict:
                status = "Conflict exists"
            elif suggestion and suggestion != cand.translated_name:
                status = f"Will use: {suggestion}"
                cand.translated_name = suggestion
                # reflect in table
                it = self._table.item(row, self.COL_NEW)
                if it:
                    it.setText(suggestion)
            else:
                status = "Ready"
        cand.status = status
        cand.conflict = conflict
        it = self._table.item(row, self.COL_STATUS)
        if it:
            it.setText(status)

    # ----------------------------------------------------------------- results
    def selected_operations(self) -> List[Tuple[str, str, bool]]:
        """Return a list of (path, new_name, is_dir) to apply."""
        out: List[Tuple[str, str, bool]] = []
        for row, cand in enumerate(self._candidates):
            chk = self._table.item(row, self.COL_CHECK)
            include = (chk.checkState() == Qt.Checked) if chk else cand.include
            if not include:
                continue
            if not cand.translated_name or cand.translated_name == cand.original_name:
                continue
            out.append((cand.path, cand.translated_name, cand.is_dir))
        return out

