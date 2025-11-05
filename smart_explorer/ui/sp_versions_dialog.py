from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QFileDialog,
)


class SPVersionsDialog(QDialog):
    def __init__(self, backend_client, server_relative_url: str, site_relative_url: Optional[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SharePoint Versions")
        self.backend = backend_client
        self.server_path = server_relative_url
        self.site_rel = site_relative_url

        root = QVBoxLayout(self)
        self.info = QLabel(self)
        self.info.setText(server_relative_url)
        root.addWidget(self.info)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Version", "Created", "Author", "Size"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.table, 1)

        btns = QDialogButtonBox(self)
        self.btn_download = QPushButton("Download", self)
        self.btn_restore = QPushButton("Restore", self)
        self.btn_close = QPushButton("Close", self)
        btns.addButton(self.btn_download, QDialogButtonBox.ActionRole)
        btns.addButton(self.btn_restore, QDialogButtonBox.ActionRole)
        btns.addButton(self.btn_close, QDialogButtonBox.RejectRole)
        root.addWidget(btns)

        self.btn_close.clicked.connect(self.reject)
        self.btn_restore.clicked.connect(self._on_restore)
        self.btn_download.clicked.connect(self._on_download)

        self._load_versions()

    def _load_versions(self) -> None:
        try:
            resp = self.backend.sp_versions(self.server_path, site_relative_url=self.site_rel)
            items: List[dict] = resp.get("versions", [])
        except Exception as exc:
            QMessageBox.warning(self, "Versions", f"Failed to fetch versions: {exc}")
            items = []
        self.table.setRowCount(len(items))
        for i, it in enumerate(items):
            ver = str(it.get("label") or "")
            created = str(it.get("created") or "")
            author = str(it.get("author") or "")
            size = str(it.get("size") or "")
            self.table.setItem(i, 0, QTableWidgetItem(ver))
            self.table.setItem(i, 1, QTableWidgetItem(created))
            self.table.setItem(i, 2, QTableWidgetItem(author))
            self.table.setItem(i, 3, QTableWidgetItem(size))
        self.table.resizeColumnsToContents()

    def _selected_label(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text().strip() if item else None

    def _on_download(self) -> None:
        label = self._selected_label()
        if not label:
            QMessageBox.information(self, "Download", "Select a version to download.")
            return
        name = self.server_path.rsplit('/', 1)[-1] or "download"
        dlg = QFileDialog(self)
        target, ok = QFileDialog.getSaveFileName(self, "Save Version As", name)
        if not ok or not target:
            return
        try:
            data = self.backend.sp_download_version(self.server_path, label, site_relative_url=self.site_rel)
            with open(target, 'wb') as f:
                f.write(data)
            QMessageBox.information(self, "Download", "Saved.")
        except Exception as exc:
            QMessageBox.warning(self, "Download", f"Failed to download: {exc}")

    def _on_restore(self) -> None:
        label = self._selected_label()
        if not label:
            QMessageBox.information(self, "Restore", "Select a version to restore.")
            return
        ok = QMessageBox.question(
            self,
            "Restore Version",
            f"Restore version {label}? Current content will be replaced.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        try:
            self.backend.sp_restore_version(self.server_path, label, site_relative_url=self.site_rel)
            QMessageBox.information(self, "Restore", "Version restored.")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Restore", f"Failed to restore version: {exc}")
