from __future__ import annotations

from typing import Optional

from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)


class SharePointSelectorDialog(QDialog):
    def __init__(self, backend_client, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select SharePoint Library")
        self.backend = backend_client

        self._sites_combo = QComboBox(self)
        self._libs_combo = QComboBox(self)
        self._manual_site = QLineEdit(self)
        self._manual_site.setPlaceholderText("https://tenant.sharepoint.com/sites/AnotherSite (optional)")
        self._manual_load = QPushButton("Load", self)

        form = QFormLayout(self)
        form.addRow(QLabel("Site:"), self._sites_combo)
        form.addRow(QLabel("Library:"), self._libs_combo)
        row = QHBoxLayout()
        row.addWidget(self._manual_site)
        row.addWidget(self._manual_load)
        form.addRow(QLabel("Or enter Site URL:"), row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

        self._sites = []
        self._libraries = []

        self._sites_combo.currentIndexChanged.connect(self._on_site_changed)
        self._manual_load.clicked.connect(self._on_manual_load)
        self._load_sites()

    def _load_sites(self) -> None:
        try:
            resp = self.backend.sp_sites()
            sites = resp.get("sites", [])
        except Exception as exc:
            QMessageBox.critical(self, "SharePoint", f"Failed to fetch sites: {exc}")
            sites = []
        self._sites = sites
        self._sites_combo.clear()
        for site in sites:
            title = site.get("title") or site.get("url") or "(Unnamed)"
            self._sites_combo.addItem(title, site)
        if sites:
            self._on_site_changed(0)

    def _on_site_changed(self, index: int) -> None:
        data = self._sites_combo.itemData(index)
        site_rel = self._normalize_site_relative(data)
        try:
            resp = self.backend.sp_libraries(site_relative_url=site_rel if site_rel != "/" else None)
            libs = resp.get("libraries", [])
        except Exception as exc:
            QMessageBox.critical(self, "SharePoint", f"Failed to fetch libraries: {exc}")
            libs = []
        self._libraries = libs
        self._libs_combo.clear()
        for lib in libs:
            path = (
                lib.get("serverRelativeUrl")
                or lib.get("server_relative_url")
                or lib.get("path")
                or ""
            )
            if not path or path == "/":
                continue
            title = lib.get("title") or lib.get("name") or path
            self._libs_combo.addItem(title, lib)
        if self._libs_combo.count() == 0:
            QMessageBox.information(self, "SharePoint", "No document libraries with valid paths were found for this site.")

    def _on_manual_load(self) -> None:
        url = (self._manual_site.text() or "").strip()
        if not url:
            return
        try:
            parsed_rel = self._normalize_site_relative({"url": url})
            resp = self.backend.sp_libraries(site_relative_url=parsed_rel if parsed_rel != "/" else None)
            libs = resp.get("libraries", [])
        except Exception as exc:
            QMessageBox.critical(self, "SharePoint", f"Failed to fetch libraries for site: {exc}")
            return
        self._libraries = libs
        self._libs_combo.clear()
        for lib in libs:
            path = (
                lib.get("serverRelativeUrl")
                or lib.get("server_relative_url")
                or lib.get("path")
                or ""
            )
            if not path or path == "/":
                continue
            title = lib.get("title") or lib.get("name") or path
            self._libs_combo.addItem(title, lib)
        if self._libs_combo.count() == 0:
            QMessageBox.information(self, "SharePoint", "No document libraries with valid paths were found for this site.")

    def selected(self) -> Optional[dict]:
        site = self._sites_combo.currentData()
        library = self._libs_combo.currentData()
        if not site or not library:
            return None
        site_rel = self._normalize_site_relative(site)
        lib_path = self._normalize_server_relative(
            library.get("server_relative_url")
            or library.get("serverRelativeUrl")
            or library.get("path")
        )
        if not lib_path or lib_path == "/":
            return None
        return {
            "site_relative_url": site_rel,
            "server_relative_url": lib_path,
            "site_title": site.get("title") or site.get("url") or "SharePoint",
            "library_title": library.get("title") or library.get("name") or "Library",
        }

    @staticmethod
    def _normalize_site_relative(site: Optional[dict]) -> str:
        if not site:
            return "/"
        rel = site.get("serverRelativeUrl") or site.get("server_relative_url")
        if rel:
            rel = rel if rel.startswith("/") else "/" + rel
            return rel or "/"
        url = site.get("url")
        if url:
            parsed = urlparse(url)
            path = parsed.path or "/"
            return path or "/"
        return "/"

    @staticmethod
    def _normalize_server_relative(path: Optional[str]) -> str:
        if not path:
            return ""
        return path if path.startswith("/") else "/" + path
