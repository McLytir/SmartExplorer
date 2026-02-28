from __future__ import annotations

from typing import Optional

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

from ..services.link_migration_log import LinkMigrationLog


class LinkMigrationLogDialog(QDialog):
    def __init__(self, log: LinkMigrationLog, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Migration Log")
        self.resize(1100, 560)
        self._log = log

        root = QVBoxLayout(self)

        self._summary = QLabel(self)
        root.addWidget(self._summary)

        self._filter = QLineEdit(self)
        self._filter.setPlaceholderText("Filter by path, site, operation, or status")
        root.addWidget(self._filter)

        self._table = QTableWidget(self)
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            [
                "Timestamp",
                "Operation",
                "Item Type",
                "Old Path",
                "New Path",
                "Source Site",
                "Target Site",
                "Status",
            ]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        self._details = QTextEdit(self)
        self._details.setReadOnly(True)
        self._details.setMaximumHeight(140)
        self._details.setPlaceholderText("Select a migration record to inspect details.")
        root.addWidget(self._details)

        actions = QHBoxLayout()
        self._btn_refresh = QPushButton("Refresh", self)
        self._btn_import_json = QPushButton("Import JSON", self)
        self._btn_export_json = QPushButton("Export JSON", self)
        self._btn_export_csv = QPushButton("Export CSV", self)
        actions.addWidget(self._btn_refresh)
        actions.addWidget(self._btn_import_json)
        actions.addStretch(1)
        actions.addWidget(self._btn_export_json)
        actions.addWidget(self._btn_export_csv)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._btn_refresh.clicked.connect(self._reload)
        self._btn_import_json.clicked.connect(self._import_json)
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
            records = [
                record
                for record in records
                if query in " ".join(
                    [
                        str(record.timestamp or ""),
                        str(record.operation_type or ""),
                        str(record.item_type or ""),
                        str(record.old_server_relative_url or ""),
                        str(record.new_server_relative_url or ""),
                        str(record.source_site_relative_url or ""),
                        str(record.target_site_relative_url or ""),
                        str(record.status or ""),
                    ]
                ).lower()
            ]
        self._table.setProperty("_records", records)
        self._summary.setText(f"{len(records)} visible migration record(s)")
        self._table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                record.timestamp,
                record.operation_type,
                record.item_type,
                record.old_server_relative_url,
                record.new_server_relative_url,
                record.source_site_relative_url or "",
                record.target_site_relative_url or "",
                record.status,
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(str(value)))
        self._table.resizeColumnsToContents()
        self._update_details()

    def _update_details(self, *_args) -> None:
        records = self._table.property("_records") or []
        row = self._table.currentRow()
        if row < 0 or row >= len(records):
            self._details.clear()
            return
        record = records[row]
        self._details.setPlainText(
            "\n".join(
                [
                    f"Timestamp: {record.timestamp}",
                    f"Operation: {record.operation_type}",
                    f"Item Type: {record.item_type}",
                    f"Old Path: {record.old_server_relative_url}",
                    f"New Path: {record.new_server_relative_url}",
                    f"Source Site Rel: {record.source_site_relative_url or ''}",
                    f"Target Site Rel: {record.target_site_relative_url or ''}",
                    f"Old URL: {record.old_web_url or ''}",
                    f"New URL: {record.new_web_url or ''}",
                    f"Workspace: {record.workspace_id or ''}",
                    f"Status: {record.status}",
                    f"Notes: {record.notes or ''}",
                ]
            )
        )

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Link Migration Log", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            report = self._log.import_json_report(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import JSON", f"Failed to import JSON: {exc}")
            return
        self._reload()
        parts = [
            f"Imported {report['added']} new migration record(s).",
            f"Skipped {report['duplicates']} duplicate record(s).",
        ]
        if report["conflicts"]:
            parts.append(f"Detected {report['conflicts']} conflicting mapping(s).")
            first = report["conflict_records"][0]
            parts.append(
                "Example conflict: "
                f"{first['old_server_relative_url']} -> {first['existing_new_server_relative_url']} "
                f"already exists, incoming target is {first['incoming_new_server_relative_url']}."
            )
        QMessageBox.information(self, "Import JSON", "\n".join(parts))

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Link Migration Log", "smart_explorer_link_migrations.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            self._log.export_json(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export JSON", f"Failed to export JSON: {exc}")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Link Migration Log", "smart_explorer_link_migrations.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            self._log.export_csv(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export CSV", f"Failed to export CSV: {exc}")
