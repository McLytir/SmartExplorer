# SmartExplorer: New Features Specification & Roadmap

---

## Feature Categories

- 🚀 **High-Impact, Low-Effort** (implement first)
- ⭐ **High-Impact, Medium-Effort** (strong ROI)
- 💎 **High-Impact, High-Effort** (future)
- 🎯 **Medium-Impact, Low-Effort** (quick wins)

---

## 🚀 HIGH-IMPACT, LOW-EFFORT Features

### 1. Session Management & Auto-Restore

**Impact:** Users frustrated when they lose their workspace setup  
**Effort:** 2-3 days

```python
# services/session_manager.py
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

@dataclass
class PaneSnapshot:
    pane_id: str
    pane_type: str  # "local", "sharepoint", "translation"
    location: str   # Path or URL
    position: int   # Left or right
    title: str
    base_pane_id: Optional[str]  # For translation/qa panes
    target_language: Optional[str]
    timestamp: float

@dataclass
class SessionSnapshot:
    workspace_id: str
    panes: list[PaneSnapshot]
    active_pane_id: Optional[str]
    preview_enabled: bool
    theme: str
    timestamp: datetime
    
    def save(self) -> None:
        path = self._get_session_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(asdict(self), f, default=str, indent=2)
    
    @staticmethod
    def load() -> Optional['SessionSnapshot']:
        path = SessionSnapshot._get_session_file()
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return SessionSnapshot(**data)
        return None
    
    @staticmethod
    def _get_session_file() -> Path:
        return Path.home() / ".smartexplorer" / "last_session.json"

# ui/main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.session_manager = SessionManager()
        
        # On startup, restore last session
        self._restore_last_session()
    
    def _restore_last_session(self) -> None:
        """Restore panes and layout from last session"""
        session = SessionSnapshot.load()
        if not session:
            return
        
        for pane_snapshot in session.panes:
            self._create_pane_from_snapshot(pane_snapshot)
        
        if session.active_pane_id:
            self._set_active_pane(session.active_pane_id)
        
        self._preview_enabled = session.preview_enabled
        if self._preview_enabled:
            self._toggle_preview()
    
    def closeEvent(self, event):
        """Save session before closing"""
        session = self._capture_session()
        session.save()
        super().closeEvent(event)
    
    def _capture_session(self) -> SessionSnapshot:
        """Capture current state"""
        panes = []
        for pane_id, pane in self._workspace_panes.items():
            panes.append(PaneSnapshot(
                pane_id=pane_id,
                pane_type=pane.get_type(),
                location=str(pane.current_path),
                position=self.splitter.indexOf(pane),
                title=pane.title,
                base_pane_id=getattr(pane, 'base_pane_id', None),
                target_language=getattr(pane, 'target_language', None),
                timestamp=time.time(),
            ))
        
        return SessionSnapshot(
            workspace_id=self._active_workspace_id,
            panes=panes,
            active_pane_id=self._active_workspace_id,
            preview_enabled=self._preview_enabled,
            theme=self._cfg.theme,
            timestamp=datetime.now(),
        )

# UI: Add "Resume Session" button in case user wants old session back
menu.addAction("Restore Previous Session", self._restore_previous_session)
```

**User Benefit:**
- "Exactly where I left off" experience
- No need to navigate again
- Translation preferences remembered

---

### 2. Keyboard Shortcuts Customizer

**Impact:** Power users want VIM/Emacs bindings  
**Effort:** 3 days

