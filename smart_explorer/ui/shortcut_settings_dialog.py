from __future__ import annotations

from typing import Dict, Iterable, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QKeySequenceEdit,
    QVBoxLayout,
    QWidget,
)


class ShortcutSettingsDialog(QDialog):
    """Simple dialog to edit app shortcuts."""

    def __init__(self, current: Dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(420, 220)
        self._result: Dict[str, str] = dict(current)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        root.addLayout(grid)

        rows: Iterable[Tuple[str, str]] = (
            ("toggle_tags", "Toggle Tags panel"),
            ("toggle_favorites", "Toggle Favorites panel"),
        )

        for row, (action, label) in enumerate(rows):
            grid.addWidget(QLabel(label, self), row, 0, Qt.AlignLeft)
            editor = QKeySequenceEdit(self)
            editor.setKeySequence(self._result.get(action, ""))
            editor.editingFinished.connect(lambda a=action, e=editor: self._update_value(a, e))
            grid.addWidget(editor, row, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _update_value(self, action: str, editor: QKeySequenceEdit) -> None:
        seq = editor.keySequence().toString(Qt.NativeText)
        if seq:
            self._result[action] = seq
        elif action in self._result:
            # Allow clearing
            self._result.pop(action)

    def result_shortcuts(self) -> Dict[str, str]:
        return dict(self._result)
