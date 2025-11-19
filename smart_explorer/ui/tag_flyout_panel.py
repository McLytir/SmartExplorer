from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, QSize, Signal, QRect, QPoint
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)


class FlowLayout(QLayout):
    """Flow layout that wraps widgets automatically."""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6) -> None:
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._hspace = spacing
        self._vspace = spacing
        self._items: list = []

    def addItem(self, item) -> None:  # type: ignore[override]
        self._items.append(item)

    def addWidget(self, widget: QWidget) -> None:  # type: ignore[override]
        self.addItem(QWidgetItem(widget))

    def count(self) -> int:  # type: ignore[override]
        return len(self._items)

    def itemAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # type: ignore[override]
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # type: ignore[override]
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # type: ignore[override]
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def clear(self) -> None:
        while self._items:
            item = self.takeAt(0)
            if not item:
                continue
            widget = item.widget()
            if widget:
                widget.setParent(None)

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        margins = self.contentsMargins()
        effective_rect = QRect(
            rect.x() + margins.left(),
            rect.y() + margins.top(),
            rect.width() - (margins.left() + margins.right()),
            rect.height() - (margins.top() + margins.bottom()),
        )
        for item in self._items:
            wid = item.widget()
            if not wid:
                continue
            space_x = self._hspace
            space_y = self._vspace
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + margins.bottom()


