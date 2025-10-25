from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Optional
from ..settings import load_config


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def cache_base_dir() -> str:
    # Allow override from config
    try:
        cfg = load_config()
        user_dir = getattr(cfg, "preview_cache_dir", None)
        if user_dir:
            base = os.path.abspath(user_dir)
            _ensure_dir(base)
            return base
    except Exception:
        pass

    # Use OS-appropriate application data/cache locations
    try:
        if sys.platform.startswith("win"):
            base_root = os.getenv("APPDATA") or os.path.expanduser("~")
            base = os.path.join(base_root, "SmartExplorer", "preview_cache")
        elif sys.platform == "darwin":
            base_root = os.path.expanduser("~/Library/Application Support")
            base = os.path.join(base_root, "SmartExplorer", "preview_cache")
        else:
            base_root = os.getenv("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
            base = os.path.join(base_root, "smart_explorer", "preview_cache")
    except Exception:
        base = os.path.abspath(os.path.join(os.getcwd(), "preview_cache"))
    _ensure_dir(base)
    return base


def downloads_dir() -> str:
    d = os.path.join(cache_base_dir(), "downloads")
    _ensure_dir(d)
    return d


def thumbs_dir() -> str:
    d = os.path.join(cache_base_dir(), "thumbnails")
    _ensure_dir(d)
    return d


def _key_for_path(path: str) -> str:
    h = hashlib.sha1(path.encode("utf-8", errors="ignore")).hexdigest()
    return h


def cached_download_path(original_path: str) -> Optional[str]:
    """Return cached downloaded file path for original_path if present, else None."""
    key = _key_for_path(original_path)
    meta = os.path.join(downloads_dir(), f"{key}.json")
    if os.path.exists(meta):
        try:
            with open(meta, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("cached_path")
            if p and os.path.exists(p):
                return p
        except Exception:
            return None
    return None


def save_downloaded_file(original_path: str, data: bytes, suggested_name: Optional[str] = None) -> str:
    """Save downloaded bytes to cache and return the cached path."""
    key = _key_for_path(original_path)
    # preserve extension if suggested_name provided
    ext = os.path.splitext(suggested_name or original_path)[1] or ""
    cached = os.path.join(downloads_dir(), f"{key}{ext}")
    with open(cached, "wb") as f:
        f.write(data)
    meta = os.path.join(downloads_dir(), f"{key}.json")
    try:
        with open(meta, "w", encoding="utf-8") as f:
            json.dump({"original_path": original_path, "cached_path": cached}, f)
    except Exception:
        pass
    return cached


def save_existing_file(original_path: str, src_path: str) -> str:
    """Move or copy an existing file into the cache and return its cached path."""
    key = _key_for_path(original_path)
    ext = os.path.splitext(src_path)[1] or os.path.splitext(original_path)[1] or ""
    cached = os.path.join(downloads_dir(), f"{key}{ext}")
    try:
        # Try to move for efficiency, fall back to copy
        try:
            os.replace(src_path, cached)
        except Exception:
            import shutil

            shutil.copy2(src_path, cached)
        meta = os.path.join(downloads_dir(), f"{key}.json")
        with open(meta, "w", encoding="utf-8") as f:
            json.dump({"original_path": original_path, "cached_path": cached}, f)
    except Exception:
        # If something went wrong, ensure we return a path (may not exist)
        return src_path
    return cached


def thumbnail_path_for(original_path: str) -> str:
    key = _key_for_path(original_path)
    return os.path.join(thumbs_dir(), f"{key}.jpg")


def get_cached_thumbnail(original_path: str) -> Optional[str]:
    p = thumbnail_path_for(original_path)
    return p if os.path.exists(p) else None


def save_thumbnail_for(original_path: str, image_bytes: bytes) -> str:
    p = thumbnail_path_for(original_path)
    with open(p, "wb") as f:
        f.write(image_bytes)
    return p
