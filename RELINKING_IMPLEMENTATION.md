# Relinking Rework Implementation

## Goal

Replace the current scattered link-migration and bookmark-conversion tools with a dedicated relinking workflow.

The new relinking workflow must support:

1. Background capture of SharePoint moves, renames, and new links.
2. Bookmark HTML import that is automatically normalized into JSON in the background.
3. A resolve action that generates resolved JSON and then exports browser-compatible bookmark HTML.

## Target UX

### Desktop

- Add a dedicated `Relinking` tab or dock surface.
- Move current `Resolve Old Link`, `View Link Log`, and bookmark conversion entry points into this surface.
- Keep background movement capture invisible to the user.

### Web Shell

- Add a dedicated `Relinking` tab in the right-side inspector.
- Remove dependence on the current `Link Migration Log` card as the only workflow surface.
- Present relinking as a managed flow:
  - `Activity`
  - `Imports`
  - `Resolve`
  - `Exports`

## Functional Model

### 1. Background movement capture

The existing `LinkMigrationLog` remains the movement source of truth.

It should continue to record:

- SharePoint rename
- SharePoint move
- folder moves that affect descendants
- new link targets where relevant

This remains background-only.

### 2. Imported bookmark artifacts

Imported bookmark HTML should no longer be treated as a one-off conversion.

Each import becomes a managed artifact with:

- `id`
- `name`
- `imported_at`
- `source_format`
- `source_browser`
- `normalized_rows` or normalized tree
- `status`
- counts:
  - total
  - resolved
  - unchanged
  - external

Short term, rows are acceptable.
Long term, the source of truth should be a normalized bookmark tree so folder hierarchy, ordering, and output formatting can be round-tripped more faithfully.

### 3. Resolve artifacts

Resolving an imported bookmark artifact should produce:

- a resolved JSON artifact
- an exported HTML artifact
- counts and summary
- traceability back to the source import

The JSON artifact is the internal resolved state.
The HTML artifact is the user-facing output.

## Data Model

### Existing

- `LinkMigrationLog`
  - movement resolution source

### New

- `RelinkingImportRecord`
- `RelinkingExportRecord`
- `RelinkingWorkspaceStore`

Suggested fields:

```text
RelinkingImportRecord
- id
- name
- imported_at
- source_format
- source_browser
- status
- bookmark_rows
- summary

RelinkingExportRecord
- id
- source_import_id
- created_at
- format
- status
- resolved_rows
- summary
```

## Implementation Phases

### Phase 1. Workflow foundation

- Add this implementation document.
- Add dedicated relinking surface in web shell.
- Add managed import/export state in web shell.
- Keep current migration log store as background activity source.

### Phase 2. Bookmark artifact management

- Change HTML import from direct conversion to managed import records.
- Persist normalized bookmark rows/tree.
- Add resolved export records.
- Auto-export HTML after resolve.

### Phase 3. HTML round-trip fidelity

- Preserve import structure and browser format metadata.
- Generate bookmark HTML from a normalized tree rather than flat rows.
- Add browser-style emitters as needed.

### Phase 4. Desktop relinking tab

- Add dedicated relinking tab/dock in desktop app.
- Move current link migration dialogs into that surface.
- Share relinking data model with web shell where practical.

## Initial Concrete Changes

The first implementation pass should do the following:

1. Add a dedicated `Relinking` tab in the web shell inspector.
2. Store imported bookmark HTML as managed relinking imports.
3. Store resolved outputs as managed relinking exports.
4. Auto-export resolved HTML when a relinking import is resolved.
5. Keep current single-link resolve and migration log export available inside the relinking tab.

## Notes

- The current `bookmark_export_converter.py` is a useful base, but it is still row-oriented.
- The long-term target is a tree-oriented internal model.
- The standard browser bookmark HTML export format is usually Netscape-style HTML; that is the first supported round-trip target.
