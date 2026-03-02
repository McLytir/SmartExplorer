from __future__ import annotations

import base64
import fnmatch
import io
import logging
import mimetypes
import os
import posixpath
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import List, Optional, Dict, Tuple
import httpx

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..settings import load_config, save_config, AppConfig
from ..services.ai_summary import AISummarizer, SummaryError, extract_text_snippet
from ..services.ai_rename_planner import AIRenamePlanner, RenamePlanningError
from ..services.tag_store import TagStore
from ..translation_cache import TranslationCache
from ..translators.base import IdentityTranslator, Translator
try:
    from ..translators.openai_translator import OpenAITranslator
except Exception:
    OpenAITranslator = None  # type: ignore[assignment]
from ..sprest.client import SharePointClient


def _is_ignored(path: str, name: str, patterns: List[str]) -> bool:
    parts = os.path.normpath(path).split(os.sep)
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


class ListItem(BaseModel):
    name: str
    path: str
    isDir: bool
    size: int
    mtime: float


class ListResponse(BaseModel):
    path: str
    items: List[ListItem]


class RenameRequest(BaseModel):
    path: str
    newName: str


class RenameResponse(BaseModel):
    newPath: str


class LocalPathResponse(BaseModel):
    path: str


class LocalMkdirRequest(BaseModel):
    path: str
    name: str


class LocalRenameRequest(BaseModel):
    path: str
    new_name: str


class LocalBatchRequest(BaseModel):
    sources: List[str]
    destination: Optional[str] = None


class GlobalSearchRequest(BaseModel):
    query: str
    include_local: bool = True
    include_sharepoint: bool = True
    local_root: Optional[str] = None
    site_relative_url: Optional[str] = None
    library_server_relative_url: Optional[str] = None
    max_results: int = 200
    max_depth: int = 6
    include_dirs: bool = False
    extensions: Optional[List[str]] = None


class GlobalSearchItem(BaseModel):
    kind: str
    name: str
    path: str
    isDir: bool
    size: int = 0
    site_relative_url: Optional[str] = None
    parent: Optional[str] = None


class GlobalSearchResponse(BaseModel):
    results: List[GlobalSearchItem]
    errors: List[str]


class PermissionProbeRequest(BaseModel):
    kind: str = "local"  # local | sharepoint
    path: str
    is_folder: bool = False
    site_relative_url: Optional[str] = None


class BulkDryRunSourceItem(BaseModel):
    kind: str
    path: str
    isDir: bool = False
    name: Optional[str] = None
    site_relative_url: Optional[str] = None


class BulkDryRunRequest(BaseModel):
    operation: str  # copy | move | delete
    conflict_policy: str = "skip"  # skip | fail | overwrite
    destination_kind: Optional[str] = None  # local | sharepoint
    destination_path: Optional[str] = None
    destination_site_relative_url: Optional[str] = None
    sources: List[BulkDryRunSourceItem]


class LocalBulkRenameItem(BaseModel):
    path: str
    new_name: str


class LocalBulkRenameRequest(BaseModel):
    items: List[LocalBulkRenameItem]


class RenamePreviewItem(BaseModel):
    path: str
    new_name: str
    is_folder: Optional[bool] = None


class RenamePreviewRequest(BaseModel):
    items: List[RenamePreviewItem]
    site_relative_url: Optional[str] = None


class LocalOpenRequest(BaseModel):
    path: str
    reveal: bool = False


class LocalWriteRequest(BaseModel):
    destination_dir: str
    filename: str
    content_base64: str
    overwrite: bool = False


class LocalTransferFromSharePointRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_urls: List[str]
    source_items: Optional[List[BulkDryRunSourceItem]] = None
    destination_dir: str
    move: bool = False


class SharePointTransferFromLocalRequest(BaseModel):
    site_relative_url: Optional[str] = None
    source_paths: List[str]
    destination_server_relative_url: str
    move: bool = False
    overwrite: bool = False


class TagGetResponse(BaseModel):
    kind: str
    identifier: str
    tags: List[str]


class TagSetRequest(BaseModel):
    kind: str = "local"
    identifier: str
    tags: List[str]


class TagSearchRequest(BaseModel):
    kind: str = "local"
    tags: List[str]


class SummaryRequest(BaseModel):
    path: str
    preset: str = "short"
    tone: str = "neutral"


class QuestionRequest(BaseModel):
    path: str
    question: str


class ItemAIRequest(BaseModel):
    kind: str = "local"  # local | sharepoint
    path: str
    site_relative_url: Optional[str] = None
    preset: Optional[str] = "short"
    tone: Optional[str] = "neutral"
    question: Optional[str] = None


class AIRenamePlanItem(BaseModel):
    source_path: str
    current_relative_path: str
    is_folder: bool = False


class AIRenamePlanRequest(BaseModel):
    kind: str = "local"  # local | sharepoint
    site_relative_url: Optional[str] = None
    root_name: Optional[str] = None
    instruction: Optional[str] = None
    items: List[AIRenamePlanItem]


class TranslateItem(BaseModel):
    name: str
    path: Optional[str] = None
    mtime: Optional[float] = None


class TranslateRequest(BaseModel):
    language: str
    items: List[TranslateItem]


class TranslateResponse(BaseModel):
    translations: List[str]

class TranslateTextRequest(BaseModel):
    language: Optional[str] = None
    texts: List[str]


class TranslateTextResponse(BaseModel):
    translations: List[str]


class SettingsResponse(BaseModel):
    target_language: str
    model: str
    ignore_patterns: List[str]
    has_api_key: bool
    sp_base_url: Optional[str] = None
    sp_has_cookies: bool = False


class SettingsUpdateRequest(BaseModel):
    target_language: Optional[str] = None
    model: Optional[str] = None
    ignore_patterns: Optional[List[str]] = None
    api_key: Optional[str] = None  # empty string clears
    sp_base_url: Optional[str] = None


def create_translator(cfg: AppConfig) -> Translator:
    api_key = (cfg.api_key or "").strip()
    if not api_key:
        try:
            from ..services import secret_store

            api_key = secret_store.get_secret("OPENAI_API_KEY") or ""
        except Exception:
            api_key = ""
    if api_key and OpenAITranslator is not None:
        return OpenAITranslator(api_key=api_key, model=cfg.model)
    return IdentityTranslator()


def create_rename_planner(cfg: AppConfig) -> Optional[AIRenamePlanner]:
    api_key = (cfg.api_key or "").strip()
    if not api_key:
        try:
            from ..services import secret_store

            api_key = secret_store.get_secret("OPENAI_API_KEY") or ""
        except Exception:
            api_key = ""
    if not api_key:
        return None
    try:
        return AIRenamePlanner(api_key=api_key, model=cfg.model)
    except Exception:
        return None


