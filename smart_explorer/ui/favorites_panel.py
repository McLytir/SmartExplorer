from __future__ import annotations

import os
from typing import Iterable, Optional, Sequence

from PySide6.QtCore import Qt, Signal, QPoint, QStringListModel
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .workspace_pane import PANE_DRAG_MIME
from .tag_editor_dialog import FlowLayout


class TagBubble(QFrame):
    removed = Signal(str)
    filter_requested = Signal(str)

    def __init__(self, tag: str, count: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tag = tag
        self._count = max(0, count)
        self.setObjectName("TagBubble")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "#TagBubble { border: 1px solid palette(mid); border-radius: 11px; padding: 2px 8px; } "
            "#TagCount { background: palette(midlight); border-radius: 8px; padding: 0 6px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 4, 0)
        layout.setSpacing(6)
        self._label = QLabel(f"#{tag}", self)
        layout.addWidget(self._label)
        self._count_label = QLabel(str(self._count), self)
        self._count_label.setObjectName("TagCount")
        layout.addWidget(self._count_label)
        remove_btn = QToolButton(self)
        remove_btn.setText("×")
        remove_btn.setAutoRaise(True)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setToolTip(f"Remove #{tag} from all files")
        remove_btn.clicked.connect(self._emit_remove)
        remove_btn.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(remove_btn)

    def set_count(self, count: int) -> None:
        self._count = max(0, count)
        self._count_label.setText(str(self._count))

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            try:
                pos = event.position().toPoint()
            except AttributeError:
                pos = event.pos()
            child = self.childAt(pos)
            if not isinstance(child, QToolButton):
                self.filter_requested.emit(self._tag)
        super().mouseReleaseEvent(event)

    def _emit_remove(self) -> None:
        self.removed.emit(self._tag)


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
    tag_ai_requested = Signal()
    tag_remove_requested = Signal(str)
    tag_open_requested = Signal(str)
    tag_reveal_requested = Signal(str)
    tag_copy_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._position = "left"
        self._favorites_index: dict[str, QListWidgetItem] = {}
        self._layouts_index: dict[str, QListWidgetItem] = {}
        self._position_actions: list = []
        self.setMinimumWidth(140)
        self._all_tags: list[tuple[str, int]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        fav_frame = self._build_favorites_section()
        tags_frame = self._build_tags_section()
        layouts_frame = self._build_layouts_section()

        root.addWidget(fav_frame)
        root.addWidget(tags_frame, 1)
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
        frame.setMinimumHeight(240)
        frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
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
        ai_btn = QPushButton("AI Suggest", self)
        ai_btn.clicked.connect(self._emit_tag_ai)
        btn_row.addWidget(ai_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._tag_chip_area = QScrollArea(self)
        self._tag_chip_area.setWidgetResizable(True)
        self._tag_chip_container = QWidget(self._tag_chip_area)
        self._tag_chip_layout = FlowLayout(self._tag_chip_container, margin=6, spacing=6)
        self._tag_chip_area.setWidget(self._tag_chip_container)
        layout.addWidget(self._tag_chip_area, 1)

        self._tag_results_label = QLabel("Tag matches: 0", self)
        layout.addWidget(self._tag_results_label)

        self._tag_results_list = QListWidget(self)
        self._tag_results_list.setSelectionMode(QListWidget.SingleSelection)
        self._tag_results_list.itemDoubleClicked.connect(self._on_tag_result_open)
        self._tag_results_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tag_results_list.customContextMenuRequested.connect(self._on_tag_result_context_menu)
        layout.addWidget(self._tag_results_list, 1)

        self.set_tag_results([])

        hint = QLabel("Click x on a bubble to remove a tag everywhere.", self)
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

    def set_tag_suggestions(self, tags: Iterable[Sequence[str]] | Iterable[str]) -> None:
        processed: list[tuple[str, int]] = []
        for entry in tags:
            if isinstance(entry, (list, tuple)) and entry:
                tag = str(entry[0]).strip()
                count = int(entry[1]) if len(entry) > 1 else 0
            else:
                tag = str(entry).strip()
                count = 0
            if not tag:
                continue
            processed.append((tag, max(0, count)))
        processed.sort(key=lambda item: item[0])
        self._all_tags = processed
        self._tag_model.setStringList([tag for tag, _ in processed])
        self._refresh_tag_bubbles()

    def _emit_tag_apply(self) -> None:
        text = self._tag_input.text().strip()
        if text:
            self.tag_apply_requested.emit(text)

    def _emit_tag_filter(self) -> None:
        text = self._tag_input.text().strip()
        self.tag_filter_requested.emit(text)

    def _emit_tag_ai(self) -> None:
        self.tag_ai_requested.emit()

    def _refresh_tag_bubbles(self) -> None:
        if not hasattr(self, "_tag_chip_layout"):
            return
        if hasattr(self._tag_chip_layout, "clear"):
            self._tag_chip_layout.clear()
        if not self._all_tags:
            placeholder = QLabel("No tags created yet.", self._tag_chip_container)
            self._tag_chip_layout.addWidget(placeholder)
            return
        for tag, count in self._all_tags:
            bubble = TagBubble(tag, count, self._tag_chip_container)
            bubble.removed.connect(self._emit_tag_remove)
            bubble.filter_requested.connect(self._filter_from_bubble)
            self._tag_chip_layout.addWidget(bubble)

    def _emit_tag_remove(self, tag: str) -> None:
        self.tag_remove_requested.emit(tag)

    def _filter_from_bubble(self, tag: str) -> None:
        self._tag_input.setText(tag)
        self.tag_filter_requested.emit(tag)

    def set_tag_results(self, results: Sequence[dict]) -> None:
        self._tag_results_list.clear()
        count = 0
        for entry in results:
            path = entry.get("path")
            if not path:
                continue
            matched = entry.get("matched") or []
            all_tags = entry.get("tags") or []
            basename = os.path.basename(path) or path
            display = f"{basename}\n{path}"
            if all_tags:
                display += f"\nTags: {', '.join(f'#{t}' for t in all_tags)}"
            if matched:
                display += f"\nMatched: {', '.join(f'#{t}' for t in matched)}"
            item = QListWidgetItem(display, self._tag_results_list)
            item.setData(Qt.UserRole, path)
            if matched:
                item.setToolTip(f"Matched tags: {', '.join(f'#{t}' for t in matched)}")
            count += 1
        self._tag_results_label.setText(f"Tag matches: {count}")

    def _on_tag_result_open(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.tag_open_requested.emit(path)

    def _on_tag_result_context_menu(self, pos) -> None:
        item = self._tag_results_list.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        reveal_act = menu.addAction("Reveal in Explorer")
        copy_act = menu.addAction("Copy Path")
        action = menu.exec(self._tag_results_list.viewport().mapToGlobal(pos))
        if not action:
            return
        if action is open_act:
            self.tag_open_requested.emit(path)
        elif action is reveal_act:
            self.tag_reveal_requested.emit(path)
        elif action is copy_act:
            self.tag_copy_requested.emit(path)

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
