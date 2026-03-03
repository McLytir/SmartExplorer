from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from .bookmark_export_converter import (
    BookmarkLinkRow,
    ConvertedBookmark,
    build_bookmark_html,
    detect_bookmark_source_browser,
    parse_bookmark_html_text,
    resolve_bookmark_rows,
)
from .link_migration_log import LinkMigrationLog


WORKSPACE_FILENAME = "smart_explorer_relinking_workspace.json"


@dataclass
class RelinkingSummary:
    total: int = 0
    resolved: int = 0
    unchanged: int = 0
    external: int = 0

    @staticmethod
    def from_dict(data: object) -> "RelinkingSummary":
        if not isinstance(data, dict):
            return RelinkingSummary()
        return RelinkingSummary(
            total=int(data.get("total") or 0),
            resolved=int(data.get("resolved") or 0),
            unchanged=int(data.get("unchanged") or 0),
            external=int(data.get("external") or 0),
        )


@dataclass
class RelinkingImportRecord:
    id: str
    name: str
    imported_at: str
    source_path: str
    source_format: str
    source_browser: str
    status: str
    bookmark_rows: list[dict]
    summary: RelinkingSummary

    @staticmethod
    def from_dict(data: object) -> "RelinkingImportRecord":
        if not isinstance(data, dict):
            raise ValueError("Invalid relinking import record")
        return RelinkingImportRecord(
            id=str(data.get("id") or f"relink-import-{uuid.uuid4().hex[:8]}"),
            name=str(data.get("name") or "Imported Bookmarks"),
            imported_at=str(data.get("imported_at") or datetime.now(timezone.utc).isoformat()),
            source_path=str(data.get("source_path") or ""),
            source_format=str(data.get("source_format") or "netscape_html"),
            source_browser=str(data.get("source_browser") or "generic"),
            status=str(data.get("status") or "imported"),
            bookmark_rows=list(data.get("bookmark_rows") or []),
            summary=RelinkingSummary.from_dict(data.get("summary")),
        )


@dataclass
class RelinkingExportRecord:
    id: str
    source_import_id: str
    source_import_name: str
    created_at: str
    format: str
    status: str
    html_title: str
    resolved_rows: list[dict]
    summary: RelinkingSummary

    @staticmethod
    def from_dict(data: object) -> "RelinkingExportRecord":
        if not isinstance(data, dict):
            raise ValueError("Invalid relinking export record")
        return RelinkingExportRecord(
            id=str(data.get("id") or f"relink-export-{uuid.uuid4().hex[:8]}"),
            source_import_id=str(data.get("source_import_id") or ""),
            source_import_name=str(data.get("source_import_name") or "Imported Bookmarks"),
            created_at=str(data.get("created_at") or datetime.now(timezone.utc).isoformat()),
            format=str(data.get("format") or "bookmark_html"),
            status=str(data.get("status") or "resolved"),
            html_title=str(data.get("html_title") or "Bookmarks"),
            resolved_rows=list(data.get("resolved_rows") or []),
            summary=RelinkingSummary.from_dict(data.get("summary")),
        )


class RelinkingWorkspaceStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = os.path.abspath(path or WORKSPACE_FILENAME)
        self._imports: list[RelinkingImportRecord] = []
        self._exports: list[RelinkingExportRecord] = []
        self._load()

    def all_imports(self) -> list[RelinkingImportRecord]:
        return list(self._imports)

    def all_exports(self) -> list[RelinkingExportRecord]:
        return list(self._exports)

    def import_bookmark_html(self, path: str) -> RelinkingImportRecord:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        rows = parse_bookmark_html_text(html)
        record = RelinkingImportRecord(
            id=f"relink-import-{uuid.uuid4().hex[:8]}",
            name=os.path.basename(path) or "Imported Bookmarks",
            imported_at=datetime.now(timezone.utc).isoformat(),
            source_path=os.path.abspath(path),
            source_format="netscape_html",
            source_browser=detect_bookmark_source_browser(html),
            status="imported",
            bookmark_rows=[asdict(row) for row in rows],
            summary=RelinkingSummary(total=len(rows)),
        )
        self._imports.insert(0, record)
        self._save()
        return record

    def resolve_import(self, import_id: str, log: LinkMigrationLog, *, base_url: Optional[str] = None) -> RelinkingExportRecord:
        record = self.get_import(import_id)
        if record is None:
            raise KeyError(f"Unknown relinking import: {import_id}")
        source_rows = [BookmarkLinkRow(**row) for row in record.bookmark_rows if isinstance(row, dict)]
        resolved_rows = resolve_bookmark_rows(source_rows, log, base_url)
        export_record = RelinkingExportRecord(
            id=f"relink-export-{uuid.uuid4().hex[:8]}",
            source_import_id=record.id,
            source_import_name=record.name,
            created_at=datetime.now(timezone.utc).isoformat(),
            format="bookmark_html",
            status="resolved",
            html_title=os.path.splitext(record.name)[0] or "Bookmarks",
            resolved_rows=[asdict(row) for row in resolved_rows],
            summary=self._summary_from_resolved_rows(resolved_rows),
        )
        self._exports.insert(0, export_record)
        self._save()
        return export_record

    def get_import(self, import_id: str) -> Optional[RelinkingImportRecord]:
        return next((item for item in self._imports if item.id == import_id), None)

    def get_export(self, export_id: str) -> Optional[RelinkingExportRecord]:
        return next((item for item in self._exports if item.id == export_id), None)

    def delete_import(self, import_id: str) -> bool:
        before = len(self._imports)
        self._imports = [item for item in self._imports if item.id != import_id]
        self._exports = [item for item in self._exports if item.source_import_id != import_id]
        changed = len(self._imports) != before
        if changed:
            self._save()
        return changed

    def delete_export(self, export_id: str) -> bool:
        before = len(self._exports)
        self._exports = [item for item in self._exports if item.id != export_id]
        changed = len(self._exports) != before
        if changed:
            self._save()
        return changed

    def clear_imports(self) -> int:
        removed = len(self._imports)
        if not removed:
            return 0
        self._imports = []
        self._exports = []
        self._save()
        return removed

    def clear_exports(self) -> int:
        removed = len(self._exports)
        if not removed:
            return 0
        self._exports = []
        self._save()
        return removed

    def export_import_json(self, import_id: str, path: str) -> None:
        record = self.get_import(import_id)
        if record is None:
            raise KeyError(f"Unknown relinking import: {import_id}")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(record), fh, indent=2)

    def export_resolved_json(self, export_id: str, path: str) -> None:
        record = self.get_export(export_id)
        if record is None:
            raise KeyError(f"Unknown relinking export: {export_id}")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(record), fh, indent=2)

    def export_resolved_html(self, export_id: str, path: str) -> None:
        record = self.get_export(export_id)
        if record is None:
            raise KeyError(f"Unknown relinking export: {export_id}")
        resolved_rows = [ConvertedBookmark(**row) for row in record.resolved_rows if isinstance(row, dict)]
        html = build_bookmark_html(resolved_rows, title=record.html_title)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)

    def reload(self) -> None:
        self._load()

    def _summary_from_resolved_rows(self, rows: list[ConvertedBookmark]) -> RelinkingSummary:
        summary = RelinkingSummary(total=len(rows))
        for row in rows:
            if row.status == "resolved":
                summary.resolved += 1
            elif row.status == "external":
                summary.external += 1
            else:
                summary.unchanged += 1
        return summary

    def _load(self) -> None:
        self._imports = []
        self._exports = []
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        for item in raw.get("imports") or []:
            try:
                self._imports.append(RelinkingImportRecord.from_dict(item))
            except Exception:
                continue
        for item in raw.get("exports") or []:
            try:
                self._exports.append(RelinkingExportRecord.from_dict(item))
            except Exception:
                continue

    def _save(self) -> None:
        payload = {
            "imports": [asdict(item) for item in self._imports],
            "exports": [asdict(item) for item in self._exports],
        }
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, self.path)