cfg = load_config()
app = FastAPI(title="SmartExplorer Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_local_path(path: Optional[str]) -> str:
    p = (path or "").strip()
    if not p:
        return os.path.expanduser("~")
    return os.path.abspath(os.path.expanduser(p))


def _list_windows_roots() -> List[ListItem]:
    roots: List[ListItem] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            roots.append(ListItem(name=drive, path=drive, isDir=True, size=0, mtime=0.0))
    return roots


def _local_list(path: str) -> List[ListItem]:
    if os.name == "nt" and path in {"\\", "/", ""}:
        return _list_windows_roots()
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    out: List[ListItem] = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    out.append(
                        ListItem(
                            name=entry.name,
                            path=entry.path,
                            isDir=is_dir,
                            size=0 if is_dir else int(stat.st_size),
                            mtime=float(stat.st_mtime),
                        )
                    )
                except Exception:
                    continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list directory: {exc}")

    out.sort(key=lambda x: (not x.isDir, x.name.lower()))
    return out


def _safe_filename(name: str) -> str:
    cleaned = (name or "").strip().replace("..", "_")
    cleaned = "".join("_" if ch in '<>:"|?*' else ch for ch in cleaned)
    return cleaned or "file"


def _preview_local_rename(items: List[RenamePreviewItem]) -> List[dict]:
    seen_targets: set[str] = set()
    out: List[dict] = []
    for item in items:
        src = _normalize_local_path(item.path)
        new_name = (item.new_name or "").strip()
        result = {"path": src, "new_name": new_name, "ok": False, "reason": ""}
        if not os.path.exists(src):
            result["reason"] = "missing_source"
            out.append(result)
            continue
        if not new_name or new_name in {".", ".."}:
            result["reason"] = "invalid_name"
            out.append(result)
            continue
        dst = os.path.join(os.path.dirname(src), new_name)
        dst_key = os.path.normcase(dst)
        if dst_key in seen_targets:
            result["reason"] = "duplicate_target_in_batch"
            out.append(result)
            continue
        seen_targets.add(dst_key)
        if os.path.normcase(src) == dst_key:
            result["reason"] = "same_name"
            out.append(result)
            continue
        if os.path.exists(dst):
            result["reason"] = "target_exists"
            out.append(result)
            continue
        result["ok"] = True
        result["reason"] = "ok"
        out.append(result)
    return out


def _preview_sp_rename(items: List[RenamePreviewItem], site_relative_url: Optional[str]) -> List[dict]:
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    illegal = set("\\/:*?\"<>|")
    out: List[dict] = []
    seen_targets: set[str] = set()
    parent_to_names: Dict[str, set[str]] = {}

    parents = {((it.path or "").rsplit("/", 1)[0] or "/") for it in items if it.path}
    for parent in parents:
        try:
            folders, files = sp_client.list_children(parent, site_relative_url=site_relative_url)
            names: set[str] = set()
            for row in folders:
                nm = str(row.get("Name") or "").strip()
                if nm:
                    names.add(nm.lower())
            for row in files:
                nm = str(row.get("Name") or "").strip()
                if nm:
                    names.add(nm.lower())
            parent_to_names[parent] = names
        except Exception:
            parent_to_names[parent] = set()

    for item in items:
        src = item.path or ""
        new_name = (item.new_name or "").strip()
        parent = src.rsplit("/", 1)[0] if "/" in src else "/"
        result = {"path": src, "new_name": new_name, "ok": False, "reason": ""}
        if not src:
            result["reason"] = "missing_source"
            out.append(result)
            continue
        if not new_name or any(ch in illegal for ch in new_name):
            result["reason"] = "invalid_name"
            out.append(result)
            continue
        current = src.rsplit("/", 1)[-1]
        if current.lower() == new_name.lower():
            result["reason"] = "same_name"
            out.append(result)
            continue
        target_key = f"{parent}/{new_name}".lower()
        if target_key in seen_targets:
            result["reason"] = "duplicate_target_in_batch"
            out.append(result)
            continue
        seen_targets.add(target_key)
        existing = parent_to_names.get(parent, set())
        if new_name.lower() in existing:
            result["reason"] = "target_exists"
            out.append(result)
            continue
        result["ok"] = True
        result["reason"] = "ok"
        out.append(result)
    return out


def _search_name_match(name: str, query: str) -> bool:
    return query in (name or "").lower()


def _search_ext_match(name: str, extensions: Optional[set[str]]) -> bool:
    if not extensions:
        return True
    ext = os.path.splitext(name or "")[1].lower()
    return ext in extensions


def _global_search_local(req: GlobalSearchRequest, query: str, ext_filter: Optional[set[str]], errors: List[str]) -> List[GlobalSearchItem]:
    root = _normalize_local_path(req.local_root)
    if not os.path.isdir(root):
        errors.append(f"Local root not found: {root}")
        return []
    max_results = max(1, min(int(req.max_results or 200), 2000))
    max_depth = max(0, min(int(req.max_depth or 6), 32))
    include_dirs = bool(req.include_dirs)

    out: List[GlobalSearchItem] = []
    root_depth = root.rstrip("\\/").count(os.sep)
    try:
        for cur, dirs, files in os.walk(root, topdown=True, followlinks=False):
            rel_depth = cur.rstrip("\\/").count(os.sep) - root_depth
            if rel_depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not _is_ignored(os.path.join(cur, d), d, cfg.ignore_patterns)]

            if include_dirs:
                for d in dirs:
                    if len(out) >= max_results:
                        return out
                    full = os.path.join(cur, d)
                    if _search_name_match(d, query):
                        out.append(GlobalSearchItem(
                            kind="local",
                            name=d,
                            path=full,
                            isDir=True,
                            size=0,
                            parent=cur,
                        ))
            for f in files:
                if len(out) >= max_results:
                    return out
                if _is_ignored(os.path.join(cur, f), f, cfg.ignore_patterns):
                    continue
                if not _search_name_match(f, query):
                    continue
                if not _search_ext_match(f, ext_filter):
                    continue
                full = os.path.join(cur, f)
                size = 0
                try:
                    size = int(os.path.getsize(full))
                except Exception:
                    size = 0
                out.append(GlobalSearchItem(
                    kind="local",
                    name=f,
                    path=full,
                    isDir=False,
                    size=size,
                    parent=cur,
                ))
    except Exception as exc:
        errors.append(f"Local search failed: {exc}")
    return out


def _global_search_sharepoint(req: GlobalSearchRequest, query: str, ext_filter: Optional[set[str]], errors: List[str]) -> List[GlobalSearchItem]:
    if not sp_client:
        errors.append("SharePoint base URL not configured")
        return []
    max_results = max(1, min(int(req.max_results or 200), 2000))
    max_depth = max(0, min(int(req.max_depth or 6), 32))
    include_dirs = bool(req.include_dirs)
    out: List[GlobalSearchItem] = []

    site = req.site_relative_url
    root = req.library_server_relative_url
    if not root:
        try:
            libs = sp_client.list_libraries(site_relative_url=site)
            if libs:
                root = libs[0].get("server_relative_url")
        except Exception as exc:
            errors.append(f"Failed to resolve SharePoint library: {exc}")
            return []
    if not root:
        errors.append("SharePoint library root not resolved")
        return []

    queue: List[Tuple[str, int]] = [(root, 0)]
    visited: set[str] = set()
    while queue and len(out) < max_results:
        folder, depth = queue.pop(0)
        key = f"{site or ''}|{folder}"
        if key in visited:
            continue
        visited.add(key)
        try:
            folders, files = sp_client.list_children(folder, site_relative_url=site)
        except Exception as exc:
            errors.append(f"SharePoint list failed for {folder}: {exc}")
            continue

        for row in folders:
            name = str(row.get("Name") or "")
            path = str(row.get("ServerRelativeUrl") or "")
            if include_dirs and _search_name_match(name, query):
                out.append(GlobalSearchItem(
                    kind="sharepoint",
                    name=name,
                    path=path,
                    isDir=True,
                    size=0,
                    site_relative_url=site,
                    parent=folder,
                ))
                if len(out) >= max_results:
                    break
            if depth < max_depth and path:
                queue.append((path, depth + 1))
        if len(out) >= max_results:
            break
        for row in files:
            if len(out) >= max_results:
                break
            name = str(row.get("Name") or "")
            if not _search_name_match(name, query):
                continue
            if not _search_ext_match(name, ext_filter):
                continue
            path = str(row.get("ServerRelativeUrl") or "")
            size = 0
            try:
                size = int(row.get("Length") or 0)
            except Exception:
                size = 0
            out.append(GlobalSearchItem(
                kind="sharepoint",
                name=name,
                path=path,
                isDir=False,
                size=size,
                site_relative_url=site,
                parent=folder,
            ))
    return out


def _destination_existing_names(kind: Optional[str], path: Optional[str], site_relative_url: Optional[str]) -> set[str]:
    names: set[str] = set()
    if kind == "local":
        p = _normalize_local_path(path)
        if not os.path.isdir(p):
            raise HTTPException(status_code=404, detail=f"Destination not found: {p}")
        try:
            with os.scandir(p) as it:
                for e in it:
                    names.add((e.name or "").lower())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to inspect local destination: {exc}")
        return names
    if kind == "sharepoint":
        if not sp_client:
            raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
        folder = path or "/"
        try:
            folders, files = sp_client.list_children(folder, site_relative_url=site_relative_url)
            for row in folders:
                names.add(str(row.get("Name") or "").lower())
            for row in files:
                names.add(str(row.get("Name") or "").lower())
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to inspect SharePoint destination: {exc}")
        return names
    return names


