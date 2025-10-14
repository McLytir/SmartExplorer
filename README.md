SmartExplorer — AI-Assisted Two‑Pane File Explorer (Windows)

Overview
- Left pane: real filesystem view.
- Right pane: mirrored view showing AI‑translated names (does not rename on disk).
- Optional action to apply a translated name as an actual rename (explicit confirmation).
- Pluggable translation provider (OpenAI implementation included).

Backend (WebDAV Mapped SharePoint)
- New optional backend API that works with SharePoint via mapped network drives (WebDAV). No Azure app registration required.
- List and rename operations use normal filesystem APIs against mapped drives; Windows handles SharePoint auth.

Quick Start
1) Create and activate a virtualenv
   - PowerShell:
     - `python -m venv .venv`
     - `.\\.venv\\Scripts\\Activate.ps1`

2) Install dependencies
   - `pip install -r requirements.txt`

3) Provide an API key (two options)
   - Easiest: Launch the app and open Settings (gear icon) to paste your OpenAI API key.
   - Or: Set env var before launch: `setx OPENAI_API_KEY "sk-..."` (restart shell to take effect).

4) Run
   - `python -m smart_explorer.app`

Backend (optional)
- Start the local backend API:
  - `python -m smart_explorer.backend.server`
- Configure mapped SharePoint roots by editing `smart_explorer_config.json`, e.g.:
  - `{ "webdav_roots": ["Z:\\", "Y:\\SharePointLibrary\\"] }`
- Health check: open `http://127.0.0.1:5001/api/health`

Map a SharePoint Library (WebDAV)
- In Windows Explorer → Map network drive…
- Choose a letter (e.g., `Z:`)
- Folder path example:
  - `\\tenant.sharepoint.com@SSL\DavWWWRoot\sites\SiteName\Shared Documents`
- Sign in with your work account when prompted.

Notes
- Target language defaults to English; change it from the toolbar.
- The app never renames by default; use the context menu or toolbar action to apply a rename for selected items.
- Translations cache in‑memory per session; they are re-fetched as needed.
 - A persistent on‑disk cache (`smart_explorer_cache.json`) avoids re-translating unchanged files between runs.
 - Use the search box to filter both panes; it matches original and translated names.
 - Expanding folders on the left synchronizes expansion on the right.
- Backend endpoints (when enabled):
   - `GET /api/list?path=...` → children under a mapped drive folder
   - `POST /api/rename` with `{ path, newName }` → rename on disk (SharePoint via WebDAV)
   - `POST /api/translate` with `{ language, items:[{ name, path, mtime }] }` → batch translations (deduplicated names, uses in‑memory + disk caches)
   - `POST /api/warmup` with `{ path, recursive?: bool, max_items?: number }` → pre-translate a directory tree into caches
   - `GET /api/warmup/stream?path=...&recursive=true&max_items=1000&batch_size=100` → Server‑Sent Events stream of warmup progress
     - Events: `folder` (starting a folder), `progress` (counters update), `done` (final counts), `error` (non-fatal step error)
   - SharePoint (cookie-backed, no Azure app):
     - `POST /api/settings` with `{ sp_base_url: "https://tenant.sharepoint.com/sites/SiteName" }`
     - `POST /api/sp/cookies` with `{ base_url, cookie_header: "FedAuth=...; rtFa=..." }` or `{ cookies: { FedAuth: "...", rtFa: "..." } }`
     - `GET /api/sp/list?site_relative_url=/sites/SiteName&folder_server_relative_url=/sites/SiteName/Shared%20Documents` → list folders/files
     - `POST /api/sp/rename` with `{ server_relative_url, new_name, is_folder }` → rename via SharePoint REST MoveTo
   - `GET /api/settings` → returns current settings (sans API key, with `has_api_key`)
   - `POST /api/settings` → updates settings (fields: `target_language`, `model`, `webdav_roots`, `ignore_patterns`, `api_key`)

Config
- A small JSON config is stored at `smart_explorer_config.json` next to the executable working directory. It holds:
  - `api_key` (OpenAI)
  - `model` (default `gpt-4o-mini`)
  - `target_language`
  - `root_path`
  - `ignore_patterns` (glob list; defaults: `.git`, `node_modules`, `__pycache__`, `.venv`, `*.tmp`)
 - `webdav_roots` (array of allowed absolute paths under mapped SharePoint drives)

Caching
- On-disk cache `smart_explorer_cache.json` stores translations keyed by `language+path+mtime+name`.
- Name-only cache: common file/folder names also cached by `language+name` to avoid re-translation across locations.
- Backend keeps an in-memory LRU to reduce repeat calls within a session.
 - Translator batching: unknown names in a request are sent together to the AI to reduce API calls; falls back gracefully per-item if needed.
 - Warmup SSE: stream progress so a UI can show live status while pre‑caching translations.

How To Run
- Map your SharePoint library as a network drive (e.g., `Z:`) via Windows Explorer.
- Edit `smart_explorer_config.json` and set allowed roots, e.g. `{ "webdav_roots": ["Z:\\"] }`.
- Backend:
  - Start: `python -m smart_explorer.backend.server`
  - Health: open `http://127.0.0.1:5001/api/health`
  - List: `GET /api/list?path=Z:%5C` (URL-encode backslashes)
  - Warmup SSE: open `http://127.0.0.1:5001/api/warmup/stream?path=Z:%5C&recursive=true&batch_size=100`
- Desktop app (optional local filesystem view):
  - Start: `python -m smart_explorer.app`
  - Use the toolbar to pick a local root, set language, and optionally set your OpenAI API key.

SharePoint (Cookie-backed) Setup
- Set base URL: `POST /api/settings` with `{ "sp_base_url": "https://peakenergyasia.sharepoint.com/sites/PeakEnergy-All" }`.
- Sign into the SharePoint site in your browser and ensure you can access the library.
- Get cookies (HttpOnly) from DevTools:
  - F12 → Application/Storage → Cookies → your SharePoint site → copy values for cookies `FedAuth` and `rtFa`.
  - Send to backend: `POST /api/sp/cookies` with `{ "base_url": "https://.../sites/PeakEnergy-All", "cookies": { "FedAuth": "<value>", "rtFa": "<value>" } }`.
- List items:
  - `GET /api/sp/list?site_relative_url=/sites/PeakEnergy-All&folder_server_relative_url=/sites/PeakEnergy-All/Shared%20Documents`
- Rename an item:
  - `POST /api/sp/rename` with `{ "server_relative_url": "/sites/PeakEnergy-All/Shared%20Documents/General/File.docx", "new_name": "New Name.docx", "is_folder": false }`

Troubleshooting
- If you see many pending translations or rate limiting, reduce how many folders you expand at once.
- You can run without an API key; the translator will fall back to an identity (no-op) translator.
