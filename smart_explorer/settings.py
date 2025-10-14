import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


CONFIG_FILENAME = "smart_explorer_config.json"


@dataclass
class AppConfig:
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    target_language: str = "English"
    root_path: str = os.path.expanduser("~")
    ignore_patterns: list[str] = None  # glob patterns to skip translating
    sp_base_url: Optional[str] = None  # e.g., https://tenant.sharepoint.com/sites/SiteName
    # Optional: override the SharePoint library root (server-relative path)
    # Example: "/sites/PeakEnergy-All/Shared Documents" or "/sites/PeakEnergy-All/Documents"
    sp_library_root: Optional[str] = None  # server-relative library root (e.g., /sites/Site/Shared Documents)
    backend_url: Optional[str] = None  # e.g., http://127.0.0.1:5001
    last_source: str = "Local"        # "Local" or "SharePoint"


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
