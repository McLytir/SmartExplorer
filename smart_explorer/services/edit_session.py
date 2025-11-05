from __future__ import annotations

import json
import os
from typing import Dict, Optional

from .preview_cache import cache_base_dir


_SESSIONS_FILE = os.path.join(cache_base_dir(), "edit_sessions.json")


def _load() -> Dict[str, Dict[str, str]]:
    try:
        if os.path.exists(_SESSIONS_FILE):
            with open(_SESSIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def _save(data: Dict[str, Dict[str, str]]) -> None:
    try:
        tmp = _SESSIONS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _SESSIONS_FILE)
    except Exception:
        pass


def _key(sp_path: str, site: Optional[str]) -> str:
    site_key = (site or "/").strip()
    return f"{site_key}::{sp_path}"


def set_session(sp_path: str, local_path: str, site: Optional[str]) -> None:
    data = _load()
    data[_key(sp_path, site)] = {"sp_path": sp_path, "site": site or "/", "local_path": local_path}
    _save(data)


def get_session(sp_path: str, site: Optional[str]) -> Optional[str]:
    data = _load()
    entry = data.get(_key(sp_path, site)) or {}
    return entry.get("local_path")


def clear_session(sp_path: str, site: Optional[str]) -> None:
    data = _load()
    data.pop(_key(sp_path, site), None)
    _save(data)


def all_sessions() -> Dict[str, Dict[str, str]]:
    return _load()