```python
# services/shortcuts_config.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import json

class ShortcutAction(Enum):
    GO_TO = "go_to"
    FOCUS_ADDRESS = "focus_address"
    BACK = "back"
    FORWARD = "forward"
    UP = "up"
    RENAME = "rename"
    DELETE = "delete"
    COPY = "copy"
    PASTE = "paste"
    UNDO = "undo"
    TOGGLE_PREVIEW = "toggle_preview"
    OPEN_FILE = "open_file"
    REVEAL_PATH = "reveal_path"
    # ... more actions

@dataclass
class KeyBinding:
    action: ShortcutAction
    keys: str  # "Ctrl+K", "Cmd+L", etc.
    description: str
    category: str  # "Navigation", "Editing", "View"

class ShortcutManager:
    PRESETS = {
        "default": {
            ShortcutAction.GO_TO: "Ctrl+K",
            ShortcutAction.FOCUS_ADDRESS: "Ctrl+L",
            ShortcutAction.BACK: "Alt+Left",
            ShortcutAction.UP: "Alt+Up",
        },
        "vim": {
            ShortcutAction.GO_TO: "Ctrl+K",
            ShortcutAction.FOCUS_ADDRESS: "Ctrl+L",
            ShortcutAction.BACK: "Ctrl+[",
            ShortcutAction.UP: "Ctrl+H",  # Navigate up
        },
        "emacs": {
            ShortcutAction.GO_TO: "Ctrl+K",
            ShortcutAction.FOCUS_ADDRESS: "Ctrl+X Ctrl+L",
            ShortcutAction.COPY: "Alt+W",
            ShortcutAction.PASTE: "Ctrl+Y",
        },
    }
    
    def __init__(self):
        self.bindings: Dict[ShortcutAction, str] = self.PRESETS["default"].copy()
        self.load()
    
    def load(self) -> None:
        config_path = Path.home() / ".smartexplorer" / "shortcuts.json"
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)
                for action_name, keys in data.items():
                    try:
                        action = ShortcutAction[action_name]
                        self.bindings[action] = keys
                    except KeyError:
                        pass  # Ignore obsolete actions
    
    def save(self) -> None:
        config_path = Path.home() / ".smartexplorer" / "shortcuts.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            action.name: keys 
            for action, keys in self.bindings.items()
        }
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def apply_preset(self, preset_name: str) -> None:
        if preset_name in self.PRESETS:
            self.bindings = self.PRESETS[preset_name].copy()
            self.save()

# ui/settings_dialog.py
class ShortcutsTab(QWidget):
    def __init__(self, shortcut_manager: ShortcutManager):
        super().__init__()
        self.shortcut_manager = shortcut_manager
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Preset buttons
        preset_layout = QHBoxLayout()
        for preset_name in ShortcutManager.PRESETS:
            btn = QPushButton(preset_name.title())
            btn.clicked.connect(
                lambda checked, p=preset_name: self._apply_preset(p)
            )
            preset_layout.addWidget(btn)
        layout.addLayout(preset_layout)
        
        # Shortcuts table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Action", "Keys", "Category"])
        
        for action, keys in self.shortcut_manager.bindings.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Action name
            self.table.setItem(row, 0, QTableWidgetItem(action.value))
            
            # Keys (editable)
            item = QTableWidgetItem(keys)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 1, item)
            
            # Category
            category = self._get_category(action)
            self.table.setItem(row, 2, QTableWidgetItem(category))
        
        layout.addWidget(self.table)
        
        # Save button
        save_btn = QPushButton("Save Shortcuts")
        save_btn.clicked.connect(self._save_shortcuts)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    def _apply_preset(self, preset_name: str):
        self.shortcut_manager.apply_preset(preset_name)
        # Refresh table
        self.table.setRowCount(0)
        self.init_ui()
    
    def _save_shortcuts(self):
        for row in range(self.table.rowCount()):
            action_name = self.table.item(row, 0).text()
            keys = self.table.item(row, 1).text()
            action = ShortcutAction[action_name]
            self.shortcut_manager.bindings[action] = keys
        
        self.shortcut_manager.save()
        QMessageBox.information(self, "Success", "Shortcuts saved!")
```

**User Benefit:**
- Power users can customize keybindings
- Support for VIM/Emacs modes
- Presets for different workflows

---

### 3. Clipboard History Ring

**Impact:** Users frequently need "paste previous"  
**Effort:** 2 days

