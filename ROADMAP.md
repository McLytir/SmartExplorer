# SmartExplorer Roadmap & Task List

## Preview Enhancements
- [ ] PDF translation overlay: extract page text, map to coordinates, draw translucent translated text over original; toggle and opacity controls.
- [ ] Live page summaries: per-page TL;DR and full document outline; clickable to jump.
- [ ] Inline glossary highlights: underline terms; hover shows preferred translation/notes.
- [ ] Annotations: add highlights/notes in preview; export/import as JSON or XFDF.
- [x] SharePoint previews pull from downloaded local copies and auto-open externally when needed.
- [ ] Page thumbnails and mini-map for quick navigation.

## AI-Powered Tools
- [x] Smart summaries with length/tone presets (tweet, paragraph, executive brief); include key risks/action items.
- [x] Document Q&A prompt (custom questions with grounded answers).
- [ ] Translation modes (identity/MT/post-edit) with confidence and “needs review” flags.
- [ ] Rewrite helpers: simplify language, bulletify, translate and adapt for client X.

## OCR & Formats
- [ ] OCR fallback for scanned PDFs (Tesseract); overlay recognized text for copy/translate/summarize.
- [ ] Office previews: server-side conversion (LibreOffice headless) to PDF/HTML for consistent preview.
- [ ] Image translation: detect text regions, OCR, and overlay translated boxes.

## SharePoint & Workflow
- [ ] Bulk export with preserved folder structure; resumable downloads.
- [x] Download action with streaming progress; bulk zip and optional auto-extract.
- [x] Drag “preparing files” progress; >20MB auto-zipping on drag for smoother drops.
- [x] Check-out/edit workflow (local edit sessions); upload edited file(s) back to SharePoint.
- [ ] True SharePoint CheckOut/CheckIn via REST (locks, comments, versioning).
- [ ] Saved searches and smart folders (e.g., modified last 7 days; has French content).
- [ ] Translation panes follow base SharePoint navigation reliably (fix sync issues).

## Search & Navigation
- [x] Tag filtering and tag search for local workspaces.
- [ ] Full-text search inside preview (original + translated) with page hits and filters.
- [ ] Cross-document search scoped to current SharePoint folder.

## Quality & Controls
- [ ] Glossary/termbase management: CSV import, priority rules, per-client sets.
- [ ] Translation memory cache with fuzzy matches and reuse indicators.


## Runner & DevX
- [x] One-shot runner to start backend + app in one command.
- [ ] Packaging/distribution scripts for Windows/macOS/Linux.
- [ ] User-configurable shortcut system (hotkey editor with presets & validation).
