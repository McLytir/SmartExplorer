from __future__ import annotations

import webbrowser
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QWidget,
    QMessageBox,
    QComboBox,
    QCheckBox,
)

from ..api.backend_client import BackendClient
from ..settings import AppConfig, save_config
from ..services.browser_cookies import collect_sharepoint_cookies, get_last_capture_hint
from .shortcut_settings_dialog import ShortcutSettingsDialog


class SettingsDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(700, 620)
        self.cfg = cfg
        self.backend = BackendClient()
        self._lt_help_shown = False
        self.setObjectName("SettingsDialog")

        root = QVBoxLayout(self)

        # Translator provider selection
        self.translator_combo = QComboBox(self)
        self.translator_combo.addItem("Auto (prefer OpenAI, then Backend)", "auto")
        self.translator_combo.addItem("OpenAI", "openai")
        self.translator_combo.addItem("Backend", "backend")
        self.translator_combo.addItem("Google Free (deep-translator)", "google_free")
        self.translator_combo.addItem("LibreTranslate", "libretranslate")
        self.translator_combo.addItem("Identity (no translation)", "identity")
        try:
            current_provider = getattr(self.cfg, "translator_provider", "auto") or "auto"
            idx = self.translator_combo.findData(current_provider)
            if idx >= 0:
                self.translator_combo.setCurrentIndex(idx)
        except Exception:
            pass
        trl = QHBoxLayout()
        trl.addWidget(QLabel("Translator:"))
        trl.addWidget(self.translator_combo)
        root.addLayout(trl)
        try:
            self.translator_combo.currentIndexChanged.connect(self._on_translator_changed)
        except Exception:
            pass

        # Backend URL (used for Backend translator and SharePoint backend)
        self.backend_url = QLineEdit(self)
        self.backend_url.setPlaceholderText("Backend URL (e.g., http://127.0.0.1:5001)")
        try:
            self.backend_url.setText(getattr(self.cfg, "backend_url", "") or "")
        except Exception:
            pass
        self._backend_url_row = QWidget(self)
        bux = QHBoxLayout(self._backend_url_row)
        bux.setContentsMargins(0, 0, 0, 0)
        bux.addWidget(QLabel("Backend URL:"))
        bux.addWidget(self.backend_url)
        root.addWidget(self._backend_url_row)

        # OpenAI key (masked; stored in system keyring)
        self.api_key = QLineEdit(self)
        self.api_key.setPlaceholderText("OpenAI API Key")
        self.api_key.setEchoMode(QLineEdit.Password)
        self._openai_key_row = QWidget(self)
        akx = QHBoxLayout(self._openai_key_row)
        akx.setContentsMargins(0, 0, 0, 0)
        akx.addWidget(QLabel("OpenAI Key:"))
        akx.addWidget(self.api_key)
        self.btn_api_clear = QPushButton("Clear", self)
        self.btn_api_clear.setToolTip("Remove saved API key from system keyring")
        self.btn_api_clear.clicked.connect(self._on_clear_api_key)
        akx.addWidget(self.btn_api_clear)
        root.addWidget(self._openai_key_row)
        self._load_saved_api_keys()

        # LibreTranslate settings
        self.lt_url = QLineEdit(self)
        self.lt_url.setPlaceholderText("LibreTranslate URL (e.g., https://libretranslate.de)")
        try:
            self.lt_url.setText(getattr(self.cfg, "libretranslate_url", "") or "")
        except Exception:
            pass
        self._lt_url_row = QWidget(self)
        ltu = QHBoxLayout(self._lt_url_row)
        ltu.setContentsMargins(0, 0, 0, 0)
        ltu.addWidget(QLabel("LibreTranslate URL:"))
        ltu.addWidget(self.lt_url)
        root.addWidget(self._lt_url_row)

        self.lt_api_key = QLineEdit(self)
        self.lt_api_key.setPlaceholderText("LibreTranslate API Key (optional)")
        self.lt_api_key.setEchoMode(QLineEdit.Password)
        self._lt_key_row = QWidget(self)
        ltk = QHBoxLayout(self._lt_key_row)
        ltk.setContentsMargins(0, 0, 0, 0)
        ltk.addWidget(QLabel("LT API Key:"))
        ltk.addWidget(self.lt_api_key)
        self.btn_lt_clear = QPushButton("Clear", self)
        self.btn_lt_clear.setToolTip("Remove saved LibreTranslate API key from system keyring")
        self.btn_lt_clear.clicked.connect(self._on_clear_lt_key)
        ltk.addWidget(self.btn_lt_clear)
        root.addWidget(self._lt_key_row)
        self._load_saved_lt_key()

        # Target language
        self.lang = QLineEdit(self)
        self.lang.setText(self.cfg.target_language)
        lgx = QHBoxLayout()
        lgx.addWidget(QLabel("Target Language:"))
        lgx.addWidget(self.lang)
        root.addLayout(lgx)

        self.translation_enabled = QCheckBox("Enable translated names by default", self)
        self.translation_enabled.setChecked(bool(getattr(self.cfg, "translation_enabled", False)))
        root.addWidget(self.translation_enabled)

        self.translation_view = QComboBox(self)
        self.translation_view.addItem("Below file names", "below_name")
        view_index = self.translation_view.findData(getattr(self.cfg, "translation_view_mode", "below_name") or "below_name")
        if view_index >= 0:
            self.translation_view.setCurrentIndex(view_index)
        tvx = QHBoxLayout()
        tvx.addWidget(QLabel("Default Translation View:"))
        tvx.addWidget(self.translation_view)
        root.addLayout(tvx)

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
        self.sp_download_browse = QPushButton("Browse...", self)
        self.sp_download_browse.clicked.connect(self._browse_sp_download_dir)
        sdd.addWidget(self.sp_download_browse)
        root.addLayout(sdd)

        # Keep bulk downloads as zip (security option)
        self.sp_keep_zip = QCheckBox('Keep bulk downloads as zip (do not auto-extract)', self)
        try:
            self.sp_keep_zip.setChecked(bool(getattr(self.cfg, 'sp_keep_zip_downloads', False)))
        except Exception:
            self.sp_keep_zip.setChecked(False)
        root.addWidget(self.sp_keep_zip)

        # Preview cache directory (optional). If empty, uses OS default location.
        self.preview_cache_dir = QLineEdit(self)
        try:
            self.preview_cache_dir.setText(getattr(self.cfg, "preview_cache_dir", "") or "")
        except Exception:
            pass
        pcd = QHBoxLayout()
        pcd.addWidget(QLabel("Preview Cache Dir:"))
        pcd.addWidget(self.preview_cache_dir, 1)
        self.preview_cache_browse = QPushButton("Browse...", self)
        self.preview_cache_browse.clicked.connect(self._browse_preview_cache_dir)
        pcd.addWidget(self.preview_cache_browse)
        root.addLayout(pcd)

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

        # Shortcuts
        shortcuts_row = QHBoxLayout()
        shortcuts_row.addWidget(QLabel("Keyboard Shortcuts:", self))
        self.btn_shortcuts = QPushButton("Configure...", self)
        self.btn_shortcuts.clicked.connect(self._open_shortcuts)
        shortcuts_row.addWidget(self.btn_shortcuts)
        shortcuts_row.addStretch(1)
        root.addLayout(shortcuts_row)

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
        # Initialize visibility for provider-specific fields
        try:
            self._update_provider_visibility()
        except Exception:
            pass
        self._apply_api_key_mask()
        self._apply_visual_style()

    def _apply_visual_style(self) -> None:
        self.setStyleSheet(
            """
QDialog#SettingsDialog {
    background-color: palette(Window);
}
QLineEdit, QTextEdit, QComboBox {
    min-height: 28px;
    border-radius: 6px;
    padding: 4px 8px;
}
QPushButton {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
}
QLabel {
    font-size: 12px;
}
"""
        )

    def _open_shortcuts(self) -> None:
        try:
            dlg = ShortcutSettingsDialog(self.cfg.shortcuts or {}, self)
            if dlg.exec() == QDialog.Accepted:
                updated = dlg.result_shortcuts()
                self.cfg.shortcuts = updated
                save_config(self.cfg)
                QMessageBox.information(self, "Shortcuts", "Shortcuts saved. Restart may be required for all changes to take effect.")
        except Exception:
            QMessageBox.warning(self, "Shortcuts", "Unable to open shortcut editor.")

    def _on_save(self):
        try:
            from ..services import secret_store as secret_store_module
        except Exception:
            secret_store_module = None

        secret_store = secret_store_module

        key_text = self.api_key.text().strip()
        if secret_store:
            if key_text:
                secret_store.set_secret("OPENAI_API_KEY", key_text)
            else:
                secret_store.delete_secret("OPENAI_API_KEY")
        else:
            self.cfg.api_key = key_text or None

        lt_key = self.lt_api_key.text().strip()
        if secret_store:
            if lt_key:
                secret_store.set_secret("LIBRETRANSLATE_API_KEY", lt_key)
            else:
                secret_store.delete_secret("LIBRETRANSLATE_API_KEY")
        self.cfg.target_language = self.lang.text().strip() or "English"
        self.cfg.translation_enabled = bool(self.translation_enabled.isChecked())
        self.cfg.translation_view_mode = self.translation_view.currentData() or "below_name"
        # Persist translator provider
        try:
            setattr(self.cfg, "translator_provider", self.translator_combo.currentData())
        except Exception:
            pass
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
        try:
            setattr(self.cfg, "libretranslate_url", self.lt_url.text().strip() or None)
        except Exception:
            pass
        try:
            self.cfg.sp_keep_zip_downloads = bool(self.sp_keep_zip.isChecked())
        except Exception:
            self.cfg.sp_keep_zip_downloads = False
        save_config(self.cfg)

    def _browse_sp_download_dir(self):
        from PySide6.QtWidgets import QFileDialog
        start_dir = self.sp_download_dir.text().strip() or (self.cfg.root_path or "")
        directory = QFileDialog.getExistingDirectory(self, "Select download directory", start_dir or "")
        if directory:
            self.sp_download_dir.setText(directory)

    def _browse_preview_cache_dir(self):
        from PySide6.QtWidgets import QFileDialog
        start_dir = self.preview_cache_dir.text().strip() or (self.cfg.preview_cache_dir or "")
        directory = QFileDialog.getExistingDirectory(self, "Select preview cache directory", start_dir or "")
        if directory:
            self.preview_cache_dir.setText(directory)

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
            "Your default browser has been opened. Please complete the SharePoint sign-in in a normal (non-private) window, then return here and click OK to capture cookies.",
        )

        cookies = collect_sharepoint_cookies(parsed.netloc)
        if not cookies:
            hint = get_last_capture_hint()
            msg = (
                "Could not locate SharePoint cookies. Ensure you are signed in using Edge, Opera, Chrome, or Firefox on this machine. "
                "Note: Incognito/Private windows do not persist cookies and cannot be captured."
            )
            if hint:
                msg = f"{msg}\n\n{hint}\n\nFallback: copy the full Cookie request header from Opera DevTools and paste it into the Cookie header box."
            QMessageBox.warning(
                self,
                "Cookie Capture",
                msg,
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

    def _on_clear_api_key(self):
        self.api_key.clear()
        self.cfg.api_key = None
        try:
            from ..services import secret_store
            secret_store.delete_secret("OPENAI_API_KEY")
        except Exception:
            pass

    def _on_clear_lt_key(self):
        try:
            from ..services import secret_store
            secret_store.delete_secret("LIBRETRANSLATE_API_KEY")
        except Exception:
            pass

    def _on_translator_changed(self, index: int) -> None:
        try:
            data = self.translator_combo.itemData(index)
        except Exception:
            data = None
        # Toggle visibility of provider-specific fields
        try:
            self._update_provider_visibility()
        except Exception:
            pass
        # Show provider-specific hints/masking
        try:
            self._apply_api_key_mask(data)
        except Exception:
            pass

    def _load_saved_api_keys(self) -> None:
        key_value = None
        try:
            from ..services import secret_store as secret_store_module
        except Exception:
            secret_store_module = None
        secret_store = secret_store_module
        if secret_store:
            try:
                key_value = secret_store.get_secret("OPENAI_API_KEY") or None
            except Exception:
                key_value = None
        if not key_value:
            key_value = getattr(self.cfg, "api_key", None)
        if key_value:
            self.api_key.setText(key_value)

    def _load_saved_lt_key(self) -> None:
        lt_value = None
        try:
            from ..services import secret_store as secret_store_module
        except Exception:
            secret_store_module = None
        secret_store = secret_store_module
        if secret_store:
            try:
                lt_value = secret_store.get_secret("LIBRETRANSLATE_API_KEY") or None
            except Exception:
                lt_value = None
        if lt_value:
            self.lt_api_key.setText(lt_value)

    def _apply_api_key_mask(self, provider: str | None = None) -> None:
        try:
            self.api_key.setEchoMode(QLineEdit.Password)
            self.lt_api_key.setEchoMode(QLineEdit.Password)
        except Exception:
            pass
        if provider is None:
            try:
                provider = self.translator_combo.currentData()
            except Exception:
                provider = None
        if provider == "libretranslate" and not self._lt_help_shown:
            self._lt_help_shown = True
            text = (
                "LibreTranslate setup options:\n\n"
                "- Public instance: set URL to https://libretranslate.de or https://libretranslate.com.\n"
                "  Some instances require an API key — check their site.\n\n"
                "- Self-host (recommended):\n"
                "  Docker: docker run -ti --rm -p 5000:5000 libretranslate/libretranslate\n"
                "  Then set URL to http://localhost:5000 in Settings.\n\n"
                "Docs: https://libretranslate.com/docs/"
            )
            msg = QMessageBox(self)
            msg.setWindowTitle("LibreTranslate Setup")
            msg.setText(text)
            open_btn = msg.addButton("Open Docs", QMessageBox.ActionRole)
            ok_btn = msg.addButton(QMessageBox.Ok)
            msg.exec()
            try:
                if msg.clickedButton() is open_btn:
                    import webbrowser as _wb
                    _wb.open("https://libretranslate.com/docs/")
            except Exception:
                pass

    def _update_provider_visibility(self) -> None:
        provider = None
        try:
            provider = self.translator_combo.currentData()
        except Exception:
            provider = None
        visible = provider == "libretranslate"
        if hasattr(self, "_lt_url_row") and self._lt_url_row is not None:
            self._lt_url_row.setVisible(bool(visible))
        if hasattr(self, "_lt_key_row") and self._lt_key_row is not None:
            self._lt_key_row.setVisible(bool(visible))
        # Keep OpenAI key editable regardless of translator choice (summaries/tagging rely on it).
        if hasattr(self, "_openai_key_row") and self._openai_key_row is not None:
            self._openai_key_row.setVisible(True)
        # Backend URL row only when Backend selected
        if hasattr(self, "_backend_url_row") and self._backend_url_row is not None:
            self._backend_url_row.setVisible(provider == "backend")
