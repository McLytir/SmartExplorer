# SmartExplorer: Quick Optimization & Implementation Guide

---

## 1. Dependency Injection Framework

**Current problem:** Services tightly coupled to UI, hard to test

**Solution:** Replace manual initialization with dependency injection

```python
# services/container.py
from typing import Optional
from dataclasses import dataclass

@dataclass
class ServiceContainer:
    """Central dependency injection container"""
    
    translator: Translator
    summarizer: Optional[AISummarizer]
    tagger: Optional[AITagger]
    translation_cache: TranslationCache
    tag_store: TagStore
    backend_client: BackendClient
    
    @staticmethod
    def from_config(config: AppConfig) -> "ServiceContainer":
        """Factory: Create all services from config"""
        translator = _create_translator(config)
        summarizer = _create_summarizer(config)
        tagger = _create_tagger(config)
        
        return ServiceContainer(
            translator=translator,
            summarizer=summarizer,
            tagger=tagger,
            translation_cache=TranslationCache(),
            tag_store=TagStore(),
            backend_client=BackendClient(config.backend_url),
        )

# usage/main_window.py
class MainWindow(QMainWindow):
    def __init__(self, container: ServiceContainer):
        super().__init__()
        self.container = container
        # Now services are injected, not hard-coded
        
# benefits:
# - Easy to mock for tests
# - Swap implementations (e.g., different translator)
# - Cleaner initialization
# - Follows SOLID principles
```

---

## 2. Replace os.path with pathlib Globally

**Current problem:** Platform-specific path handling bugs, verbose code

**Refactoring script:**

```python
# scripts/migrate_to_pathlib.py
import re
from pathlib import Path

patterns = [
    (r'os\.path\.join\((.*?)\)', lambda m: f"Path({m.group(1).replace(',', ' /')}),"),
    (r'os\.path\.exists\((\w+)\)', r"Path(\1).exists()"),
    (r'os\.path\.isdir\((\w+)\)', r"Path(\1).is_dir()"),
    (r'os\.path\.isfile\((\w+)\)', r"Path(\1).is_file()"),
    (r'os\.path\.dirname\((\w+)\)', r"Path(\1).parent"),
    (r'os\.path\.basename\((\w+)\)', r"Path(\1).name"),
    (r'os\.path\.splitext\((\w+)\)', r"Path(\1).suffix"),
    (r'os\.listdir\((\w+)\)', r"list(Path(\1).iterdir())"),
]

def migrate_file(filepath: Path):
    content = filepath.read_text()
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)
    filepath.write_text(content)

# Better approach using AST:
import ast
import libcst as cst

class PathMigrator(cst.CSTTransformer):
    """LibCST-based migration for safe refactoring"""
    
    def leave_Call(self, original_node, updated_node):
        # Replace os.path.join(...) calls
        if isinstance(original_node.func, cst.Attribute):
            if (isinstance(original_node.func.value, cst.Name) and
                original_node.func.value.value == "os" and
                original_node.func.attr.value == "path"):
                
                method = original_node.func.attr.value
                if method == "join":
                    # Convert to Path(...) / ... / ...
                    # Implementation here
                    pass
        return updated_node
```

**Before & After:**

```python
# BEFORE
import os
config_path = os.path.join(os.path.expanduser("~"), ".config", "smartexplorer")
if os.path.exists(config_path):
    files = os.listdir(config_path)
    for f in files:
        full_path = os.path.join(config_path, f)
        if os.path.isfile(full_path):
            size = os.path.getsize(full_path)

# AFTER
from pathlib import Path
config_path = Path.home() / ".config" / "smartexplorer"
if config_path.exists():
    files = list(config_path.iterdir())
    for f in files:
        if f.is_file():
            size = f.stat().st_size
```

---

## 3. Comprehensive Type Hints

**Current problem:** Missing type hints reduce IDE support, harder debugging