def _sp_name(path: str) -> str:
    value = str(path or "").rstrip("/")
    return posixpath.basename(value) or value or "item"


def _collect_sharepoint_download_entries(
    source_items: List[BulkDryRunSourceItem],
    *,
    site_relative_url: Optional[str],
) -> List[dict]:
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    out: List[dict] = []
    seen_files: set[str] = set()
    seen_dirs: set[str] = set()

    def add_dir(rel_path: str) -> None:
        rel = str(rel_path or "").strip("/").replace("\\", "/")
        if not rel or rel in seen_dirs:
            return
        seen_dirs.add(rel)
        out.append({"kind": "dir", "relative_path": rel})

    def add_file(server_path: str, rel_path: str) -> None:
        rel = str(rel_path or "").strip("/").replace("\\", "/")
        if not rel or rel in seen_files:
            return
        seen_files.add(rel)
        out.append({"kind": "file", "server_relative_url": server_path, "relative_path": rel})

    def walk_folder(folder_path: str, rel_prefix: str) -> None:
        normalized_prefix = str(rel_prefix or "").strip("/").replace("\\", "/")
        if normalized_prefix:
            add_dir(normalized_prefix)
        folders, files = sp_client.list_children(folder_path, site_relative_url=site_relative_url)
        for row in folders:
            child_path = str(row.get("ServerRelativeUrl") or "")
            child_name = _safe_filename(str(row.get("Name") or _sp_name(child_path)))
            child_rel = "/".join(part for part in [normalized_prefix, child_name] if part)
            walk_folder(child_path, child_rel)
        for row in files:
            child_path = str(row.get("ServerRelativeUrl") or "")
            child_name = _safe_filename(str(row.get("Name") or _sp_name(child_path)))
            child_rel = "/".join(part for part in [normalized_prefix, child_name] if part)
            add_file(child_path, child_rel)

    for item in source_items:
        src = str(item.path or "").strip()
        if not src:
            continue
        top_name = _safe_filename(str(item.name or _sp_name(src)))
        if bool(item.isDir):
            walk_folder(src, top_name)
        else:
            add_file(src, top_name)
    return out


def _safe_extract_zip_to_dir(zip_path: str, destination_dir: str) -> int:
    dest_root = os.path.abspath(destination_dir)
    extracted = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            rel_name = info.filename.replace("\\", "/").strip("/")
            if not rel_name:
                continue
            target_path = os.path.abspath(os.path.join(dest_root, rel_name))
            if target_path != dest_root and not target_path.startswith(dest_root + os.sep):
                raise HTTPException(status_code=400, detail=f"Unsafe archive entry: {info.filename}")
            if info.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(info) as src_fh, open(target_path, "wb") as dst_fh:
                shutil.copyfileobj(src_fh, dst_fh)
            extracted += 1
    return extracted


def _prepare_item_for_ai(kind: str, path: str, site_relative_url: Optional[str]) -> tuple[str, Optional[str]]:
    item_kind = (kind or "local").strip().lower()
    if item_kind == "local":
        local_path = _normalize_local_path(path)
        if not os.path.isfile(local_path):
            raise HTTPException(status_code=404, detail=f"File not found: {local_path}")
        return local_path, None
    if item_kind == "sharepoint":
        if not sp_client:
            raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
        try:
            content = sp_client.download_file(path, site_relative_url=site_relative_url)
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"SharePoint download failed: {exc}")
        suffix = os.path.splitext(path)[1] or ".bin"
        tmp = tempfile.NamedTemporaryFile(prefix="smx_ai_", suffix=suffix, delete=False)
        tmp.write(content)
        tmp.close()
        return tmp.name, tmp.name
    raise HTTPException(status_code=400, detail=f"Unsupported kind: {kind}")


def _prepare_rename_plan_item(
    kind: str,
    path: str,
    current_relative_path: str,
    is_folder: bool,
    site_relative_url: Optional[str],
) -> tuple[dict, Optional[str]]:
    if not rename_planner:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    item_kind = (kind or "local").strip().lower()
    temp_path: Optional[str] = None
    excerpt_path: Optional[str] = None
    if not is_folder:
        try:
            excerpt_path, temp_path = _prepare_item_for_ai(item_kind, path, site_relative_url)
        except HTTPException:
            excerpt_path = None
            temp_path = None
    planner_item = rename_planner.build_item(
        source_path=path,
        current_relative_path=current_relative_path,
        is_dir=is_folder,
        text_source_path=excerpt_path,
    )
    return {
        "source_path": planner_item.source_path,
        "current_relative_path": planner_item.current_relative_path,
        "name": planner_item.name,
        "is_dir": planner_item.is_dir,
        "parent_relative_path": planner_item.parent_relative_path,
        "text_excerpt": planner_item.text_excerpt,
    }, temp_path


translator = create_translator(cfg)
rename_planner = create_rename_planner(cfg)
cache = TranslationCache()
tag_store = TagStore()
_local_rename_undo_stack: List[List[Dict[str, str]]] = []
sp_client: Optional[SharePointClient] = None
if getattr(cfg, "sp_base_url", None):
    try:
        sp_client = SharePointClient(cfg.sp_base_url)  # type: ignore[arg-type]
    except Exception:
        sp_client = None

# SharePoint folder cache with background prefetch
_SP_LIST_TTL = 300.0
_SP_PREFETCH_LIMIT = 5
_sp_list_cache: Dict[str, tuple[float, list[dict], list[dict]]] = {}
_sp_cache_lock = Lock()
_prefetch_executor = ThreadPoolExecutor(max_workers=4)
_SP_SITES_TTL = 600.0
_sp_sites_cache: Optional[tuple[float, List[dict]]] = None
_SP_LIB_TTL = 300.0
_sp_libraries_cache: Dict[str, tuple[float, List[dict]]] = {}

# Small in-memory LRU cache for frequent names to reduce API calls
from collections import OrderedDict

_MEM_CACHE_MAX = 500
_mem_cache: "OrderedDict[str, str]" = OrderedDict()

_web_dir = Path(__file__).resolve().parent.parent / "web"
if _web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(_web_dir), html=True), name="web")


def _create_summarizer() -> Optional[AISummarizer]:
    api_key = (cfg.api_key or "").strip()
    if not api_key:
        try:
            from ..services import secret_store

            api_key = secret_store.get_secret("OPENAI_API_KEY") or ""
        except Exception:
            api_key = ""
    if not api_key:
        return None
    try:
        return AISummarizer(api_key=api_key, model=cfg.model, timeout=45.0)
    except Exception:
        return None


def _mem_get(key: str) -> Optional[str]:
    try:
        val = _mem_cache.pop(key)
        _mem_cache[key] = val
        return val
    except KeyError:
        return None


def _mem_put(key: str, value: str) -> None:
    if key in _mem_cache:
        _mem_cache.pop(key)
    _mem_cache[key] = value
    while len(_mem_cache) > _MEM_CACHE_MAX:
        _mem_cache.popitem(last=False)


def _translator_namespace(language: str) -> str:
    try:
        key = translator.cache_namespace()
    except Exception:
        key = translator.__class__.__name__
    return f"{language}|{key}"


def _mem_key(language: str, name: str) -> str:
    return f"{_translator_namespace(language)}\n{name}"


def _cache_key(site: Optional[str], path: str) -> str:
    return f"{site or ''}|{path}"


def _cache_get(site: Optional[str], path: str) -> Optional[tuple[float, list[dict], list[dict]]]:
    with _sp_cache_lock:
        return _sp_list_cache.get(_cache_key(site, path))


def _cache_put(site: Optional[str], path: str, folders: list[dict], files: list[dict]) -> None:
    with _sp_cache_lock:
        _sp_list_cache[_cache_key(site, path)] = (time.time(), folders, files)


def _prefetch_folder(path: str, site: Optional[str]) -> None:
    global sp_client
    client = sp_client
    if not client:
        return
    try:
        cached = _cache_get(site, path)
        if cached and (time.time() - cached[0]) < _SP_LIST_TTL:
            return
        folders, files = client.list_children(path, site_relative_url=site)
        _cache_put(site, path, folders, files)
    except Exception:
        pass