```python
# services/clipboard_manager.py
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ClipboardEntry:
    content: str
    timestamp: datetime
    source: str  # "copy", "cut", "drag"

class ClipboardRing:
    def __init__(self, max_size: int = 20):
        self.ring: deque[ClipboardEntry] = deque(maxlen=max_size)
        self.history_index = 0
    
    def push(self, content: str, source: str = "copy") -> None:
        """Add to clipboard ring"""
        entry = ClipboardEntry(
            content=content,
            timestamp=datetime.now(),
            source=source
        )
        self.ring.appendleft(entry)
        self.history_index = 0
    
    def current(self) -> Optional[str]:
        """Get current clipboard entry"""
        if not self.ring:
            return None
        return self.ring[self.history_index].content
    
    def next(self) -> Optional[str]:
        """Cycle to next clipboard entry"""
        if not self.ring:
            return None
        self.history_index = (self.history_index + 1) % len(self.ring)
        return self.current()
    
    def prev(self) -> Optional[str]:
        """Cycle to previous clipboard entry"""
        if not self.ring:
            return None
        self.history_index = (self.history_index - 1) % len(self.ring)
        return self.current()
    
    def get_history(self) -> list[ClipboardEntry]:
        """Get all entries with timestamps"""
        return list(self.ring)
    
    def clear(self) -> None:
        """Clear clipboard history"""
        self.ring.clear()
        self.history_index = 0

# ui/main_window.py
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.clipboard_ring = ClipboardRing()
        self._setup_clipboard_shortcuts()
    
    def _setup_clipboard_shortcuts(self):
        # Cycle clipboard history with Shift+Ctrl+V
        QShortcut(QKeySequence("Shift+Ctrl+V"), self, self._cycle_clipboard)
    
    def _cycle_clipboard(self):
        """Cycle through clipboard history"""
        content = self.clipboard_ring.next()
        if content:
            clipboard = QApplication.clipboard()
            clipboard.setText(content)
            
            # Show toast notification
            self._show_toast(f"Clipboard: {content[:50]}...")

# Track all copy operations
def _on_copy(self, text: str):
    """Intercept copy operations"""
    self.clipboard_ring.push(text, source="copy")
    # ... continue with normal copy

def _on_cut(self, text: str):
    """Intercept cut operations"""
    self.clipboard_ring.push(text, source="cut")
    # ... continue with normal cut
```

**User Benefit:**
- "Oops, I copied over what I needed" solved
- Quick cycling through recent clipboard items

---

### 4. File Type Icons & Color Coding

**Impact:** Visual scanning much faster  
**Effort:** 2 days