```python
# BEFORE: settings.py
def load_config():
    path = _config_path()
    cfg = AppConfig()
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
                # ... lots of dict access without type safety

# AFTER: settings.py
from typing import TypedDict, Optional, List
from pathlib import Path

class ConfigDict(TypedDict, total=False):
    api_key: Optional[str]
    model: str
    target_language: str
    translator_provider: str
    theme: str
    sp_base_url: Optional[str]
    ignore_patterns: List[str]

def load_config() -> AppConfig:
    path = _config_path()
    cfg = AppConfig()
    if Path(path).exists():
        try:
            with open(path) as f:
                data: ConfigDict = json.load(f)
                cfg = _parse_config(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load config: {e}")
    return cfg

def _parse_config(data: ConfigDict) -> AppConfig:
    """Type-safe config parsing"""
    return AppConfig(
        api_key=data.get("api_key"),
        model=data.get("model", "gpt-4o-mini"),
        # ... etc
    )
```

**Add to pyproject.toml:**

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true

[tool.pyright]
typeCheckingMode = "strict"
reportMissingImports = false
```

---

## 4. Plugin Architecture

**Current problem:** Hard to extend without modifying core code

```python
# smart_explorer/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class TranslatorPlugin(ABC):
    """Base class for translator plugins"""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """e.g., 'openai', 'google_free', 'my_custom_translator'"""
        pass
    
    @abstractmethod
    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        """Translate a file/folder name"""
        pass
    
    def translate_titles(self, titles: list[str], target_language: str) -> list[Optional[str]]:
        """Batch translation (override for efficiency)"""
        return [self.translate_title(t, target_language) for t in titles]

class ActionPlugin(ABC):
    """Base class for custom right-click actions"""
    
    @property
    @abstractmethod
    def action_label(self) -> str:
        """Display text for menu"""
        pass
    
    @abstractmethod
    async def execute(self, context: "ActionContext") -> None:
        """Execute the action"""
        pass

class TaggerPlugin(ABC):
    """Base class for auto-tagging plugins"""
    
    @abstractmethod
    async def suggest_tags(self, filepath: str) -> list[str]:
        """AI-driven tag suggestions"""
        pass

# smart_explorer/plugins/manager.py
class PluginManager:
    """Discover, load, and manage plugins"""
    
    def __init__(self, plugin_dir: Path = None):
        self.plugin_dir = plugin_dir or Path.home() / ".smartexplorer" / "plugins"
        self.translators: Dict[str, TranslatorPlugin] = {}
        self.actions: list[ActionPlugin] = []
        self.taggers: list[TaggerPlugin] = []
    
    def load_plugins(self) -> None:
        """Dynamically import plugins from plugin directory"""
        if not self.plugin_dir.exists():
            self.plugin_dir.mkdir(parents=True)
            return
        
        import importlib.util
        import sys
        
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.stem.startswith("_"):
                continue
            
            spec = importlib.util.spec_from_file_location(
                plugin_file.stem, plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_file.stem] = module
            spec.loader.exec_module(module)
            
            # Register plugins
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type):
                    if issubclass(attr, TranslatorPlugin) and attr != TranslatorPlugin:
                        plugin = attr()
                        self.translators[plugin.provider_name] = plugin
                    elif issubclass(attr, ActionPlugin) and attr != ActionPlugin:
                        self.actions.append(attr())
    
    def get_translator(self, provider: str) -> Optional[TranslatorPlugin]:
        return self.translators.get(provider)

# Example plugin: ~/.smartexplorer/plugins/deepl_translator.py
from smart_explorer.plugins.base import TranslatorPlugin
import deepl

class DeepLTranslator(TranslatorPlugin):
    provider_name = "deepl"
    
    def __init__(self):
        self.client = deepl.Translator(os.environ["DEEPL_API_KEY"])
    
    def translate_title(self, title: str, target_language: str) -> str:
        result = self.client.translate_text(
            title, 
            target_lang=target_language
        )
        return result.text

