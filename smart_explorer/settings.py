import json
import os
from dataclasses import dataclass, asdict
from typing import Optional, Dict


CONFIG_FILENAME = "smart_explorer_config.json"


@dataclass
class AppConfig:
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    target_language: str = "English"
    translator_provider: str = "auto"  # auto, openai, backend, google_free, libretranslate, identity
    translation_enabled: bool = False
    translation_view_mode: str = "below_name"  # below_name
    theme: str = "light"  # "light", "dark", "solarized_light", "solarized_dark"
    root_path: str = os.path.expanduser("~")
    ignore_patterns: list[str] = None  # glob patterns to skip translating
    sp_base_url: Optional[str] = None  # e.g., https://tenant.sharepoint.com/sites/SiteName
    # Optional: override the SharePoint library root (server-relative path)
    # Example: "/sites/PeakEnergy-All/Shared Documents" or "/sites/PeakEnergy-All/Documents"
    sp_library_root: Optional[str] = None  # server-relative library root (e.g., /sites/Site/Shared Documents)
    backend_url: Optional[str] = None  # e.g., http://127.0.0.1:5001
    last_source: str = "Local"        # "Local" or "SharePoint"
    workspaces: Optional[list[dict]] = None  # persisted workspace definitions
    favorites: Optional[list[dict]] = None  # favorite locations
    saved_layouts: Optional[list[dict]] = None  # saved workspace configurations
    favorites_bar_position: str = "left"  # left, right, top, bottom
    favorites_bar_size: int = 200  # pixels
    # Directory to store SharePoint downloads when opening files.
    # If None, uses the OS temporary directory.
    sp_download_dir: Optional[str] = None
    # If True, keep bulk downloads as .zip without auto-extracting
    sp_keep_zip_downloads: bool = False
    # Preview cache directory (if None, use OS-appropriate cache/appdata)
    preview_cache_dir: Optional[str] = None
    # LibreTranslate settings
    libretranslate_url: Optional[str] = None  # e.g., https://libretranslate.de
    # User shortcuts (action -> key sequence string)
    shortcuts: Optional[Dict[str, str]] = None
    # Recent "Resolve Old Link" history
    recent_resolved_links: Optional[list[dict]] = None


def _config_path() -> str:
    # Store config in the current working directory by default
    return os.path.abspath(CONFIG_FILENAME)


def load_config() -> AppConfig:
    path = _config_path()
    cfg = AppConfig()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = AppConfig(**{**asdict(cfg), **data})
        except Exception:
            pass
    if not cfg.ignore_patterns:
        cfg.ignore_patterns = [
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "*.tmp",
        ]
    if cfg.favorites is None:
        cfg.favorites = []
    if cfg.saved_layouts is None:
        cfg.saved_layouts = []
    if cfg.recent_resolved_links is None:
        cfg.recent_resolved_links = []
    if getattr(cfg, "theme", None) not in {"light", "dark", "solarized_light", "solarized_dark"}:
        cfg.theme = "light"
    if getattr(cfg, "translator_provider", None) not in {"auto", "openai", "backend", "google_free", "libretranslate", "identity"}:
        cfg.translator_provider = "auto"
    cfg.translation_enabled = bool(getattr(cfg, "translation_enabled", False))
    if getattr(cfg, "translation_view_mode", None) not in {"below_name"}:
        cfg.translation_view_mode = "below_name"
    if cfg.favorites_bar_position not in {"left", "right", "top", "bottom"}:
        cfg.favorites_bar_position = "left"
    try:
        cfg.favorites_bar_size = int(cfg.favorites_bar_size)
    except Exception:
        cfg.favorites_bar_size = 200
    cfg.favorites_bar_size = max(120, min(600, cfg.favorites_bar_size))
    if cfg.favorites_bar_size == 240:
        cfg.favorites_bar_size = 200
    # Shortcuts defaults
    if cfg.shortcuts is None or not isinstance(cfg.shortcuts, dict):
        cfg.shortcuts = {}
    defaults = {
        "toggle_tags": "Ctrl+Shift+L",
        "toggle_favorites": "Ctrl+Shift+B",
    }
    for key, val in defaults.items():
        cfg.shortcuts.setdefault(key, val)
    # Keep sp_base_url as-is (may be None)
    # Allow env var override for API key
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        cfg.api_key = env_key
    return cfg


def save_config(cfg: AppConfig) -> None:
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2)
    except Exception:
        pass