def _schedule_prefetch(folders: List[dict], site: Optional[str]) -> None:
    if not folders:
        return
    scheduled = 0
    for entry in folders:
        path = entry.get("ServerRelativeUrl") or entry.get("path")
        if not path:
            continue
        if scheduled >= _SP_PREFETCH_LIMIT:
            break
        _prefetch_executor.submit(_prefetch_folder, path, site)
        scheduled += 1


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/local/home", response_model=LocalPathResponse)
def local_home():
    return LocalPathResponse(path=os.path.expanduser("~"))


@app.get("/api/local/list", response_model=ListResponse)
def local_list(path: Optional[str] = Query(None)):
    normalized = _normalize_local_path(path)
    items = _local_list(normalized)
    return ListResponse(path=normalized, items=items)


@app.post("/api/search/global", response_model=GlobalSearchResponse)
def global_search(req: GlobalSearchRequest):
    q = (req.query or "").strip().lower()
    if not q:
        return GlobalSearchResponse(results=[], errors=[])
    ext_filter: Optional[set[str]] = None
    if req.extensions:
        normalized = set()
        for raw in req.extensions:
            e = (raw or "").strip().lower()
            if not e:
                continue
            if not e.startswith("."):
                e = "." + e
            normalized.add(e)
        if normalized:
            ext_filter = normalized

    errors: List[str] = []
    out: List[GlobalSearchItem] = []
    limit = max(1, min(int(req.max_results or 200), 2000))

    if req.include_local:
        rows = _global_search_local(req, q, ext_filter, errors)
        out.extend(rows[: max(0, limit - len(out))])
    if req.include_sharepoint and len(out) < limit:
        rows = _global_search_sharepoint(req, q, ext_filter, errors)
        out.extend(rows[: max(0, limit - len(out))])

    return GlobalSearchResponse(results=out[:limit], errors=errors[:50])


@app.post("/api/permissions/probe")
def permissions_probe(req: PermissionProbeRequest):
    kind = (req.kind or "local").strip().lower()
    if kind == "local":
        p = _normalize_local_path(req.path)
        exists = os.path.exists(p)
        parent = os.path.dirname(p) if not req.is_folder else p
        return {
            "kind": "local",
            "path": p,
            "exists": exists,
            "can_read": bool(exists and os.access(p, os.R_OK)),
            "can_write": bool(exists and os.access(p, os.W_OK)),
            "can_execute": bool(exists and os.access(p, os.X_OK)),
            "can_delete": bool(parent and os.path.isdir(parent) and os.access(parent, os.W_OK)),
        }
    if kind == "sharepoint":
        if not sp_client:
            raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
        try:
            perms = sp_client.get_effective_permissions(
                req.path,
                is_folder=bool(req.is_folder),
                site_relative_url=req.site_relative_url,
            )
            return {
                "kind": "sharepoint",
                "path": req.path,
                "site_relative_url": req.site_relative_url,
                **perms,
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to probe SharePoint permissions: {exc}")
    raise HTTPException(status_code=400, detail=f"Unsupported kind: {req.kind}")


@app.post("/api/bulk/dry-run")
def bulk_dry_run(req: BulkDryRunRequest):
    op = (req.operation or "").strip().lower()
    if op not in {"copy", "move", "delete"}:
        raise HTTPException(status_code=400, detail="Unsupported operation")
    policy = (req.conflict_policy or "skip").strip().lower()
    if policy not in {"skip", "fail", "overwrite"}:
        policy = "skip"
    rows: List[dict] = []
    errors: List[str] = []
    if not req.sources:
        return {"ok": True, "rows": [], "summary": {"total": 0, "ready": 0, "blocked": 0}}

    existing_names: set[str] = set()
    if op != "delete":
        existing_names = _destination_existing_names(
            (req.destination_kind or "").strip().lower(),
            req.destination_path,
            req.destination_site_relative_url,
        )

    blocked = 0
    for src in req.sources:
        name = (src.name or os.path.basename(src.path or "") or "").strip()
        path = src.path or ""
        if not path:
            blocked += 1
            rows.append({"path": path, "status": "blocked", "reason": "missing_path"})
            continue
        if op == "delete":
            rows.append({"path": path, "status": "ok", "reason": "delete"})
            continue
        conflict = name.lower() in existing_names if name else False
        if conflict and policy != "overwrite":
            blocked += 1
            rows.append({"path": path, "status": "blocked", "reason": "target_exists"})
        else:
            rows.append({"path": path, "status": "ok", "reason": "overwrite" if conflict else "ok"})

    ready = len(rows) - blocked
    return {
        "ok": blocked == 0,
        "rows": rows,
        "errors": errors[:50],
        "summary": {"total": len(rows), "ready": ready, "blocked": blocked},
    }


@app.post("/api/local/mkdir", response_model=LocalPathResponse)
def local_mkdir(req: LocalMkdirRequest):
    parent = _normalize_local_path(req.path)
    if not os.path.isdir(parent):
        raise HTTPException(status_code=404, detail=f"Directory not found: {parent}")
    name = (req.name or "").strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid directory name")
    target = os.path.join(parent, name)
    try:
        os.makedirs(target, exist_ok=False)
    except FileExistsError:
        raise HTTPException(status_code=409, detail=f"Path already exists: {target}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {exc}")
    return LocalPathResponse(path=target)


@app.post("/api/local/rename", response_model=LocalPathResponse)
def local_rename(req: LocalRenameRequest):
    src = _normalize_local_path(req.path)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail=f"Path not found: {src}")
    new_name = (req.new_name or "").strip()
    if not new_name or new_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid new name")
    dst = os.path.join(os.path.dirname(src), new_name)
    if os.path.exists(dst):
        raise HTTPException(status_code=409, detail=f"Path already exists: {dst}")
    try:
        os.rename(src, dst)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rename failed: {exc}")
    return LocalPathResponse(path=dst)


@app.post("/api/local/copy")
def local_copy(req: LocalBatchRequest):
    destination = _normalize_local_path(req.destination)
    if not os.path.isdir(destination):
        raise HTTPException(status_code=404, detail=f"Destination not found: {destination}")
    if not req.sources:
        return {"ok": True, "copied": 0}

    copied = 0
    errors: List[str] = []
    for src_raw in req.sources:
        src = _normalize_local_path(src_raw)
        if not os.path.exists(src):
            errors.append(f"Missing: {src}")
            continue
        dst = os.path.join(destination, os.path.basename(src))
        if os.path.exists(dst):
            errors.append(f"Exists: {dst}")
            continue
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            copied += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    return {"ok": len(errors) == 0, "copied": copied, "errors": errors}


@app.post("/api/local/move")
def local_move(req: LocalBatchRequest):
    destination = _normalize_local_path(req.destination)
    if not os.path.isdir(destination):
        raise HTTPException(status_code=404, detail=f"Destination not found: {destination}")
    if not req.sources:
        return {"ok": True, "moved": 0}

    moved = 0
    errors: List[str] = []
    for src_raw in req.sources:
        src = _normalize_local_path(src_raw)
        if not os.path.exists(src):
            errors.append(f"Missing: {src}")
            continue
        dst = os.path.join(destination, os.path.basename(src))
        if os.path.exists(dst):
            errors.append(f"Exists: {dst}")
            continue
        try:
            shutil.move(src, dst)
            moved += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    return {"ok": len(errors) == 0, "moved": moved, "errors": errors}


@app.post("/api/local/delete")
def local_delete(req: LocalBatchRequest):
    if not req.sources:
        return {"ok": True, "deleted": 0}

    deleted = 0
    errors: List[str] = []
    for src_raw in req.sources:
        src = _normalize_local_path(src_raw)
        if not os.path.exists(src):
            errors.append(f"Missing: {src}")
            continue
        try:
            if os.path.isdir(src):
                shutil.rmtree(src)
            else:
                os.remove(src)
            deleted += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    return {"ok": len(errors) == 0, "deleted": deleted, "errors": errors}