```python
# services/file_types.py
from enum import Enum
from pathlib import Path
from typing import Dict

class FileCategory(Enum):
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    CODE = "code"
    ARCHIVE = "archive"
    FOLDER = "folder"
    UNKNOWN = "unknown"

FILE_CATEGORY_MAP: Dict[str, FileCategory] = {
    # Documents
    '.pdf': FileCategory.DOCUMENT,
    '.doc': FileCategory.DOCUMENT,
    '.docx': FileCategory.DOCUMENT,
    '.txt': FileCategory.DOCUMENT,
    '.pages': FileCategory.DOCUMENT,
    '.odt': FileCategory.DOCUMENT,
    
    # Spreadsheets
    '.xlsx': FileCategory.SPREADSHEET,
    '.xls': FileCategory.SPREADSHEET,
    '.csv': FileCategory.SPREADSHEET,
    '.numbers': FileCategory.SPREADSHEET,
    '.ods': FileCategory.SPREADSHEET,
    
    # Presentations
    '.pptx': FileCategory.PRESENTATION,
    '.ppt': FileCategory.PRESENTATION,
    '.key': FileCategory.PRESENTATION,
    '.odp': FileCategory.PRESENTATION,
    
    # Images
    '.png': FileCategory.IMAGE,
    '.jpg': FileCategory.IMAGE,
    '.jpeg': FileCategory.IMAGE,
    '.gif': FileCategory.IMAGE,
    '.svg': FileCategory.IMAGE,
    '.webp': FileCategory.IMAGE,
    
    # Video
    '.mp4': FileCategory.VIDEO,
    '.mov': FileCategory.VIDEO,
    '.mkv': FileCategory.VIDEO,
    '.avi': FileCategory.VIDEO,
    
    # Audio
    '.mp3': FileCategory.AUDIO,
    '.wav': FileCategory.AUDIO,
    '.flac': FileCategory.AUDIO,
    '.m4a': FileCategory.AUDIO,
    
    # Code
    '.py': FileCategory.CODE,
    '.js': FileCategory.CODE,
    '.ts': FileCategory.CODE,
    '.java': FileCategory.CODE,
    '.cpp': FileCategory.CODE,
    '.c': FileCategory.CODE,
    '.h': FileCategory.CODE,
    '.go': FileCategory.CODE,
    '.rs': FileCategory.CODE,
    
    # Archives
    '.zip': FileCategory.ARCHIVE,
    '.rar': FileCategory.ARCHIVE,
    '.7z': FileCategory.ARCHIVE,
    '.tar': FileCategory.ARCHIVE,
    '.gz': FileCategory.ARCHIVE,
}

CATEGORY_COLORS = {
    FileCategory.DOCUMENT: "#4A90E2",
    FileCategory.SPREADSHEET: "#7ED321",
    FileCategory.PRESENTATION: "#F5A623",
    FileCategory.IMAGE: "#BD10E0",
    FileCategory.VIDEO: "#50E3C2",
    FileCategory.AUDIO: "#B8E986",
    FileCategory.CODE: "#417505",
    FileCategory.ARCHIVE: "#D0021B",
    FileCategory.FOLDER: "#F8E71C",
    FileCategory.UNKNOWN: "#9013FE",
}

class FileTypeDetector:
    @staticmethod
    def get_category(filepath: str) -> FileCategory:
        """Detect file category from extension"""
        ext = Path(filepath).suffix.lower()
        return FILE_CATEGORY_MAP.get(ext, FileCategory.UNKNOWN)
    
    @staticmethod
    def get_color(filepath: str) -> str:
        """Get color for file type"""
        category = FileTypeDetector.get_category(filepath)
        return CATEGORY_COLORS[category]
    
    @staticmethod
    def get_icon(filepath: str) -> str:
        """Get icon for file type (emoji or path to icon)"""
        category = FileTypeDetector.get_category(filepath)
        icons = {
            FileCategory.DOCUMENT: "📄",
            FileCategory.SPREADSHEET: "📊",
            FileCategory.PRESENTATION: "📽️",
            FileCategory.IMAGE: "🖼️",
            FileCategory.VIDEO: "🎬",
            FileCategory.AUDIO: "🎵",
            FileCategory.CODE: "💻",
            FileCategory.ARCHIVE: "📦",
            FileCategory.FOLDER: "📁",
            FileCategory.UNKNOWN: "❓",
        }
        return icons[category]

# ui/workspace_pane.py
class FileListModel(QAbstractListModel):
    def data(self, index, role):
        if role == Qt.DecorationRole:
            filepath = self.items[index.row()].path
            color = FileTypeDetector.get_color(filepath)
            # Create colored circle icon
            pixmap = self._create_colored_icon(color, 16)
            return QIcon(pixmap)
        
        if role == Qt.BackgroundRole:
            filepath = self.items[index.row()].path
            color = FileTypeDetector.get_color(filepath)
            # Subtle background color
            return QColor(color + "22")  # Add transparency
```

**User Benefit:**
- Quick visual identification of file types
- Easier scanning of large folders
- Color-coded organization

---

## ⭐ HIGH-IMPACT, MEDIUM-EFFORT Features

### 5. Advanced Search & Filtering Engine

**Impact:** Most requested feature after bulk operations  
**Effort:** 1-2 weeks

