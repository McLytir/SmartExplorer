from __future__ import annotations

import os
import typing

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QProgressBar
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from ..services.preview_cache import get_cached_thumbnail, save_thumbnail_for

try:
    # Qt WebEngine is optional; gracefully degrade if unavailable
    from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    try:
        from PySide6.QtWebEngineCore import QWebEngineSettings  # type: ignore
    except Exception:
        QWebEngineSettings = None  # type: ignore
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None  # type: ignore
    QWebEngineSettings = None  # type: ignore
    WEBENGINE_AVAILABLE = False


class PreviewPane(QWidget):
    """A lightweight preview pane.

    - Disabled by default (created by MainWindow when toggled).
    - For local PDFs: uses QWebEngineView (if available) to load the file (fast, uses chromium PDF viewer).
    - For images: shows a scaled QPixmap.
    - Emits open_requested(path) when user clicks Open Full.
    """

    open_requested = Signal(str)
    cancel_requested = Signal()

    def __init__(self, parent: typing.Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewPane")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        self._title = QLabel("Preview")
        self._title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._layout.addWidget(self._title)

        # Content area: either web view or image label or a fallback label
        if WEBENGINE_AVAILABLE:
            self._web = QWebEngineView(self)
        else:
            self._web = None
        self._image = QLabel(self)
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setScaledContents(False)
        self._fallback = QLabel("No preview available")
        self._fallback.setAlignment(Qt.AlignCenter)

        # Start with fallback
        self._layout.addWidget(self._fallback, 1)
        # Controls: progress bar, cancel, open
        ctrl_row = QHBoxLayout()
        self._progress = QProgressBar(self)
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setVisible(False)
        ctrl_row.addWidget(self._progress, 1)
        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.setVisible(False)
        ctrl_row.addWidget(self._cancel_btn)
        ctrl_row.addStretch(1)
        self._open_btn = QPushButton("Open full", self)
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        ctrl_row.addWidget(self._open_btn)
        self._layout.addLayout(ctrl_row)

        # wire cancel button to the signal
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        self._current_path: str | None = None

    def _clear_content_widgets(self) -> None:
        # Remove content widgets from layout, we'll add the desired one
        for w in (self._web, self._image, self._fallback):
            try:
                self._layout.removeWidget(w)  # safe even if not present
            except Exception:
                pass
            if w is not None:
                w.setParent(None)

    def preview_paths(self, paths: list[str]) -> None:
        """Preview the first path from the list (if any)."""
        if not paths:
            self._show_fallback("No selection")
            return
        path = paths[0]
        self._current_path = path
        if not path:
            self._show_fallback("No selection")
            return
        # Local file handling only
        if os.path.exists(path) and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in {".pdf"} and WEBENGINE_AVAILABLE and self._web is not None:
                self._show_web(path)
                return
            if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
                self._show_image(path)
                return
            # Unknown file types: try to load in web view if available (some types like html)
            if WEBENGINE_AVAILABLE and self._web is not None:
                self._show_web(path)
                return
            # Fallback: show basic info
            self._show_fallback(f"No preview for {ext} files")
            return
        else:
            self._show_fallback("File not available locally")

    def _show_web(self, path: str) -> None:
        self._clear_content_widgets()
        if not WEBENGINE_AVAILABLE or self._web is None:
            self._show_fallback("Web preview not available (missing Qt WebEngine)")
            return
        file_url = QUrl.fromLocalFile(os.path.abspath(path))
        self._web = QWebEngineView(self)
        # Ensure built-in PDF viewer is enabled (Qt defaults vary by platform)
        if QWebEngineSettings is not None:
            try:
                settings = self._web.settings()
                settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
                try:
                    settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                default_settings = QWebEngineSettings.defaultSettings()
                default_settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
                try:
                    default_settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
                except Exception:
                    pass
            except Exception:
                pass
        self._layout.insertWidget(1, self._web, 1)
        # Let chromium's built-in PDF viewer handle the PDF quickly
        self._web.load(file_url)
        self._open_btn.setEnabled(True)
        self._title.setText(f"Preview — {os.path.basename(path)}")
        # No progress for web view (handled by internal renderer), hide controls
        try:
            self._progress.setVisible(False)
            self._cancel_btn.setVisible(False)
        except Exception:
            pass

    def _show_image(self, path: str) -> None:
        self._clear_content_widgets()
        # Use cached thumbnail if available
        thumb = get_cached_thumbnail(path)
        if thumb and os.path.exists(thumb):
            pix = QPixmap(thumb)
        else:
            pix = QPixmap(path)
        if pix.isNull():
            self._show_fallback("Unable to render image")
            return
        self._image = QLabel(self)
        self._image.setAlignment(Qt.AlignCenter)
        # scale down if very large
        maxw = 900
        if pix.width() > maxw:
            pix = pix.scaledToWidth(maxw, Qt.SmoothTransformation)
        self._image.setPixmap(pix)
        self._layout.insertWidget(1, self._image, 1)
        try:
            self._open_btn.setEnabled(True)
            self._title.setText(f"Preview — {os.path.basename(path)}")
        except Exception:
            pass

        # Save a thumbnail for faster subsequent loads (only if none existed)
        try:
            if not thumb:
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                # Save as JPEG to in-memory buffer
                pix.save(buf, "JPEG", quality=80)
                data = bytes(ba)
                save_thumbnail_for(path, data)
        except Exception:
            pass

    def show_progress(self, percent: int) -> None:
        try:
            self._progress.setVisible(True)
            self._progress.setValue(int(percent))
            self._cancel_btn.setVisible(True)
        except Exception:
            pass

    def hide_progress(self) -> None:
        try:
            self._progress.setVisible(False)
            self._cancel_btn.setVisible(False)
        except Exception:
            pass

    def _show_fallback(self, text: str) -> None:
        self._clear_content_widgets()
        self._fallback = QLabel(text, self)
        self._fallback.setAlignment(Qt.AlignCenter)
        self._layout.insertWidget(1, self._fallback, 1)
        self._open_btn.setEnabled(False)
        self._title.setText("Preview")

    def _on_open(self) -> None:
        if self._current_path:
            self.open_requested.emit(self._current_path)
