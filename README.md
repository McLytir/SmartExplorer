SmartExplorer — AI-Assisted Two-Pane File Explorer (Windows • Linux • macOS)

Overview
- Two synchronized panes: left shows your real files; right shows AI-translated names side-by-side (no automatic rename).
- Confirmed renames only: apply translated names in bulk with a review dialog and one-click undo.
- Optional SharePoint backend: browse, rename, copy/move, upload/download via SharePoint REST using your browser cookies (no Azure app).

Key Features
- Translation preview pane: shows natural translations of file/folder names in your target language without changing disk names.
- Bulk Rename Preview + Undo: review conflicts, edit names inline, apply in one shot, and undo the last batch.
- Open files from the app: double-click opens with the system default app (SharePoint items download to a configurable folder first).
- Reveal and Copy Path: “Reveal in Explorer/Finder/Files” and “Copy Path” from the context menu.
- Breadcrumbs + Go To: click path segments to jump; press Ctrl+K (?K on macOS) for a quick “Go To” palette.
- Favorites and Layout Tabs: save layouts of panes and switch via tabs.
- Smart titles: pane headers auto-reflect the current location; you can also manually rename a pane and reset to auto when needed.
- Caching: avoids re-translating unchanged names across sessions; supports name-only cache for common terms.

OS Support
- Windows: full support (Explorer integration for reveal, standard shortcuts).
- Linux: works with common desktop environments (xdg-open for reveal/open).
- macOS: native file open and Finder reveal; mac-friendly shortcuts (?K, ?L, ?[, ?], ??).

Install
1) Create and activate a virtualenv
   - PowerShell:
     - `python -m venv .venv`
     - `.\.venv\Scripts\Activate.ps1`
   - bash/zsh:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`
2) Install dependencies
   - `pip install -r requirements.txt`
3) Provide an API key (optional)
   - Easiest: launch the app and open Settings (gear icon) to paste your OpenAI API key.
   - Or set env var before launch: `OPENAI_API_KEY=sk-...`

Run
- Desktop app: `python -m smart_explorer.app`
- Optional backend (SharePoint): `python -m smart_explorer.backend.server`
  - Health: http://127.0.0.1:5001/api/health

SharePoint Setup (Cookie-Backed)
1) In Settings, set “SharePoint Site URL” (e.g., `https://tenant.sharepoint.com/sites/SiteName`).
2) Provide cookies via either:
   - Paste full Cookie header (FedAuth/rtFa) in Settings, then “Send to Backend”, or
   - Use “Capture Cookies” (sign in via your browser, then send captured cookies).
3) Optional: choose “SharePoint Download Dir” — where files are downloaded before opening.

Using the App
- Add panes:
  - Local: choose a folder.
  - SharePoint: pick a site/library.
  - Translation: pick a base pane and a language.
- Translate & rename:
  - The right (translation) pane mirrors the base pane location automatically.
  - Use “Apply Translation Rename” to review and apply changes; use “Undo Last Rename” if needed.
- Navigation:
  - Breadcrumbs in each pane; Go To palette (Ctrl+K / ?K); address bar (Ctrl+L / ?L).
- Pane titles:
  - Auto: shows current folder/library or “<Base> ? <Language>” for translation panes.
  - Manual: right-click pane header ? “Rename Pane…”. Reset via “Reset Auto Title”.

Shortcuts
- Ctrl+K / ?K: Go To…
- Ctrl+L / ?L: Focus address bar
- Alt+Left/Right/Up or ?[/?]/??: Back/Forward/Up
- Standard Copy/Cut/Paste/Delete work as expected

Settings & Config
- Settings dialog covers: API key, model, target language, theme, backend URL, SharePoint site URL, optional library root, SharePoint download dir, ignore patterns.
- A JSON config `smart_explorer_config.json` is stored in the working directory; settings persist automatically.
- Environment variable `OPENAI_API_KEY` overrides the API key.

Backend Endpoints (selected)
- `GET /api/health`
- `GET /api/settings`, `POST /api/settings`
- `POST /api/sp/cookies`
- `GET /api/sp/sites`, `GET /api/sp/libraries?site_relative_url=...`
- `GET /api/sp/list?site_relative_url=...&folder_server_relative_url=...`
- `POST /api/sp/rename` `{ server_relative_url, new_name, is_folder }`
- `POST /api/sp/copy`, `POST /api/sp/move`, `POST /api/sp/delete`, `POST /api/sp/folder`, `POST /api/sp/upload`
- `GET /api/sp/download?server_relative_url=...`
- `POST /api/sp/share-link` `{ server_relative_url }`

Notes & Tips
- Translation cache is both in-memory and on-disk to reduce repeat costs and latency.
- Ignore patterns help skip noisy folders (defaults include `.git`, `node_modules`, `__pycache__`, `.venv`, `*.tmp`).
- You can run without an API key; translation pane will show original names (identity mode).

Troubleshooting
- If you hit rate limits or see many pending items, collapse folders or navigate a bit slower.
- On Linux, install `xdg-utils` for reliable “open”/“reveal”.
- SharePoint errors often stem from expired cookies — recapture or resend cookies in Settings.