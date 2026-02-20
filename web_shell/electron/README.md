# SmartExplorer Web-First Desktop Shell (Electron)

This is an active migration target for SmartExplorer and now mirrors most daily workflows.

## Currently ported
- Two-pane browsing with per-pane source mode:
  - Local filesystem
  - SharePoint libraries/folders
- Operations:
  - Copy, cut, paste
  - Rename, delete, create folder
  - Open and reveal
  - Upload to local or SharePoint panes
- Cross-source transfers:
  - Local -> SharePoint (files)
  - SharePoint -> Local (files)
- Translation:
  - Toggle translated names
  - Apply translated rename (local + SharePoint)
  - Undo last rename batch (local + SharePoint)
- Preview/AI:
  - Image/PDF/video/audio preview
  - Text extraction preview
  - AI summary and document Q&A for local and SharePoint files
- Tags:
  - Set/get/search tags for selected item
- SharePoint advanced actions:
  - Check-out / Check-in / Undo check-out
  - Version list / download version / restore version
  - Properties panel
  - Embedded SharePoint sign-in window with automatic cookie capture
- Productivity:
  - Favorites (localStorage)
  - Layout save/load + quick layout tabs
  - Multi-session workspace tabs
  - Recent locations list
  - Pane-level filter search
  - Operation log panel
  - Config export/import (JSON, includes sessions)
  - Rename-preview conflict checks before bulk translated rename
  - Keyboard shortcuts: Ctrl+C / Ctrl+X / Ctrl+V / Delete

## Run
1. Start backend once (optional if Electron can launch it):
   - `python -m smart_explorer.backend.server`
2. Install Electron deps:
   - `cd web_shell/electron`
   - `npm install`
3. Launch shell:
   - `npm start`

The shell opens `http://127.0.0.1:5001/web/index.html` in Electron.

## Optional env vars
- `SMX_BACKEND_URL` (default `http://127.0.0.1:5001`)
- `SMX_PYTHON` (default `python`)
