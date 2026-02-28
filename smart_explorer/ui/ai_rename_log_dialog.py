from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ..services.ai_rename_batch_log import AIRenameBatchLog


class AIRenameLogDialog(QDialog):
    def __init__(self, log: AIRenameBatchLog, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Rename Batch Log")
        self.resize(1100, 600)
        self._log = log

        root = QVBoxLayout(self)
        self._summary = QLabel(self)
        root.addWidget(self._summary)

        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Filter by summary, path, instruction, status, or site")
        root.addWidget(self._filter)

        self._table = QTableWidget(self)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["Timestamp", "Kind", "Root", "Recursive", "Ops", "Summary", "Site"])
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, 1)

        self._details = QTextEdit(self)
        self._details.setReadOnly(True)
        self._details.setMaximumHeight(180)
        root.addWidget(self._details)

        actions = QHBoxLayout()
        self._btn_refresh = QPushButton("Refresh", self)
        self._btn_export_json = QPushButton("Export JSON", self)
        self._btn_export_csv = QPushButton("Export CSV", self)
        actions.addWidget(self._btn_refresh)
        actions.addStretch(1)
        actions.addWidget(self._btn_export_json)
        actions.addWidget(self._btn_export_csv)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._btn_refresh.clicked.connect(self._reload)
        self._btn_export_json.clicked.connect(self._export_json)
        self._btn_export_csv.clicked.connect(self._export_csv)
        self._filter.textChanged.connect(self._reload)
        self._table.currentCellChanged.connect(self._update_details)

        self._reload()

    def _reload(self) -> None:
        self._log.reload()
        records = list(reversed(self._log.all()))
        query = (self._filter.text() or "").strip().lower()
        if query:
            filtered = []
            for record in records:
                blob = " ".join(
                    [
                        record.timestamp,
                        record.kind,
                        record.root_path,
                        record.site_relative_url or "",
                        record.summary,
                        record.instruction,
                        " ".join(record.warnings),
                        " ".join(op.source_path for op in record.operations),
                        " ".join(op.target_path for op in record.operations),
                        " ".join(op.status for op in record.operations),
                    ]
                ).lower()
                if query in blob:
                    filtered.append(record)
            records = filtered
        self._table.setProperty("_records", records)
        self._summary.setText(f"{len(records)} AI rename batch record(s)")
        self._table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                record.timestamp,
                record.kind,
                record.root_path,
                "Yes" if record.recursive else "No",
                str(len(record.operations)),
                record.summary,
                record.site_relative_url or "",
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._table.resizeColumnsToContents()
        self._update_details()

    def _update_details(self, *_args) -> None:
        records = self._table.property("_records") or []
        row = self._table.currentRow()
        if row < 0 or row >= len(records):
            self._details.clear()
            return
        record = records[row]
        lines = [
            f"Timestamp: {record.timestamp}",
            f"Kind: {record.kind}",
            f"Site: {record.site_relative_url or ''}",
            f"Root: {record.root_path}",
            f"Recursive: {record.recursive}",
            f"Summary: {record.summary}",
            f"Instruction: {record.instruction}",
            "Warnings:",
        ]
        lines.extend(f"- {value}" for value in (record.warnings or []))
        lines.append("Operations:")
        for op in record.operations:
            lines.append(
                f"- [{op.status}] {op.action}: {op.source_path} -> {op.target_path} | {op.reason}"
                + (f" | error={op.error}" if op.error else "")
            )
        self._details.setPlainText("\n".join(lines))

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export AI Rename Log", "smart_explorer_ai_rename_batches.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            self._log.export_json(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export AI Rename Log", f"Failed to export JSON: {exc}")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export AI Rename Log", "smart_explorer_ai_rename_batches.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            self._log.export_csv(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export AI Rename Log", f"Failed to export CSV: {exc}")