@app.post("/api/local/bulk-rename")
def local_bulk_rename(req: LocalBulkRenameRequest):
    if not req.items:
        return {"ok": True, "renamed": 0, "errors": []}
    batch_undo: List[Dict[str, str]] = []
    renamed = 0
    errors: List[str] = []
    for item in req.items:
        src = _normalize_local_path(item.path)
        if not os.path.exists(src):
            errors.append(f"Missing: {src}")
            continue
        new_name = (item.new_name or "").strip()
        if not new_name or new_name in {".", ".."}:
            errors.append(f"Invalid name for {src}")
            continue
        dst = os.path.join(os.path.dirname(src), new_name)
        if os.path.exists(dst):
            errors.append(f"Exists: {dst}")
            continue
        try:
            os.rename(src, dst)
            batch_undo.append({"old": src, "new": dst})
            renamed += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    if batch_undo:
        _local_rename_undo_stack.append(batch_undo)
    return {"ok": len(errors) == 0, "renamed": renamed, "errors": errors}


@app.post("/api/local/rename-preview")
def local_rename_preview(req: RenamePreviewRequest):
    return {"items": _preview_local_rename(req.items or [])}


@app.post("/api/local/undo-rename")
def local_undo_rename():
    if not _local_rename_undo_stack:
        return {"ok": True, "undone": 0, "errors": []}
    batch = _local_rename_undo_stack.pop()
    undone = 0
    errors: List[str] = []
    for op in reversed(batch):
        src = op.get("new") or ""
        dst = op.get("old") or ""
        if not src or not dst:
            continue
        if not os.path.exists(src):
            errors.append(f"Missing: {src}")
            continue
        try:
            os.rename(src, dst)
            undone += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    return {"ok": len(errors) == 0, "undone": undone, "errors": errors}


@app.post("/api/local/open")
def local_open(req: LocalOpenRequest):
    path = _normalize_local_path(req.path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    try:
        if req.reveal:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            if sys.platform.startswith("win"):
                if os.path.isfile(path):
                    subprocess.Popen(["explorer.exe", "/select,", path])
                else:
                    subprocess.Popen(["explorer.exe", target])
            elif sys.platform == "darwin":
                if os.path.isfile(path):
                    subprocess.Popen(["open", "-R", path])
                else:
                    subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        else:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open path: {exc}")
    return {"ok": True}


@app.get("/api/local/download")
def local_download(path: str = Query(...)):
    normalized = _normalize_local_path(path)
    if not os.path.isfile(normalized):
        raise HTTPException(status_code=404, detail=f"File not found: {normalized}")
    filename = os.path.basename(normalized) or "download"
    mime, _ = mimetypes.guess_type(filename)
    media_type = mime or "application/octet-stream"
    with open(normalized, "rb") as fh:
        data = fh.read()
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": _build_content_disposition(filename)},
    )