# Example plugin: ~/.smartexplorer/plugins/slack_action.py
from smart_explorer.plugins.base import ActionPlugin

class SendToSlackAction(ActionPlugin):
    action_label = "Send to Slack"
    
    async def execute(self, context) -> None:
        import aiohttp
        webhook_url = os.environ["SLACK_WEBHOOK"]
        
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json={
                "text": f"Check out: {context.filepath}"
            })

# Usage in main_window.py
class MainWindow(QMainWindow):
    def __init__(self, container: ServiceContainer):
        super().__init__()
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins()
        
        # Use plugins instead of hardcoded translators
        provider = self._cfg.translator_provider
        if provider in self.plugin_manager.translators:
            self._translator = self.plugin_manager.get_translator(provider)
        
        # Add plugin actions to context menu
        for action_plugin in self.plugin_manager.actions:
            self.context_menu.addAction(
                action_plugin.action_label,
                lambda p=action_plugin: asyncio.run(p.execute(context))
            )
```

---

## 5. Async-First Backend Architecture

**Current problem:** Some operations are blocking and not fully async

```python
# BEFORE: services/file_service.py
def list_files(path: str) -> List[FileInfo]:
    """Blocks the event loop"""
    items = []
    for f in os.listdir(path):
        stat = os.stat(os.path.join(path, f))
        items.append(FileInfo(...))
    return items

# AFTER: services/file_service.py
import asyncio
from pathlib import Path
from typing import List

async def list_files_async(path: str) -> List[FileInfo]:
    """Non-blocking async version"""
    loop = asyncio.get_event_loop()
    items = []
    
    def _list_sync():
        return list(Path(path).iterdir())
    
    entries = await loop.run_in_executor(None, _list_sync)
    
    tasks = [
        _stat_file_async(entry)
        for entry in entries
    ]
    
    return await asyncio.gather(*tasks)

async def _stat_file_async(path_obj: Path) -> FileInfo:
    """Get file stats asynchronously"""
    loop = asyncio.get_event_loop()
    stat = await loop.run_in_executor(None, path_obj.stat)
    return FileInfo(
        name=path_obj.name,
        size=stat.st_size,
        mtime=stat.st_mtime,
        is_dir=path_obj.is_dir(),
    )

# Backend: api/file_routes.py
from fastapi import APIRouter
from typing import List

router = APIRouter()

@router.get("/files/")
async def get_files(path: str) -> List[FileInfo]:
    """Async endpoint doesn't block other requests"""
    return await list_files_async(path)

# UI: ui/workspace_pane.py
class WorkspacePane(QWidget):
    async def load_files_async(self, path: str) -> None:
        """Load files without blocking UI"""
        client = get_backend_client()
        files = await client.get_files(path)
        self.update_model(files)
```

---

## 6. Better Error Handling & User Feedback

**Current problem:** Silent failures, unclear error messages

```python
# BEFORE
def apply_rename(path, new_name):
    try:
        os.rename(path, new_name)
    except Exception:
        pass  # Silent failure!

# AFTER
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OperationStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"
    PATH_NOT_FOUND = "path_not_found"
    INVALID_NAME = "invalid_name"
    DISK_FULL = "disk_full"

@dataclass
class OperationResult:
    status: OperationStatus
    message: str
    user_message: str  # Friendly message for UI
    error: Optional[Exception] = None

