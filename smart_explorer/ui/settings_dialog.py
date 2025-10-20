from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QWidget, QMessageBox, QComboBox
)

from ..api.backend_client import BackendClient
from ..settings import AppConfig, save_config
from ..services.browser_cookies import collect_sharepoint_cookies


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(520, 420)
        self.cfg = cfg
        self.backend = BackendClient()

        root = QVBoxLayout(self)

        # Backend URL
        self.backend_url = QLineEdit(self)
        self.backend_url.setPlaceholderText("Backend URL (e.g., http://127.0.0.1:5001)")
        try:
            self.backend_url.setText(getattr(self.cfg, "backend_url", "") or "")
        except Exception:
            pass
        bux = QHBoxLayout()
        bux.addWidget(QLabel("Backend URL:"))
        bux.addWidget(self.backend_url)
        root.addLayout(bux)

        '# OpenAI key (masked; stored in system keyring)
        self.api_key = QLineEdit(self)
        self.api_key.setPlaceholderText("OpenAI API Key")
        self.api_key.setEchoMode(QLineEdit.Password)
        akx = QHBoxLayout()
        akx.addWidget(QLabel("OpenAI Key:"))
        akx.addWidget(self.api_key)
        self.btn_api_clear = QPushButton("Clear", self)
        self.btn_api_clear.setToolTip("Remove saved API key from system keyring")
        self.btn_api_clear.clicked.connect(self._on_clear_api_key)
        akx.addWidget(self.btn_api_clear)
        root.addLayout(akx)'

        # Target language
        self.lang = QLineEdit(self)
        self.lang.setText(self.cfg.target_language)
        lgx = QHBoxLayout()
        lgx.addWidget(QLabel("Target Language:"))
        lgx.addWidget(self.lang)
        root.addLayout(lgx)

        # Theme selection
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Solarized Light", "solarized_light")
        self.theme_combo.addItem("Solarized Dark", "solarized_dark")
        current_theme = getattr(self.cfg, "theme", "light")
        index = self.theme_combo.findData(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        thx = QHBoxLayout()
        thx.addWidget(QLabel("Theme:"))
        thx.addWidget(self.theme_combo)
        root.addLayout(thx)

        # SharePoint base URL
        self.sp_base = QLineEdit(self)
        self.sp_base.setPlaceholderText("https://tenant.sharepoint.com/sites/SiteName")
        self.sp_base.setText(getattr(self.cfg, "sp_base_url", "") or "")
        spx = QHBoxLayout()
        spx.addWidget(QLabel("SharePoint Site URL:"))
        spx.addWidget(self.sp_base)
        root.addLayout(spx)

        # Optional: library root override (server-relative)
        self.sp_root = QLineEdit(self)
        self.sp_root.setPlaceholderText("/sites/Site/Shared Documents (optional)")
        self.sp_root.setText(getattr(self.cfg, "sp_library_root", "") or "")
        srx = QHBoxLayout()
        srx.addWidget(QLabel("Library Root (server-relative):"))
        srx.addWidget(self.sp_root)
        root.addLayout(srx)

        # SharePoint download directory for opening files
        self.sp_download_dir = QLineEdit(self)
        try:
            self.sp_download_dir.setText(getattr(self.cfg, "sp_download_dir", "") or "")
        except Exception:
            pass
        sdd = QHBoxLayout()
        sdd.addWidget(QLabel("SharePoint Download Dir:"))
        sdd.addWidget(self.sp_download_dir, 1)
        self.sp_download_browse = QPushButton("Browse…", self)
        self.sp_download_browse.clicked.connect(self._browse_sp_download_dir)
        sdd.addWidget(self.sp_download_browse)
        root.addLayout(sdd)

        # Cookies
        self.cookie_header = QTextEdit(self)
        self.cookie_header.setPlaceholderText("Paste full Cookie header here (e.g., FedAuth=...; rtFa=...)\n-or- paste values below")
        root.addWidget(QLabel("SharePoint Cookies (from DevTools):"))
        root.addWidget(self.cookie_header)

        self.fedauth = QLineEdit(self)
        self.rtfa = QLineEdit(self)
        cgrid = QHBoxLayout()
        left = QWidget(self); left_l = QVBoxLayout(left)
        left_l.addWidget(QLabel("FedAuth:")); left_l.addWidget(self.fedauth)
        right = QWidget(self); right_l = QVBoxLayout(right)
        right_l.addWidget(QLabel("rtFa:")); right_l.addWidget(self.rtfa)
        cgrid.addWidget(left); cgrid.addWidget(right)
        root.addLayout(cgrid)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save", self)
        self.btn_send = QPushButton("Send to Backend", self)
        self.btn_capture = QPushButton("Capture Cookies", self)
        self.btn_close = QPushButton("Close", self)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_capture)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_send.clicked.connect(self._on_send)
        self.btn_capture.clicked.connect(self._on_capture)
        self.btn_close.clicked.connect(self.accept)

    def _on_save(self):
        from ..services import secret_store\n        key_text = self.api_key.text().strip()\n        if key_text:\n            secret_store.set_secret("OPENAI_API_KEY", key_text)\n        self.cfg.api_key = None
        self.cfg.target_language = self.lang.text().strip() or "English"
        self.cfg.theme = self.theme_combo.currentData() or "light"
        # Persist backend URL
        try:
            setattr(self.cfg, "backend_url", self.backend_url.text().strip() or None)
        except Exception:
            pass
        try:
            setattr(self.cfg, "sp_base_url", self.sp_base.text().strip() or None)
        except Exception:
            pass
        try:
            setattr(self.cfg, "sp_library_root", self.sp_root.text().strip() or None)
        except Exception:
            pass
        try:
            setattr(self.cfg, "sp_download_dir", self.sp_download_dir.text().strip() or None)
        except Exception:
            pass
        save_config(self.cfg)

    def _browse_sp_download_dir(self):
        from PySide6.QtWidgets import QFileDialog
        start_dir = self.sp_download_dir.text().strip() or (self.cfg.root_path or "")
        directory = QFileDialog.getExistingDirectory(self, "Select download directory", start_dir or "")
        if directory:
            self.sp_download_dir.setText(directory)

    def _on_send(self):
        # Update backend settings and cookies
        base = self.sp_base.text().strip()
        burl = self.backend_url.text().strip() or "http://127.0.0.1:5001"
        self.backend.base_url = burl.rstrip('/')
        if base:
            self.backend.update_settings(sp_base_url=base)
        cookie_header = self.cookie_header.toPlainText().strip() or None
        cookies = None
        if not cookie_header:
            fa = self.fedauth.text().strip()
            ra = self.rtfa.text().strip()
            cookies = {}
            if fa:
                cookies["FedAuth"] = fa
            if ra:
                cookies["rtFa"] = ra
            if not cookies:
                cookies = None
        self.backend.set_sp_cookies(base_url=base, cookies=cookies, cookie_header=cookie_header)

    def _on_capture(self):
        base = self.sp_base.text().strip()
        if not base:
            QMessageBox.information(self, "SharePoint", "Enter the SharePoint Site URL before capturing cookies.")
            return
        burl = self.backend_url.text().strip() or "http://127.0.0.1:5001"
        self.backend.base_url = burl.rstrip('/')
        parsed = urlparse(base)
        if not parsed.scheme or not parsed.netloc:
            QMessageBox.warning(self, "SharePoint", "SharePoint Site URL is invalid.")
            return

        webbrowser.open(base)
        QMessageBox.information(
            self,
            "Sign In to SharePoint",
            "Your default browser has been opened. Please complete the SharePoint sign-in, then return here and click OK to capture cookies.",
        )

        cookies = collect_sharepoint_cookies(parsed.netloc)
        if not cookies:
            QMessageBox.warning(
                self,
                "Cookie Capture",
                "Could not locate SharePoint cookies. Ensure you are signed in using Edge, Chrome, or Firefox on this machine.",
            )
            return

        fed = cookies.get("FedAuth")
        rt = cookies.get("rtFa")
        if fed:
            self.fedauth.setText(fed)
        if rt:
            self.rtfa.setText(rt)

        try:
            self.backend.set_sp_cookies(base_url=base, cookies=cookies)
            QMessageBox.information(self, "Cookie Capture", "Cookies captured and sent to backend.")
        except Exception as exc:
            QMessageBox.warning(self, "Backend Error", f"Failed to send cookies: {exc}")
