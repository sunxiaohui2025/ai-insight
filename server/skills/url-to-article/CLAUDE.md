# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

InSight is an "AI reading ecosystem": a cross-platform deep-bookmarking system (Chrome extension + iOS App with Share Extension) + a React blog (`web/`), all backed by one self-hosted FastAPI cloud. The authoritative overview/entry point is `README.md`; the blog design & progress doc is `BLOG_DEVELOPMENT.md`.

```
insight/         # Chrome Manifest V3 extension (no build step, load unpacked)
InsightIOS/      # SwiftUI + SwiftData iOS app (Xcode project) + Share Extension
server/          # FastAPI + SQLite backend (deep-collection + blog + Agent/Skills APIs)
web/             # React 19 + TS + Material UI blog frontend (see web/README.md)
```

## Commands

### Server

```bash
cd server

# Init venv & install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit config (see env vars section below)
cp .env.example .env

# Production-style start (reads .env, no auto-reload)
./start.sh              # start | stop | restart | status | logs

# Dev start with auto-reload (reads .env.local)
./start-local.sh

# Docker
docker compose up -d --build   # binds 127.0.0.1:8000

# Verify
curl http://localhost:8080/health    # or the port in .env
```

### Chrome extension (`insight/`)

No build step. `chrome://extensions` → Developer mode → "Load unpacked" → select `insight/`.

### iOS (`InsightIOS/`)

Open in Xcode, configure signing, add Share Extension target, build & run.

---

## General principles