def apply_rename(path: str, new_name: str) -> OperationResult:
    """Rename with comprehensive error handling"""
    try:
        if not os.path.exists(path):
            return OperationResult(
                status=OperationStatus.PATH_NOT_FOUND,
                message=f"Path not found: {path}",
                user_message=f"File not found: {Path(path).name}",
            )
        
        if not safe_new_name(new_name):
            return OperationResult(
                status=OperationStatus.INVALID_NAME,
                message=f"Invalid filename: {new_name}",
                user_message="Name contains invalid characters (< > | / \\ etc.)",
            )
        
        new_path = os.path.join(os.path.dirname(path), new_name)
        os.rename(path, new_path)
        
        logger.info(f"Renamed {path} → {new_path}")
        return OperationResult(
            status=OperationStatus.SUCCESS,
            message=f"Successfully renamed to {new_name}",
            user_message=f"✓ Renamed to {new_name}",
        )
    
    except PermissionError as e:
        logger.error(f"Permission denied renaming {path}: {e}")
        return OperationResult(
            status=OperationStatus.PERMISSION_DENIED,
            message=str(e),
            user_message="Permission denied. Try running as administrator.",
            error=e,
        )
    
    except OSError as e:
        if e.errno == 28:  # No space left on device
            return OperationResult(
                status=OperationStatus.DISK_FULL,
                message="Disk full",
                user_message="Not enough disk space for this operation.",
                error=e,
            )
        
        logger.error(f"OS error renaming {path}: {e}")
        return OperationResult(
            status=OperationStatus.FAILED,
            message=str(e),
            user_message="Could not rename file. Check file permissions.",
            error=e,
        )

# UI: ui/workspace_pane.py
class WorkspacePane(QWidget):
    def on_rename_files(self, rename_map: Dict[str, str]) -> None:
        """Apply renames with user feedback"""
        results = []
        errors = []
        
        for old_name, new_name in rename_map.items():
            result = apply_rename(old_name, new_name)
            results.append(result)
            
            if result.status != OperationStatus.SUCCESS:
                errors.append(result)
        
        # Show summary dialog
        self.show_operation_summary(results)
        
        if errors:
            self.show_error_dialog(errors)
    
    def show_operation_summary(self, results: List[OperationResult]) -> None:
        """Dialog showing what succeeded/failed"""
        success_count = sum(1 for r in results if r.status == OperationStatus.SUCCESS)
        failed_count = len(results) - success_count
        
        msg = f"✓ {success_count} renamed successfully"
        if failed_count > 0:
            msg += f"\n✗ {failed_count} failed"
            
            for result in results:
                if result.status != OperationStatus.SUCCESS:
                    msg += f"\n- {result.user_message}"
        
        QMessageBox.information(self, "Rename Results", msg)
```

---

## 7. Structured Logging

**Current problem:** Logs scattered, hard to debug distributed system

```python
# logging_config.py
import logging
import logging.config
from pathlib import Path
import json
from pythonjsonlogger import jsonlogger
import contextvars