@app.post("/api/local/write", response_model=LocalPathResponse)
def local_write(req: LocalWriteRequest):
    destination_dir = _normalize_local_path(req.destination_dir)
    if not os.path.isdir(destination_dir):
        raise HTTPException(status_code=404, detail=f"Destination not found: {destination_dir}")
    filename = _safe_filename(req.filename)
    target = os.path.join(destination_dir, filename)
    if os.path.exists(target) and not req.overwrite:
        raise HTTPException(status_code=409, detail=f"Path already exists: {target}")
    try:
        content = base64.b64decode(req.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    try:
        with open(target, "wb") as fh:
            fh.write(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Write failed: {exc}")
    return LocalPathResponse(path=target)


@app.post("/api/transfer/sp-to-local")
def transfer_sharepoint_to_local(req: LocalTransferFromSharePointRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    destination_dir = _normalize_local_path(req.destination_dir)
    if not os.path.isdir(destination_dir):
        raise HTTPException(status_code=404, detail=f"Destination not found: {destination_dir}")
    source_items = list(req.source_items or [])
    if not source_items:
        source_items = [
            BulkDryRunSourceItem(
                kind="sharepoint",
                path=src,
                isDir=False,
                name=_sp_name(src),
                site_relative_url=req.site_relative_url,
            )
            for src in (req.server_relative_urls or [])
            if src
        ]
    transferred = 0
    errors: List[str] = []
    uses_archive = len(source_items) > 1 or any(bool(item.isDir) for item in source_items)

    if not uses_archive and len(source_items) == 1:
        item = source_items[0]
        try:
            content = sp_client.download_file(item.path, site_relative_url=req.site_relative_url)
            name = _safe_filename(str(item.name or _sp_name(item.path)))
            target = os.path.join(destination_dir, name)
            if os.path.exists(target):
                errors.append(f"Exists: {target}")
            else:
                with open(target, "wb") as fh:
                    fh.write(content)
                transferred = 1
                if req.move:
                    try:
                        sp_client.delete_item(item.path, is_folder=False, site_relative_url=req.site_relative_url, recycle=True)
                    except Exception:
                        pass
        except Exception as exc:
            errors.append(f"{item.path}: {exc}")
        return {"ok": len(errors) == 0, "transferred": transferred, "errors": errors, "mode": "direct"}

    archive_entries: List[dict] = []
    archive_path = ""
    try:
        archive_entries = _collect_sharepoint_download_entries(source_items, site_relative_url=req.site_relative_url)
        if not archive_entries:
            return {"ok": False, "transferred": 0, "errors": ["No SharePoint content resolved for download."], "mode": "archive"}
        fd, archive_path = tempfile.mkstemp(prefix="smx-sp-download-", suffix=".zip")
        os.close(fd)
        with zipfile.ZipFile(archive_path, mode="w", compression=getattr(zipfile, "ZIP_DEFLATED", zipfile.ZIP_STORED)) as zf:
            for entry in archive_entries:
                rel_path = str(entry.get("relative_path") or "").replace("\\", "/").strip("/")
                if not rel_path:
                    continue
                if entry.get("kind") == "dir":
                    zf.writestr(rel_path.rstrip("/") + "/", b"")
                    continue
                content = sp_client.download_file(str(entry.get("server_relative_url") or ""), site_relative_url=req.site_relative_url)
                zf.writestr(rel_path, content)
        transferred = _safe_extract_zip_to_dir(archive_path, destination_dir)
        if req.move:
            for item in source_items:
                try:
                    sp_client.delete_item(
                        str(item.path or ""),
                        is_folder=bool(item.isDir),
                        site_relative_url=req.site_relative_url,
                        recycle=True,
                    )
                except Exception:
                    pass
        return {
            "ok": True,
            "transferred": transferred,
            "errors": [],
            "mode": "archive_extract",
            "archive_entries": len(archive_entries),
        }
    except Exception as exc:
        errors.append(str(exc))
        return {"ok": False, "transferred": transferred, "errors": errors, "mode": "archive"}
    finally:
        if archive_path:
            try:
                os.remove(archive_path)
            except Exception:
                pass


@app.post("/api/transfer/local-to-sp")
def transfer_local_to_sharepoint(req: SharePointTransferFromLocalRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    if not req.destination_server_relative_url:
        raise HTTPException(status_code=400, detail="destination_server_relative_url is required")
    transferred = 0
    errors: List[str] = []
    for src_raw in req.source_paths:
        src = _normalize_local_path(src_raw)
        if not os.path.isfile(src):
            errors.append(f"Not a file: {src}")
            continue
        try:
            with open(src, "rb") as fh:
                data = fh.read()
            name = _safe_filename(os.path.basename(src))
            sp_client.upload_file(
                req.destination_server_relative_url,
                name,
                data,
                site_relative_url=req.site_relative_url,
                overwrite=req.overwrite,
            )
            if req.move:
                try:
                    os.remove(src)
                except Exception:
                    pass
            transferred += 1
        except Exception as exc:
            errors.append(f"{src}: {exc}")
    return {"ok": len(errors) == 0, "transferred": transferred, "errors": errors}


@app.get("/api/tags/stats")
def tags_stats(kind: str = Query("local")):
    return {"kind": kind, "stats": tag_store.tag_stats(kind)}


@app.get("/api/tags/get", response_model=TagGetResponse)
def tags_get(kind: str = Query("local"), identifier: str = Query(...)):
    return TagGetResponse(kind=kind, identifier=identifier, tags=tag_store.get_tags(kind, identifier))


@app.post("/api/tags/set")
def tags_set(req: TagSetRequest):
    tag_store.set_tags(req.kind, req.identifier, req.tags)
    return {"ok": True, "tags": tag_store.get_tags(req.kind, req.identifier)}


@app.post("/api/tags/search")
def tags_search(req: TagSearchRequest):
    return {"kind": req.kind, "results": tag_store.find_paths_for_tags(req.kind, req.tags)}


@app.post("/api/ai/summary")
def ai_summary(req: SummaryRequest):
    path = _normalize_local_path(req.path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    summarizer = _create_summarizer()
    if summarizer is None:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    try:
        result = summarizer.summarize_file(path, preset=req.preset, tone=req.tone)
        return {"preset": result.preset, "tone": result.tone, "summary": result.summary}
    except SummaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Summary failed: {exc}")


@app.post("/api/ai/question")
def ai_question(req: QuestionRequest):
    path = _normalize_local_path(req.path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    summarizer = _create_summarizer()
    if summarizer is None:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    try:
        answer = summarizer.ask_question(path, req.question)
        return {"answer": answer}
    except SummaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question failed: {exc}")


@app.post("/api/ai/summary-item")
def ai_summary_item(req: ItemAIRequest):
    summarizer = _create_summarizer()
    if summarizer is None:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    temp_path: Optional[str] = None
    local_path, temp_path = _prepare_item_for_ai(req.kind, req.path, req.site_relative_url)
    try:
        result = summarizer.summarize_file(local_path, preset=req.preset or "short", tone=req.tone or "neutral")
        return {"preset": result.preset, "tone": result.tone, "summary": result.summary}
    except SummaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Summary failed: {exc}")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/ai/question-item")
def ai_question_item(req: ItemAIRequest):
    summarizer = _create_summarizer()
    if summarizer is None:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    if not (req.question or "").strip():
        raise HTTPException(status_code=400, detail="Question is required.")
    temp_path: Optional[str] = None
    local_path, temp_path = _prepare_item_for_ai(req.kind, req.path, req.site_relative_url)
    try:
        answer = summarizer.ask_question(local_path, req.question or "")
        return {"answer": answer}
    except SummaryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Question failed: {exc}")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/ai/rename-plan")
def ai_rename_plan(req: AIRenamePlanRequest):
    if not rename_planner:
        raise HTTPException(status_code=400, detail="OpenAI key is not configured.")
    if not req.items:
        return {"summary": "", "warnings": ["No items were provided."], "operations": []}
    from ..services.ai_rename_planner import RenamePlannerItem

    planner_items: list[dict] = []
    temp_paths: list[str] = []
    try:
        for item in req.items:
            planner_item, temp_path = _prepare_rename_plan_item(
                req.kind,
                item.source_path,
                item.current_relative_path,
                bool(item.is_folder),
                req.site_relative_url,
            )
            planner_items.append(planner_item)
            if temp_path:
                temp_paths.append(temp_path)
        plan = rename_planner.plan(
            [
                RenamePlannerItem(
                    source_path=entry["source_path"],
                    current_relative_path=entry["current_relative_path"],
                    name=entry["name"],
                    is_dir=bool(entry["is_dir"]),
                    parent_relative_path=entry["parent_relative_path"],
                    text_excerpt=entry["text_excerpt"],
                )
                for entry in planner_items
            ],
            instruction=req.instruction or "",
            root_name=req.root_name or "",
        )
        return plan
    except RenamePlanningError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rename planning failed: {exc}")
    finally:
        for temp_path in temp_paths:
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.get("/api/local/extract-text")
def local_extract_text(path: str = Query(...), limit: int = Query(8000)):
    normalized = _normalize_local_path(path)
    if not os.path.isfile(normalized):
        raise HTTPException(status_code=404, detail=f"File not found: {normalized}")
    text = extract_text_snippet(normalized, limit=max(1000, min(50000, int(limit))))
    return {"path": normalized, "text": text}


@app.post("/api/extract-text-item")
def extract_text_item(req: ItemAIRequest):
    local_path, temp_path = _prepare_item_for_ai(req.kind, req.path, req.site_relative_url)
    try:
        text = extract_text_snippet(local_path, limit=12000)
        return {"path": req.path, "kind": req.kind, "text": text}
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.get("/api/settings", response_model=SettingsResponse)
def get_settings():
    return SettingsResponse(
        target_language=cfg.target_language,
        model=cfg.model,
        ignore_patterns=cfg.ignore_patterns or [],
        has_api_key=bool(cfg.api_key),
        sp_base_url=(sp_client.base_url if sp_client else None),
        sp_has_cookies=(sp_client.has_cookies() if sp_client else False),
    )


@app.post("/api/settings", response_model=SettingsResponse)
def update_settings(update: SettingsUpdateRequest):
    global translator
    global rename_planner
    global sp_client
    changed_translator = False
    if update.target_language is not None:
        cfg.target_language = update.target_language or "English"
    if update.model is not None:
        cfg.model = update.model or cfg.model
        changed_translator = True
    if update.ignore_patterns is not None:
        cfg.ignore_patterns = update.ignore_patterns or []
    if update.api_key is not None:
        # Store in system keyring instead of config
        try:
            from ..services import secret_store

            key_text = (update.api_key or "").strip()
            if key_text:
                secret_store.set_secret("OPENAI_API_KEY", key_text)
                cfg.api_key = None
            else:
                cfg.api_key = None
                secret_store.delete_secret("OPENAI_API_KEY")
        except Exception:
            cfg.api_key = (update.api_key or "").strip() or None
        changed_translator = True
    if update.sp_base_url is not None:
        if update.sp_base_url:
            sp_client = SharePointClient(update.sp_base_url)
        else:
            sp_client = None
    save_config(cfg)
    if changed_translator:
        translator = create_translator(cfg)
        rename_planner = create_rename_planner(cfg)
        # Clear in-memory translation LRU when key/model changes
        _mem_cache.clear()
    return get_settings()


# Removed mapped-drive endpoints


class SPCookiesRequest(BaseModel):
    base_url: str
    cookie_header: Optional[str] = None  # e.g., "FedAuth=...; rtFa=..."
    cookies: Optional[Dict[str, str]] = None


@app.post("/api/sp/cookies")
def sp_set_cookies(req: SPCookiesRequest):
    global sp_client
    if not req.base_url:
        raise HTTPException(status_code=400, detail="base_url is required")
    sp_client = SharePointClient(req.base_url)
    if req.cookie_header:
        sp_client.set_cookies_from_header(req.cookie_header)
    if req.cookies:
        for k, v in req.cookies.items():
            sp_client.set_cookie(k, v)
    global _sp_sites_cache, _sp_libraries_cache
    _sp_sites_cache = None
    _sp_libraries_cache.clear()
    with _sp_cache_lock:
        _sp_list_cache.clear()
    return {"ok": True, "has_cookies": sp_client.has_cookies()}


class SPSite(BaseModel):
    title: Optional[str] = None
    server_relative_url: Optional[str] = None
    url: Optional[str] = None
    id: Optional[str] = None


class SPLibrary(BaseModel):
    title: Optional[str] = None
    server_relative_url: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None


class SPLibraryResponse(BaseModel):
    site_relative_url: Optional[str] = None
    libraries: List[SPLibrary]


class SPSitesResponse(BaseModel):
    sites: List[SPSite]


class SPPathRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_url: str


class SPCopyMoveRequest(BaseModel):
    site_relative_url: Optional[str] = None
    source_server_relative_url: str
    target_server_relative_url: str
    is_folder: bool
    overwrite: bool = False


class SPDeleteRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_url: str
    is_folder: bool
    recycle: bool = True


class SPCreateFolderRequest(BaseModel):
    site_relative_url: Optional[str] = None
    parent_server_relative_url: str
    name: str


class SPUploadRequest(BaseModel):
    site_relative_url: Optional[str] = None
    parent_server_relative_url: str
    name: str
    content_base64: str
    overwrite: bool = True


class SPShareLinkResponse(BaseModel):
    url: str


@app.get("/api/sp/sites", response_model=SPSitesResponse)
def sp_sites():
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        global _sp_sites_cache
        now = time.time()
        if _sp_sites_cache and (now - _sp_sites_cache[0]) < _SP_SITES_TTL:
            sites = _sp_sites_cache[1]
        else:
            sites = sp_client.list_sites()
            _sp_sites_cache = (now, sites)
        return SPSitesResponse(sites=[SPSite(**s) for s in sites])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sites: {e}")


@app.get("/api/sp/libraries", response_model=SPLibraryResponse)
def sp_libraries(site_relative_url: Optional[str] = Query(None, description="e.g., /sites/Contoso")):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        key = site_relative_url or "__default__"
        now = time.time()
        cached = _sp_libraries_cache.get(key)
        if cached and (now - cached[0]) < _SP_LIB_TTL:
            libs = cached[1]
        else:
            libs = sp_client.list_libraries(site_relative_url=site_relative_url)
            _sp_libraries_cache[key] = (now, libs)
        return SPLibraryResponse(site_relative_url=site_relative_url, libraries=[SPLibrary(**lib) for lib in libs])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list libraries: {e}")


@app.post("/api/sp/copy", response_model=RenameResponse)
def sp_copy(req: SPCopyMoveRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        new_path = sp_client.copy_item(
            req.source_server_relative_url,
            req.target_server_relative_url,
            is_folder=req.is_folder,
            overwrite=req.overwrite,
            site_relative_url=req.site_relative_url,
        )
        parent_dst = req.target_server_relative_url.rsplit('/', 1)[0]
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent_dst), None)
        return RenameResponse(newPath=new_path)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copy failed: {e}")


@app.post("/api/sp/move", response_model=RenameResponse)
def sp_move(req: SPCopyMoveRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        new_path = sp_client.move_item(
            req.source_server_relative_url,
            req.target_server_relative_url,
            is_folder=req.is_folder,
            overwrite=req.overwrite,
            site_relative_url=req.site_relative_url,
        )
        # invalidate caches for source and destination parents
        parent_src = req.source_server_relative_url.rsplit('/', 1)[0]
        parent_dst = req.target_server_relative_url.rsplit('/', 1)[0]
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent_src), None)
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent_dst), None)
        return RenameResponse(newPath=new_path)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Move failed: {e}")


