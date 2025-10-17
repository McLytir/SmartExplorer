from __future__ import annotations

import itertools
import os
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Literal, Optional

from .settings import AppConfig

WorkspaceKind = Literal["local", "sharepoint", "translation"]
FavoriteKind = Literal["local", "sharepoint"]


@dataclass
class WorkspaceDefinition:
    id: str
    kind: WorkspaceKind
    name: str
    root_path: Optional[str] = None
    site_relative_url: Optional[str] = None
    server_relative_url: Optional[str] = None
    base_workspace_id: Optional[str] = None
    language: Optional[str] = None
    auto_sync: bool = True

    def to_config(self) -> dict:
        data = asdict(self)
        # Filter None values for compact config storage
        return {k: v for k, v in data.items() if v is not None}

    @staticmethod
    def from_config(data: dict) -> "WorkspaceDefinition":
        return WorkspaceDefinition(
            id=str(data.get("id") or f"ws-{uuid.uuid4().hex[:6]}"),
            kind=data.get("kind", "local"),
            name=data.get("name") or data.get("id") or "Workspace",
            root_path=data.get("root_path"),
            site_relative_url=data.get("site_relative_url"),
            server_relative_url=data.get("server_relative_url"),
            base_workspace_id=data.get("base_workspace_id"),
            language=data.get("language"),
            auto_sync=bool(data.get("auto_sync", True)),
        )


@dataclass
class FavoriteLocation:
    id: str
    kind: FavoriteKind
    name: str
    root_path: Optional[str] = None
    site_relative_url: Optional[str] = None
    server_relative_url: Optional[str] = None

    def to_config(self) -> dict:
        data = asdict(self)
        return {k: v for k, v in data.items() if v not in (None, "")}

    @staticmethod
    def from_config(data: dict) -> "FavoriteLocation":
        return FavoriteLocation(
            id=str(data.get("id") or f"fav-{uuid.uuid4().hex[:6]}"),
            kind=data.get("kind", "local"),
            name=data.get("name") or "Favorite",
            root_path=data.get("root_path"),
            site_relative_url=data.get("site_relative_url"),
            server_relative_url=data.get("server_relative_url"),
        )


@dataclass
class LayoutDefinition:
    id: str
    name: str
    workspaces: List[dict]

    def to_config(self) -> dict:
        return {"id": self.id, "name": self.name, "workspaces": list(self.workspaces)}

    @staticmethod
    def from_config(data: dict) -> "LayoutDefinition":
        return LayoutDefinition(
            id=str(data.get("id") or f"layout-{uuid.uuid4().hex[:6]}"),
            name=data.get("name") or "Layout",
            workspaces=list(data.get("workspaces") or []),
        )