# Context for tracing across async operations
request_id = contextvars.ContextVar('request_id', default=None)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
        },
        'json': {
            '()': jsonlogger.JsonFormatter
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': get_log_path(),
            'maxBytes': 10_000_000,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
            'level': 'DEBUG',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': get_error_log_path(),
            'maxBytes': 5_000_000,
            'backupCount': 3,
            'formatter': 'json',
            'level': 'ERROR',
        }
    },
    'loggers': {
        'smart_explorer': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'PySide6': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'fastapi': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

logging.config.dictConfig(LOGGING_CONFIG)

class ContextFilter(logging.Filter):
    """Add request_id to all log records"""
    def filter(self, record):
        record.request_id = request_id.get()
        return True

# Add filter to all handlers
for handler in logging.root.handlers:
    handler.addFilter(ContextFilter())

# Usage in services
logger = logging.getLogger(__name__)

class AITagger:
    async def tag_file(self, filepath: str) -> List[str]:
        """Log with structured context"""
        logger.info(
            "Starting tagging",
            extra={
                'filepath': filepath,
                'request_id': request_id.get(),
            }
        )
        
        try:
            tags = await self._tag_impl(filepath)
            logger.info(
                "Tagging successful",
                extra={'filepath': filepath, 'tags': tags}
            )
            return tags
        except Exception as e:
            logger.exception(
                "Tagging failed",
                extra={'filepath': filepath, 'error': str(e)},
                exc_info=True
            )
            raise
```

---

## 8. Caching Strategy Improvements

**Current problem:** Cache invalidation unclear, potential stale data

```python
# services/caching.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, TypeVar, Generic, Callable, Dict
import hashlib
import json

T = TypeVar('T')

@dataclass
class CacheEntry(Generic[T]):
    value: T
    created_at: datetime
    expires_at: Optional[datetime] = None
    source: str = ""  # e.g., "openai", "google", "cached"
    hash_key: str = ""  # For validation

class CachePolicy(ABC):
    """Pluggable cache invalidation strategies"""
    
    @abstractmethod
    def should_invalidate(self, entry: CacheEntry) -> bool:
        pass

class TTLPolicy(CachePolicy):
    """Invalidate after time-to-live"""
    def __init__(self, ttl_hours: int):
        self.ttl = timedelta(hours=ttl_hours)
    
    def should_invalidate(self, entry: CacheEntry) -> bool:
        if entry.expires_at:
            return datetime.now() > entry.expires_at
        return (datetime.now() - entry.created_at) > self.ttl

class ContentHashPolicy(CachePolicy):
    """Invalidate if file content changed"""
    def __init__(self, get_content_hash: Callable[[str], str]):
        self.get_hash = get_content_hash
    
    def should_invalidate(self, entry: CacheEntry) -> bool:
        current_hash = self.get_hash(entry.hash_key)
        return current_hash != entry.hash_key

class TranslationCache:
    """Smarter translation caching with policies"""
    
    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}
        self.policies: Dict[str, CachePolicy] = {
            "default": TTLPolicy(ttl_hours=30 * 24),  # 30 days
            "file_content": ContentHashPolicy(self._get_file_hash),
        }
    
    def get(self, key: str, policy: str = "default") -> Optional[str]:
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if self.policies[policy].should_invalidate(entry):
            del self.cache[key]
            return None
        
        return entry.value
    
    def set(self, key: str, value: str, source: str, expires_in_hours: int = None) -> None:
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        self.cache[key] = CacheEntry(
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at,
            source=source,
        )
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Bulk invalidation by pattern (e.g., filename)"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for k in keys_to_delete:
            del self.cache[k]
        return len(keys_to_delete)
    
    @staticmethod
    def _get_file_hash(filepath: str) -> str:
        """Get hash of file content"""
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
```

---

## 9. Testing Scaffold

```python
# tests/conftest.py
import pytest
from pathlib import Path
from smart_explorer.settings import AppConfig
from smart_explorer.plugins.manager import PluginManager
from smart_explorer.services.container import ServiceContainer
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_config() -> AppConfig:
    return AppConfig(
        api_key="test-key",
        model="gpt-4o-mini",
        target_language="French",
        translator_provider="identity",
    )

@pytest.fixture
def mock_backend_client():
    mock = AsyncMock()
    mock.health = AsyncMock(return_value={"status": "ok"})
    return mock

@pytest.fixture
def service_container(mock_config, mock_backend_client) -> ServiceContainer:
    from smart_explorer.translators.base import IdentityTranslator
    from smart_explorer.services.caching import TranslationCache
    from smart_explorer.services.tag_store import TagStore
    
    return ServiceContainer(
        translator=IdentityTranslator(),
        summarizer=None,
        tagger=None,
        translation_cache=TranslationCache(),
        tag_store=TagStore(),
        backend_client=mock_backend_client,
    )

@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for testing"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.txt").write_text("Hello")
    (workspace / "subdir").mkdir()
    (workspace / "subdir" / "file2.txt").write_text("World")
    return workspace

# tests/test_translator.py
@pytest.mark.asyncio
async def test_translator_basic(service_container):
    translator = service_container.translator
    result = translator.translate_title("hello.txt", "French")
    assert result == "hello.txt"  # Identity translator returns original