```python
# services/search_engine.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from datetime import datetime, timedelta
import re

class SearchOperator(Enum):
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    CONTAINS = "~"
    NOT_CONTAINS = "!~"
    IN = "in"
    NOT_IN = "!in"

class FileProperty(Enum):
    NAME = "name"
    SIZE = "size"
    MTIME = "mtime"
    TYPE = "type"
    TAG = "tag"
    TRANSLATION = "translation"

@dataclass
class SearchCriterion:
    property: FileProperty
    operator: SearchOperator
    value: str
    
    def matches(self, file_info) -> bool:
        """Check if file matches criterion"""
        prop_value = self._get_property_value(file_info)
        
        if self.operator == SearchOperator.EQUALS:
            return prop_value == self.value
        elif self.operator == SearchOperator.CONTAINS:
            return self.value.lower() in str(prop_value).lower()
        elif self.operator == SearchOperator.GREATER_THAN:
            return int(prop_value) > int(self.value)
        elif self.operator == SearchOperator.LESS_THAN:
            return int(prop_value) < int(self.value)
        # ... other operators
        return False
    
    def _get_property_value(self, file_info):
        if self.property == FileProperty.NAME:
            return file_info.name
        elif self.property == FileProperty.SIZE:
            return file_info.size
        elif self.property == FileProperty.MTIME:
            return file_info.mtime
        elif self.property == FileProperty.TYPE:
            return FileTypeDetector.get_category(file_info.path)
        # ... other properties

class SearchQuery:
    def __init__(self, query_string: str):
        self.criteria: List[SearchCriterion] = []
        self._parse_query(query_string)
    
    def _parse_query(self, query_string: str) -> None:
        """Parse human-readable search syntax"""
        # Examples:
        # - "size:>10MB modified:today tag:important"
        # - "type:pdf content:invoice"
        # - "name~report after:2024-01-01"
        
        tokens = re.findall(r'(\w+):([^\s]+)', query_string)
        
        for key, value in tokens:
            try:
                prop = FileProperty[key.upper()]
                criterion = self._parse_criterion(prop, value)
                self.criteria.append(criterion)
            except KeyError:
                continue  # Skip unknown properties
    
    def _parse_criterion(self, prop: FileProperty, value: str) -> SearchCriterion:
        # Detect operator
        if value.startswith(">"):
            op = SearchOperator.GREATER_THAN
            val = value[1:]
        elif value.startswith("<"):
            op = SearchOperator.LESS_THAN
            val = value[1:]
        else:
            op = SearchOperator.EQUALS
            val = value
        
        return SearchCriterion(prop, op, val)
    
    def matches(self, file_info) -> bool:
        """Check if file matches ALL criteria (AND)"""
        return all(c.matches(file_info) for c in self.criteria)

class SearchEngine:
    def __init__(self, file_provider):
        self.file_provider = file_provider
        self.saved_searches = {}
    
    async def search(self, query: SearchQuery) -> List:
        """Execute search query"""
        all_files = await self.file_provider.list_files()
        return [f for f in all_files if query.matches(f)]
    
    def save_search(self, name: str, query_string: str) -> None:
        """Save search as smart folder"""
        self.saved_searches[name] = query_string
    
    async def get_saved_search_results(self, name: str) -> List:
        """Execute saved search"""
        if name not in self.saved_searches:
            return []
        
        query = SearchQuery(self.saved_searches[name])
        return await self.search(query)

# ui/search_panel.py
class SearchDialog(QDialog):
    def __init__(self, search_engine: SearchEngine):
        super().__init__()
        self.search_engine = search_engine
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search input with autocomplete
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "size:>10MB type:pdf modified:today tag:important"
        )
        completer = QCompleter([
            "name:", "size:", "type:", "tag:", "modified:",
            "size:>", "size:<", "modified:today",
            ">10MB", "<5MB"
        ])
        self.search_input.setCompleter(completer)
        layout.addWidget(self.search_input)
        
        # Search button
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._execute_search)
        layout.addWidget(search_btn)
        
        # Results
        self.results_table = QTableWidget()
        layout.addWidget(self.results_table)
        
        # Save search button
        save_btn = QPushButton("Save as Smart Folder")
        save_btn.clicked.connect(self._save_search)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    async def _execute_search(self):
        query_str = self.search_input.text()
        query = SearchQuery(query_str)
        results = await self.search_engine.search(query)
        self._display_results(results)
    
    def _display_results(self, results):
        self.results_table.setRowCount(len(results))
        for row, file_info in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(file_info.name))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(file_info.size)))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(file_info.mtime)))
    
    def _save_search(self):
        name, ok = QInputDialog.getText(self, "Save Search", "Search name:")
        if ok and name:
            query = self.search_input.text()
            self.search_engine.save_search(name, query)
```

