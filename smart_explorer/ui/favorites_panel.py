from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal, QPoint, QStringListModel
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QCompleter,
)

from .workspace_pane import PANE_DRAG_MIME


class FavoritesListWidget(QListWidget):
    def __init__(self, panel: "FavoritesPanel") -> None:
        super().__init__(panel)
        self._panel = panel
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasFormat(PANE_DRAG_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasFormat(PANE_DRAG_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):  # type: ignore[override]
        if event.mimeData().hasFormat(PANE_DRAG_MIME):
            wid = bytes(event.mimeData().data(PANE_DRAG_MIME)).decode("utf-8")
            if wid:
                self._panel.favorite_add_from_workspace.emit(wid)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class FavoritesPanel(QWidget):
    favorite_selected = Signal(str)
    favorite_add_requested = Signal()
    favorite_remove_requested = Signal(str)
    favorite_rename_requested = Signal(str)
    favorite_move_requested = Signal(str, int)
    favorite_add_from_workspace = Signal(str)

    layout_apply_requested = Signal(str)
    layout_save_requested = Signal()
    layout_remove_requested = Signal(str)
    layout_rename_requested = Signal(str)
    layout_move_requested = Signal(str, int)

    position_changed = Signal(str)
    tag_apply_requested = Signal(str)
    tag_filter_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._position = "left"
        self._favorites_index: dict[str, QListWidgetItem] = {}
        self._layouts_index: dict[str, QListWidgetItem] = {}
        self._position_actions: list = []
        self.setMinimumWidth(140)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        fav_frame = self._build_favorites_section()
        tags_frame = self._build_tags_section()
        layouts_frame = self._build_layouts_section()

        root.addWidget(fav_frame)
        root.addWidget(tags_frame)
        root.addWidget(layouts_frame)
        root.addStretch(1)

    # ------------------------------------------------------------------ build
    def _build_header(self, title: str) -> QHBoxLayout:
        label = QLabel(title, self)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        button = QToolButton(self)
        button.setText("⋮")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        position_menu = menu.addMenu("Position")
        for pos in ("left", "right", "top", "bottom"):
            action = position_menu.addAction(pos.capitalize())
            action.setCheckable(True)
            action.setData(pos)
            if pos == self._position:
                action.setChecked(True)
            self._position_actions.append(action)
        menu.triggered.connect(self._on_position_menu_triggered)
        button.setMenu(menu)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(button)
        return layout

    def _build_favorites_section(self) -> QWidget:
        frame = QFrame(self)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = self._build_header("Favorites")
        layout.addLayout(header)

        self._favorites_list = FavoritesListWidget(self)
        self._favorites_list.setSelectionMode(QListWidget.SingleSelection)
        self._favorites_list.itemDoubleClicked.connect(self._on_favorite_double_clicked)
        self._favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._favorites_list.customContextMenuRequested.connect(self._on_favorite_context_menu)
        layout.addWidget(self._favorites_list, 1)

        fav_buttons = [
            ("add", "＋", "Add current pane to favorites", lambda: self.favorite_add_requested.emit()),
            ("rename", "✎", "Rename selected favorite", self._on_rename_favorite),
            ("remove", "－", "Remove selected favorite", self._on_remove_favorite),
            ("up", "↑", "Move favorite up", lambda: self._move_favorite(-1)),
            ("down", "↓", "Move favorite down", lambda: self._move_favorite(1)),
        ]
        layout.addLayout(self._build_button_grid(fav_buttons, prefix="fav", columns=2))
        self._favorites_list.currentRowChanged.connect(self._update_favorite_buttons)
        self._update_favorite_buttons()
        return frame

    def _build_tags_section(self) -> QWidget:
        frame = QFrame(self)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        label = QLabel("Tags", self)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.addWidget(label)
        header.addStretch(1)
        layout.addLayout(header)

        self._tag_input = QLineEdit(self)
        self._tag_input.setPlaceholderText("Add or filter tags (comma separated)")
        self._tag_model = QStringListModel([], self)
        self._tag_completer = QCompleter(self._tag_model, self)
        self._tag_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._tag_input.setCompleter(self._tag_completer)
        self._tag_input.returnPressed.connect(self._emit_tag_apply)
        layout.addWidget(self._tag_input)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply to Selection", self)
        apply_btn.clicked.connect(self._emit_tag_apply)
        btn_row.addWidget(apply_btn)
        filter_btn = QPushButton("Filter", self)
        filter_btn.clicked.connect(self._emit_tag_filter)
        btn_row.addWidget(filter_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        hint = QLabel("Existing tags appear as suggestions.", self)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return frame

    def _build_layouts_section(self) -> QWidget:
        frame = QFrame(self)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        label = QLabel("Layouts", self)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.addWidget(label)
        header.addStretch(1)
        layout.addLayout(header)

        self._layouts_list = QListWidget(self)
        self._layouts_list.setSelectionMode(QListWidget.SingleSelection)
        self._layouts_list.itemDoubleClicked.connect(self._on_layout_double_clicked)
        self._layouts_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._layouts_list.customContextMenuRequested.connect(self._on_layout_context_menu)
        layout.addWidget(self._layouts_list, 1)

        layout_buttons = [
            ("save", "💾", "Save current layout", lambda: self.layout_save_requested.emit()),
            ("apply", "▶", "Apply layout", self._on_apply_layout),
            ("rename", "✎", "Rename selected layout", self._on_rename_layout),
            ("remove", "－", "Remove layout", self._on_remove_layout),
            ("up", "↑", "Move layout up", lambda: self._move_layout(-1)),
            ("down", "↓", "Move layout down", lambda: self._move_layout(1)),
        ]
        layout.addLayout(self._build_button_grid(layout_buttons, prefix="layout", columns=2))
        self._layouts_list.currentRowChanged.connect(self._update_layout_buttons)
        self._update_layout_buttons()
        return frame

    def _build_button_grid(self, specs, *, prefix: str, columns: int = 2) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for idx, (name, text, tooltip, handler) in enumerate(specs):
            btn = QPushButton(text, self)
            if tooltip:
                btn.setToolTip(tooltip)
            btn.clicked.connect(handler)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.setMaximumWidth(36)
            btn.setMinimumWidth(28)
            setattr(self, f"_{prefix}_{name}_btn", btn)
            row, col = divmod(idx, columns)
            grid.addWidget(btn, row, col)
        return grid

    # ----------------------------------------------------------------- helpers
    def set_position(self, position: str) -> None:
        if position not in {"left", "right", "top", "bottom"}:
            position = "left"
        self._position = position
        for action in self._position_actions:
            action.setChecked(action.data() == position)

    def set_favorites(self, favorites: Iterable[dict]) -> None:
        self._favorites_index.clear()
        self._favorites_list.clear()
        for fav in favorites:
            fid = fav.get("id")
            name = fav.get("name", fid)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, fid)
            self._favorites_index[fid] = item
            self._favorites_list.addItem(item)
        self._update_favorite_buttons()

    def set_layouts(self, layouts: Iterable[dict]) -> None:
        self._layouts_index.clear()
        self._layouts_list.clear()
        for layout in layouts:
            lid = layout.get("id")
            name = layout.get("name", lid)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, lid)
            self._layouts_index[lid] = item
            self._layouts_list.addItem(item)
        self._update_layout_buttons()

    def set_tag_suggestions(self, tags: Iterable[str]) -> None:
        unique = sorted({tag.strip() for tag in tags if tag.strip()})
        self._tag_model.setStringList(unique)

    def _emit_tag_apply(self) -> None:
        text = self._tag_input.text().strip()
        if text:
            self.tag_apply_requested.emit(text)

    def _emit_tag_filter(self) -> None:
        text = self._tag_input.text().strip()
        self.tag_filter_requested.emit(text)

    def select_favorite(self, favorite_id: str) -> None:
        item = self._favorites_index.get(favorite_id)
        if item:
            row = self._favorites_list.row(item)
            self._favorites_list.setCurrentRow(row)
            self._favorites_list.scrollToItem(item)

    def select_layout(self, layout_id: str) -> None:
        item = self._layouts_index.get(layout_id)
        if item:
            row = self._layouts_list.row(item)
            self._layouts_list.setCurrentRow(row)
            self._layouts_list.scrollToItem(item)

    # ----------------------------------------------------------------- events
    def _on_position_menu_triggered(self, action) -> None:
        pos = action.data()
        if not pos:
            return
        self._position = pos
        for act in self._position_actions:
            act.setChecked(act is action)
        self.position_changed.emit(pos)

    def _current_favorite_id(self) -> Optional[str]:
        item = self._favorites_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _current_layout_id(self) -> Optional[str]:
        item = self._layouts_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_favorite_double_clicked(self, item: QListWidgetItem) -> None:
        fid = item.data(Qt.UserRole)
        if fid:
            self.favorite_selected.emit(fid)

    def _on_favorite_context_menu(self, pos: QPoint) -> None:
        fid = self._current_favorite_id()
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        rename_act = menu.addAction("Rename")
        remove_act = menu.addAction("Remove")
        menu.addSeparator()
        up_act = menu.addAction("Move Up")
        down_act = menu.addAction("Move Down")
        add_act = menu.addAction("Add Current Pane")

        if not fid:
            open_act.setEnabled(False)
            rename_act.setEnabled(False)
            remove_act.setEnabled(False)
            up_act.setEnabled(False)
            down_act.setEnabled(False)

        action = menu.exec(self._favorites_list.viewport().mapToGlobal(pos))
        if not action:
            return
        if action is open_act and fid:
            self.favorite_selected.emit(fid)
        elif action is rename_act and fid:
            self.favorite_rename_requested.emit(fid)
        elif action is remove_act and fid:
            self.favorite_remove_requested.emit(fid)
        elif action is up_act and fid:
            self.favorite_move_requested.emit(fid, -1)
        elif action is down_act and fid:
            self.favorite_move_requested.emit(fid, 1)
        elif action is add_act:
            self.favorite_add_requested.emit()

    def _on_layout_double_clicked(self, item: QListWidgetItem) -> None:
        lid = item.data(Qt.UserRole)
        if lid:
            self.layout_apply_requested.emit(lid)

    def _on_layout_context_menu(self, pos: QPoint) -> None:
        lid = self._current_layout_id()
        menu = QMenu(self)
        save_act = menu.addAction("Save Current")
        apply_act = menu.addAction("Apply")
        rename_act = menu.addAction("Rename")
        remove_act = menu.addAction("Remove")
        menu.addSeparator()
        up_act = menu.addAction("Move Up")
        down_act = menu.addAction("Move Down")

        if not lid:
            apply_act.setEnabled(False)
            rename_act.setEnabled(False)
            remove_act.setEnabled(False)
            up_act.setEnabled(False)
            down_act.setEnabled(False)

        action = menu.exec(self._layouts_list.viewport().mapToGlobal(pos))
        if not action:
            return
        if action is save_act:
            self.layout_save_requested.emit()
        elif action is apply_act and lid:
            self.layout_apply_requested.emit(lid)
        elif action is rename_act and lid:
            self.layout_rename_requested.emit(lid)
        elif action is remove_act and lid:
            self.layout_remove_requested.emit(lid)
        elif action is up_act and lid:
            self.layout_move_requested.emit(lid, -1)
        elif action is down_act and lid:
            self.layout_move_requested.emit(lid, 1)

    def _on_remove_favorite(self) -> None:
        fid = self._current_favorite_id()
        if fid:
            self.favorite_remove_requested.emit(fid)

    def _on_rename_favorite(self) -> None:
        fid = self._current_favorite_id()
        if fid:
            self.favorite_rename_requested.emit(fid)

    def _on_apply_layout(self) -> None:
        lid = self._current_layout_id()
        if lid:
            self.layout_apply_requested.emit(lid)

    def _on_rename_layout(self) -> None:
        lid = self._current_layout_id()
        if lid:
            self.layout_rename_requested.emit(lid)

    def _on_remove_layout(self) -> None:
        lid = self._current_layout_id()
        if lid:
            self.layout_remove_requested.emit(lid)

    def _move_favorite(self, offset: int) -> None:
        fid = self._current_favorite_id()
        if fid:
            self.favorite_move_requested.emit(fid, offset)

    def _move_layout(self, offset: int) -> None:
        lid = self._current_layout_id()
        if lid:
            self.layout_move_requested.emit(lid, offset)

    def _update_favorite_buttons(self) -> None:
        has_selection = self._favorites_list.currentItem() is not None
        for btn in (self._fav_rename_btn, self._fav_remove_btn, self._fav_up_btn, self._fav_down_btn):
            btn.setEnabled(has_selection)

    def _update_layout_buttons(self) -> None:
        has_selection = self._layouts_list.currentItem() is not None
        for btn in (self._layout_apply_btn, self._layout_rename_btn, self._layout_remove_btn, self._layout_up_btn, self._layout_down_btn):
            btn.setEnabled(has_selection)
