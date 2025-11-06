from __future__ import annotations

import os
import typing

import traceback
from concurrent.futures import Future, ThreadPoolExecutor

from PySide6.QtCore import Qt, QUrl, Signal, QPoint, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QProgressBar,
    QSlider,
    QComboBox,
    QScrollArea,
    QStackedLayout,
)
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

_OVERLAY_EXECUTOR = ThreadPoolExecutor(max_workers=1)


class PreviewPane(QWidget):
    """A lightweight preview pane.

    - Disabled by default (created by MainWindow when toggled).
    - For local PDFs: uses QWebEngineView (if available) to load the file (fast, uses chromium PDF viewer).
    - For images: shows a scaled QPixmap.
    - Emits open_requested(path) when user clicks Open Full.
    """

    open_requested = Signal(str)
    cancel_requested = Signal()
    overlay_language_changed = Signal(str)

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
        # Overlay controls (hidden by default)
        self._overlay_btn = QPushButton("Overlay", self)
        self._overlay_btn.setCheckable(True)
        self._overlay_btn.setVisible(False)
        self._overlay_btn.clicked.connect(self._on_toggle_overlay)
        ctrl_row.addWidget(self._overlay_btn)
        self._opacity_slider = QSlider(Qt.Horizontal, self)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(60)
        self._opacity_slider.setVisible(False)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        ctrl_row.addWidget(self._opacity_slider)
        self._language_combo = QComboBox(self)
        self._language_combo.setEditable(True)
        self._language_combo.setVisible(False)
        try:
            self._language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        except Exception:
            pass
        self._language_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for lang in [
            "English",
            "Japanese",
            "Spanish",
            "French",
            "German",
            "Korean",
            "Chinese (Simplified)",
            "Chinese (Traditional)",
            "Portuguese",
            "Italian",
        ]:
            self._language_combo.addItem(lang)
        self._language_combo.currentTextChanged.connect(self._on_overlay_language_changed)
        ctrl_row.addWidget(self._language_combo)
        self._layout.addLayout(ctrl_row)

        # wire cancel button to the signal
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        self._current_path: str | None = None
        self._current_widget: QWidget | None = None
        self._overlay_opacity = 0.6
        self._translator = None
        self._overlay_language = "English"
        try:
            self._language_combo.setCurrentText(self._overlay_language)
        except Exception:
            pass
        self._current_pdf_overlay = None
        self._current_kind = "other"
        self._pdf_overlay_raw_text: str | None = None
        self._current_overlay_translations: list[str] | None = None
        self._overlay_window: PdfOverlayWindow | None = None
        self._overlay_fallback_text: str | None = None
        self._overlay_prepared: bool = False
        self._overlay_future: Future | None = None
        self._overlay_future_path: str | None = None

    def _clear_content_widgets(self) -> None:
        # Remove content widgets from layout, we'll add the desired one
        for w in (self._web, self._image, self._fallback):
            try:
                self._layout.removeWidget(w)  # safe even if not present
            except Exception:
                pass
            if w is not None:
                w.setParent(None)
        self._current_widget = None

    def preview_paths(self, paths: list[str]) -> None:
        """Preview the first path from the list (if any)."""
        if not paths:
            self._show_fallback("No selection")
            return
        path = paths[0]
        self._current_path = path
        self._current_kind = "other"
        self._close_overlay_window()
        self._overlay_prepared = False
        self._cancel_overlay_future()
        self._current_pdf_overlay = None
        self._language_combo.setVisible(False)
        if not path:
            self._show_fallback("No selection")
            return
        # Local file handling only
        if os.path.exists(path) and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in {".pdf"} and WEBENGINE_AVAILABLE and self._web is not None:
                self._current_kind = "pdf"
                self._show_web(path, is_pdf=True)
                return
            if ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif"}:
                self._current_kind = "image"
                self._show_image(path)
                return
            # Unknown file types: try to load in web view if available (some types like html)
            if WEBENGINE_AVAILABLE and self._web is not None:
                self._current_kind = "web"
                self._show_web(path)
                return
            # Fallback: show basic info
            self._show_fallback(f"No preview for {ext} files")
            return
        else:
            self._current_kind = "other"
            self._show_fallback("File not available locally")

    def _show_web(self, path: str, *, is_pdf: bool = False) -> None:
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
        self._current_widget = self._web
        # Let chromium's built-in PDF viewer handle the PDF quickly
        self._web.load(file_url)
        self._open_btn.setEnabled(True)
        self._title.setText(f"Preview â€” {os.path.basename(path)}")
        # No progress for web view (handled by internal renderer), hide controls
        try:
            self._progress.setVisible(False)
            self._cancel_btn.setVisible(False)
        except Exception:
            pass
        if is_pdf:
            self._enable_overlay_controls(True, show_language=True)
            self._overlay_prepared = False
        else:
            self._enable_overlay_controls(False)

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
        self._current_widget = self._image
        try:
            self._open_btn.setEnabled(True)
            self._title.setText(f"Preview â€” {os.path.basename(path)}")
        except Exception:
            pass
        self._enable_overlay_controls(True)

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
        self._enable_overlay_controls(False)

    def _on_open(self) -> None:
        if self._current_path:
            self.open_requested.emit(self._current_path)

    # --- overlay helpers ---
    def set_translator(self, translator) -> None:
        self._translator = translator

    def _enable_overlay_controls(self, enable: bool, *, show_language: bool = False) -> None:
        enabled = bool(enable)
        self._overlay_btn.setVisible(enabled)
        self._overlay_btn.setEnabled(enabled)
        self._opacity_slider.setVisible(enabled)
        if not enabled:
            try:
                self._overlay_btn.setChecked(False)
            except Exception:
                pass
            self._pdf_overlay_raw_text = None
            if self._current_widget:
                self._current_widget.setVisible(True)
            self._close_overlay_window()
            self._overlay_prepared = False
            self._cancel_overlay_future()
        self._language_combo.setVisible(enabled and bool(show_language))

    def _on_toggle_overlay(self, checked: bool) -> None:
        if self._current_kind != "pdf":
            return
        if checked:
            self._open_overlay_window()
        else:
            self._close_overlay_window()

    def _on_opacity_changed(self, value: int) -> None:
        try:
            self._overlay_opacity = max(0.1, min(1.0, float(value) / 100.0))
            if self._overlay_window:
                self._overlay_window.set_opacity(self._overlay_opacity)
        except Exception:
            pass

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._position_overlay()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        try:
            if event.key() == Qt.Key_Escape and self._overlay_btn.isChecked():
                self._overlay_btn.setChecked(False)
                self._on_toggle_overlay(False)
                event.accept()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    def _position_overlay(self) -> None:
        pass

    def _apply_overlay_result(self, overlay, fallback_text: str) -> None:
        self._current_pdf_overlay = overlay
        self._pdf_overlay_raw_text = None
        self._current_overlay_translations = None
        self._overlay_fallback_text = None
        self._overlay_prepared = True

        if overlay and getattr(overlay, "boxes", None):
            self._overlay_btn.setEnabled(True)
            self._language_combo.setVisible(True)
            self._apply_pdf_overlay_translations()
            return

        # Fallback to translated paragraph
        fallback_text = (fallback_text or "").strip()
        if not fallback_text:
            self._overlay_btn.setEnabled(False)
            self._language_combo.setVisible(False)
            self._overlay_fallback_text = ""
            self._update_overlay_window_content()
            return

        self._overlay_btn.setEnabled(True)
        self._language_combo.setVisible(True)
        self._pdf_overlay_raw_text = fallback_text
        self._apply_pdf_overlay_fallback_translation()

    def _apply_pdf_overlay_fallback_translation(self) -> None:
        raw = (self._pdf_overlay_raw_text or "").strip()
        if not raw:
            self._overlay_fallback_text = ""
            self._update_overlay_window_content()
            return
        translations = self._translate_texts([raw])
        translated = translations[0] if translations else raw
        self._overlay_fallback_text = translated.strip()
        self._current_overlay_translations = None
        self._update_overlay_window_content()


    def _apply_pdf_overlay_translations(self) -> None:
        overlay = self._current_pdf_overlay
        if not overlay or not overlay.boxes:
            self._current_overlay_translations = None
            self._overlay_fallback_text = None
            self._update_overlay_window_content()
            return
        self._pdf_overlay_raw_text = None

        texts = [box.text for box in overlay.boxes]
        translations = list(texts)

        translations = self._translate_texts(texts)

        if len(translations) < len(texts):
            translations = list(translations) + [""] * (len(texts) - len(translations))
        elif len(translations) > len(texts):
            translations = list(translations[: len(texts)])

        final_texts = []
        for src, dst in zip(texts, translations):
            stripped = (dst or "").strip()
            final_texts.append(stripped if stripped else src)

        self._current_overlay_translations = final_texts
        self._overlay_fallback_text = None
        self._update_overlay_window_content()

    def _on_overlay_language_changed(self, text: str) -> None:
        language = (text or "").strip()
        if not language:
            language = self._overlay_language
        if language == self._overlay_language:
            return
        self._overlay_language = language
        try:
            self.overlay_language_changed.emit(language)
        except Exception:
            pass
        if self._current_kind == "pdf":
            if self._current_pdf_overlay and self._current_pdf_overlay.boxes:
                self._apply_pdf_overlay_translations()
            elif self._pdf_overlay_raw_text:
                self._apply_pdf_overlay_fallback_translation()

    def _translate_texts(self, texts: list[str]) -> list[str]:
        if not texts:
            return []

        language = self._overlay_language or "English"
        results: list[str] = []

        translator = getattr(self, "_translator", None)
        if translator is not None and hasattr(translator, "translate_texts"):
            try:
                raw = translator.translate_texts(texts, language)
                if isinstance(raw, list) and len(raw) == len(texts):
                    results = [
                        item.strip() if isinstance(item, str) and item.strip() else original
                        for item, original in zip(raw, texts)
                    ]
            except Exception:
                results = []

        if not results or all(a == b for a, b in zip(results, texts)):
            try:
                from ..services.text_translate import translate_texts as _fallback_translate

                raw_results = _fallback_translate(texts, language, source_language="auto")
                if isinstance(raw_results, list) and len(raw_results) == len(texts):
                    results = [
                        item.strip() if isinstance(item, str) and item.strip() else original
                        for item, original in zip(raw_results, texts)
                    ]
            except Exception:
                pass

        if not results:
            results = list(texts)
        return results

    def _ensure_overlay_window(self) -> "PdfOverlayWindow":
        if self._overlay_window is None:
            self._overlay_window = PdfOverlayWindow(self)
            self._overlay_window.closed.connect(self._on_overlay_window_closed)
        return self._overlay_window

    def _open_overlay_window(self) -> None:
        if self._current_kind != "pdf":
            return
        if not self._overlay_prepared:
            path = self._current_path
            if path and os.path.isfile(path):
                self._start_overlay_preparation(path)
            else:
                self._overlay_prepared = True
        win = self._ensure_overlay_window()
        win.set_opacity(self._overlay_opacity)
        self._update_overlay_window_content()
        win.show()
        win.raise_()
        try:
            win.activateWindow()
        except Exception:
            pass
        if not self._overlay_prepared and not self._overlay_future:
            win.show_message("Preparing overlay…")

    def _close_overlay_window(self) -> None:
        if not self._overlay_window:
            self._cancel_overlay_future()
            return
        win = self._overlay_window
        self._overlay_window = None
        try:
            win.closed.disconnect(self._on_overlay_window_closed)
        except Exception:
            pass
        win.close()
        self._cancel_overlay_future()

    def _cancel_overlay_future(self) -> None:
        fut = self._overlay_future
        if fut and not fut.done():
            fut.cancel()
        self._overlay_future = None
        self._overlay_future_path = None

    def _on_overlay_window_closed(self) -> None:
        self._overlay_window = None
        blocker = self._overlay_btn.blockSignals(True)
        try:
            self._overlay_btn.setChecked(False)
        finally:
            self._overlay_btn.blockSignals(blocker)

    def _update_overlay_window_content(self) -> None:
        win = self._overlay_window
        if not win:
            return
        if self._current_pdf_overlay and self._current_overlay_translations:
            win.show_overlay(self._current_pdf_overlay, self._current_overlay_translations, self._overlay_opacity)
            return
        if self._current_pdf_overlay and self._current_pdf_overlay.boxes:
            texts = [box.text for box in self._current_pdf_overlay.boxes]
            win.show_overlay(self._current_pdf_overlay, texts, self._overlay_opacity)
            return
        if self._overlay_fallback_text:
            win.show_fallback(self._overlay_fallback_text)
            return
        if self._pdf_overlay_raw_text:
            win.show_fallback(self._pdf_overlay_raw_text)
            return
        win.show_message("No overlay content available.")

    def _start_overlay_preparation(self, path: str) -> None:
        self._cancel_overlay_future()
        self._overlay_prepared = False
        self._overlay_btn.setEnabled(False)
        win = self._overlay_window
        if win:
            win.show_message("Preparing overlay…")
        self._overlay_future_path = path

        def _done(fut: Future) -> None:
            QTimer.singleShot(0, lambda: self._on_overlay_future_done(path, fut))

        future = _OVERLAY_EXECUTOR.submit(self._generate_overlay_data, path)
        self._overlay_future = future
        future.add_done_callback(_done)

    def _on_overlay_future_done(self, path: str, future: Future) -> None:
        if future.cancelled():
            if self._overlay_future is future:
                self._overlay_future = None
            return
        try:
            overlay, fallback_text, error = future.result()
        except Exception:
            overlay, fallback_text, error = None, "", traceback.format_exc()

        if self._overlay_future is future:
            self._overlay_future = None
            self._overlay_future_path = None

        if path != self._current_path:
            # Stale result; ignore
            return

        if error:
            print("Overlay preparation error:", error)

        self._apply_overlay_result(overlay, fallback_text)
        self._update_overlay_window_content()

    @staticmethod
    def _generate_overlay_data(path: str):
        from ..services import pdf_overlay as _pdfov

        overlay = None
        fallback_text = ""
        error = None
        try:
            overlay = _pdfov.first_page_overlay(path)
        except Exception:
            overlay = None
            error = traceback.format_exc()

        if not overlay or not getattr(overlay, "boxes", None):
            try:
                fallback_text = (_pdfov.first_page_text(path) or "").strip()
            except Exception:
                fallback_text = ""
            if overlay and not getattr(overlay, "boxes", None):
                overlay = None
        return overlay, fallback_text, error

    def set_overlay_language(self, language: str) -> None:
        new_lang = (language or self._overlay_language).strip() or "English"
        if new_lang == self._overlay_language:
            return
        self._overlay_language = new_lang
        block = self._language_combo.blockSignals(True)
        try:
            idx = self._language_combo.findText(new_lang, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self._language_combo.setCurrentIndex(idx)
            else:
                self._language_combo.setEditText(new_lang)
        finally:
            self._language_combo.blockSignals(block)
        if self._current_kind == "pdf":
            if self._current_pdf_overlay and self._current_pdf_overlay.boxes:
                self._apply_pdf_overlay_translations()
            elif self._pdf_overlay_raw_text:
                self._apply_pdf_overlay_fallback_translation()

class PdfOverlayWindow(QWidget):
    closed = Signal()

    def __init__(self, parent: typing.Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("PDF Overlay")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(960, 720)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._stack = QStackedLayout()
        root_layout.addLayout(self._stack, 1)

        self._overlay_widget = PdfOverlayWidget(self)
        self._stack.addWidget(self._overlay_widget)

        self._fallback_area = QScrollArea(self)
        self._fallback_area.setWidgetResizable(True)
        self._fallback_label = QLabel(self)
        self._fallback_label.setWordWrap(True)
        self._fallback_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._fallback_label.setMargin(12)
        self._fallback_label.setStyleSheet("background-color: rgba(0,0,0,0.85); color: #00ff99; font-weight: 600;")
        self._fallback_area.setWidget(self._fallback_label)
        self._stack.addWidget(self._fallback_area)

        self._message_label = QLabel("Preparing overlay…", self)
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setMargin(12)
        self._stack.addWidget(self._message_label)

        self._stack.setCurrentWidget(self._message_label)

    def show_overlay(self, overlay, texts: list[str], opacity: float) -> None:
        self._overlay_widget.set_overlay(overlay, texts, opacity=opacity)
        self._stack.setCurrentWidget(self._overlay_widget)

    def show_fallback(self, text: str) -> None:
        self._overlay_widget.clear()
        self._fallback_label.setText(text or "")
        self._stack.setCurrentWidget(self._fallback_area)

    def show_message(self, text: str) -> None:
        self._overlay_widget.clear()
        self._message_label.setText(text)
        self._stack.setCurrentWidget(self._message_label)

    def set_opacity(self, opacity: float) -> None:
        self._overlay_widget.set_opacity(opacity)

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.closed.emit()
        except Exception:
            pass
        super().closeEvent(event)


class PdfOverlayWidget(QWidget):
    def __init__(self, parent: typing.Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setScaledContents(False)
        self._overlay_layer = QWidget(self)
        self._overlay_layer.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._overlay_layer.setAttribute(Qt.WA_NoSystemBackground, True)
        self._overlay_layer.setStyleSheet("background: transparent;")

        self._pixmap: typing.Optional[QPixmap] = None
        self._boxes: list[typing.Any] = []
        self._labels: list[QLabel] = []
        self._overlay_entries: list[tuple[QLabel, typing.Any]] = []
        self._opacity: float = 0.6

    def clear(self) -> None:
        for label in self._labels:
            label.deleteLater()
        self._labels = []
        self._overlay_entries = []
        self._boxes = []
        self._pixmap = None
        self._image_label.clear()
        self._overlay_layer.hide()
        self._image_label.hide()

    def has_overlay(self) -> bool:
        return bool(self._pixmap and self._overlay_entries)

    def set_overlay(self, overlay, texts: list[str], *, opacity: float | None = None) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(getattr(overlay, "image_png", b"")):
            self.clear()
            return
        if opacity is not None:
            self._opacity = max(0.05, min(1.0, float(opacity)))

        self._pixmap = pixmap
        self._boxes = list(getattr(overlay, "boxes", []))

        for label in self._labels:
            label.deleteLater()
        self._labels = []

        style = self._style_for_opacity(self._opacity)
        self._overlay_entries = []

        for box, text in zip(self._boxes, texts):
            lbl = QLabel(self._overlay_layer)
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            lbl.setMargin(2)
            lbl.setStyleSheet(style)
            lbl.setText(text)
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lbl.show()
            self._labels.append(lbl)
            self._overlay_entries.append((lbl, box))

        self._image_label.setPixmap(pixmap)
        self._image_label.show()
        self._overlay_layer.show()
        self._update_layout()

    def set_opacity(self, opacity: float) -> None:
        self._opacity = max(0.05, min(1.0, float(opacity)))
        style = self._style_for_opacity(self._opacity)
        for label in self._labels:
            label.setStyleSheet(style)

    def resizeEvent(self, event) -> None:  # noqa: D401
        super().resizeEvent(event)
        self._update_layout()

    def _update_layout(self) -> None:
        if not self._pixmap:
            return
        available_width = max(1, self.width())
        available_height = max(1, self.height())
        scaled = self._pixmap.scaled(available_width, available_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        offset_x = (available_width - scaled.width()) // 2
        offset_y = (available_height - scaled.height()) // 2
        self._image_label.setPixmap(scaled)
        self._image_label.setGeometry(offset_x, offset_y, scaled.width(), scaled.height())
        self._overlay_layer.setGeometry(offset_x, offset_y, scaled.width(), scaled.height())
        self._overlay_layer.raise_()

        if self._pixmap.width() <= 0 or self._pixmap.height() <= 0:
            return
        ratio_x = scaled.width() / self._pixmap.width()
        ratio_y = scaled.height() / self._pixmap.height()

        for label, box in self._overlay_entries:
            try:
                x = int(getattr(box, "x", 0.0) * ratio_x)
                y = int(getattr(box, "y", 0.0) * ratio_y)
                width = max(4, int(getattr(box, "width", 0.0) * ratio_x))
                height = max(4, int(getattr(box, "height", 0.0) * ratio_y))
                label.setGeometry(x, y, width, height)
            except Exception:
                label.hide()

    @staticmethod
    def _style_for_opacity(opacity: float) -> str:
        alpha = max(0.05, min(1.0, float(opacity)))
        return f"background-color: rgba(0,0,0,{alpha:.2f}); color: #00ff99; font-weight: 600; padding: 4px;"