@app.post("/api/sp/delete")
def sp_delete(req: SPDeleteRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        sp_client.delete_item(
            req.server_relative_url,
            is_folder=req.is_folder,
            site_relative_url=req.site_relative_url,
            recycle=req.recycle,
        )
        parent = req.server_relative_url.rsplit('/', 1)[0]
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent), None)
            _sp_list_cache.pop(_cache_key(req.site_relative_url, req.server_relative_url), None)
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


@app.post("/api/sp/folder", response_model=RenameResponse)
def sp_create_folder(req: SPCreateFolderRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        new_path = sp_client.create_folder(
            req.parent_server_relative_url,
            req.name,
            site_relative_url=req.site_relative_url,
        )
        parent = req.parent_server_relative_url
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent), None)
        return RenameResponse(newPath=new_path)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create folder failed: {e}")


@app.post("/api/sp/upload", response_model=RenameResponse)
def sp_upload(req: SPUploadRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        content = base64.b64decode(req.content_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    try:
        new_path = sp_client.upload_file(
            req.parent_server_relative_url,
            req.name,
            content,
            site_relative_url=req.site_relative_url,
            overwrite=req.overwrite,
        )
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, req.parent_server_relative_url), None)
        return RenameResponse(newPath=new_path)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@app.get("/api/sp/download")
def sp_download(site_relative_url: Optional[str] = Query(None), server_relative_url: str = Query(...)):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        content = sp_client.download_file(server_relative_url, site_relative_url=site_relative_url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")
    filename = server_relative_url.rsplit('/', 1)[-1] or "download"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": _build_content_disposition(filename),
        },
    )


