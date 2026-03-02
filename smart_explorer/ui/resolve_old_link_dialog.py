from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..services.bookmark_export_converter import (
    convert_bookmark_html,
    export_converted_bookmarks_csv,
    export_converted_bookmarks_json,
)
from ..services.link_migration_log import LinkMigrationLog
from ..settings import AppConfig, save_config


class ResolveOldLinkDialog(QDialog):
    open_in_app_requested = Signal(str, str)

    def __init__(self, log: LinkMigrationLog, cfg: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve Old SharePoint Link")
        self.resize(760, 320)
        self._log = log
        self._cfg = cfg

        root = QVBoxLayout(self)

        form = QFormLayout()
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Paste a stale SharePoint URL or server-relative path")
        form.addRow("Old Link or Path:", self._input)

        self._resolved_path = QLineEdit(self)
        self._resolved_path.setReadOnly(True)
        form.addRow("Resolved Path:", self._resolved_path)

        self._resolved_site = QLineEdit(self)
        self._resolved_site.setReadOnly(True)
        form.addRow("Resolved Site:", self._resolved_site)

        self._resolved_url = QLineEdit(self)
        self._resolved_url.setReadOnly(True)
        form.addRow("Resolved URL:", self._resolved_url)
        root.addLayout(form)

        self._notes = QTextEdit(self)
        self._notes.setReadOnly(True)
        self._notes.setPlaceholderText("Resolution details appear here.")
        self._notes.setMaximumHeight(120)
        root.addWidget(self._notes)

        self._recent_list = QListWidget(self)
        self._recent_list.setMinimumHeight(120)
        self._recent_list.itemClicked.connect(self._apply_recent_item)
        root.addWidget(self._recent_list)

        actions = QHBoxLayout()
        self._resolve_btn = QPushButton("Resolve", self)
        self._copy_btn = QPushButton("Copy Result", self)
        self._open_in_app_btn = QPushButton("Open in SmartExplorer", self)
        self._open_btn = QPushButton("Open Resolved", self)
        self._convert_bookmarks_btn = QPushButton("Convert Bookmark HTML", self)
        self._copy_btn.setEnabled(False)
        self._open_in_app_btn.setEnabled(False)
        self._open_btn.setEnabled(False)
        actions.addWidget(self._resolve_btn)
        actions.addWidget(self._copy_btn)
        actions.addWidget(self._open_in_app_btn)
        actions.addWidget(self._open_btn)
        actions.addWidget(self._convert_bookmarks_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._resolve_btn.clicked.connect(self._resolve)
        self._copy_btn.clicked.connect(self._copy_result)
        self._open_in_app_btn.clicked.connect(self._open_in_app)
        self._open_btn.clicked.connect(self._open_result)
        self._convert_bookmarks_btn.clicked.connect(self._convert_bookmark_export)
        self._input.returnPressed.connect(self._resolve)
        self._load_recent_entries()

    def _resolve(self) -> None:
        raw = self._input.text().strip()
        if not raw:
            return
        parsed = urlparse(raw)
        if parsed.scheme and parsed.netloc:
            path = parsed.path or ""
        else:
            path = raw
        resolved = self._log.resolve_target(path)
        if not resolved:
            self._resolved_path.clear()
            self._resolved_site.clear()
            self._resolved_url.clear()
            self._copy_btn.setEnabled(False)
            self._open_in_app_btn.setEnabled(False)
            self._open_btn.setEnabled(False)
            self._notes.setPlainText("No migration record matched that link or path.")
            return
        resolved_path = str(resolved.get("server_relative_url") or "")
        resolved_site = str(resolved.get("site_relative_url") or "")
        resolved_url = self._log.build_web_url(self._cfg.sp_base_url, resolved_path) or ""
        self._resolved_path.setText(resolved_path)
        self._resolved_site.setText(resolved_site)
        self._resolved_url.setText(resolved_url)
        self._copy_btn.setEnabled(bool(resolved_url or resolved_path))
        self._open_in_app_btn.setEnabled(bool(resolved_path))
        self._open_btn.setEnabled(bool(resolved_url or resolved_path))
        self._notes.setPlainText(
            f"Resolved stale input:\n{raw}\n\nCurrent path:\n{resolved_path}\n\n"
            f"Current site:\n{resolved_site or '(unchanged/unknown)'}"
        )
        self._push_recent_entry(
            input_value=raw,
            resolved_path=resolved_path,
            resolved_site=resolved_site,
            resolved_url=resolved_url,
        )

    def _copy_result(self) -> None:
        value = self._resolved_url.text().strip() or self._resolved_path.text().strip()
        if not value:
            return
        QApplication.clipboard().setText(value)
        QMessageBox.information(self, "Resolve Old Link", "Resolved link copied to clipboard.")

    def _open_result(self) -> None:
        value = self._resolved_url.text().strip()
        if not value:
            QMessageBox.information(self, "Resolve Old Link", "No resolved browser URL is available to open.")
            return
        target = QUrl(value)
        if not target.isValid():
            QMessageBox.warning(self, "Resolve Old Link", "Resolved target is not a valid link.")
            return
        if not QDesktopServices.openUrl(target):
            QMessageBox.warning(self, "Resolve Old Link", "Failed to open the resolved target.")

    def _open_in_app(self) -> None:
        path = self._resolved_path.text().strip()
        site = self._resolved_site.text().strip()
        if not path:
            QMessageBox.information(self, "Resolve Old Link", "No resolved SharePoint path is available.")
            return
        self.open_in_app_requested.emit(path, site)
        self.accept()

    def _convert_bookmark_export(self) -> None:
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Bookmark Export",
            "",
            "HTML Files (*.html *.htm)",
        )
        if not source_path:
            return
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Converted Bookmark Export",
            "smart_explorer_bookmark_resolution.json",
            "JSON Files (*.json);;CSV Files (*.csv)",
        )
        if not target_path:
            return
        try:
            rows = convert_bookmark_html(source_path, self._log, self._cfg.sp_base_url)
            if target_path.lower().endswith(".csv"):
                export_converted_bookmarks_csv(target_path, rows)
            else:
                export_converted_bookmarks_json(target_path, rows)
        except Exception as exc:
            QMessageBox.warning(self, "Convert Bookmark HTML", f"Failed to convert bookmark export: {exc}")
            return
        resolved = sum(1 for row in rows if row.status == "resolved")
        unchanged = sum(1 for row in rows if row.status == "unchanged")
        external = sum(1 for row in rows if row.status == "external")
        QMessageBox.information(
            self,
            "Convert Bookmark HTML",
            (
                f"Converted {len(rows)} bookmark(s) to {target_path}.\n"
                f"Resolved: {resolved}\n"
                f"Unchanged: {unchanged}\n"
                f"External: {external}"
            ),
        )

    def _load_recent_entries(self) -> None:
        self._recent_list.clear()
        items = list(getattr(self._cfg, "recent_resolved_links", None) or [])
        for entry in items[:20]:
            item = QListWidgetItem(str(entry.get("input") or entry.get("resolved_path") or ""), self._recent_list)
            item.setData(256, entry)
            subtitle = str(entry.get("resolved_url") or entry.get("resolved_path") or "")
            item.setToolTip(subtitle)

    def _push_recent_entry(
        self,
        *,
        input_value: str,
        resolved_path: str,
        resolved_site: str,
        resolved_url: str,
    ) -> None:
        items = list(getattr(self._cfg, "recent_resolved_links", None) or [])
        entry = {
            "input": input_value,
            "resolved_path": resolved_path,
            "resolved_site": resolved_site,
            "resolved_url": resolved_url,
        }
        items = [x for x in items if str(x.get("input") or "") != input_value]
        items.insert(0, entry)
        self._cfg.recent_resolved_links = items[:20]
        save_config(self._cfg)
        self._load_recent_entries()

    def _apply_recent_item(self, item: QListWidgetItem) -> None:
        entry = item.data(256) or {}
        self._input.setText(str(entry.get("input") or ""))
        self._resolved_path.setText(str(entry.get("resolved_path") or ""))
        self._resolved_site.setText(str(entry.get("resolved_site") or ""))
        self._resolved_url.setText(str(entry.get("resolved_url") or ""))
        has_value = bool(self._resolved_path.text().strip() or self._resolved_url.text().strip())
        self._copy_btn.setEnabled(has_value)
        self._open_in_app_btn.setEnabled(bool(self._resolved_path.text().strip()))
        self._open_btn.setEnabled(bool(self._resolved_url.text().strip()))
        self._notes.setPlainText(
            f"Recent resolution:\n{self._input.text().strip()}\n\nCurrent path:\n{self._resolved_path.text().strip()}\n\n"
            f"Current site:\n{self._resolved_site.text().strip() or '(unchanged/unknown)'}"
        )
