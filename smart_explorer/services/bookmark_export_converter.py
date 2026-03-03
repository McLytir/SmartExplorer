from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

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


@dataclass
class BookmarkLinkRow:
    title: str
    folder_path: str
    url: str


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
        query = parse_qs(parsed.query or "", keep_blank_values=False)
        for key in ("id", "RootFolder", "rootfolder", "FileRef", "SourceUrl", "src"):
            values = query.get(key) or query.get(key.lower()) or query.get(key.upper())
            if values:
                candidate = unquote(str(values[0] or "").strip())
                if candidate.startswith("/"):
                    return candidate.rstrip("/") or "/"
        path = unquote(str(parsed.path or "").strip())
        if path.startswith("/:") and "/r/" in path:
            path = path.split("/r/", 1)[1]
            if not path.startswith("/"):
                path = "/" + path
        if path.startswith("/"):
            return path.rstrip("/") or "/"
        return ""
    if raw.startswith("/"):
        return raw.rstrip("/") or "/"
    return ""


def _resolve_bookmark_web_url(original_url: str, current_path: str, log: LinkMigrationLog, base_url: Optional[str]) -> str:
    direct = log.build_web_url(base_url, current_path)
    if direct:
        return direct
    parsed = urlparse(str(original_url or "").strip())
    if parsed.scheme and parsed.netloc and current_path.startswith("/"):
        return urljoin(f"{parsed.scheme}://{parsed.netloc}", current_path)
    return str(original_url or "").strip()


def parse_bookmark_html_text(html: str) -> list[BookmarkLinkRow]:
    parser = _NetscapeBookmarkParser()
    parser.feed(html)
    return [
        BookmarkLinkRow(
            title=str(row.get("title") or "").strip(),
            folder_path=str(row.get("folder_path") or "").strip(),
            url=str(row.get("url") or "").strip(),
        )
        for row in parser.rows
        if str(row.get("url") or "").strip()
    ]


def parse_bookmark_html(path: str) -> list[BookmarkLinkRow]:
    return parse_bookmark_html_text(Path(path).read_text(encoding="utf-8", errors="replace"))


def detect_bookmark_source_browser(html: str) -> str:
    lowered = html.lower()
    if "netscape-bookmark-file-1" in lowered:
        return "generic_netscape"
    return "generic"


def resolve_bookmark_rows(
    rows: list[BookmarkLinkRow],
    log: LinkMigrationLog,
    base_url: Optional[str] = None,
) -> list[ConvertedBookmark]:
    converted_rows: list[ConvertedBookmark] = []
    for row in rows:
        original_url = str(row.url or "").strip()
        original_path = _extract_server_relative_url(original_url)
        title = str(row.title or original_url or "").strip()
        folder_path = str(row.folder_path or "").strip()
        if not original_url:
            continue
        if not original_path:
            converted_rows.append(
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
        current_url = _resolve_bookmark_web_url(original_url, current_path, log, base_url)
        converted_rows.append(
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
    return converted_rows


def convert_bookmark_html(path: str, log: LinkMigrationLog, base_url: Optional[str] = None) -> list[ConvertedBookmark]:
    return resolve_bookmark_rows(parse_bookmark_html(path), log, base_url)


def build_bookmark_html(rows: list[ConvertedBookmark], title: str = "Bookmarks") -> str:
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        "<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=UTF-8\">",
        f"<TITLE>{escape(title)}</TITLE>",
        f"<H1>{escape(title)}</H1>",
        "<DL><p>",
    ]
    current_folders: list[str] = []
    sorted_rows = sorted(rows, key=lambda row: ((row.folder_path or "").lower(), row.title.lower(), row.current_url.lower()))

    def close_to(depth: int) -> None:
        while len(current_folders) > depth:
            current_folders.pop()
            lines.append("    " * (len(current_folders) + 1) + "</DL><p>")

    for row in sorted_rows:
        folder_parts = [part.strip() for part in str(row.folder_path or "").split(" / ") if part.strip()]
        common = 0
        while common < len(current_folders) and common < len(folder_parts) and current_folders[common] == folder_parts[common]:
            common += 1
        close_to(common)
        for part in folder_parts[common:]:
            lines.append("    " * (len(current_folders) + 1) + f"<DT><H3>{escape(part)}</H3>")
            lines.append("    " * (len(current_folders) + 1) + "<DL><p>")
            current_folders.append(part)
        href = escape(row.current_url or row.original_url or "")
        name = escape(row.title or row.current_url or row.original_url or "Bookmark")
        lines.append("    " * (len(current_folders) + 1) + f"<DT><A HREF=\"{href}\">{name}</A>")

    close_to(0)
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"


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
