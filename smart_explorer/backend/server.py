from __future__ import annotations

import fnmatch
import os
import sys
import time
from typing import List, Optional, Dict, Tuple
import httpx

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..settings import load_config, save_config, AppConfig
from ..translation_cache import TranslationCache
from ..translators.base import IdentityTranslator, Translator
from ..translators.openai_translator import OpenAITranslator
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


class TranslateItem(BaseModel):
    name: str
    path: Optional[str] = None
    mtime: Optional[float] = None


class TranslateRequest(BaseModel):
    language: str
    items: List[TranslateItem]


class TranslateResponse(BaseModel):
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
    if api_key:
        return OpenAITranslator(api_key=api_key, model=cfg.model)
    return IdentityTranslator()


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

translator = create_translator(cfg)
cache = TranslationCache()
sp_client: Optional[SharePointClient] = None
if getattr(cfg, "sp_base_url", None):
    try:
        sp_client = SharePointClient(cfg.sp_base_url)  # type: ignore[arg-type]
    except Exception:
        sp_client = None

# Short TTL cache for SharePoint folder listing to reduce round-trips
_SP_LIST_TTL = 15.0
_sp_list_cache: Dict[str, tuple[float, list[dict], list[dict]]] = {}

# Small in-memory LRU cache for frequent names to reduce API calls
from collections import OrderedDict

_MEM_CACHE_MAX = 500
_mem_cache: "OrderedDict[str, str]" = OrderedDict()


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


@app.get("/api/health")
def health():
    return {"status": "ok"}


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
        cfg.api_key = update.api_key.strip() or None
        changed_translator = True
    if update.sp_base_url is not None:
        if update.sp_base_url:
            sp_client = SharePointClient(update.sp_base_url)
        else:
            sp_client = None
    save_config(cfg)
    if changed_translator:
        translator = create_translator(cfg)
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
    return {"ok": True, "has_cookies": sp_client.has_cookies()}


class SPListResponse(BaseModel):
    path: str
    items: List[ListItem]


@app.get("/api/sp/list", response_model=SPListResponse)
def sp_list(site_relative_url: str = Query(..., description="e.g., /sites/PeakEnergy-All"),
            folder_server_relative_url: str = Query(..., description="e.g., /sites/PeakEnergy-All/Shared Documents")):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured. Set via /api/settings or /api/sp/cookies.")
    try:
        now = time.time()
        cached = _sp_list_cache.get(folder_server_relative_url)
        if cached and (now - cached[0]) < _SP_LIST_TTL:
            folders, files = cached[1], cached[2]
        else:
            folders, files = sp_client.list_children(folder_server_relative_url)
            _sp_list_cache[folder_server_relative_url] = (now, folders, files)
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


class SPRenameRequest(BaseModel):
    server_relative_url: str
    new_name: str
    is_folder: bool


@app.post("/api/sp/rename", response_model=RenameResponse)
def sp_rename(req: SPRenameRequest):
    if not sp_client:
        raise HTTPException(status_code=400, detail="SharePoint base URL not configured")
    ILLEGAL = set("\\/:*?\"<>|")
    if not req.new_name or any(ch in ILLEGAL for ch in req.new_name):
        raise HTTPException(status_code=400, detail="Invalid new name")
    try:
        new_path = sp_client.rename(req.server_relative_url, req.new_name, req.is_folder)
        # Invalidate parent folder cache
        parent = (req.server_relative_url if req.is_folder else req.server_relative_url).rsplit('/', 1)[0]
        _sp_list_cache.pop(parent, None)
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
        mem_key = f"{language}\n{name}"
        translated = _mem_get(mem_key)
        if not translated and item.path and item.mtime is not None:
            translated = cache.get(language, item.path, name, float(item.mtime))
        if not translated:
            translated = cache.get_by_name(language, name)

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
            translated = tr or name
            cache.set_by_name(language, name, translated)
            _mem_put(f"{language}\n{name}", translated)
            for idx in miss_name_to_indices.get(name, []):
                item = req.items[idx]
                out[idx] = translated
                if item.path and item.mtime is not None:
                    try:
                        cache.set(language, item.path, item.name, float(item.mtime), translated)
                    except Exception:
                        pass

    return TranslateResponse(translations=out)


# Removed warmup endpoints that depended on local filesystem


def main(argv: Optional[list[str]] = None):
    import uvicorn

    host = "127.0.0.1"
    port = 5001
    uvicorn.run("smart_explorer.backend.server:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main(sys.argv[1:])
