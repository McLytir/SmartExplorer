# Feature Spec: SharePoint Link Migration Log

## Purpose

When SmartExplorer moves or renames files and folders in SharePoint, it should keep a persistent mapping of old links to new links.

This allows:
- SmartExplorer to update its own saved favorites automatically
- admins to export mappings and update users' browser bookmarks programmatically
- old links to remain traceable after reorganizations

## Problem

Users often save SharePoint document and folder links in:
- browser bookmarks/favorites
- emails
- notes
- SmartExplorer favorites

When items are moved or renamed, those links become stale. SmartExplorer currently performs the file operation but does not preserve a structured old-to-new link history.

## Goals

- Record every SharePoint move and rename with old and new link information
- Persist that history locally in SmartExplorer
- Auto-update SmartExplorer favorites when a matching saved link changes
- Provide exportable mappings for external bookmark migration tools
- Allow future lookup of an old link or path and resolution to the new one

## Non-Goals

- Automatically updating every browser's bookmarks on every machine
- Acting as a SharePoint redirect service
- Rewriting links inside third-party documents or emails

## Primary Use Cases

### 1. SharePoint move or rename

A user moves a folder or file in SharePoint using SmartExplorer.

Expected result:
- SmartExplorer logs old path/link to new path/link
- SmartExplorer updates matching internal favorites

### 2. Admin export

An admin exports the migration log and uses the data to update browser bookmarks for colleagues.

### 3. Old-link resolution

A user opens an outdated SmartExplorer favorite and SmartExplorer resolves it to the newest known location.

## User Stories

- As a SmartExplorer user, when I move a SharePoint file, I want the old and new links stored automatically.
- As a SmartExplorer user, I want my SmartExplorer favorites updated if a saved SharePoint item moved.
- As an admin, I want to export all link changes so I can update browser bookmarks for users.
- As a user, if I try to open an outdated saved link, I want SmartExplorer to suggest or open the new location.

## Functional Requirements

### 1. Migration Logging

SmartExplorer must:
- log all SharePoint move operations
- log all SharePoint rename operations
- log folder and file changes
- store enough metadata to identify the item and reconstruct user-facing links

### 2. Migration Record Fields

Each migration record should include:
- `id`
- `timestamp`
- `operation_type` (`move`, `rename`, `move_and_rename`)
- `item_type` (`file`, `folder`)
- `source_site_url`
- `old_server_relative_url`
- `new_server_relative_url`
- `old_web_url`
- `new_web_url`
- `old_display_name`
- `new_display_name`
- `workspace_id`
- `initiated_by`
- `status` (`completed`, `failed`, `partial`)
- `notes`

### 3. SmartExplorer Favorites Update

After a successful logged operation, SmartExplorer should:
- search SmartExplorer favorites for matching old links or paths
- rewrite favorites to the new location
- preserve favorite labels where possible
- optionally mark the favorite as updated from migration history

### 4. Export

SmartExplorer should support export to:
- JSON
- CSV

Export should allow filtering by:
- date range
- operation type
- site
- item type

### 5. Resolution

Given an old SharePoint path or URL, SmartExplorer should be able to:
- find a direct migration record
- return the latest known destination

Future enhancement:
- recursively resolve chains such as `A -> B -> C` to current `C`

## Suggested Data Model

```python
from dataclasses import dataclass


@dataclass
class LinkMigrationRecord:
    id: str
    timestamp: str
    operation_type: str
    item_type: str
    source_site_url: str | None
    old_server_relative_url: str
    new_server_relative_url: str
    old_web_url: str | None
    new_web_url: str | None
    old_display_name: str | None
    new_display_name: str | None
    workspace_id: str | None
    initiated_by: str | None
    status: str
    notes: str | None = None
```

## Storage

Recommended V1 approach:
- local JSON file managed by SmartExplorer

Suggested filename:
- `smart_explorer_link_migrations.json`

Possible V2 upgrade:
- SQLite for indexing, filtering, deduplication, and chain resolution

## Behavior Rules

- Only log after a successful SharePoint operation
- Do not log failed operations as successful mappings
- Preserve full history when an item moves multiple times
- Treat the newest mapping as authoritative for resolution
- Handle folder moves carefully because child links implicitly change too

## Folder Move Handling

If a folder moves:
- the folder itself has a direct old-to-new mapping
- all child files and folders also effectively moved

Recommended V1 behavior:
- log the folder move only
- resolve descendants later using prefix substitution

Example:
- old folder: `/sites/A/Docs/OldFolder`
- new folder: `/sites/A/Docs/NewFolder`

Then:
- `/sites/A/Docs/OldFolder/file.pdf`

resolves to:
- `/sites/A/Docs/NewFolder/file.pdf`

## URL Handling

Store both:
- server-relative path
- browser-facing URL

Reason:
- server-relative path is more stable for API operations
- browser URL is what users bookmark

## Favorite Update Rules

If a favorite matches:
- exact old URL
- exact old server-relative path
- descendant of a moved folder path

Then update it to:
- exact new URL or path
- prefix-rewritten descendant when the move was a folder move

## UI Requirements

Later implementation should add:
- settings toggle: `Enable link migration logging`
- history viewer: `Link Migration Log`
- export button
- resolve old link tool
- optional notification when favorites were updated automatically

## Admin Export Format

CSV columns:
- `timestamp`
- `operation_type`
- `item_type`
- `old_server_relative_url`
- `new_server_relative_url`
- `old_web_url`
- `new_web_url`
- `status`

JSON should preserve full metadata.

## Error Handling

- If the operation succeeds but web URL generation fails:
  - still log the path mapping
  - set URL fields to null
- If favorite update fails:
  - keep the migration record
  - log the favorite update failure separately
- If duplicate migrations exist:
  - keep full history instead of overwriting blindly

## Security and Privacy

- Do not store secrets, cookies, or auth tokens in the migration log
- Avoid storing personal data unless explicitly required
- If `initiated_by` is stored, keep it minimal

## Open Questions

- Should migration logs be per-user or shared/team-wide?
- Should SmartExplorer support importing migration logs from another machine?
- Should folder descendant resolution happen eagerly or only at lookup time?
- Should browser bookmark remediation be a separate admin script in this repo?

## Recommended V1 Scope

- local persistent JSON log
- logging for SharePoint move and rename operations
- SmartExplorer favorites auto-update
- export to JSON and CSV
- exact-match and folder-prefix resolution

## Recommended V2 Scope

- log viewer UI
- chain resolution
- SQLite storage
- admin remediation script for browser bookmarks
- import/export sync across machines

## Acceptance Criteria

- Moving or renaming a SharePoint item in SmartExplorer creates a persistent migration record
- SmartExplorer favorites referencing the old location are updated automatically
- Export produces usable JSON and CSV mapping data
- Old links can be resolved to the latest known location within SmartExplorer
- Folder moves correctly update descendant favorite links via prefix mapping