**Features:**
- Human-readable syntax: `size:>10MB modified:today tag:important`
- saved searches (smart folders)
- Complex filters (any/all matching)
- Integration with tag system

---

### 6. Glossary & Terminology Management

**Impact:** Translation consistency for professional translators  
**Effort:** 1 week

```python
# services/glossary.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import csv
from pathlib import Path

@dataclass
class TermEntry:
    source_term: str
    target_term: str
    part_of_speech: str = ""
    definition: str = ""
    example: str = ""
    priority: int = 1  # 1-10, higher = use more often
    context: List[str] = field(default_factory=list)  # e.g., ["technical", "legal"]

class Glossary:
    def __init__(self, name: str):
        self.name = name
        self.entries: Dict[str, List[TermEntry]] = {}  # source_term -> [entries]
        self.language_pair: Optional[tuple] = None
    
    def add_entry(self, entry: TermEntry) -> None:
        """Add term to glossary"""
        source = entry.source_term.lower()
        if source not in self.entries:
            self.entries[source] = []
        self.entries[source].append(entry)
        # Sort by priority (descending)
        self.entries[source].sort(key=lambda e: e.priority, reverse=True)
    
    def suggest(self, term: str, context: Optional[str] = None) -> Optional[str]:
        """Get suggestion for term"""
        key = term.lower()
        if key not in self.entries:
            return None
        
        entries = self.entries[key]
        
        # If context provided, filter by context
        if context:
            context_entries = [
                e for e in entries if context in e.context
            ]
            if context_entries:
                return context_entries[0].target_term
        
        # Return highest priority entry
        return entries[0].target_term
    
    def fuzzy_match(self, term: str, threshold: float = 0.8) -> List[TermEntry]:
        """Find similar terms using fuzzy matching"""
        from difflib import SequenceMatcher
        
        matches = []
        for source_term, entries in self.entries.items():
            similarity = SequenceMatcher(
                None, term.lower(), source_term
            ).ratio()
            if similarity >= threshold:
                matches.extend(entries)
        
        return sorted(matches, key=lambda e: e.priority, reverse=True)
    
    def export_csv(self, filepath: Path) -> None:
        """Export glossary to CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Source Term", "Target Term", "POS", "Definition",
                "Example", "Priority", "Contexts"
            ])
            
            for entries in self.entries.values():
                for entry in entries:
                    writer.writerow([
                        entry.source_term,
                        entry.target_term,
                        entry.part_of_speech,
                        entry.definition,
                        entry.example,
                        entry.priority,
                        "|".join(entry.context),
                    ])
    
    @staticmethod
    def import_csv(filepath: Path) -> 'Glossary':
        """Import glossary from CSV"""
        glossary = Glossary(filepath.stem)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entry = TermEntry(
                    source_term=row["Source Term"],
                    target_term=row["Target Term"],
                    part_of_speech=row.get("POS", ""),
                    definition=row.get("Definition", ""),
                    example=row.get("Example", ""),
                    priority=int(row.get("Priority", "1")),
                    context=row.get("Contexts", "").split("|") if row.get("Contexts") else [],
                )
                glossary.add_entry(entry)
        
        return glossary

class GlossaryManager:
    def __init__(self):
        self.glossaries: Dict[str, Glossary] = {}
        self.active_glossary: Optional[str] = None
    
    def create_glossary(self, name: str, language_pair: tuple) -> Glossary:
        """Create new glossary"""
        glossary = Glossary(name)
        glossary.language_pair = language_pair
        self.glossaries[name] = glossary
        return glossary
    
    def get_suggestion(self, term: str, context: Optional[str] = None) -> Optional[str]:
        """Get translation suggestion from active glossary"""
        if self.active_glossary and self.active_glossary in self.glossaries:
            return self.glossaries[self.active_glossary].suggest(term, context)
        return None

# services/translator.py (modification)
class OpenAITranslator(Translator):
    def __init__(self, glossary_manager: Optional[GlossaryManager] = None):
        super().__init__()
        self.glossary_manager = glossary_manager
    
    def translate_title(self, title: str, target_language: str) -> Optional[str]:
        # Check glossary first
        if self.glossary_manager:
            suggestion = self.glossary_manager.get_suggestion(title)
            if suggestion:
                return suggestion
        
        # Fall back to API
        return super().translate_title(title, target_language)
    
    def translate_titles(self, titles: List[str], target_language: str) -> List[Optional[str]]:
        results = []
        for title in titles:
            # Check glossary
            if self.glossary_manager:
                suggestion = self.glossary_manager.get_suggestion(title)
                if suggestion:
                    results.append(suggestion)
                    continue
            
            # Fall back to API
            result = self.translate_title(title, target_language)
            results.append(result)
        
        return results

# ui/glossary_dialog.py
class GlossaryManagerDialog(QDialog):
    def __init__(self, glossary_manager: GlossaryManager):
        super().__init__()
        self.glossary_manager = glossary_manager
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Glossary selector
        selector_layout = QHBoxLayout()
        self.glossary_combo = QComboBox()
        self.glossary_combo.addItems(self.glossary_manager.glossaries.keys())
        selector_layout.addWidget(QLabel("Active Glossary:"))
        selector_layout.addWidget(self.glossary_combo)
        layout.addLayout(selector_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("New Glossary", self._create_glossary))
        btn_layout.addWidget(QPushButton("Import CSV", self._import_glossary))
        btn_layout.addWidget(QPushButton("Export CSV", self._export_glossary))
        btn_layout.addWidget(QPushButton("Edit Terms", self._edit_terms))
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _create_glossary(self):
        name, ok = QInputDialog.getText(self, "New Glossary", "Name:")
        if ok and name:
            self.glossary_manager.create_glossary(name, ("English", "French"))
```

