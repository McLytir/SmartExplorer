from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


COMMON_URL_KEYS = ("url", "href", "uri", "link")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def save_text(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def append_change(stats: dict[str, Any], original: str, rewritten: str) -> None:
    if original == rewritten:
        return
    stats["updated"] += 1
    samples = stats.setdefault("samples", [])
    if len(samples) < 25:
        samples.append({"old": original, "new": rewritten})


def normalize_path(path: str) -> str:
    value = str(path or "").strip()
    if not value:
        return ""
    if not value.startswith("/"):
        value = "/" + value
    return value.rstrip("/") or "/"


def rewrite_url(url: str, mappings: list[dict]) -> str:
    if not url:
        return url
    for record in reversed(mappings):
        if str(record.get("status") or "").lower() != "completed":
            continue
        old_web = str(record.get("old_web_url") or "").strip()
        new_web = str(record.get("new_web_url") or "").strip()
        if old_web and new_web and url == old_web:
            return new_web

    parsed = urlparse(url)
    current_path = normalize_path(parsed.path)
    for record in reversed(mappings):
        if str(record.get("status") or "").lower() != "completed":
            continue
        old_web = str(record.get("old_web_url") or "").strip()
        new_web = str(record.get("new_web_url") or "").strip()
        old_path = normalize_path(str(record.get("old_server_relative_url") or ""))
        new_path = normalize_path(str(record.get("new_server_relative_url") or ""))
        if not old_path or not new_path:
            continue
        if old_web:
            old_parsed = urlparse(old_web)
            if (parsed.scheme, parsed.netloc) != (old_parsed.scheme, old_parsed.netloc):
                continue
        if current_path == old_path:
            replacement = new_web if new_web else urlunparse(parsed._replace(path=new_path))
            return replacement
        if current_path.startswith(old_path.rstrip("/") + "/"):
            suffix = current_path[len(old_path):]
            rewritten_path = new_path.rstrip("/") + suffix
            if new_web:
                new_parsed = urlparse(new_web)
                return urlunparse(new_parsed._replace(path=rewritten_path))
            return urlunparse(parsed._replace(path=rewritten_path))
    return url


def looks_like_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return bool(parsed.scheme in {"http", "https"} and parsed.netloc)


def update_json_node(
    node: Any,
    mappings: list[dict],
    stats: dict[str, int],
    *,
    url_keys: set[str],
    rewrite_all_strings: bool,
) -> Any:
    if isinstance(node, dict):
        updated: dict[str, Any] = {}
        for key, value in node.items():
            key_lower = str(key).lower()
            if isinstance(value, str) and (key_lower in url_keys or (rewrite_all_strings and looks_like_url(value))):
                rewritten = rewrite_url(value, mappings)
                stats["checked"] += 1
                append_change(stats, value, rewritten)
                updated[key] = rewritten
            else:
                updated[key] = update_json_node(
                    value,
                    mappings,
                    stats,
                    url_keys=url_keys,
                    rewrite_all_strings=rewrite_all_strings,
                )
        return updated
    if isinstance(node, list):
        return [
            update_json_node(
                item,
                mappings,
                stats,
                url_keys=url_keys,
                rewrite_all_strings=rewrite_all_strings,
            )
            for item in node
        ]
    if isinstance(node, str) and rewrite_all_strings and looks_like_url(node):
        rewritten = rewrite_url(node, mappings)
        stats["checked"] += 1
        append_change(stats, node, rewritten)
        return rewritten
    return node


class NetscapeBookmarkRewriter(HTMLParser):
    def __init__(self, mappings: list[dict], stats: dict[str, int]) -> None:
        super().__init__(convert_charrefs=False)
        self.mappings = mappings
        self.stats = stats
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self._render_start_tag(tag, attrs, closing=False))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self._render_start_tag(tag, attrs, closing=True))

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def _render_start_tag(self, tag: str, attrs: list[tuple[str, str | None]], *, closing: bool) -> str:
        rendered: list[str] = []
        for key, value in attrs:
            if value is None:
                rendered.append(key)
                continue
            new_value = value
            if tag.lower() == "a" and key.lower() == "href":
                self.stats["checked"] += 1
                new_value = rewrite_url(value, self.mappings)
                append_change(self.stats, value, new_value)
            escaped = new_value.replace("&", "&amp;").replace('"', "&quot;")
            rendered.append(f'{key}="{escaped}"')
        attrs_str = (" " + " ".join(rendered)) if rendered else ""
        suffix = " /" if closing else ""
        return f"<{tag}{attrs_str}{suffix}>"

    def result(self) -> str:
        return "".join(self.parts)


def update_text_blob(text: str, mappings: list[dict], stats: dict[str, int]) -> str:
    def repl(match: re.Match[str]) -> str:
        original = match.group(0)
        rewritten = rewrite_url(original, mappings)
        stats["checked"] += 1
        append_change(stats, original, rewritten)
        return rewritten

    return URL_PATTERN.sub(repl, text)


