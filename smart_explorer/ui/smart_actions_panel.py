from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SmartActionsPanel(QWidget):
    summarize_requested = Signal()
    auto_tag_requested = Signal()
    ask_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SmartActionsPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = QLabel("Smart Actions", self)
        header.setObjectName("SmartActionsHeader")
        root.addWidget(header)

        self._selection_card = QFrame(self)
        self._selection_card.setObjectName("SmartSelectionCard")
        card_layout = QVBoxLayout(self._selection_card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(6)

        self._selection_title = QLabel("No file selected", self._selection_card)
        self._selection_title.setObjectName("SmartSelectionTitle")
        self._selection_title.setWordWrap(True)
        card_layout.addWidget(self._selection_title)

        self._selection_meta = QLabel("Select a file to preview AI actions.", self._selection_card)
        self._selection_meta.setObjectName("SmartSelectionMeta")
        self._selection_meta.setWordWrap(True)
        card_layout.addWidget(self._selection_meta)

        root.addWidget(self._selection_card)

        self._btn_summarize = QPushButton("Summarize File", self)
        self._btn_summarize.clicked.connect(self.summarize_requested.emit)
        root.addWidget(self._btn_summarize)

        self._btn_auto_tag = QPushButton("Auto-Tag Selection", self)
        self._btn_auto_tag.clicked.connect(self.auto_tag_requested.emit)
        root.addWidget(self._btn_auto_tag)

        ask_row = QHBoxLayout()
        ask_row.setContentsMargins(0, 0, 0, 0)
        ask_row.setSpacing(6)
        self._ask_input = QLineEdit(self)
        self._ask_input.setPlaceholderText("Ask AI about selected file...")
        ask_row.addWidget(self._ask_input, 1)
        self._ask_btn = QPushButton("Ask", self)
        self._ask_btn.clicked.connect(self._emit_ask)
        ask_row.addWidget(self._ask_btn)
        root.addLayout(ask_row)

        self._cost_label = QLabel("Current Task Cost: n/a", self)
        self._cost_label.setObjectName("SmartCostLabel")
        root.addWidget(self._cost_label)

        root.addStretch(1)

        self._set_ai_buttons_enabled(False)

    def set_selection_context(self, file_name: str, details: str) -> None:
        has_selection = bool(file_name.strip())
        self._selection_title.setText(file_name if has_selection else "No file selected")
        self._selection_meta.setText(details if details else "Select a file to preview AI actions.")
        self._set_ai_buttons_enabled(has_selection)

    def set_cost_hint(self, text: str) -> None:
        value = text.strip() if text else "n/a"
        self._cost_label.setText(f"Current Task Cost: {value}")

    def _set_ai_buttons_enabled(self, enabled: bool) -> None:
        self._btn_summarize.setEnabled(enabled)
        self._btn_auto_tag.setEnabled(enabled)
        self._ask_input.setEnabled(enabled)
        self._ask_btn.setEnabled(enabled)

    def _emit_ask(self) -> None:
        question = self._ask_input.text().strip()
        if not question:
            return
        self.ask_requested.emit(question)
