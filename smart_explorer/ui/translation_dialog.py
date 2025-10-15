from __future__ import annotations

from typing import List, Tuple

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


class TranslationWorkspaceDialog(QDialog):
    def __init__(self, base_workspaces: List[Tuple[str, str]], default_language: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Translation Workspace")

        self._base_combo = QComboBox(self)
        for workspace_id, name in base_workspaces:
            self._base_combo.addItem(name, workspace_id)

        self._language_edit = QLineEdit(self)
        self._language_edit.setText(default_language)

        form = QFormLayout(self)
        form.addRow("Source workspace:", self._base_combo)
        form.addRow("Target language:", self._language_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    @property
    def base_workspace_id(self) -> str:
        return self._base_combo.currentData()

    @property
    def language(self) -> str:
        return self._language_edit.text().strip() or "English"
