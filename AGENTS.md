# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

## Repository layout

- `README.md` — project overview, API docs, and quick start (entry point).
- `BLOG_DEVELOPMENT.md` — blog system design, DB schema, and progress.
- `insight/` — Chrome Manifest V3 extension (no build step, load unpacked directly).
- `InsightIOS/` — SwiftUI + SwiftData iOS app with Share Extension.
- `web/` — React 19 + TS + Material UI blog frontend.
- `server/` — FastAPI + SQLite backend (deep-collection + blog + Agent/Skills APIs).

## Running the extension

`chrome://extensions` → Developer mode → "Load unpacked" → select `insight/`.

## Architecture (`insight/`)

MV3 extension with two core files:

| File | Role |
|------|------|
| `background.js` | Service worker: API requests, auth token management, message routing |
| `popup.js` | Popup UI: save current page, category selection, recent articles, settings/login |

### Workflow

1. User clicks extension icon → popup shows current page URL and category list
2. User selects category (or leaves default) → clicks "保存"
3. Extension sends `POST /api/v1/insight/articles/save` to server
4. Server triggers background task: extract content → translate → save
5. Popup shows recent articles and stats

## Language

Respond in Chinese (中文), except for technical terms.

## UI style

陶土橙 (#b95737) accent color, warm paper-like background.

## Working style

- **Think before coding:** state assumptions; ask if unclear.
- **Simplicity first:** minimum code, no speculative features.
- **Surgical changes:** touch only what's needed; match existing style.
- **Goal-driven:** verify against acceptance criteria from `README.md`.