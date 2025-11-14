from __future__ import annotations

from typing import Iterable, List

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class FlowLayout(QHBoxLayout):
    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 6) -> None:
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[QWidget] = []

    def addWidget(self, widget: QWidget) -> None:  # type: ignore[override]
        super().addWidget(widget)
        self._items.append(widget)

    def clear(self) -> None:
        while self.count():
            item = self.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        self._items.clear()


class TagChip(QFrame):
    removed = Signal(str)

    def __init__(self, tag: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tag = tag
        self.setObjectName("TagChip")
        self.setStyleSheet(
            "#TagChip { border: 1px solid palette(mid); border-radius: 10px; padding: 2px 6px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 2, 0)
        label = QLabel(tag, self)
        layout.addWidget(label)
        btn = QPushButton("×", self)
        btn.setFixedSize(QSize(16, 16))
        btn.setToolTip("Remove tag")
        btn.clicked.connect(self._emit_remove)
        btn.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(btn)

    def _emit_remove(self) -> None:
        self.removed.emit(self._tag)


class TagEditorDialog(QDialog):
    def __init__(self, tags: Iterable[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Tags")
        self.resize(420, 320)
        self._tags: list[str] = sorted({tag.strip().lower() for tag in tags if tag.strip()})

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        info = QLabel("Click × to remove tags. Type a tag and press Add to include new ones.", self)
        info.setWordWrap(True)
        root.addWidget(info)

        self._chip_area = QScrollArea(self)
        self._chip_area.setWidgetResizable(True)
        content = QWidget(self._chip_area)
        self._chip_layout = FlowLayout(content, margin=6, spacing=6)
        content.setLayout(self._chip_layout)
        self._chip_area.setWidget(content)
        root.addWidget(self._chip_area, 1)

        entry_row = QHBoxLayout()
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("Add tag…")
        self._input.returnPressed.connect(self._add_tag_from_input)
        entry_row.addWidget(self._input, 1)
        add_btn = QPushButton("Add", self)
        add_btn.clicked.connect(self._add_tag_from_input)
        entry_row.addWidget(add_btn)
        root.addLayout(entry_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_chips()

    def tags(self) -> List[str]:
        return list(self._tags)

    # internal helpers --------------------------------------------------
    def _add_tag_from_input(self) -> None:
        text = self._input.text().strip().lower()
        if not text:
            return
        if text not in self._tags:
            self._tags.append(text)
            self._tags.sort()
            self._refresh_chips()
        self._input.clear()

    def _refresh_chips(self) -> None:
        self._chip_layout.clear()
        for tag in self._tags:
            chip = TagChip(tag, self)
            chip.removed.connect(self._remove_tag)
            self._chip_layout.addWidget(chip)

    def _remove_tag(self, tag: str) -> None:
        if tag in self._tags:
            self._tags.remove(tag)
            self._refresh_chips()