- **Cloud-first**: Content extraction and translation runs server-side. Chrome extension and iOS app are thin clients.
- **Strict translation**: LLM translates full content without summarization, condensation, or omission. Format preserved.
- **Content extraction pipeline**: trafilatura (primary) → BeautifulSoup (fallback) → LLM (last resort).
- **LLM constraint**: ALL chat completion calls MUST include `"chat_template_kwargs": {"enable_thinking": false}`, `temperature: 0`.
- **Language**: respond in 中文 except for technical terms.
- **UI style**: 陶土橙 (#b95737) accent color, warm paper-like background.

---

## Chrome extension (`insight/`)

### Core files

| File | Role |
|------|------|
| `background.js` | Service worker: API requests, auth token management, message routing |
| `popup.js` | Popup UI: save current page, category selection, recent articles, settings/login |
| `popup.html` | Popup layout with stats, article list, settings panel |

### Storage (`chrome.storage.local`)

| Key | Type | Description |
|-----|------|-------------|
| `insight_baseURL` | string | Server base URL |
| `insight_token` | string | Auth token |
| `insight_user` | object | `{email, name, role}` |
| `insight_credentials` | object | Saved `{email, password}` for autofill |

---

## iOS App (`InsightIOS/`)

SwiftUI + SwiftData, iOS 17+.

### SwiftData models

- **Article** (`Models/Article.swift`): id (unique), url, title, sourceDomain, originalContent, translatedContent, excerpt, status (pending/extracting/translating/ready/failed), isRead, isStarred, wordCount, categoryId/Name/Icon, timestamps.
- **Category** (`Models/Category.swift`): id (unique), name, icon, sortOrder, articleCount.

### Key services

- `CloudService.swift`: Auth (login/register/logout via Keychain), REST client (GET/POST/PATCH/DELETE), codable response models. Server URL stored in `UserDefaults.standard` under key `insightBaseURL`.
- `AppTheme.swift`: 陶土橙 color palette and typography.

### Share Extension (`InsightShare/`)

- `ShareViewController.swift`: UIKit VC receiving shared URLs, loads categories from API, saves to server.
- `SharePreprocessor.js`: JavaScript preprocessor for extracting URL/title from web pages.

### Keychain

Token stored in Keychain with service `com.sun.insight.cloud`, account `token`.

---

## Server (`server/`)

Single-file FastAPI app (`app/main.py`) + SQLite. No ORM — raw sqlite3. Admin console HTML is embedded as a raw Python string (`ADMIN_HTML`).

### Environment variables (`INSIGHT_*` prefix)

Code uses the `INSIGHT_*` prefix (shown in `.env.example`). Note: **port and workers are read directly** (not via `INSIGHT_PORT`):

| Variable | Default | Description |
|---|---|---|
| `INSIGHT_SECRET` | `change-me-in-production` | HMAC signing secret for tokens |
| `INSIGHT_ADMIN_EMAIL` | — | Auto-created admin user |
| `INSIGHT_ADMIN_PASSWORD` | — | Admin password (scrypt hashed at bootstrap) |
| `INSIGHT_DATABASE` | `server/insight.db` | SQLite file path |
| `INSIGHT_LLM_BASE_URL` | `http://127.0.0.1:6018` | vLLM / OpenAI-compatible base URL |
| `INSIGHT_LLM_MODEL` | `your-model` | Model name |
| `INSIGHT_LLM_API_KEY` | — | API key (server-side only, never sent to clients) |
| `INSIGHT_PUBLIC_URL` | — | Public-facing URL (for CORS/docs) |
| `INSIGHT_SKILLS_PATH` | `server/data/skills` | Skills storage dir |
| `INSIGHT_UPLOADS_PATH` | `server/data/agent_uploads` | Agent file uploads dir |
| `INSIGHT_MEDIA_PATH` | — | Media storage |
| `INSIGHT_PORT` / workers | `8000` / `2` | Listen port / uvicorn workers |

### Bootstrap behavior

- On first startup (`@app.on_event("startup")`), `init_db()` creates all tables and calls `bootstrap_admin()`.
- `bootstrap_admin()` uses `INSERT OR IGNORE` — admin is created once and never updated even if `.env` changes.
- `bootstrap_default_categories()` lazily creates 5 default categories per user on first API call.

### Two startup scripts

| Script | Env file | Uvicorn flags | Use case |
|--------|----------|---------------|----------|
| `start.sh` | `.env` (env var `WORDHINT_ENV_FILE` overrideable) | `--workers N --proxy-headers` | Production |
| `start-local.sh` | `.env.local` | `--reload` | Development (hot reload) |

### LLM proxy endpoint

`POST /api/v1/llm/chat` accepts OpenAI-compatible chat completion requests and proxies to the configured LLM. The API key is held server-side — clients never see it. Injects `temperature: 0`, `enable_thinking: false` automatically.

### InSight content processing

Article save (`POST /api/v1/insight/articles/save`) returns immediately with status `pending` and triggers a FastAPI `BackgroundTasks`:

1. **Extract** (status → `extracting`): trafilatura → BeautifulSoup fallback → LLM fallback (sends truncated HTML)
2. **Translate** (status → `translating`): chunked at 6000 chars, strict translation prompt
3. **Ready** (status → `ready`): generates excerpt (first 200 chars of translation)

Failed articles get status `failed`.

### All API endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/health` | None | Health check |
| `POST` | `/api/v1/auth/register` | None | Register (status: pending) |
| `POST` | `/api/v1/auth/login` | None | Login → token |
| `GET` | `/api/v1/me` | User | Current user info |
| `POST` | `/api/v1/sync` | User | WordHint vocabulary sync |
| `POST` | `/api/v1/llm/chat` | User | LLM proxy |
| `GET` | `/admin` | Admin | Admin console (HTML page) |
| `GET/PATCH` | `/api/v1/admin/users` | Admin | User management |
| `GET/PUT` | `/api/v1/admin/llm` | Admin | LLM config |
| `GET` | `/api/v1/admin/stats` | Admin | Usage statistics |
| `GET` | `/api/v1/insight/categories` | User | List categories |
| `POST` | `/api/v1/insight/categories` | User | Create category |
| `PUT` | `/api/v1/insight/categories/reorder` | User | Reorder categories |
| `PUT` | `/api/v1/insight/categories/{id}` | User | Update category |
| `DELETE` | `/api/v1/insight/categories/{id}` | User | Delete category |
| `POST` | `/api/v1/insight/articles/save` | User | Save article (async) |
| `GET` | `/api/v1/insight/articles` | User | List (filter/search/paginate) |
| `GET` | `/api/v1/insight/articles/{id}` | User | Detail (marks as read) |
| `PATCH` | `/api/v1/insight/articles/{id}` | User | Update (category/read/star) |
| `DELETE` | `/api/v1/insight/articles/{id}` | User | Delete article |
| `GET` | `/api/v1/insight/stats` | User | Stats (total/unread/starred/processing) |
| `GET` | `/api/v1/blog/articles` | None | Blog article list (public) |
| `GET` | `/api/v1/blog/articles/{id}` | None | Blog article detail (public) |
| `GET` | `/api/v1/blog/sections` `/categories` `/featured` `/latest` | None | Blog public endpoints |
| `GET/POST/PUT/DELETE` | `/api/v1/admin/articles` `/categories` `/sections` | Admin | Blog content management |
| `GET/POST/PUT/DELETE` | `/api/v1/admin/skills` | Admin | Skills upload & management |
| `POST/GET/DELETE` | `/api/v1/agent/sessions...` | User | Agent sessions/chat/files/publish |

> Blog design details & progress: see [BLOG_DEVELOPMENT.md](./BLOG_DEVELOPMENT.md).

### Auth

Password hashed with scrypt (n=2¹⁴, r=8, p=1). Token is base64-encoded `user_id:expiry:HMAC-SHA256`. iOS stores token in Keychain; Chrome uses `chrome.storage.local`; admin console uses localStorage. All user-facing APIs require `Authorization: Bearer <token>` header.

### LAN testing for iOS

iPhone must be on same Wi-Fi as Mac. Get Mac IP with `ipconfig getifaddr en0`. Phone uses `http://192.168.x.x:<port>` (not `127.0.0.1`). Server must listen on `0.0.0.0`.

---

## Working style

- **Think before coding**: state assumptions; ask if unclear.
- **Simplicity first**: minimum code, no speculative features.
- **Surgical changes**: touch only what's needed; match existing style.
- **Goal-driven**: verify against acceptance criteria from `README.md` / `BLOG_DEVELOPMENT.md`.
