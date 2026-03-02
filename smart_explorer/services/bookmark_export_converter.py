from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from .link_migration_log import LinkMigrationLog


@dataclass
class ConvertedBookmark:
    title: str
    folder_path: str
    original_url: str
    original_server_relative_url: str
    current_url: str
    current_server_relative_url: str
    current_site_relative_url: str
    status: str
    notes: str = ""


class _NetscapeBookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._folder_stack: list[str] = []
        self._dl_stack: list[bool] = []
        self._pending_folder: Optional[str] = None
        self._capture_folder = False
        self._capture_link = False
        self._current_folder_text: list[str] = []
        self._current_link_text: list[str] = []
        self._current_link_attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        lower = tag.lower()
        if lower == "h3":
            self._capture_folder = True
            self._current_folder_text = []
            return
        if lower == "dl":
            if self._pending_folder:
                self._folder_stack.append(self._pending_folder)
                self._dl_stack.append(True)
                self._pending_folder = None
            else:
                self._dl_stack.append(False)
            return
        if lower == "a":
            self._capture_link = True
            self._current_link_text = []
            self._current_link_attrs = {str(k or ""): str(v or "") for k, v in attrs}

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "h3":
            self._capture_folder = False
            name = "".join(self._current_folder_text).strip()
            self._pending_folder = name or None
            self._current_folder_text = []
            return
        if lower == "a":
            self._capture_link = False
            title = "".join(self._current_link_text).strip()
            href = str(self._current_link_attrs.get("href") or "").strip()
            if href:
                self.rows.append(
                    {
                        "title": title or href,
                        "folder_path": " / ".join(self._folder_stack),
                        "url": href,
                    }
                )
            self._current_link_text = []
            self._current_link_attrs = {}
            return
        if lower == "dl" and self._dl_stack:
            did_push = self._dl_stack.pop()
            if did_push and self._folder_stack:
                self._folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._capture_folder:
            self._current_folder_text.append(data)
        if self._capture_link:
            self._current_link_text.append(data)


def _extract_server_relative_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return unquote(str(parsed.path or "").strip())
    if raw.startswith("/"):
        return raw
    return ""


def convert_bookmark_html(path: str, log: LinkMigrationLog, base_url: Optional[str] = None) -> list[ConvertedBookmark]:
    parser = _NetscapeBookmarkParser()
    parser.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    rows: list[ConvertedBookmark] = []
    for row in parser.rows:
        original_url = str(row.get("url") or "").strip()
        original_path = _extract_server_relative_url(original_url)
        title = str(row.get("title") or original_url or "").strip()
        folder_path = str(row.get("folder_path") or "").strip()
        if not original_url:
            continue
        if not original_path:
            rows.append(
                ConvertedBookmark(
                    title=title,
                    folder_path=folder_path,
                    original_url=original_url,
                    original_server_relative_url="",
                    current_url=original_url,
                    current_server_relative_url="",
                    current_site_relative_url="",
                    status="external",
                    notes="Bookmark does not contain a SharePoint-style server-relative path.",
                )
            )
            continue
        resolved = log.resolve_target(original_path)
        current_path = str((resolved or {}).get("server_relative_url") or original_path)
        current_site = str((resolved or {}).get("site_relative_url") or "")
        current_url = log.build_web_url(base_url, current_path) or original_url
        rows.append(
            ConvertedBookmark(
                title=title,
                folder_path=folder_path,
                original_url=original_url,
                original_server_relative_url=original_path,
                current_url=current_url,
                current_server_relative_url=current_path,
                current_site_relative_url=current_site,
                status="resolved" if resolved else "unchanged",
                notes="" if resolved else "No migration record matched this bookmark path.",
            )
        )
    return rows


def export_converted_bookmarks_json(path: str, rows: list[ConvertedBookmark]) -> None:
    payload = [asdict(row) for row in rows]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def export_converted_bookmarks_csv(path: str, rows: list[ConvertedBookmark]) -> None:
    headers = list(ConvertedBookmark.__dataclass_fields__.keys())
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