@pytest.mark.asyncio
async def test_batch_translation(service_container):
    titles = ["file1.txt", "file2.pdf", "folder"]
    results = service_container.translator.translate_titles(titles, "German")
    assert len(results) == 3

# tests/test_file_operations.py
def test_safe_rename(temp_workspace):
    from smart_explorer.services.rename_service import safe_new_name
    
    assert safe_new_name("valid_name.txt")
    assert not safe_new_name("invalid<name>.txt")
    assert not safe_new_name("invalid|name.txt")

def test_list_files_async(temp_workspace):
    from smart_explorer.services.file_service import list_files_async
    import asyncio
    
    files = asyncio.run(list_files_async(str(temp_workspace)))
    assert len(files) == 3  # file1.txt, file2.txt, subdir

# tests/test_caching.py
def test_translation_cache():
    from smart_explorer.services.caching import TranslationCache, TTLPolicy
    
    cache = TranslationCache()
    cache.set("key1", "bonjour", source="openai")
    
    assert cache.get("key1") == "bonjour"
    assert cache.get("nonexistent") is None

def test_cache_invalidation():
    from smart_explorer.services.caching import TranslationCache
    
    cache = TranslationCache()
    cache.set("file.txt", "translated", source="openai", expires_in_hours=0)
    
    import time
    time.sleep(0.1)
    
    # Should be expired
    assert cache.get("file.txt") is None
```

---

## 10. Performance Monitoring

```python
# services/performance.py
import time
import functools
from typing import Callable
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Track operation performance"""
    
    def __init__(self):
        self.metrics = {}
    
    def track(self, operation_name: str):
        """Decorator to track function performance"""
        def decorator(func: Callable):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    self._record_metric(operation_name, duration, success=True)
                    return result
                except Exception as e:
                    duration = time.perf_counter() - start
                    self._record_metric(operation_name, duration, success=False)
                    raise
            
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    duration = time.perf_counter() - start
                    self._record_metric(operation_name, duration, success=True)
                    return result
                except Exception as e:
                    duration = time.perf_counter() - start
                    self._record_metric(operation_name, duration, success=False)
                    raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return decorator
    
    def _record_metric(self, name: str, duration: float, success: bool):
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append({
            'duration': duration,
            'success': success,
            'timestamp': time.time(),
        })
        
        if duration > 1.0:  # Log slow operations
            logger.warning(f"Slow operation: {name} took {duration:.2f}s")
    
    def get_stats(self, operation_name: str) -> dict:
        """Get performance statistics"""
        if operation_name not in self.metrics:
            return {}
        
        samples = self.metrics[operation_name]
        durations = [s['duration'] for s in samples]
        successful = sum(1 for s in samples if s['success'])
        
        return {
            'count': len(samples),
            'success_rate': successful / len(samples) if samples else 0,
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'p95_duration': sorted(durations)[int(0.95 * len(durations))],
        }

# Usage
perf = PerformanceMonitor()

class TranslationService:
    @perf.track("translate_title")
    async def translate_title(self, title: str, lang: str) -> str:
        # Implementation
        pass

@perf.track("list_files")
async def list_files(path: str):
    # Implementation
    pass
```

---

## Implementation Priority

### Week 1-2 (Foundation)
1. ✅ Add dependency injection (easier to test)
2. ✅ Migrate to pathlib
3. ✅ Add comprehensive type hints
4. ✅ Improve error handling

### Week 3-4 (Testing)
5. ✅ Build test scaffold
6. ✅ Add structured logging
7. ✅ Performance monitoring

### Week 5-6 (Extensibility)
8. ✅ Plugin architecture
9. ✅ Better caching strategy
10. ✅ Async-first refactoring

---

**Each section includes:**
- Problem statement
- Before/After comparison
- Runnable code examples
- Integration instructions

Start with **Section 1-6** for maximum improvement with minimal effort!
