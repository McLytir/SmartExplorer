from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services.link_migration_log import LinkMigrationLog
from ..services.relinking_workspace import RelinkingExportRecord, RelinkingImportRecord, RelinkingWorkspaceStore


class RelinkingPanel(QWidget):
    open_in_app_requested = Signal(str, str)
    status_message_requested = Signal(str, int)

    def __init__(
        self,
        log: LinkMigrationLog,
        store: RelinkingWorkspaceStore,
        parent: Optional[QWidget] = None,
        *,
        sp_base_url: str = "",
    ) -> None:
        super().__init__(parent)
        self._log = log
        self._store = store
        self._sp_base_url = str(sp_base_url or "")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel("Relinking", self)
        header.setObjectName("RelinkingHeader")
        root.addWidget(header)

        resolve_card = QFrame(self)
        resolve_layout = QVBoxLayout(resolve_card)
        resolve_layout.setContentsMargins(10, 10, 10, 10)
        resolve_layout.setSpacing(8)
        resolve_layout.addWidget(QLabel("Resolve stale SharePoint links against the background migration log.", resolve_card))

        resolve_row = QHBoxLayout()
        self._resolve_input = QLineEdit(resolve_card)
        self._resolve_input.setPlaceholderText("Paste old SharePoint URL or server-relative path")
        self._resolve_btn = QPushButton("Resolve", resolve_card)
        resolve_row.addWidget(self._resolve_input, 1)
        resolve_row.addWidget(self._resolve_btn)
        resolve_layout.addLayout(resolve_row)

        resolve_grid = QGridLayout()
        resolve_grid.setHorizontalSpacing(8)
        resolve_grid.setVerticalSpacing(6)
        resolve_grid.addWidget(QLabel("Resolved Path:", resolve_card), 0, 0)
        self._resolved_path = QLineEdit(resolve_card)
        self._resolved_path.setReadOnly(True)
        resolve_grid.addWidget(self._resolved_path, 0, 1)
        resolve_grid.addWidget(QLabel("Resolved Site:", resolve_card), 1, 0)
        self._resolved_site = QLineEdit(resolve_card)
        self._resolved_site.setReadOnly(True)
        resolve_grid.addWidget(self._resolved_site, 1, 1)
        resolve_grid.addWidget(QLabel("Resolved URL:", resolve_card), 2, 0)
        self._resolved_url = QLineEdit(resolve_card)
        self._resolved_url.setReadOnly(True)
        resolve_grid.addWidget(self._resolved_url, 2, 1)
        resolve_layout.addLayout(resolve_grid)

        self._resolve_notes = QTextEdit(resolve_card)
        self._resolve_notes.setReadOnly(True)
        self._resolve_notes.setMaximumHeight(100)
        self._resolve_notes.setPlaceholderText("Resolution details appear here.")
        resolve_layout.addWidget(self._resolve_notes)

        resolve_actions = QHBoxLayout()
        self._copy_resolved_btn = QPushButton("Copy Result", resolve_card)
        self._open_in_app_btn = QPushButton("Open in SmartExplorer", resolve_card)
        self._open_resolved_btn = QPushButton("Open Resolved", resolve_card)
        resolve_actions.addWidget(self._copy_resolved_btn)
        resolve_actions.addWidget(self._open_in_app_btn)
        resolve_actions.addWidget(self._open_resolved_btn)
        resolve_actions.addStretch(1)
        resolve_layout.addLayout(resolve_actions)
        root.addWidget(resolve_card)

        imports_card = QFrame(self)
        imports_layout = QVBoxLayout(imports_card)
        imports_layout.setContentsMargins(10, 10, 10, 10)
        imports_layout.setSpacing(8)
        imports_layout.addWidget(QLabel("Imports", imports_card))
        self._imports_summary = QLabel(imports_card)
        imports_layout.addWidget(self._imports_summary)
        self._imports_table = QTableWidget(imports_card)
        self._imports_table.setColumnCount(6)
        self._imports_table.setHorizontalHeaderLabels(["Name", "Imported", "Browser", "Total", "Status", "Source"])
        self._imports_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._imports_table.setSelectionMode(QTableWidget.SingleSelection)
        self._imports_table.setEditTriggers(QTableWidget.NoEditTriggers)
        imports_layout.addWidget(self._imports_table)
        imports_actions = QHBoxLayout()
        self._import_html_btn = QPushButton("Import Bookmark HTML", imports_card)
        self._export_import_json_btn = QPushButton("Export Import JSON", imports_card)
        self._resolve_import_btn = QPushButton("Resolve Selected", imports_card)
        self._delete_import_btn = QPushButton("Delete Selected", imports_card)
        self._clear_imports_btn = QPushButton("Clear Imports", imports_card)
        imports_actions.addWidget(self._import_html_btn)
        imports_actions.addWidget(self._export_import_json_btn)
        imports_actions.addWidget(self._resolve_import_btn)
        imports_actions.addWidget(self._delete_import_btn)
        imports_actions.addWidget(self._clear_imports_btn)
        imports_actions.addStretch(1)
        imports_layout.addLayout(imports_actions)
        root.addWidget(imports_card, 1)

        activity_card = QFrame(self)
        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(10, 10, 10, 10)
        activity_layout.setSpacing(8)
        activity_layout.addWidget(QLabel("Background Activity", activity_card))
        self._activity_summary = QLabel(activity_card)
        activity_layout.addWidget(self._activity_summary)
        self._activity_table = QTableWidget(activity_card)
        self._activity_table.setColumnCount(4)
        self._activity_table.setHorizontalHeaderLabels(["Timestamp", "Operation", "Old Path", "New Path"])
        self._activity_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._activity_table.setSelectionMode(QTableWidget.SingleSelection)
        self._activity_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._activity_table.setMaximumHeight(180)
        activity_layout.addWidget(self._activity_table)
        activity_actions = QHBoxLayout()
        self._import_log_btn = QPushButton("Import Activity JSON", activity_card)
        self._export_log_btn = QPushButton("Export Activity", activity_card)
        self._delete_log_btn = QPushButton("Delete Selected", activity_card)
        self._clear_log_btn = QPushButton("Clear Activity", activity_card)
        self._refresh_activity_btn = QPushButton("Refresh", activity_card)
        activity_actions.addWidget(self._import_log_btn)
        activity_actions.addWidget(self._export_log_btn)
        activity_actions.addWidget(self._delete_log_btn)
        activity_actions.addWidget(self._clear_log_btn)
        activity_actions.addWidget(self._refresh_activity_btn)
        activity_actions.addStretch(1)
        activity_layout.addLayout(activity_actions)
        root.addWidget(activity_card)

        exports_card = QFrame(self)
        exports_layout = QVBoxLayout(exports_card)
        exports_layout.setContentsMargins(10, 10, 10, 10)
        exports_layout.setSpacing(8)
        exports_layout.addWidget(QLabel("Exports", exports_card))
        self._exports_summary = QLabel(exports_card)
        exports_layout.addWidget(self._exports_summary)
        self._exports_table = QTableWidget(exports_card)
        self._exports_table.setColumnCount(7)
        self._exports_table.setHorizontalHeaderLabels(["Import", "Created", "Total", "Resolved", "Unchanged", "External", "Status"])
        self._exports_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._exports_table.setSelectionMode(QTableWidget.SingleSelection)
        self._exports_table.setEditTriggers(QTableWidget.NoEditTriggers)
        exports_layout.addWidget(self._exports_table)
        exports_actions = QHBoxLayout()
        self._download_html_btn = QPushButton("Download HTML", exports_card)
        self._download_json_btn = QPushButton("Download JSON", exports_card)
        self._delete_export_btn = QPushButton("Delete Selected", exports_card)
        self._clear_exports_btn = QPushButton("Clear Exports", exports_card)
        exports_actions.addWidget(self._download_html_btn)
        exports_actions.addWidget(self._download_json_btn)
        exports_actions.addWidget(self._delete_export_btn)
        exports_actions.addWidget(self._clear_exports_btn)
        exports_actions.addStretch(1)
        exports_layout.addLayout(exports_actions)
        root.addWidget(exports_card, 1)

        self._resolve_btn.clicked.connect(self._resolve_path)
        self._resolve_input.returnPressed.connect(self._resolve_path)
        self._copy_resolved_btn.clicked.connect(self._copy_resolved)
        self._open_in_app_btn.clicked.connect(self._open_in_app)
        self._open_resolved_btn.clicked.connect(self._open_resolved)
        self._import_html_btn.clicked.connect(self._import_bookmark_html)
        self._export_import_json_btn.clicked.connect(self._export_import_json)
        self._resolve_import_btn.clicked.connect(self._resolve_selected_import)
        self._delete_import_btn.clicked.connect(self._delete_selected_import)
        self._clear_imports_btn.clicked.connect(self._clear_imports)
        self._import_log_btn.clicked.connect(self._import_log_json)
        self._export_log_btn.clicked.connect(self._export_log)
        self._delete_log_btn.clicked.connect(self._delete_selected_log_record)
        self._clear_log_btn.clicked.connect(self._clear_log)
        self._refresh_activity_btn.clicked.connect(self.refresh_all)
        self._download_html_btn.clicked.connect(self._download_selected_export_html)
        self._download_json_btn.clicked.connect(self._download_selected_export_json)
        self._delete_export_btn.clicked.connect(self._delete_selected_export)
        self._clear_exports_btn.clicked.connect(self._clear_exports)

        self._set_resolve_actions_enabled(False)
        self.refresh_all()

    def set_base_url(self, base_url: str) -> None:
        self._sp_base_url = str(base_url or "")

    def refresh_all(self) -> None:
        self._log.reload()
        self._store.reload()
        self._render_activity()
        self._render_imports()
        self._render_exports()

    def _render_activity(self) -> None:
        records = list(reversed(self._log.all()))
        self._activity_summary.setText(f"{len(records)} migration record(s) captured in the background.")
        recent = records[:12]
        self._activity_table.setRowCount(len(recent))
        for row, record in enumerate(recent):
            values = [
                str(record.timestamp or ""),
                str(record.operation_type or ""),
                str(record.old_server_relative_url or ""),
                str(record.new_server_relative_url or ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, record.id)
                self._activity_table.setItem(row, column, item)
        self._activity_table.resizeColumnsToContents()

    def _render_imports(self) -> None:
        imports = self._store.all_imports()
        self._imports_summary.setText(f"{len(imports)} managed bookmark import(s).")
        self._imports_table.setRowCount(len(imports))
        for row, record in enumerate(imports):
            values = [
                record.name,
                record.imported_at,
                record.source_browser,
                str(record.summary.total),
                record.status,
                record.source_path,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, record.id)
                self._imports_table.setItem(row, column, item)
        self._imports_table.resizeColumnsToContents()

    def _render_exports(self) -> None:
        exports = self._store.all_exports()
        self._exports_summary.setText(f"{len(exports)} resolved export artifact(s).")
        self._exports_table.setRowCount(len(exports))
        for row, record in enumerate(exports):
            values = [
                record.source_import_name,
                record.created_at,
                str(record.summary.total),
                str(record.summary.resolved),
                str(record.summary.unchanged),
                str(record.summary.external),
                record.status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, record.id)
                self._exports_table.setItem(row, column, item)
        self._exports_table.resizeColumnsToContents()

    def _selected_import(self) -> Optional[RelinkingImportRecord]:
        row = self._imports_table.currentRow()
        if row < 0:
            return None
        item = self._imports_table.item(row, 0)
        record_id = str(item.data(Qt.UserRole) or "") if item else ""
        return self._store.get_import(record_id)

    def _selected_export(self) -> Optional[RelinkingExportRecord]:
        row = self._exports_table.currentRow()
        if row < 0:
            return None
        item = self._exports_table.item(row, 0)
        record_id = str(item.data(Qt.UserRole) or "") if item else ""
        return self._store.get_export(record_id)

    def _selected_log_record_id(self) -> str:
        row = self._activity_table.currentRow()
        if row < 0:
            return ""
        item = self._activity_table.item(row, 0)
        return str(item.data(Qt.UserRole) or "") if item else ""

    def _resolve_path(self) -> None:
        raw = self._resolve_input.text().strip()
        if not raw:
            return
        parsed = urlparse(raw)
        path = parsed.path or "" if parsed.scheme and parsed.netloc else raw
        resolved = self._log.resolve_target(path)
        if not resolved:
            self._resolved_path.clear()
            self._resolved_site.clear()
            self._resolved_url.clear()
            self._resolve_notes.setPlainText("No migration record matched that link or path.")
            self._set_resolve_actions_enabled(False)
            return
        resolved_path = str(resolved.get("server_relative_url") or "")
        resolved_site = str(resolved.get("site_relative_url") or "")
        resolved_url = self._log.build_web_url(self._sp_base_url, resolved_path) or ""
        self._resolved_path.setText(resolved_path)
        self._resolved_site.setText(resolved_site)
        self._resolved_url.setText(resolved_url)
        self._resolve_notes.setPlainText(
            f"Resolved stale input:\n{raw}\n\nCurrent path:\n{resolved_path}\n\nCurrent site:\n{resolved_site or '(unchanged/unknown)'}"
        )
        self._set_resolve_actions_enabled(True)

    def _set_resolve_actions_enabled(self, enabled: bool) -> None:
        self._copy_resolved_btn.setEnabled(enabled)
        self._open_in_app_btn.setEnabled(enabled)
        self._open_resolved_btn.setEnabled(enabled)

    def _copy_resolved(self) -> None:
        value = self._resolved_url.text().strip() or self._resolved_path.text().strip()
        if not value:
            return
        QApplication.clipboard().setText(value)
        self.status_message_requested.emit("Resolved link copied to clipboard.", 4000)

    def _open_in_app(self) -> None:
        path = self._resolved_path.text().strip()
        site = self._resolved_site.text().strip()
        if not path:
            return
        self.open_in_app_requested.emit(path, site)

    def _open_resolved(self) -> None:
        url = self._resolved_url.text().strip()
        if not url:
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "Open Resolved", "Failed to open the resolved link.")

    def _import_bookmark_html(self) -> None:
        source_path, _ = QFileDialog.getOpenFileName(self, "Import Bookmark HTML", "", "HTML Files (*.html *.htm)")
        if not source_path:
            return
        try:
            record = self._store.import_bookmark_html(source_path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Bookmark HTML", f"Failed to import bookmark HTML: {exc}")
            return
        self.refresh_all()
        self.status_message_requested.emit(f"Imported {record.summary.total} bookmark(s) from {record.name}.", 5000)

    def _export_import_json(self) -> None:
        record = self._selected_import()
        if record is None:
            QMessageBox.information(self, "Export Import JSON", "Select an imported bookmark artifact first.")
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Import JSON",
            f"{os.path.splitext(record.name)[0]}-import.json",
            "JSON Files (*.json)",
        )
        if not target_path:
            return
        try:
            self._store.export_import_json(record.id, target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Export Import JSON", f"Failed to export import JSON: {exc}")
            return
        self.status_message_requested.emit(f"Exported import JSON to {target_path}.", 5000)

    def _delete_selected_import(self) -> None:
        record = self._selected_import()
        if record is None:
            QMessageBox.information(self, "Delete Import", "Select an imported bookmark artifact first.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Import",
            f"Delete import '{record.name}' and its resolved exports?",
        )
        if confirm != QMessageBox.Yes:
            return
        if self._store.delete_import(record.id):
            self.refresh_all()
            self.status_message_requested.emit(f"Deleted import '{record.name}'.", 5000)

    def _clear_imports(self) -> None:
        if not self._store.all_imports():
            return
        confirm = QMessageBox.question(
            self,
            "Clear Imports",
            "Delete all imported bookmark artifacts and their resolved exports?",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = self._store.clear_imports()
        self.refresh_all()
        self.status_message_requested.emit(f"Cleared {removed} import artifact(s).", 5000)

    def _resolve_selected_import(self) -> None:
        record = self._selected_import()
        if record is None:
            QMessageBox.information(self, "Resolve Selected", "Select an imported bookmark artifact first.")
            return
        try:
            export_record = self._store.resolve_import(record.id, self._log, base_url=self._sp_base_url)
        except Exception as exc:
            QMessageBox.warning(self, "Resolve Selected", f"Failed to resolve bookmark import: {exc}")
            return
        self.refresh_all()
        default_name = f"{os.path.splitext(record.name)[0]}-resolved.html"
        target_path, _ = QFileDialog.getSaveFileName(self, "Export Resolved Bookmark HTML", default_name, "HTML Files (*.html)")
        if target_path:
            try:
                self._store.export_resolved_html(export_record.id, target_path)
                self.status_message_requested.emit(f"Resolved HTML exported to {target_path}.", 6000)
            except Exception as exc:
                QMessageBox.warning(self, "Export Resolved Bookmark HTML", f"Failed to export resolved HTML: {exc}")
                return

    def _download_selected_export_html(self) -> None:
        record = self._selected_export()
        if record is None:
            QMessageBox.information(self, "Download HTML", "Select a resolved export first.")
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download Resolved Bookmark HTML",
            f"{os.path.splitext(record.source_import_name)[0]}-resolved.html",
            "HTML Files (*.html)",
        )
        if not target_path:
            return
        try:
            self._store.export_resolved_html(record.id, target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Download HTML", f"Failed to export resolved HTML: {exc}")
            return
        self.status_message_requested.emit(f"Resolved HTML exported to {target_path}.", 6000)

    def _download_selected_export_json(self) -> None:
        record = self._selected_export()
        if record is None:
            QMessageBox.information(self, "Download JSON", "Select a resolved export first.")
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download Resolved JSON",
            f"{os.path.splitext(record.source_import_name)[0]}-resolved.json",
            "JSON Files (*.json)",
        )
        if not target_path:
            return
        try:
            self._store.export_resolved_json(record.id, target_path)
        except Exception as exc:
            QMessageBox.warning(self, "Download JSON", f"Failed to export resolved JSON: {exc}")
            return
        self.status_message_requested.emit(f"Resolved JSON exported to {target_path}.", 6000)

    def _delete_selected_export(self) -> None:
        record = self._selected_export()
        if record is None:
            QMessageBox.information(self, "Delete Export", "Select a resolved export first.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Export",
            f"Delete resolved export '{record.source_import_name}' created at {record.created_at}?",
        )
        if confirm != QMessageBox.Yes:
            return
        if self._store.delete_export(record.id):
            self.refresh_all()
            self.status_message_requested.emit("Deleted resolved export artifact.", 5000)

    def _clear_exports(self) -> None:
        if not self._store.all_exports():
            return
        confirm = QMessageBox.question(
            self,
            "Clear Exports",
            "Delete all resolved export artifacts?",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = self._store.clear_exports()
        self.refresh_all()
        self.status_message_requested.emit(f"Cleared {removed} export artifact(s).", 5000)

    def _import_log_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Link Migration Log", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            report = self._log.import_json_report(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Activity JSON", f"Failed to import migration log: {exc}")
            return
        self.refresh_all()
        self.status_message_requested.emit(
            f"Imported {report['added']} migration record(s), skipped {report['duplicates']} duplicate(s), detected {report['conflicts']} conflict(s).",
            7000,
        )

    def _export_log(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Link Migration Log",
            "smart_explorer_link_migrations.json",
            "JSON Files (*.json);;CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv") or "CSV" in selected_filter:
                self._log.export_csv(path)
            else:
                self._log.export_json(path)
        except Exception as exc:
            QMessageBox.warning(self, "Export Activity", f"Failed to export migration log: {exc}")
            return
        self.status_message_requested.emit(f"Exported activity log to {path}.", 5000)

    def _delete_selected_log_record(self) -> None:
        record_id = self._selected_log_record_id()
        if not record_id:
            QMessageBox.information(self, "Delete Activity", "Select an activity record first.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Activity",
            "Delete the selected migration activity record?",
        )
        if confirm != QMessageBox.Yes:
            return
        if self._log.delete(record_id):
            self.refresh_all()
            self.status_message_requested.emit("Deleted selected migration activity.", 5000)

    def _clear_log(self) -> None:
        if not self._log.all():
            return
        confirm = QMessageBox.question(
            self,
            "Clear Activity",
            "Delete all migration activity records?",
        )
        if confirm != QMessageBox.Yes:
            return
        removed = self._log.clear()
        self.refresh_all()
        self.status_message_requested.emit(f"Cleared {removed} migration record(s).", 5000)
