from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..services.link_migration_log import LinkMigrationLog
from ..services.relinking_workspace import RelinkingWorkspaceStore
from .relinking_panel import RelinkingPanel
from .smart_actions_panel import SmartActionsPanel


class WorkspaceToolsPanel(QWidget):
    def __init__(
        self,
        log: LinkMigrationLog,
        relinking_store: RelinkingWorkspaceStore,
        parent: Optional[QWidget] = None,
        *,
        sp_base_url: str = "",
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget(self)
        self.smart_actions_panel = SmartActionsPanel(self._tabs)
        self.relinking_panel = RelinkingPanel(log, relinking_store, self._tabs, sp_base_url=sp_base_url)
        self._tabs.addTab(self.smart_actions_panel, "Smart Actions")
        self._tabs.addTab(self.relinking_panel, "Relinking")
        root.addWidget(self._tabs)

    def open_tab(self, name: str) -> None:
        value = str(name or "").strip().lower()
        if value == "relinking":
            self._tabs.setCurrentWidget(self.relinking_panel)
            return
        self._tabs.setCurrentWidget(self.smart_actions_panel)
