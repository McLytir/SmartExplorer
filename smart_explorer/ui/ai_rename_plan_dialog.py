from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class AIRenamePlanCandidate:
    source_path: str
    current_relative_path: str
    target_relative_path: str
    action: str
    reason: str
    is_dir: bool
    include: bool = True
    status: str = ""
    conflict: bool = False


class AIRenamePlanDialog(QDialog):
    COL_CHECK = 0
    COL_CURRENT = 1
    COL_TARGET = 2
    COL_ACTION = 3
    COL_STATUS = 4
    COL_REASON = 5

    def __init__(
        self,
        candidates: List[AIRenamePlanCandidate],
        *,
        summary: str,
        warnings: List[str],
        validator: Optional[Callable[[List[AIRenamePlanCandidate]], dict[str, tuple[str, bool]]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Rename & Organize Preview")
        self.resize(1100, 650)
        self._candidates = candidates
        self._validator = validator
        self._base_summary = summary or "Review the AI rename plan before applying it."

        layout = QVBoxLayout(self)

        self._summary = QLabel(self._base_summary, self)
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._select_all = QCheckBox("Select all safe operations", self)
        self._select_all.setChecked(True)
        self._select_all.stateChanged.connect(self._on_select_all)
        layout.addWidget(self._select_all)

        self._table = QTableWidget(self)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["", "Current", "Target", "Action", "Status", "Reason"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table, 1)

        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        log_lines = []
        if warnings:
            log_lines.append("Warnings:")
            log_lines.extend(f"- {value}" for value in warnings)
        log_lines.append("Planned operations:")
        for cand in candidates:
            log_lines.append(f"- {cand.action}: {cand.current_relative_path or '.'} -> {cand.target_relative_path or '.'}")
        self._log.setPlainText("\n".join(log_lines))
        self._log.setMaximumHeight(180)
        layout.addWidget(self._log)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate()
        self._revalidate()

    def _populate(self) -> None:
        self._table.setRowCount(len(self._candidates))
        for row, cand in enumerate(self._candidates):
            check = QTableWidgetItem("")
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Checked if cand.include else Qt.Unchecked)
            self._table.setItem(row, self.COL_CHECK, check)
            self._table.setItem(row, self.COL_CURRENT, QTableWidgetItem(cand.current_relative_path or "."))
            self._table.setItem(row, self.COL_TARGET, QTableWidgetItem(cand.target_relative_path or "."))
            self._table.setItem(row, self.COL_ACTION, QTableWidgetItem(cand.action))
            self._table.setItem(row, self.COL_STATUS, QTableWidgetItem(cand.status))
            self._table.setItem(row, self.COL_REASON, QTableWidgetItem(cand.reason))
        self._table.resizeColumnsToContents()
        self._table.itemChanged.connect(self._on_item_changed)

    def _on_select_all(self, state: int) -> None:
        checked = state == Qt.Checked
        for row, cand in enumerate(self._candidates):
            if cand.conflict and checked:
                continue
            item = self._table.item(row, self.COL_CHECK)
            if item:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self.COL_CHECK:
            return
        row = item.row()
        if 0 <= row < len(self._candidates):
            self._candidates[row].include = item.checkState() == Qt.Checked

    def _revalidate(self) -> None:
        statuses = self._validator(self._candidates) if self._validator else {}
        safe_count = 0
        for row, cand in enumerate(self._candidates):
            status, conflict = statuses.get(cand.source_path, ("Ready", False))
            cand.status = status
            cand.conflict = conflict
            if conflict:
                cand.include = False
                check = self._table.item(row, self.COL_CHECK)
                if check:
                    check.setCheckState(Qt.Unchecked)
            elif cand.include:
                safe_count += 1
            status_item = self._table.item(row, self.COL_STATUS)
            if status_item:
                status_item.setText(status)
        self._summary.setText(f"{self._base_summary}\nSafe operations selected: {safe_count} / {len(self._candidates)}")

    def selected_candidates(self) -> List[AIRenamePlanCandidate]:
        selected: List[AIRenamePlanCandidate] = []
        for row, cand in enumerate(self._candidates):
            check = self._table.item(row, self.COL_CHECK)
            include = (check.checkState() == Qt.Checked) if check else cand.include
            if not include or cand.conflict:
                continue
            selected.append(cand)
        return selected