class WorkspaceManager:
    """
    Keeps track of workspace definitions and ensures IDs remain unique.
    """

    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._definitions: Dict[str, WorkspaceDefinition] = {}
        raw = getattr(cfg, "workspaces", None) or []
        for entry in raw:
            try:
                ws = WorkspaceDefinition.from_config(entry)
                self._definitions[ws.id] = ws
            except Exception:
                continue
        self._prune_invalid()
        if not self._definitions:
            self._install_default_workspaces()

    def _install_default_workspaces(self) -> None:
        root = self._cfg.root_path or os.path.expanduser("~")
        base = WorkspaceDefinition(
            id="ws-local",
            kind="local",
            name="Local",
            root_path=root,
        )
        translation = WorkspaceDefinition(
            id="ws-local-en",
            kind="translation",
            name="Local (Translated)",
            base_workspace_id=base.id,
            language=self._cfg.target_language or "English",
        )
        self._definitions = {base.id: base, translation.id: translation}

    def definitions(self) -> List[WorkspaceDefinition]:
        # Preserve insertion order
        return list(self._definitions.values())

    def get(self, workspace_id: str) -> Optional[WorkspaceDefinition]:
        return self._definitions.get(workspace_id)

    def ensure_unique_id(self, base_name: str) -> str:
        candidate = base_name
        counter = itertools.count(2)
        while candidate in self._definitions:
            candidate = f"{base_name}-{next(counter)}"
        return candidate

    def add(self, definition: WorkspaceDefinition) -> WorkspaceDefinition:
        if definition.id in self._definitions:
            definition.id = self.ensure_unique_id(definition.id)
        self._definitions[definition.id] = definition
        self._prune_invalid()
        return definition

    def remove(self, workspace_id: str) -> None:
        self._definitions.pop(workspace_id, None)
        # Remove translations referencing this workspace
        to_delete = [ws_id for ws_id, ws in self._definitions.items() if ws.base_workspace_id == workspace_id]
        for ws_id in to_delete:
            self._definitions.pop(ws_id, None)

    def update(self, definition: WorkspaceDefinition) -> None:
        self._definitions[definition.id] = definition
        self._prune_invalid()

    def to_config(self) -> List[dict]:
        return [ws.to_config() for ws in self._definitions.values()]

    # ------------------------------------------------------------------ helpers
    def _prune_invalid(self) -> None:
        removed = True
        while removed:
            removed = False
            to_remove = []
            for ws_id, ws in list(self._definitions.items()):
                if not self._is_valid(ws):
                    to_remove.append(ws_id)
            for ws_id in to_remove:
                self._definitions.pop(ws_id, None)
                removed = True

    def _is_valid(self, ws: WorkspaceDefinition) -> bool:
        if ws.kind == "local":
            return bool(ws.root_path)
        if ws.kind == "sharepoint":
            return bool(ws.site_relative_url and ws.server_relative_url and ws.server_relative_url != "/")
        if ws.kind == "translation":
            return bool(ws.base_workspace_id and ws.language and ws.base_workspace_id in self._definitions)
        return False

    def reorder_before(self, source_id: str, target_id: Optional[str]) -> None:
        order = [ws for ws in self._definitions.values()]
        ids = [ws.id for ws in order]
        if source_id not in ids:
            return
        if target_id == source_id:
            return
        source_ws = self._definitions[source_id]
        order = [ws for ws in order if ws.id != source_id]
        if target_id and target_id in [ws.id for ws in order]:
            index = next(i for i, ws in enumerate(order) if ws.id == target_id)
            order.insert(index, source_ws)
        else:
            order.append(source_ws)
        self._definitions = {ws.id: ws for ws in order}

    def move_by_offset(self, workspace_id: str, offset: int) -> None:
        order = [ws for ws in self._definitions.values()]
        ids = [ws.id for ws in order]
        if workspace_id not in ids or offset == 0:
            return
        index = ids.index(workspace_id)
        new_index = max(0, min(len(order) - 1, index + offset))
        ws = order.pop(index)
        order.insert(new_index, ws)
        self._definitions = {item.id: item for item in order}


def ensure_workspaces(cfg: AppConfig) -> WorkspaceManager:
    mgr = WorkspaceManager(cfg)
    cfg.workspaces = mgr.to_config()
    return mgr


class FavoritesManager:
    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._favorites: Dict[str, FavoriteLocation] = {}
        for entry in getattr(cfg, "favorites", None) or []:
            try:
                fav = FavoriteLocation.from_config(entry)
                self._favorites[fav.id] = fav
            except Exception:
                continue
        self._prune_invalid()

    def all(self) -> List[FavoriteLocation]:
        return list(self._favorites.values())

    def get(self, favorite_id: str) -> Optional[FavoriteLocation]:
        return self._favorites.get(favorite_id)

    def add(self, favorite: FavoriteLocation) -> FavoriteLocation:
        if favorite.id in self._favorites:
            favorite.id = self._ensure_unique_id(favorite.id)
        self._favorites[favorite.id] = favorite
        self._prune_invalid()
        return favorite

    def remove(self, favorite_id: str) -> None:
        self._favorites.pop(favorite_id, None)

    def update(self, favorite: FavoriteLocation) -> None:
        self._favorites[favorite.id] = favorite
        self._prune_invalid()

    def reorder_before(self, source_id: str, target_id: Optional[str]) -> None:
        order = [fav for fav in self._favorites.values()]
        ids = [fav.id for fav in order]
        if source_id not in ids:
            return
        source = self._favorites[source_id]
        order = [fav for fav in order if fav.id != source_id]
        if target_id and target_id in [fav.id for fav in order]:
            idx = next(i for i, fav in enumerate(order) if fav.id == target_id)
            order.insert(idx, source)
        else:
            order.append(source)
        self._favorites = {fav.id: fav for fav in order}

    def move_by_offset(self, favorite_id: str, offset: int) -> None:
        order = [fav for fav in self._favorites.values()]
        ids = [fav.id for fav in order]
        if favorite_id not in ids or offset == 0:
            return
        index = ids.index(favorite_id)
        new_index = max(0, min(len(order) - 1, index + offset))
        fav = order.pop(index)
        order.insert(new_index, fav)
        self._favorites = {f.id: f for f in order}

    def to_config(self) -> List[dict]:
        return [fav.to_config() for fav in self._favorites.values()]

    def _ensure_unique_id(self, base_id: str) -> str:
        candidate = base_id
        counter = itertools.count(2)
        while candidate in self._favorites:
            candidate = f"{base_id}-{next(counter)}"
        return candidate

    def _prune_invalid(self) -> None:
        to_remove = []
        for fav in self._favorites.values():
            if not self._is_valid(fav):
                to_remove.append(fav.id)
        for fid in to_remove:
            self._favorites.pop(fid, None)

    @staticmethod
    def _is_valid(favorite: FavoriteLocation) -> bool:
        if favorite.kind == "local":
            return bool(favorite.root_path)
        if favorite.kind == "sharepoint":
            return bool(favorite.site_relative_url and favorite.server_relative_url)
        return False