class TagChip(QFrame):
    clicked = Signal(str)
    removed = Signal(str)

    def __init__(self, tag: str, *, closable: bool = False, tone: str = "apply", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tag = tag
        self._closable = closable
        self.setObjectName("TagChip")
        tones = {
            "apply": ("#d9f5e5", "#2f8f5b"),
            "filter": ("#e5e7eb", "#374151"),
        }
        bg, fg = tones.get(tone, ("#e5e7eb", "#374151"))
        self.setStyleSheet(
            f"#TagChip {{ background: {bg}; color: {fg}; border: 1px solid rgba(0,0,0,0.08); border-radius: 12px; padding: 4px 8px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 4, 2)
        label = QLabel(tag, self)
        layout.addWidget(label)
        if closable:
            btn = QPushButton("×", self)
            btn.setFixedSize(QSize(16, 16))
            btn.setToolTip("Remove tag")
            btn.clicked.connect(self._emit_remove)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(
                "QPushButton { border: none; background: transparent; color: #4b5563; font-weight: bold; }"
                "QPushButton:hover { color: #111827; }"
            )
            layout.addWidget(btn)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.clicked.emit(self._tag)
        return super().mouseReleaseEvent(event)

    def _emit_remove(self) -> None:
        self.removed.emit(self._tag)


class TagFlyoutPanel(QWidget):
    tag_apply_requested = Signal(str)
    tag_filter_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(460)
        self._apply_tags: list[str] = []
        self._suggestions: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = QLabel("File Tagging", self)
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(header)

        apply_card = self._build_apply_card()
        root.addWidget(apply_card)

        filter_card = self._build_filter_card()
        root.addWidget(filter_card)
        root.addStretch(1)

        self.setStyleSheet(
            """
            QWidget#TagCard { border: 1px solid #e5e7eb; border-radius: 10px; background: #ffffff; }
            QLineEdit { padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; }
            QLineEdit:focus { border-color: #2563eb; }
            QPushButton[variant="primary"] { background: #0f172a; color: white; border-radius: 8px; padding: 6px 12px; }
            QPushButton[variant="primary"]:hover { background: #1f2937; }
            QPushButton[variant="secondary"] { background: #f3f4f6; color: #111827; border-radius: 8px; padding: 6px 12px; border: 1px solid #e5e7eb; }
            QPushButton[variant="secondary"]:hover { background: #e5e7eb; }
            """
        )

    def _build_apply_card(self) -> QWidget:
        card = QFrame(self)
        card.setObjectName("TagCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Add tags to selection", card)
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        input_row = QHBoxLayout()
        self._apply_input = QLineEdit(card)
        self._apply_input.setPlaceholderText("Add new tag…")
        self._apply_input.setClearButtonEnabled(True)
        self._apply_input.returnPressed.connect(self._add_apply_tag_from_input)
        input_row.addWidget(self._apply_input, 1)
        add_btn = QPushButton("Add", card)
        add_btn.setProperty("variant", "primary")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setMinimumWidth(72)
        add_btn.setMaximumWidth(84)
        add_btn.setToolTip("Add the tag to the apply list")
        add_btn.setDefault(True)
        add_btn.setAutoDefault(True)
        add_btn.clicked.connect(self._add_apply_tag_from_input)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self._apply_chip_layout = FlowLayout(None, margin=0, spacing=6)
        chips = QWidget(card)
        chips_layout = QVBoxLayout(chips)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)
        chips_layout.addLayout(self._apply_chip_layout)
        layout.addWidget(chips)

        apply_row = QHBoxLayout()
        apply_btn = QPushButton("Apply to selection", card)
        apply_btn.setProperty("variant", "primary")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.clicked.connect(self._emit_apply)
        apply_row.addWidget(apply_btn)
        clear_btn = QPushButton("Clear", card)
        clear_btn.setProperty("variant", "secondary")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_apply_tags)
        apply_row.addWidget(clear_btn)
        apply_row.addStretch(1)
        layout.addLayout(apply_row)

        subtitle = QLabel("Suggestions", card)
        subtitle.setStyleSheet("font-weight: 500; color: #4b5563;")
        layout.addWidget(subtitle)

        self._apply_suggestions_layout = FlowLayout(None, margin=0, spacing=6)
        suggest_wrap = QWidget(card)
        suggest_wrap.setLayout(self._apply_suggestions_layout)
        layout.addWidget(suggest_wrap)
        return card

    def _build_filter_card(self) -> QWidget:
        card = QFrame(self)
        card.setObjectName("TagCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Search tags", card)
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        self._filter_input = QLineEdit(card)
        self._filter_input.setPlaceholderText("Search tags…")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.returnPressed.connect(self._emit_filter)
        layout.addWidget(self._filter_input)

        btn_row = QHBoxLayout()
        filter_btn = QPushButton("Filter workspace", card)
        filter_btn.setProperty("variant", "secondary")
        filter_btn.setCursor(Qt.PointingHandCursor)
        filter_btn.clicked.connect(self._emit_filter)
        btn_row.addWidget(filter_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        hint = QLabel("Click a suggestion to prefill the filter.", card)
        hint.setStyleSheet("color: #6b7280;")
        layout.addWidget(hint)

        self._filter_suggestions_layout = FlowLayout(None, margin=0, spacing=6)
        filter_wrap = QWidget(card)
        filter_wrap.setLayout(self._filter_suggestions_layout)
        layout.addWidget(filter_wrap)
        return card

    # ----------------------------------------------------------------- actions
    def set_tag_suggestions(self, tags: Iterable[str]) -> None:
        unique = sorted({tag.strip() for tag in tags if tag.strip()})
        self._suggestions = unique
        self._refresh_suggestion_chips()

    def _add_apply_tag_from_input(self) -> None:
        text = self._apply_input.text()
        segments = [segment.strip().lstrip("#") for segment in text.split(",") if segment.strip()]
        if not segments:
            return
        for segment in segments:
            if segment not in self._apply_tags:
                self._apply_tags.append(segment)
        self._apply_tags.sort()
        self._apply_input.clear()
        self._refresh_apply_chips()

    def _refresh_apply_chips(self) -> None:
        self._apply_chip_layout.clear()
        for tag in self._apply_tags:
            chip = TagChip(tag, closable=True, tone="apply", parent=self)
            chip.removed.connect(self._remove_apply_tag)
            chip.clicked.connect(self._remove_apply_tag)
            self._apply_chip_layout.addWidget(chip)

    def _refresh_suggestion_chips(self) -> None:
        self._apply_suggestions_layout.clear()
        self._filter_suggestions_layout.clear()
        for tag in self._suggestions:
            add_chip = TagChip(tag, closable=False, tone="apply", parent=self)
            add_chip.clicked.connect(self._add_apply_tag_from_chip)
            self._apply_suggestions_layout.addWidget(add_chip)

            filter_chip = TagChip(tag, closable=False, tone="filter", parent=self)
            filter_chip.clicked.connect(self._on_filter_chip_clicked)
            self._filter_suggestions_layout.addWidget(filter_chip)

    def _remove_apply_tag(self, tag: str) -> None:
        if tag in self._apply_tags:
            self._apply_tags.remove(tag)
            self._refresh_apply_chips()

    def _add_apply_tag_from_chip(self, tag: str) -> None:
        if tag not in self._apply_tags:
            self._apply_tags.append(tag)
            self._apply_tags.sort()
            self._refresh_apply_chips()

    def _clear_apply_tags(self) -> None:
        self._apply_tags.clear()
        self._refresh_apply_chips()

    def _emit_apply(self) -> None:
        if self._apply_input.text().strip():
            self._add_apply_tag_from_input()
        if not self._apply_tags:
            return
        payload = ", ".join(self._apply_tags)
        self.tag_apply_requested.emit(payload)

    def _emit_filter(self) -> None:
        text = self._filter_input.text().strip()
        self.tag_filter_requested.emit(text)

    def _on_filter_chip_clicked(self, tag: str) -> None:
        self._filter_input.setText(tag)
        self._emit_filter()