def detect_format(path: Path, raw_text: str | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "netscape-html"
    if suffix in {".csv", ".tsv", ".txt", ".md"}:
        return "text"
    if suffix == ".json":
        return "generic-json"
    text = raw_text or ""
    stripped = text.lstrip()
    if stripped.startswith("<!DOCTYPE NETSCAPE-Bookmark-file-1") or "<DT><A " in text.upper():
        return "netscape-html"
    if stripped.startswith("{") or stripped.startswith("["):
        return "generic-json"
    return "text"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rewrite bookmark links using a SmartExplorer link migration log.")
    parser.add_argument("--bookmarks", required=True, help="Input bookmark/export file")
    parser.add_argument("--migrations", required=True, help="Path to smart_explorer_link_migrations.json")
    parser.add_argument("--format", default="auto", choices=["auto", "chromium-json", "generic-json", "netscape-html", "text"], help="Input bookmark file format")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the bookmark file in place")
    parser.add_argument("--output", help="Write updated bookmarks to this path instead")
    parser.add_argument("--backup", action="store_true", help="Create a .bak backup before overwriting")
    parser.add_argument("--url-keys", default="url,href,uri,link", help="Comma-separated JSON keys to treat as bookmark URLs")
    parser.add_argument("--rewrite-all-json-strings", action="store_true", help="For generic JSON, rewrite any string that looks like a URL")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and report bookmark rewrites without writing changes")
    parser.add_argument("--report", help="Write a JSON report describing detected bookmark rewrites")
    args = parser.parse_args()

    bookmarks_path = Path(args.bookmarks).expanduser().resolve()
    migrations_path = Path(args.migrations).expanduser().resolve()
    if not bookmarks_path.exists():
        raise SystemExit(f"Bookmarks file not found: {bookmarks_path}")
    if not migrations_path.exists():
        raise SystemExit(f"Migration log not found: {migrations_path}")
    if not args.dry_run and not args.in_place and not args.output:
        raise SystemExit("Specify either --in-place or --output.")

    mappings = load_json(migrations_path)
    if not isinstance(mappings, list):
        raise SystemExit("Migration file must be a JSON list.")

    raw_text: str | None = None
    fmt = args.format
    if fmt == "auto":
        try:
            raw_text = load_text(bookmarks_path)
        except Exception:
            raw_text = None
        fmt = detect_format(bookmarks_path, raw_text=raw_text)
    elif fmt in {"netscape-html", "text"} and raw_text is None:
        raw_text = load_text(bookmarks_path)

    stats: dict[str, Any] = {"checked": 0, "updated": 0, "samples": []}
    url_keys = {part.strip().lower() for part in args.url_keys.split(",") if part.strip()}

    if fmt == "chromium-json":
        bookmarks = load_json(bookmarks_path)
        updated = update_json_node(bookmarks, mappings, stats, url_keys={"url"}, rewrite_all_strings=False)
        output_kind = "json"
    elif fmt == "generic-json":
        bookmarks = load_json(bookmarks_path)
        updated = update_json_node(
            bookmarks,
            mappings,
            stats,
            url_keys=url_keys or set(COMMON_URL_KEYS),
            rewrite_all_strings=bool(args.rewrite_all_json_strings),
        )
        output_kind = "json"
    elif fmt == "netscape-html":
        html = raw_text if raw_text is not None else load_text(bookmarks_path)
        parser_html = NetscapeBookmarkRewriter(mappings, stats)
        parser_html.feed(html)
        updated = parser_html.result()
        output_kind = "text"
    elif fmt == "text":
        text = raw_text if raw_text is not None else load_text(bookmarks_path)
        updated = update_text_blob(text, mappings, stats)
        output_kind = "text"
    else:
        raise SystemExit(f"Unsupported format: {fmt}")

    target: Path | None = None
    if not args.dry_run:
        if args.in_place:
            if args.backup:
                backup_path = bookmarks_path.with_suffix(bookmarks_path.suffix + ".bak")
                shutil.copy2(bookmarks_path, backup_path)
            target = bookmarks_path
        else:
            target = Path(args.output).expanduser().resolve()

        if output_kind == "json":
            save_json(target, updated)
        else:
            save_text(target, updated)

    report = {
        "bookmarks": str(bookmarks_path),
        "migrations": str(migrations_path),
        "detected_format": fmt,
        "checked": stats["checked"],
        "updated": stats["updated"],
        "dry_run": bool(args.dry_run),
        "output_path": str(target) if target else None,
        "sample_changes": stats.get("samples", []),
    }
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        save_json(report_path, report)

    print(f"Detected format: {fmt}")
    print(f"Checked {stats['checked']} bookmark/url field(s)")
    print(f"Updated {stats['updated']} bookmark/url field(s)")
    if args.report:
        print(f"Wrote report to {Path(args.report).expanduser().resolve()}")
    if args.dry_run:
        print("Dry run complete. No bookmark file was written.")
    else:
        print(f"Wrote output to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