class LayoutManager:
    def __init__(self, cfg: AppConfig) -> None:
        self._cfg = cfg
        self._layouts: Dict[str, LayoutDefinition] = {}
        for entry in getattr(cfg, "saved_layouts", None) or []:
            try:
                layout = LayoutDefinition.from_config(entry)
                self._layouts[layout.id] = layout
            except Exception:
                continue
        self._prune_invalid()

    def all(self) -> List[LayoutDefinition]:
        return list(self._layouts.values())

    def get(self, layout_id: str) -> Optional[LayoutDefinition]:
        return self._layouts.get(layout_id)

    def add(self, layout: LayoutDefinition) -> LayoutDefinition:
        if layout.id in self._layouts:
            layout.id = self._ensure_unique_id(layout.id)
        self._layouts[layout.id] = layout
        self._prune_invalid()
        return layout

    def update(self, layout: LayoutDefinition) -> None:
        self._layouts[layout.id] = layout
        self._prune_invalid()

    def remove(self, layout_id: str) -> None:
        self._layouts.pop(layout_id, None)

    def reorder_before(self, source_id: str, target_id: Optional[str]) -> None:
        order = [layout for layout in self._layouts.values()]
        ids = [layout.id for layout in order]
        if source_id not in ids:
            return
        source = self._layouts[source_id]
        order = [layout for layout in order if layout.id != source_id]
        if target_id and target_id in [layout.id for layout in order]:
            idx = next(i for i, layout in enumerate(order) if layout.id == target_id)
            order.insert(idx, source)
        else:
            order.append(source)
        self._layouts = {layout.id: layout for layout in order}

    def move_by_offset(self, layout_id: str, offset: int) -> None:
        order = [layout for layout in self._layouts.values()]
        ids = [layout.id for layout in order]
        if layout_id not in ids or offset == 0:
            return
        index = ids.index(layout_id)
        new_index = max(0, min(len(order) - 1, index + offset))
        layout = order.pop(index)
        order.insert(new_index, layout)
        self._layouts = {layout.id: layout for layout in order}

    def to_config(self) -> List[dict]:
        return [layout.to_config() for layout in self._layouts.values()]

    def _ensure_unique_id(self, base_id: str) -> str:
        candidate = base_id
        counter = itertools.count(2)
        while candidate in self._layouts:
            candidate = f"{base_id}-{next(counter)}"
        return candidate

    def _prune_invalid(self) -> None:
        to_remove = []
        for layout in self._layouts.values():
            if not layout.workspaces:
                to_remove.append(layout.id)
        for lid in to_remove:
            self._layouts.pop(lid, None)


def ensure_favorites(cfg: AppConfig) -> FavoritesManager:
    mgr = FavoritesManager(cfg)
    cfg.favorites = mgr.to_config()
    return mgr


def ensure_layouts(cfg: AppConfig) -> LayoutManager:
    mgr = LayoutManager(cfg)
    cfg.saved_layouts = mgr.to_config()
    return mgr