@app.post("/api/sp/share-link", response_model=SPShareLinkResponse)
def sp_share_link(req: SPPathRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        url = sp_client.share_link(req.server_relative_url, site_relative_url=req.site_relative_url)
        return SPShareLinkResponse(url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create share link: {e}")


class SPListResponse(BaseModel):
    path: str
    items: List[ListItem]


def _build_content_disposition(filename: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = "".join(
        ch if 32 <= ord(ch) < 127 and ch not in {'"', '\\'} else "_"
        for ch in ascii_name
    ).strip() or "download"
    utf8_name = quote(filename, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'


@app.get("/api/sp/list", response_model=SPListResponse)
def sp_list(site_relative_url: str = Query(..., description="e.g., /sites/PeakEnergy-All"),
            folder_server_relative_url: str = Query(..., description="e.g., /sites/PeakEnergy-All/Shared Documents")):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured. Set via /api/settings or /api/sp/cookies.")
    try:
        cached = _cache_get(site_relative_url, folder_server_relative_url)
        if cached and (time.time() - cached[0]) < _SP_LIST_TTL:
            folders, files = cached[1], cached[2]
        else:
            folders, files = sp_client.list_children(folder_server_relative_url, site_relative_url=site_relative_url)
            _cache_put(site_relative_url, folder_server_relative_url, folders, files)
            _schedule_prefetch(folders, site_relative_url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list SharePoint folder: {e}")

    items: List[ListItem] = []
    for f in folders:
        items.append(ListItem(
            name=f.get("Name", ""),
            path=f.get("ServerRelativeUrl", ""),
            isDir=True,
            size=0,
            mtime=0.0,
        ))
    for fi in files:
        items.append(ListItem(
            name=fi.get("Name", ""),
            path=fi.get("ServerRelativeUrl", ""),
            isDir=False,
            size=int(fi.get("Length", 0) or 0),
            mtime=0.0,
        ))
    items.sort(key=lambda x: (not x.isDir, x.name.lower()))
    return SPListResponse(path=folder_server_relative_url, items=items)


class SPDocLibResponse(BaseModel):
    title: str
    server_relative_url: str


@app.get("/api/sp/default_doclib", response_model=SPDocLibResponse)
def sp_default_doclib():
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        title, url = sp_client.get_default_doclib()
        return SPDocLibResponse(title=title, server_relative_url=url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect default library: {e}")



class SPCheckoutRequest(BaseModel):
    server_relative_url: str
    site_relative_url: Optional[str] = None


@app.post("/api/sp/checkout")
def sp_checkout(req: SPCheckoutRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        sp_client.checkout_file(req.server_relative_url, site_relative_url=req.site_relative_url)
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout failed: {e}")


class SPCheckinRequest(BaseModel):
    server_relative_url: str
    comment: Optional[str] = ""
    checkin_type: Optional[int] = 1
    site_relative_url: Optional[str] = None


@app.post("/api/sp/checkin")
def sp_checkin(req: SPCheckinRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        sp_client.checkin_file(req.server_relative_url, comment=req.comment or "", checkin_type=int(req.checkin_type or 1), site_relative_url=req.site_relative_url)
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check-in failed: {e}")


@app.post("/api/sp/undo-checkout")
def sp_undo_checkout(req: SPCheckoutRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        sp_client.undo_checkout(req.server_relative_url, site_relative_url=req.site_relative_url)
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Undo checkout failed: {e}")


class SPVersionsResponse(BaseModel):
    versions: List[dict]


@app.get("/api/sp/versions", response_model=SPVersionsResponse)
def sp_versions(site_relative_url: Optional[str] = Query(None), server_relative_url: str = Query(...)):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        items = sp_client.list_versions(server_relative_url, site_relative_url=site_relative_url)
        return SPVersionsResponse(versions=items)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list versions: {e}")



@app.get("/api/sp/download-version")
def sp_download_version(server_relative_url: str = Query(...), label: str = Query(...), site_relative_url: Optional[str] = Query(None)):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        versions = sp_client.list_versions(server_relative_url, site_relative_url=site_relative_url)
        version_id = None
        for v in versions:
            if str(v.get("label") or "") == str(label):
                version_id = v.get("id")
                break
        if version_id is None:
            import urllib.parse as _up
            enc = _up.quote(server_relative_url if server_relative_url.startswith("/") else "/" + server_relative_url, safe="/")
            site_base = sp_client._resolve_site(site_relative_url)  # type: ignore[attr-defined]
            url = "%s/_api/web/GetFileByServerRelativeUrl('%s')/Versions?$select=ID,VersionLabel" % (site_base, enc)
            with sp_client._http() as client:  # type: ignore[attr-defined]
                r = client.get(url)
                r.raise_for_status()
                data = r.json()
            items = data.get("value") or data.get("d", {}).get("results", [])
            for it in items:
                if str(it.get("VersionLabel") or "") == str(label):
                    version_id = it.get("ID")
                    break
        if version_id is None:
            raise HTTPException(status_code=404, detail="Version not found")
        import urllib.parse as _up
        enc = _up.quote(server_relative_url if server_relative_url.startswith("/") else "/" + server_relative_url, safe="/")
        site_base = sp_client._resolve_site(site_relative_url)  # type: ignore[attr-defined]
        ver_url = "%s/_api/web/GetFileByServerRelativeUrl('%s')/Versions(%s)/$value" % (site_base, enc, version_id)
        with sp_client._http() as client:  # type: ignore[attr-defined]
            resp = client.get(ver_url)
            resp.raise_for_status()
            content = resp.content
        filename = server_relative_url.rsplit('/', 1)[-1] or "download"
        return StreamingResponse(io.BytesIO(content), media_type="application/octet-stream", headers={
            "Content-Disposition": "attachment; filename=\"%s\"" % filename
        })
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="SharePoint error: %s" % e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to download version: %s" % e)

class SPRestoreVersionRequest(BaseModel):
    server_relative_url: str
    label: str
    site_relative_url: Optional[str] = None


@app.post("/api/sp/restore-version")
def sp_restore_version(req: SPRestoreVersionRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        sp_client.restore_version(req.server_relative_url, req.label, site_relative_url=req.site_relative_url)
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore version: {e}")

class SPRenameRequest(BaseModel):
    server_relative_url: str
    new_name: str
    is_folder: bool
    site_relative_url: Optional[str] = None


@app.post("/api/sp/rename-preview")
def sp_rename_preview(req: RenamePreviewRequest):
    return {"items": _preview_sp_rename(req.items or [], req.site_relative_url)}


@app.post("/api/sp/rename", response_model=RenameResponse)
def sp_rename(req: SPRenameRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    ILLEGAL = set("\\/:*?\"<>|")
    if not req.new_name or any(ch in ILLEGAL for ch in req.new_name):
        raise HTTPException(status_code=400, detail="Invalid new name")
    try:
        new_path = sp_client.rename(
            req.server_relative_url,
            req.new_name,
            req.is_folder,
            site_relative_url=req.site_relative_url,
        )
        # Invalidate parent folder cache
        parent = req.server_relative_url.rsplit('/', 1)[0]
        with _sp_cache_lock:
            _sp_list_cache.pop(_cache_key(req.site_relative_url, parent), None)
            _sp_list_cache.pop(_cache_key(req.site_relative_url, req.server_relative_url), None)
        return RenameResponse(newPath=new_path)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {e}")


# Removed mapped-drive rename endpoint


@app.post("/api/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest):
    language = req.language or cfg.target_language or "English"
    n = len(req.items)
    out: List[str] = [""] * n

    namespace = _translator_namespace(language)

    # First pass: fill from caches; collect misses
    miss_indices: List[int] = []
    miss_names: List[str] = []
    miss_name_to_indices: Dict[str, List[int]] = {}

    for idx, item in enumerate(req.items):
        name = item.name or ""
        if not name:
            out[idx] = ""
            continue

        # Try caches in order: in-memory name-only -> by-path -> by-name
        mem_key = _mem_key(language, name)
        translated = _mem_get(mem_key)
        if not translated and item.path and item.mtime is not None:
            translated = cache.get(namespace, item.path, name, float(item.mtime))
        if not translated:
            translated = cache.get_by_name(namespace, name)

        if translated:
            out[idx] = translated
        else:
            miss_indices.append(idx)
            miss_names.append(name)
            miss_name_to_indices.setdefault(name, []).append(idx)

    # Deduplicate names for translations
    unique_names: List[str] = list(dict.fromkeys(miss_names))

    # Batch translate unknown names
    if unique_names:
        results = translator.translate_titles(unique_names, language)
        if len(results) != len(unique_names):
            # Fallback to per-item if batch length mismatch
            results = [translator.translate_title(nm, language) for nm in unique_names]

        # Assign results and update caches
        for name, tr in zip(unique_names, results):
            translated: str
            cleaned = tr.strip() if isinstance(tr, str) else ""
            if cleaned:
                translated = cleaned
                cache.set_by_name(namespace, name, translated)
                _mem_put(_mem_key(language, name), translated)
            else:
                translated = name
            for idx in miss_name_to_indices.get(name, []):
                item = req.items[idx]
                out[idx] = translated
                if translated != name and item.path and item.mtime is not None:
                    try:
                        cache.set(namespace, item.path, item.name, float(item.mtime), translated)
                    except Exception:
                        pass

    return TranslateResponse(translations=out)


@app.post("/api/translate/text", response_model=TranslateTextResponse)
def translate_text(req: TranslateTextRequest):
    language = req.language or cfg.target_language or "English"
    texts = req.texts or []
    if not texts:
        return TranslateTextResponse(translations=[])
    try:
        results = translator.translate_texts(texts, language)
    except Exception as exc:
        logging.exception("translate_text failed: %s", exc)
        results = list(texts)

    normalized: List[str] = []
    for original, translated in zip(texts, results or []):
        if isinstance(translated, str) and translated.strip():
            normalized.append(translated.strip())
        else:
            normalized.append(original)
    if len(normalized) < len(texts):
        normalized.extend(texts[len(normalized):])
    return TranslateTextResponse(translations=normalized)


# Removed warmup endpoints that depended on local filesystem


class SPPropertiesRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_url: str
    is_folder: bool


class SPPropertiesResponse(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    isDir: bool = False
    size: int = 0
    mtime: Optional[str] = None
    author: Optional[str] = None
    modifiedBy: Optional[str] = None


@app.post("/api/sp/properties", response_model=SPPropertiesResponse)
def sp_properties(req: SPPropertiesRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        info = sp_client.get_item_info(req.server_relative_url, is_folder=req.is_folder, site_relative_url=req.site_relative_url)  # type: ignore[arg-type]
        return SPPropertiesResponse(**info)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get properties: {e}")


class SPMetadataField(BaseModel):
    internal_name: str
    title: str
    type: str
    read_only: bool
    hidden: bool
    required: bool
    value: str
    choices: Optional[List[str]] = None


class SPMetadataFieldsResponse(BaseModel):
    fields: List[SPMetadataField]


class SPMetadataFieldsRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_url: str
    is_folder: bool = False


class SPMetadataUpdateRequest(BaseModel):
    site_relative_url: Optional[str] = None
    server_relative_url: str
    is_folder: bool = False
    fields: Dict[str, str]


@app.post("/api/sp/metadata-fields", response_model=SPMetadataFieldsResponse)
def sp_metadata_fields(req: SPMetadataFieldsRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        rows = sp_client.list_item_fields(
            req.server_relative_url,
            is_folder=req.is_folder,
            site_relative_url=req.site_relative_url,
        )
        return SPMetadataFieldsResponse(fields=[SPMetadataField(**r) for r in rows])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load metadata fields: {e}")


@app.post("/api/sp/metadata-update")
def sp_metadata_update(req: SPMetadataUpdateRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    try:
        result = sp_client.update_item_fields(
            req.server_relative_url,
            req.fields or {},
            is_folder=req.is_folder,
            site_relative_url=req.site_relative_url,
        )
        failures = [r for r in result if r.get("has_exception")]
        return {"ok": len(failures) == 0, "results": result, "failures": failures}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"SharePoint error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update metadata: {e}")


def main(argv: Optional[list[str]] = None):
    import uvicorn

    host = "127.0.0.1"
    port = 5001
    uvicorn.run("smart_explorer.backend.server:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main(sys.argv[1:])