---

## 💎 HIGH-IMPACT, HIGH-EFFORT Features

### 7. Workflow Automation Rules Engine

**Impact:** Enterprise users can automate repetitive tasks  
**Effort:** 2-3 weeks

```python
# services/automation.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from enum import Enum
import json

class TriggerType(Enum):
    FILE_ADDED = "file_added"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    TRANSLATION_COMPLETE = "translation_complete"
    TAG_ADDED = "tag_added"
    SCHEDULED = "scheduled"

class ActionType(Enum):
    MOVE = "move"
    COPY = "copy"
    DELETE = "delete"
    TAG = "tag"
    RENAME = "rename"
    TRANSLATE = "translate"
    SEND_WEBHOOK = "send_webhook"
    NOTIFY = "notify"

@dataclass
class Condition:
    property: str  # e.g., "filename", "size", "type"
    operator: str  # "contains", "equals", "greater_than"
    value: str

@dataclass
class Action:
    type: ActionType
    parameters: Dict  # Action-specific params

@dataclass
class AutomationRule:
    name: str
    trigger: TriggerType
    conditions: List[Condition]
    actions: List[Action]
    enabled: bool = True
    description: str = ""

class AutomationEngine:
    def __init__(self):
        self.rules: List[AutomationRule] = []
        self.listeners: Dict[TriggerType, List[Callable]] = {
            t: [] for t in TriggerType
        }
    
    def add_rule(self, rule: AutomationRule) -> None:
        """Register automation rule"""
        self.rules.append(rule)
    
    def trigger(self, trigger_type: TriggerType, context: Dict) -> None:
        """Fire trigger and execute matching rules"""
        for rule in self.rules:
            if not rule.enabled or rule.trigger != trigger_type:
                continue
            
            # Check all conditions
            if self._match_conditions(rule.conditions, context):
                # Execute actions
                for action in rule.actions:
                    self._execute_action(action, context)
    
    def _match_conditions(self, conditions: List[Condition], context: Dict) -> bool:
        """Check if all conditions match (AND logic)"""
        for condition in conditions:
            value = context.get(condition.property, "")
            
            if condition.operator == "contains":
                if condition.value not in value:
                    return False
            elif condition.operator == "equals":
                if condition.value != value:
                    return False
            # ... other operators
        
        return True
    
    def _execute_action(self, action: Action, context: Dict) -> None:
        """Execute automation action"""
        if action.type == ActionType.MOVE:
            # Implement move
            pass
        elif action.type == ActionType.TAG:
            # Add tag to file
            pass
        elif action.type == ActionType.SEND_WEBHOOK:
            # Send to webhook
            pass
        # ... other actions

# Example rules:
rules = [
    AutomationRule(
        name="Auto-tag PDFs",
        trigger=TriggerType.FILE_ADDED,
        conditions=[Condition("type", "equals", "pdf")],
        actions=[Action(ActionType.TAG, {"tag": "document"})],
    ),
    AutomationRule(
        name="Archive old files",
        trigger=TriggerType.SCHEDULED,  # Daily
        conditions=[Condition("age_days", "greater_than", "90")],
        actions=[Action(ActionType.MOVE, {"destination": "/Archive"})],
    ),
]
```

---

## 🎯 MEDIUM-IMPACT, LOW-EFFORT Quick Wins

### 8. Dark Mode Themes

**Effort:** 1 day (if using stylesheet)

### 9. Improved Error Messages

**Effort:** 2-3 days (review all error paths)

### 10. Notification System

**Effort:** 2-3 days (integrate with OS notifications)

### 11. Bulk Processing with Progress

**Effort:** 2-3 days (progress bars, cancellation)

### 12. File Type Icons

**Already covered above** ✅

---

## Feature Implementation Priority Matrix

```
IMPACT
 ^
 │    💎 Automation Rules  💎 Workflow Rules
 │    ⭐ Glossary          ⭐ Plugin System
 │    ⭐ Search Engine     ⭐ Offline Mode
 │    🚀 Session Mgmt      🚀 Notifications
 │    🎯 Dark Mode         🎯"Error Handling
 │
 └─────────────────────────────────────────> EFFORT
      quick   easy    medium   hard    very hard
```

---

## Implementation Timeline

```
PHASE 1 (Weeks 1-2):     PHASE 2 (Weeks 3-6):
🚀 Session Management    ⭐ Advanced Search
🚀 Clipboard History     ⭐ Glossary Management
🚀 File Type Icons       ⭐ Plugin Architecture
🎯 Dark Mode
🎯 Shortcuts Customizer

PHASE 3 (Weeks 7-10):    PHASE 4 (Weeks 11+):
💎 Automation Rules      💎 Cloud Sync
💎 Workflow Engine       💎 Mobile Support
💎 Collaboration         💎 Analytics
```

---

## Success Metrics

For each feature, track:

1. **Adoption Rate:** % users using feature
2. **Time Saved:** Estimated hours per user per week
3. **Error Reduction:** Fewer "oops" moments
4. **User Satisfaction:** NPS impact
5. **Technical Debt:** Does it solve or create problems?

---

*Document Version: 1.0*  
*Last Updated: February 13, 2026*
