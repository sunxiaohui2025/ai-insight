from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import shutil
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from trafilatura import extract as trafilatura_extract

DB_PATH = os.getenv("INSIGHT_DATABASE", str(Path(__file__).parent.parent / "insight.db"))
SKILLS_PATH = Path(os.getenv("INSIGHT_SKILLS_PATH", str(Path(__file__).parent.parent / "data" / "skills")))
UPLOADS_PATH = Path(os.getenv("INSIGHT_UPLOADS_PATH", str(Path(__file__).parent.parent / "data" / "agent_uploads")))
MEDIA_PATH = Path(os.getenv("INSIGHT_MEDIA_PATH", str(Path(__file__).parent.parent / "data" / "media")))
STYLE_SPEC_PATH = Path(__file__).parent.parent / "anthropic-style.md"
SECRET = os.getenv("INSIGHT_SECRET", "change-me-in-production").encode()
TOKEN_TTL = 60 * 60 * 24 * 30

app = FastAPI(title="InSight Cloud", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded banners / attachments
MEDIA_PATH.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_PATH)), name="media")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_time(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return fallback


@contextmanager
def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL, last_login_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );
        -- InSight tables
        CREATE TABLE IF NOT EXISTS insight_categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          name TEXT NOT NULL, icon TEXT NOT NULL DEFAULT '📄',
          sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS insight_articles (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          category_id INTEGER, url TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
          source_domain TEXT NOT NULL DEFAULT '', original_content TEXT NOT NULL DEFAULT '',
          translated_content TEXT NOT NULL DEFAULT '', excerpt TEXT NOT NULL DEFAULT '',
          one_page_summary TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending',
          is_read INTEGER NOT NULL DEFAULT 0, is_starred INTEGER NOT NULL DEFAULT 0,
          word_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(category_id) REFERENCES insight_categories(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_insight_articles_user ON insight_articles(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_insight_articles_category ON insight_articles(category_id);
        CREATE INDEX IF NOT EXISTS idx_insight_categories_user ON insight_categories(user_id, sort_order);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_insight_categories_user_name ON insight_categories(user_id, name);

        -- Content sections (系统板块: 项目沉淀, 研究解读)
        CREATE TABLE IF NOT EXISTS content_sections (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          slug TEXT NOT NULL UNIQUE,
          description TEXT DEFAULT '',
          sort_order INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        -- Hierarchical categories within sections
        CREATE TABLE IF NOT EXISTS content_categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          section_id INTEGER NOT NULL,
          parent_id INTEGER,
          name TEXT NOT NULL,
          slug TEXT NOT NULL,
          icon TEXT DEFAULT '📄',
          sort_order INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(section_id) REFERENCES content_sections(id) ON DELETE CASCADE,
          FOREIGN KEY(parent_id) REFERENCES content_categories(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_content_categories_section ON content_categories(section_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_content_categories_parent ON content_categories(parent_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_content_categories_slug ON content_categories(section_id, slug);

        CREATE TABLE IF NOT EXISTS agent_skills (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
          version TEXT NOT NULL DEFAULT '1.0.0', description TEXT NOT NULL DEFAULT '',
          skill_type TEXT NOT NULL DEFAULT 'prompt', manifest_json TEXT NOT NULL DEFAULT '{}',
          storage_path TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_sessions (
          id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT 'link',
          title TEXT NOT NULL DEFAULT '', draft_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_session_skills (
          session_id TEXT NOT NULL, skill_id INTEGER NOT NULL,
          PRIMARY KEY(session_id, skill_id), FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE,
          FOREIGN KEY(skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS agent_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_files (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
          filename TEXT NOT NULL, mime_type TEXT NOT NULL DEFAULT '', storage_path TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        -- LLM 模型配置
        CREATE TABLE IF NOT EXISTS llm_models (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          provider TEXT NOT NULL DEFAULT 'openai',
          model_id TEXT NOT NULL,
          api_base_url TEXT NOT NULL DEFAULT '',
          api_key TEXT NOT NULL DEFAULT '',
          path_style TEXT NOT NULL DEFAULT 'openai',
          max_tokens INTEGER NOT NULL DEFAULT 4096,
          temperature REAL NOT NULL DEFAULT 0,
          is_default INTEGER NOT NULL DEFAULT 0,
          enabled INTEGER NOT NULL DEFAULT 1,
          last_tested_at TEXT NOT NULL DEFAULT '',
          last_test_ok INTEGER NOT NULL DEFAULT -1,
          last_test_message TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_models_name ON llm_models(name);
        """)
        # Keep existing installations compatible with the richer reader.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(insight_articles)").fetchall()}
        if "one_page_summary" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN one_page_summary TEXT NOT NULL DEFAULT ''")
        if "section_id" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN section_id INTEGER")
        if "sub_category_id" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN sub_category_id INTEGER")
        if "content_type" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN content_type TEXT NOT NULL DEFAULT 'url'")
        if "manual_content" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN manual_content TEXT NOT NULL DEFAULT ''")
        if "subtitle" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN subtitle TEXT NOT NULL DEFAULT ''")
        if "banner_url" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN banner_url TEXT NOT NULL DEFAULT ''")
        if "attachment_url" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN attachment_url TEXT NOT NULL DEFAULT ''")
        if "attachment_name" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN attachment_name TEXT NOT NULL DEFAULT ''")
        if "content_format" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN content_format TEXT NOT NULL DEFAULT 'richtext'")
        if "doc_kind" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN doc_kind TEXT NOT NULL DEFAULT ''")
        if "read_count" not in columns:
            conn.execute("ALTER TABLE insight_articles ADD COLUMN read_count INTEGER NOT NULL DEFAULT 0")
        # Migrate existing one_page_summary columns to new name
        if "one_page_summary" in columns and "summary_content" not in columns:
            try:
                conn.execute("ALTER TABLE insight_articles ADD COLUMN summary_content TEXT NOT NULL DEFAULT ''")
                conn.execute("UPDATE insight_articles SET summary_content = one_page_summary WHERE one_page_summary != ''")
            except Exception:
                pass
    bootstrap_admin()
    bootstrap_default_categories()
    bootstrap_content_sections()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_text, _ = stored.split("$", 1)
        return hmac.compare_digest(hash_password(password, base64.urlsafe_b64decode(salt_text)), stored)
    except (ValueError, TypeError):
        return False


def make_token(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + TOKEN_TTL}"
    signature = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def parse_token(token: str) -> int:
    try:
        user, expiry, signature = base64.urlsafe_b64decode(token.encode()).decode().split(":")
        payload = f"{user}:{expiry}"
        expected = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()
        if int(expiry) < time.time() or not hmac.compare_digest(signature, expected):
            raise ValueError
        return int(user)
    except Exception as exc:
        raise HTTPException(401, "登录已失效") from exc


def current_user(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    user_id = parse_token(authorization[7:])
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or user["status"] != "approved":
        raise HTTPException(403, "账号尚未获批或已停用")
    return user


def admin_user(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
    if user["role"] != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


def bootstrap_admin() -> None:
    email = os.getenv("INSIGHT_ADMIN_EMAIL")
    password = os.getenv("INSIGHT_ADMIN_PASSWORD")
    if not email or not password:
        return
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(email,name,password_hash,status,role,created_at) VALUES(?,?,?,?,?,?)",
            (email.lower(), "管理员", hash_password(password), "approved", "admin", now()),
        )


def bootstrap_content_sections() -> None:
    """Create default content sections (项目沉淀, 研究解读) with sample categories.

    板块(sections) 使用 INSERT OR IGNORE 可安全重复执行；但默认分类只在首次初始化时
    写入一次：之后即使分类被删除或改名，也不会在服务重启时被重新创建。
    """
    default_sections = [
        ("项目沉淀", "project", "把一次次真实交付中的判断、方案和复盘，整理成团队下一次可以直接复用的工程资产。", 0),
        ("研究解读", "research", "把论文、技术文章和行业动态转化成结构清晰的一页纸判断。", 1),
    ]
    default_categories = {
        "project": [
            ("技术方案", "tech-solution", None, "🛠️", 0),
            ("项目复盘", "retrospective", None, "📊", 1),
            ("架构设计", "architecture", None, "🏗️", 2),
            ("性能优化", "performance", None, "⚡", 3),
            ("最佳实践", "best-practice", None, "📋", 4),
        ],
        "research": [
            ("AI/大模型", "ai-ml", None, "🤖", 0),
            ("系统架构", "system-design", None, "🔧", 1),
            ("前端技术", "frontend", None, "🎨", 2),
            ("安全隐私", "security", None, "🔒", 3),
            ("行业趋势", "industry", None, "📈", 4),
        ],
    }
    with db() as conn:
        for name, slug, desc, order in default_sections:
            conn.execute(
                "INSERT OR IGNORE INTO content_sections(name,slug,description,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (name, slug, desc, order, now(), now()),
            )
        # 默认分类只初始化一次：若已设置过标记则跳过，避免用户删除/改名后重启又被重建
        seeded = conn.execute(
            "SELECT value FROM settings WHERE key='content_categories_seeded'"
        ).fetchone()
        if seeded:
            return
        # 兼容旧版本：若库中已有分类数据（说明系统早已初始化过），则不再补默认分类，
        # 只是写下一个标记，防止后续重启把用户删除的默认分类重新建出来。
        existing = conn.execute("SELECT COUNT(*) FROM content_categories").fetchone()[0]
        if existing > 0:
            conn.execute(
                "INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)",
                ("content_categories_seeded", "1", now()),
            )
            return

        for section_slug, cats in default_categories.items():
            sec = conn.execute("SELECT id FROM content_sections WHERE slug=?", (section_slug,)).fetchone()
            if not sec:
                continue
            for name, slug, parent_id, icon, order in cats:
                conn.execute(
                    "INSERT OR IGNORE INTO content_categories(section_id,parent_id,name,slug,icon,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (sec["id"], parent_id, name, slug, icon, order, now(), now()),
                )
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)",
            ("content_categories_seeded", "1", now()),
        )


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(Credentials):
    name: str = Field(min_length=1, max_length=50)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": now()}


@app.post("/api/v1/auth/register", status_code=201)
def register(body: RegisterRequest) -> dict[str, str]:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "邮箱格式不正确")
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO users(email,name,password_hash,status,role,created_at) VALUES(?,?,?,?,?,?)",
                (email, body.name.strip(), hash_password(body.password), "pending", "user", now()),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "该邮箱已注册") from exc
    return {"status": "pending", "message": "注册成功，请等待管理员审批"}


@app.post("/api/v1/auth/login")
def login(body: Credentials) -> dict[str, Any]:
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),)).fetchone()
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "邮箱或密码错误")
        if user["status"] != "approved":
            raise HTTPException(403, "账号正在等待审批" if user["status"] == "pending" else "账号已停用")
        conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now(), user["id"]))
        conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)", (user["id"], "login", now()))
    return {"token": make_token(user["id"]), "user": {"email": user["email"], "name": user["name"], "role": user["role"]}}


@app.get("/api/v1/me")
def me(user: sqlite3.Row = Depends(current_user)) -> dict[str, str]:
    return {"email": user["email"], "name": user["name"], "role": user["role"]}


def get_llm_settings() -> dict[str, Any]:
    """Resolution order: llm_models default row > settings table > env defaults."""
    defaults = {
        "base_url": os.getenv("INSIGHT_LLM_BASE_URL", "http://127.0.0.1:6018"),
        "model": os.getenv("INSIGHT_LLM_MODEL", "your-model-name"),
        "api_key": os.getenv("INSIGHT_LLM_API_KEY", ""), "temperature": 0, "max_tokens": 5000,
        "path_style": "model-in-path",
    }
    with db() as conn:
        rows = conn.execute("SELECT key,value FROM settings WHERE key LIKE 'llm.%'").fetchall()
        try:
            active = conn.execute(
                "SELECT model_id, api_base_url, api_key, path_style, temperature, max_tokens "
                "FROM llm_models WHERE is_default=1 AND enabled=1 LIMIT 1"
            ).fetchone()
        except sqlite3.OperationalError:
            active = None
    for row in rows:
        defaults[row["key"][4:]] = json.loads(row["value"])
    if active:
        defaults.update({
            "base_url": active["api_base_url"],
            "model": active["model_id"],
            "api_key": active["api_key"],
            "path_style": active["path_style"],
            "temperature": active["temperature"],
            "max_tokens": active["max_tokens"],
        })
    return defaults


@app.post("/api/v1/llm/chat")
async def llm_proxy(request: Request, user: sqlite3.Row = Depends(current_user)):
    body = await request.json()
    settings = get_llm_settings()
    body["model"] = settings["model"]
    body["temperature"] = settings["temperature"]
    body["max_tokens"] = min(int(body.get("max_tokens", 5000)), int(settings["max_tokens"]))
    body["chat_template_kwargs"] = {"enable_thinking": False}
    url = _resolve_chat_url(
        settings["base_url"], settings["model"], settings.get("path_style", "model-in-path")
    )
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read())
    except Exception as exc:
        raise HTTPException(502, f"模型服务不可用: {exc}") from exc
    with db() as conn:
        conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)", (user["id"], "llm", now()))
    return data


# ── Agent / Skill APIs ──

def _safe_skill_manifest(root: Path) -> tuple[dict[str, Any], str]:
    manifest_file = root / "skill.json"
    instructions_file = root / "SKILL.md"
    if not manifest_file.exists():
        raise HTTPException(422, "ZIP 中缺少 skill.json")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(422, "skill.json 格式错误") from exc
    if not manifest.get("name"):
        raise HTTPException(422, "skill.json 缺少 name")
    instructions = instructions_file.read_text(encoding="utf-8", errors="ignore") if instructions_file.exists() else ""
    return manifest, instructions


@app.get("/api/v1/admin/skills")
def admin_list_skills(_: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        rows = conn.execute("SELECT id,name,display_name,version,description,skill_type,enabled,created_at,updated_at FROM agent_skills ORDER BY display_name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/skills", status_code=201)
async def admin_upload_skill(file: UploadFile = File(...), _: sqlite3.Row = Depends(admin_user)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(422, "请上传 ZIP 格式的 Skill")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Skill ZIP 不能超过 20MB")
    SKILLS_PATH.mkdir(parents=True, exist_ok=True)
    temp = SKILLS_PATH / f".upload-{secrets.token_hex(8)}.zip"
    temp.write_bytes(data)
    try:
        with zipfile.ZipFile(temp) as archive:
            names = archive.namelist()
            if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names):
                raise HTTPException(422, "Skill ZIP 包含不安全路径")
            if len(names) > 300:
                raise HTTPException(422, "Skill 文件数量过多")
            extract_dir = SKILLS_PATH / f".extract-{secrets.token_hex(8)}"
            extract_dir.mkdir()
            archive.extractall(extract_dir)
        root = extract_dir
        if not (root / "skill.json").exists() and len(list(root.iterdir())) == 1:
            root = next(root.iterdir())
        manifest, _ = _safe_skill_manifest(root)
        name = re.sub(r"[^a-zA-Z0-9._-]", "-", str(manifest["name"]))[:80]
        final_dir = SKILLS_PATH / name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(root), str(final_dir))
        shutil.rmtree(extract_dir, ignore_errors=True)
        with db() as conn:
            conn.execute("INSERT INTO agent_skills(name,display_name,version,description,skill_type,manifest_json,storage_path,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET display_name=excluded.display_name,version=excluded.version,description=excluded.description,skill_type=excluded.skill_type,manifest_json=excluded.manifest_json,storage_path=excluded.storage_path,updated_at=excluded.updated_at", (name, manifest.get("display_name", name), manifest.get("version", "1.0.0"), manifest.get("description", ""), manifest.get("type", "prompt"), json.dumps(manifest, ensure_ascii=False), str(final_dir), 1, now(), now()))
            row = conn.execute("SELECT id,name,display_name,version,description,skill_type,enabled FROM agent_skills WHERE name=?", (name,)).fetchone()
        return dict(row)
    finally:
        temp.unlink(missing_ok=True)


@app.delete("/api/v1/admin/skills/{skill_id}")
def admin_delete_skill(skill_id: int, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        row = conn.execute("SELECT storage_path FROM agent_skills WHERE id=?", (skill_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Skill 不存在")
        conn.execute("DELETE FROM agent_skills WHERE id=?", (skill_id,))
    shutil.rmtree(row["storage_path"], ignore_errors=True)
    return {"ok": True}


@app.patch("/api/v1/admin/skills/{skill_id}")
async def admin_toggle_skill(skill_id: int, request: Request, _: sqlite3.Row = Depends(admin_user)):
    body = await request.json()
    with db() as conn:
        conn.execute("UPDATE agent_skills SET enabled=?,updated_at=? WHERE id=?", (1 if body.get("enabled", True) else 0, now(), skill_id))
    return {"ok": True}


# ── 站点执行技能（Site Skills，磁盘上可执行的独立技能，例如 url-to-article URL 提取）──
# 这类技能与 agent_skills 表里的“对话提示词技能”不同：它们是完整的可执行目录，含 SKILL.md /
# skill.json / src/*.py，由后端直接以子进程方式运行。存放在 server/skills/<name>/ 下。

SITE_SKILLS_PATH = Path(__file__).parent.parent / "skills"


def _site_skill_info(skill_dir: Path) -> dict[str, Any]:
    """读取磁盘上某个站点技能的基本信息（不强制要求 skill.json，兼容纯可执行技能）。"""
    name = skill_dir.name
    manifest: dict[str, Any] = {}
    manifest_file = skill_dir / "skill.json"
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    skill_md_file = skill_dir / "SKILL.md"
    instructions = skill_md_file.read_text(encoding="utf-8", errors="ignore") if skill_md_file.exists() else ""
    src_main = skill_dir / "src" / "main.py"
    try:
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(skill_dir.stat().st_mtime))
    except Exception:
        mtime = ""
    return {
        "name": manifest.get("name") or name,
        "display_name": manifest.get("display_name") or manifest.get("name") or name,
        "version": manifest.get("version", "1.0.0"),
        "description": manifest.get("description", ""),
        "entry": "python -m src.main" if src_main.exists() else ("Prompt" if instructions else ""),
        "has_skill_md": skill_md_file.exists(),
        "instruction_chars": len(instructions),
        "updated_at": mtime,
        "path": str(skill_dir),
    }


@app.get("/api/v1/admin/site-skills")
def admin_list_site_skills(_: sqlite3.Row = Depends(admin_user)):
    SITE_SKILLS_PATH.mkdir(parents=True, exist_ok=True)
    skills: list[dict[str, Any]] = []
    for d in sorted(SITE_SKILLS_PATH.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name.startswith("_"):
            continue
        skills.append(_site_skill_info(d))
    return skills


def _locate_site_skill_root(extract_dir: Path) -> Path:
    """在解压目录里定位技能根目录：优先找含 SKILL.md / skill.json / src/main.py 的那一层。"""
    for d in [extract_dir, *sorted(extract_dir.iterdir(), key=lambda p: p.name)]:
        if d.is_dir():
            if any((d / f).exists() for f in ("SKILL.md", "skill.json", "src/main.py")):
                return d
    return extract_dir


@app.post("/api/v1/admin/site-skills", status_code=201)
async def admin_upload_site_skill(file: UploadFile = File(...), _: sqlite3.Row = Depends(admin_user)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(422, "请上传 ZIP 格式的站点技能")
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(413, "站点技能 ZIP 不能超过 100MB")
    SITE_SKILLS_PATH.mkdir(parents=True, exist_ok=True)
    temp = SITE_SKILLS_PATH / f".upload-{secrets.token_hex(8)}.zip"
    temp.write_bytes(data)
    extract_dir = SITE_SKILLS_PATH / f".extract-{secrets.token_hex(8)}"
    try:
        with zipfile.ZipFile(temp) as archive:
            names = archive.namelist()
            if any(Path(n).is_absolute() or ".." in Path(n).parts for n in names):
                raise HTTPException(422, "站点技能 ZIP 包含不安全路径")
            if len(names) > 5000:
                raise HTTPException(422, "站点技能文件数量过多")
            extract_dir.mkdir()
            archive.extractall(extract_dir)
        root = _locate_site_skill_root(extract_dir)
        if not any((root / f).exists() for f in ("SKILL.md", "skill.json", "src/main.py")):
            raise HTTPException(422, "ZIP 中未找到技能内容（缺少 SKILL.md / skill.json / src/main.py）")
        # 技能目录名（用于替换/定位）：优先 manifest 里的 name，否则用解压出的目录名
        slug = root.name if root != extract_dir else file.filename.rsplit(".", 1)[0]
        manifest = {}
        if (root / "skill.json").exists():
            try:
                manifest = json.loads((root / "skill.json").read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        name = manifest.get("name") or slug
        name = re.sub(r"[^A-Za-z0-9._-]", "-", str(name)).strip("-")[:80] or "skill"
        final_dir = SITE_SKILLS_PATH / name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root), str(final_dir))
        return _site_skill_info(final_dir)
    finally:
        temp.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)


@app.delete("/api/v1/admin/site-skills/{name}")
def admin_delete_site_skill(name: str, _: sqlite3.Row = Depends(admin_user)):
    clean = Path(name).name
    target = SITE_SKILLS_PATH / clean
    if not target.is_dir():
        raise HTTPException(404, "站点技能不存在")
    shutil.rmtree(target, ignore_errors=True)
    return {"ok": True}


@app.get("/api/v1/agent/skills")
def agent_skills(user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        rows = conn.execute("SELECT id,name,display_name,version,description,skill_type FROM agent_skills WHERE enabled=1 ORDER BY display_name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/agent/sessions", status_code=201)
async def create_agent_session(request: Request, user: sqlite3.Row = Depends(current_user)):
    body = await request.json()
    session_id = secrets.token_urlsafe(16)
    skill_ids = [int(x) for x in body.get("skill_ids", [])]
    with db() as conn:
        conn.execute("INSERT INTO agent_sessions(id,user_id,mode,created_at,updated_at) VALUES(?,?,?,?,?)", (session_id, user["id"], body.get("mode", "link"), now(), now()))
        for sid in skill_ids:
            conn.execute("INSERT OR IGNORE INTO agent_session_skills(session_id,skill_id) SELECT ?,id FROM agent_skills WHERE id=? AND enabled=1", (session_id, sid))
    return {"id": session_id, "skill_ids": skill_ids}


def _load_agent_prompt(session_id: str, user_id: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    with db() as conn:
        session = conn.execute("SELECT * FROM agent_sessions WHERE id=? AND user_id=?", (session_id, user_id)).fetchone()
        if not session:
            raise HTTPException(404, "Agent 会话不存在")
        messages = [dict(r) for r in conn.execute("SELECT role,content FROM agent_messages WHERE session_id=? ORDER BY id", (session_id,)).fetchall()]
        skills = conn.execute("SELECT s.* FROM agent_skills s JOIN agent_session_skills x ON x.skill_id=s.id WHERE x.session_id=? AND s.enabled=1", (session_id,)).fetchall()
    skill_text = []
    for skill in skills:
        try:
            _, instructions = _safe_skill_manifest(Path(skill["storage_path"]))
        except HTTPException:
            instructions = ""
        skill_text.append(f"\n## Skill: {skill['display_name']}\n{instructions[:30000]}")
    draft = json.loads(session["draft_json"] or "{}")
    system = '''你是 InSight 内容生产 Agent。你要根据用户要求协助生成和修改博客草稿。只修改草稿，不自动发布。输出必须是 JSON：{"message":"给用户的回复","draft":{"title":"","content_html":"","summary_html":""},"needs_confirmation":false}。当前挂载的第三方 Skills 如下，请遵循其规则并在必要时调用对应能力：''' + "".join(skill_text)
    return [{"role": "system", "content": system}, *messages], draft


@app.post("/api/v1/agent/sessions/{session_id}/messages")
async def agent_message(session_id: str, request: Request, user: sqlite3.Row = Depends(current_user)):
    body = await request.json()
    user_text = str(body.get("content", "")).strip()
    if not user_text:
        raise HTTPException(422, "请输入消息")
    messages, old_draft = _load_agent_prompt(session_id, user["id"])
    messages.append({"role": "user", "content": user_text})
    settings = get_llm_settings()
    payload = {"model": settings["model"], "messages": messages, "temperature": 0.2, "max_tokens": min(int(settings["max_tokens"]), 8000), "response_format": {"type": "json_object"}}
    url = f"{settings['base_url'].rstrip('/')}/{settings['model']}/v1/chat/completions"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings['api_key']}"})
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.loads(response.read())
        content = result["choices"][0]["message"]["content"]
        answer = json.loads(content)
    except Exception as exc:
        raise HTTPException(502, f"Agent 执行失败: {exc}") from exc
    draft = answer.get("draft") or old_draft
    with db() as conn:
        conn.execute("INSERT INTO agent_messages(session_id,role,content,created_at) VALUES(?,?,?,?)", (session_id, "user", user_text, now()))
        conn.execute("INSERT INTO agent_messages(session_id,role,content,created_at) VALUES(?,?,?,?)", (session_id, "assistant", answer.get("message", "已更新草稿"), now()))
        conn.execute("UPDATE agent_sessions SET draft_json=?,title=?,updated_at=? WHERE id=?", (json.dumps(draft, ensure_ascii=False), draft.get("title", ""), now(), session_id))
    return {"message": answer.get("message", "已更新草稿"), "draft": draft, "needs_confirmation": bool(answer.get("needs_confirmation"))}


@app.post("/api/v1/agent/sessions/{session_id}/files")
async def agent_file(session_id: str, file: UploadFile = File(...), user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM agent_sessions WHERE id=? AND user_id=?", (session_id, user["id"])).fetchone():
            raise HTTPException(404, "Agent 会话不存在")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(413, "文件不能超过 30MB")
    folder = UPLOADS_PATH / session_id
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "upload").name
    path = folder / f"{secrets.token_hex(5)}-{name}"
    path.write_bytes(data)
    with db() as conn:
        row = conn.execute("INSERT INTO agent_files(session_id,filename,mime_type,storage_path,created_at) VALUES(?,?,?,?,?) RETURNING id", (session_id, name, file.content_type or "", str(path), now())).fetchone()
    return {"id": row["id"], "filename": name, "message": "文件已上传，可在对话中要求 Agent 使用它"}


@app.post("/api/v1/agent/sessions/{session_id}/publish")
def publish_agent_draft(session_id: str, user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        row = conn.execute("SELECT draft_json FROM agent_sessions WHERE id=? AND user_id=?", (session_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Agent 会话不存在")
        draft = json.loads(row["draft_json"] or "{}")
        if not draft.get("title") or not draft.get("content_html"):
            raise HTTPException(422, "草稿标题和正文不能为空")
        cursor = conn.execute("INSERT INTO insight_articles(user_id,url,title,source_domain,original_content,translated_content,excerpt,one_page_summary,status,content_type,manual_content,word_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (user["id"], draft.get("source_url", "agent://" + session_id), draft["title"], "agent", draft["content_html"], draft["content_html"], re.sub(r"<[^>]+>", " ", draft["content_html"])[:200], draft.get("summary_html", ""), "ready", "manual", draft["content_html"], len(draft["content_html"].split()), now(), now()))
        conn.execute("UPDATE agent_sessions SET status='published',updated_at=? WHERE id=?", (now(), session_id))
    return {"id": cursor.lastrowid, "status": "published"}


@app.get("/api/v1/admin/users")
def list_users(_: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        rows = conn.execute("""
          SELECT u.id,u.email,u.name,u.status,u.role,u.created_at,u.last_login_at,
            (SELECT COUNT(*) FROM insight_articles a WHERE a.user_id=u.id) AS article_count,
            (SELECT COUNT(*) FROM events e WHERE e.user_id=u.id AND e.kind='llm') AS llm_count,
            (SELECT COUNT(*) FROM events e WHERE e.user_id=u.id AND e.kind LIKE 'insight_%') AS insight_events,
            (SELECT MAX(e.created_at) FROM events e WHERE e.user_id=u.id) AS last_activity_at
          FROM users u ORDER BY u.created_at DESC
        """).fetchall()
    return [dict(row) for row in rows]


@app.patch("/api/v1/admin/users/{user_id}")
async def update_user(user_id: int, request: Request, _: sqlite3.Row = Depends(admin_user)):
    body = await request.json()
    status = body.get("status")
    if status not in {"pending", "approved", "disabled"}:
        raise HTTPException(422, "无效状态")
    with db() as conn:
        conn.execute("UPDATE users SET status=? WHERE id=? AND role!='admin'", (status, user_id))
    return {"ok": True}


@app.get("/api/v1/admin/stats")
def stats(_: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        users = conn.execute("SELECT status,COUNT(*) count FROM users GROUP BY status").fetchall()
        articles = conn.execute("SELECT COUNT(*) count FROM insight_articles").fetchone()["count"]
        events = conn.execute("SELECT kind,COUNT(*) count FROM events GROUP BY kind").fetchall()
    return {"users": {r["status"]: r["count"] for r in users}, "articles": articles, "events": {r["kind"]: r["count"] for r in events}}


@app.get("/api/v1/admin/dashboard/stats")
def admin_dashboard_stats(_: sqlite3.Row = Depends(admin_user)):
    """后台概览首页统计数据：总文章数 / 总分类数 / 总阅读量 / 本月新增"""
    month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
    with db() as conn:
        total_articles = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE section_id IS NOT NULL"
        ).fetchone()[0]
        total_categories = conn.execute(
            "SELECT COUNT(*) FROM content_categories"
        ).fetchone()[0]
        total_reads = conn.execute(
            "SELECT COALESCE(SUM(read_count),0) FROM insight_articles WHERE section_id IS NOT NULL"
        ).fetchone()[0]
        new_this_month = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE section_id IS NOT NULL AND substr(created_at,1,7)=?",
            (month_prefix,),
        ).fetchone()[0]
    return {
        "total_articles": total_articles,
        "total_categories": total_categories,
        "total_reads": total_reads,
        "new_this_month": new_this_month,
    }


@app.get("/api/v1/admin/llm")
def read_llm(_: sqlite3.Row = Depends(admin_user)):
    value = get_llm_settings()
    value["api_key"] = "********" if value["api_key"] else ""
    return value


@app.put("/api/v1/admin/llm")
async def write_llm(request: Request, _: sqlite3.Row = Depends(admin_user)):
    body = await request.json()
    allowed = {"base_url", "model", "api_key", "temperature", "max_tokens"}
    with db() as conn:
        for key, value in body.items():
            if key in allowed and not (key == "api_key" and value == "********"):
                conn.execute("INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,?)", (f"llm.{key}", json.dumps(value), now()))
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# InSight – 链接内容保存与翻译系统
# ═══════════════════════════════════════════════════════════

DEFAULT_CATEGORIES = [
    ("稍后阅读", "tray", 0),
    ("工具教程", "wrench.and.screwdriver", 1),
    ("产品发布", "sparkles", 2),
    ("商业动态", "briefcase", 3),
    ("研究解读", "atom", 4),
    ("项目沉淀", "square.stack.3d.up", 5),
    ("认知提升", "brain", 6),
]


def bootstrap_default_categories(user_id: int | None = None) -> None:
    with db() as conn:
        users = conn.execute("SELECT id FROM users WHERE ? IS NULL OR id=?", (user_id, user_id)).fetchall() if user_id else conn.execute("SELECT id FROM users").fetchall()
        for user in users:
            existing = conn.execute(
                "SELECT COUNT(*) FROM insight_categories WHERE user_id=?", (user["id"],)
            ).fetchone()[0]
            for name, icon, order in DEFAULT_CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO insight_categories(user_id,name,icon,sort_order,created_at) VALUES(?,?,?,?,?)",
                    (user["id"], name, icon, order, now()),
                )


def bootstrap_sample_articles(user_id: int) -> None:
    """给新用户准备少量可阅读样例，已有收藏时不打扰用户数据。"""
    with db() as conn:
        if conn.execute("SELECT 1 FROM insight_articles WHERE user_id=? LIMIT 1", (user_id,)).fetchone():
            return
        cats = {r["name"]: r["id"] for r in conn.execute(
            "SELECT id,name FROM insight_categories WHERE user_id=?", (user_id,)
        ).fetchall()}
        samples = [
            ("AI 客服项目：从知识库到可观测的服务闭环", "项目沉淀", "围绕真实业务目标，拆解知识库、检索增强、工具调用与评测闭环。", "ai-customer-service"),
            ("KV Cache 为什么能让大模型推理更快", "研究解读", "用直观的方式理解注意力缓存、显存占用与吞吐之间的关系。", "kv-cache"),
            ("一页纸：如何挑选适合团队的 AI 工具", "工具教程", "从任务类型、数据边界、协作方式和成本四个维度建立选择框架。", "ai-tools"),
            ("AI 产品发布观察：从功能到工作流", "产品发布", "关注产品如何进入真实工作流，以及发布背后的商业信号。", "ai-product"),
        ]
        for title, category, excerpt, slug in samples:
            cid = cats.get(category) or cats.get("稍后阅读")
            content = f"<h2>{title}</h2><p>{excerpt}</p><h3>核心观点</h3><p>这是 InSight 的示例文章，用来展示正文、分类与一页纸解读的阅读体验。后续你保存的链接会自动替换为真实提取内容。</p><ul><li>先理解问题，再选择工具。</li><li>把关键判断记录成可复用的知识。</li><li>用清晰的结构降低阅读成本。</li></ul>"
            summary = f"<div class='summary-block'><h3>一句话结论</h3><p>{excerpt}</p><h3>值得记住</h3><ul><li>从真实场景出发，而不是从名词出发。</li><li>把复杂内容拆成背景、方案、证据和行动。</li></ul></div>"
            url = f"https://insight.local/sample/{slug}"
            conn.execute(
                "INSERT INTO insight_articles(user_id,category_id,url,title,source_domain,original_content,translated_content,excerpt,one_page_summary,status,word_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, cid, url, title, "insight.local", content, content, excerpt, summary, "ready", 120, now(), now()),
            )


# ── Pydantic models ──

class InsightCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    icon: str = "📄"
    sort_order: int = 0


class InsightCategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    sort_order: int | None = None


class InsightCategoryReorder(BaseModel):
    order: list[int]  # category id list in desired order


class InsightArticleSave(BaseModel):
    url: str
    category_id: int | None = None  # None = 稍后阅读


class InsightArticleUpdate(BaseModel):
    category_id: int | None = None
    is_read: bool | None = None
    is_starred: bool | None = None


class InsightDecodeRequest(BaseModel):
    url: str
    category_id: int | None = None


class InsightDecodeResponse(BaseModel):
    url: str
    title: str
    source_domain: str
    word_count: int
    original_content: str
    translated_content: str
    one_page_summary: str
    article_id: int | None = None


# ═══════════════════════════════════════════════════════════
# Content Management – 内容板块/分类/发布管理
# ═══════════════════════════════════════════════════════════

class ContentSectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    slug: str = Field(min_length=1, max_length=50)
    description: str = ""
    sort_order: int = 0


class ContentSectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None


class ContentCategoryCreate(BaseModel):
    section_id: int
    parent_id: int | None = None
    name: str = Field(min_length=1, max_length=30)
    slug: str = Field(min_length=1, max_length=50)
    icon: str = "📄"
    sort_order: int = 0


class ContentCategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    icon: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class ManualArticlePublish(BaseModel):
    section_id: int
    sub_category_id: int | None = None
    title: str = Field(min_length=1, max_length=200)
    excerpt: str = ""
    manual_content: str = ""  # HTML rich content


class UrlArticlePublish(BaseModel):
    section_id: int
    sub_category_id: int | None = None
    url: str
    title_hint: str = ""


# ── Section APIs (Admin) ──

@app.get("/api/v1/admin/sections")
def admin_list_sections(_: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        rows = conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM content_categories WHERE section_id=s.id) AS cat_count FROM content_sections s ORDER BY s.sort_order, s.id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/sections", status_code=201)
def admin_create_section(body: ContentSectionCreate, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO content_sections(name,slug,description,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (body.name, body.slug, body.description, body.sort_order, now(), now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "板块 slug 已存在")
    return {"id": cursor.lastrowid, "name": body.name, "slug": body.slug}


@app.put("/api/v1/admin/sections/{section_id}")
def admin_update_section(section_id: int, body: ContentSectionUpdate, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        existing = conn.execute("SELECT id FROM content_sections WHERE id=?", (section_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "板块不存在")
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.description is not None:
            updates["description"] = body.description
        if body.sort_order is not None:
            updates["sort_order"] = body.sort_order
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [now(), section_id]
            conn.execute(f"UPDATE content_sections SET {set_clause}, updated_at=? WHERE id=?", values)
    return {"ok": True}


@app.delete("/api/v1/admin/sections/{section_id}")
def admin_delete_section(section_id: int, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        existing = conn.execute("SELECT id FROM content_sections WHERE id=?", (section_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "板块不存在")
        conn.execute("DELETE FROM content_categories WHERE section_id=?", (section_id,))
        conn.execute("DELETE FROM content_sections WHERE id=?", (section_id,))
    return {"ok": True}


# ── Category APIs (Admin) ──

@app.get("/api/v1/admin/sections/{section_id}/categories")
def admin_list_categories(section_id: int, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        rows = conn.execute(
            """SELECT c.*,
               (SELECT COUNT(*) FROM content_categories WHERE parent_id=c.id) AS child_count,
               (SELECT COUNT(*) FROM insight_articles WHERE sub_category_id=c.id) AS article_count
               FROM content_categories c
               WHERE c.section_id=?
               ORDER BY CASE WHEN c.parent_id IS NULL THEN 0 ELSE 1 END, c.sort_order, c.id""",
            (section_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/categories", status_code=201)
def admin_create_category(body: ContentCategoryCreate, _: sqlite3.Row = Depends(admin_user)):
    # Validate section exists
    with db() as conn:
        section = conn.execute("SELECT id FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        if not section:
            raise HTTPException(404, "板块不存在")
        if body.parent_id is not None:
            parent = conn.execute(
                "SELECT id FROM content_categories WHERE id=? AND section_id=? AND parent_id IS NULL",
                (body.parent_id, body.section_id),
            ).fetchone()
            if not parent:
                raise HTTPException(404, "父分类不存在或不是一级分类")
        try:
            cursor = conn.execute(
                "INSERT INTO content_categories(section_id,parent_id,name,slug,icon,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (body.section_id, body.parent_id, body.name, body.slug, body.icon, body.sort_order, now(), now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "分类 slug 在该板块下已存在")
    return {"id": cursor.lastrowid, "name": body.name, "slug": body.slug}


@app.put("/api/v1/admin/categories/{category_id}")
def admin_update_category(category_id: int, body: ContentCategoryUpdate, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        existing = conn.execute("SELECT * FROM content_categories WHERE id=?", (category_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "分类不存在")
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.slug is not None:
            updates["slug"] = body.slug
        if body.icon is not None:
            updates["icon"] = body.icon
        if body.parent_id is not None:
            updates["parent_id"] = body.parent_id
        if body.sort_order is not None:
            updates["sort_order"] = body.sort_order
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [now(), category_id]
            try:
                conn.execute(f"UPDATE content_categories SET {set_clause}, updated_at=? WHERE id=?", values)
            except sqlite3.IntegrityError:
                raise HTTPException(409, "分类 slug 在该板块下已存在")
    return {"ok": True}


@app.delete("/api/v1/admin/categories/{category_id}")
def admin_delete_category(category_id: int, _: sqlite3.Row = Depends(admin_user)):
    with db() as conn:
        existing = conn.execute("SELECT * FROM content_categories WHERE id=?", (category_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "分类不存在")
        # Set articles using this category to NULL
        conn.execute("UPDATE insight_articles SET sub_category_id=NULL WHERE sub_category_id=?", (category_id,))
        # Delete child categories
        conn.execute("DELETE FROM content_categories WHERE parent_id=?", (category_id,))
        conn.execute("DELETE FROM content_categories WHERE id=?", (category_id,))
    return {"ok": True}


# ── Public Section/Category APIs ──

@app.get("/api/v1/content/sections")
def list_content_sections():
    with db() as conn:
        rows = conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM insight_articles WHERE section_id=s.id AND status='ready') AS article_count FROM content_sections s ORDER BY s.sort_order, s.id"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/content/sections/{section_id}/categories-tree")
def get_category_tree(section_id: int):
    with db() as conn:
        section = conn.execute("SELECT * FROM content_sections WHERE id=?", (section_id,)).fetchone()
        if not section:
            raise HTTPException(404, "板块不存在")
        # Get level-1 categories
        l1_cats = conn.execute(
            "SELECT * FROM content_categories WHERE section_id=? AND parent_id IS NULL ORDER BY sort_order, id",
            (section_id,),
        ).fetchall()
        result = []
        for cat in l1_cats:
            d = dict(cat)
            d["children"] = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM content_categories WHERE parent_id=? ORDER BY sort_order, id",
                    (cat["id"],),
                ).fetchall()
            ]
            result.append(d)
    return {"section": dict(section), "categories": result}


# ── Article Publish APIs ──

@app.post("/api/v1/content/articles/publish-url", status_code=201)
def publish_url_article(
    body: UrlArticlePublish,
    background_tasks: BackgroundTasks,
    user: sqlite3.Row = Depends(current_user),
):
    """Publish article from URL to a content section."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "请输入有效的网页链接")

    # Validate section
    with db() as conn:
        section = conn.execute("SELECT * FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        if not section:
            raise HTTPException(404, "内容板块不存在")
        if body.sub_category_id is not None:
            sub_cat = conn.execute(
                "SELECT * FROM content_categories WHERE id=? AND section_id=?",
                (body.sub_category_id, body.section_id),
            ).fetchone()
            if not sub_cat:
                raise HTTPException(404, "分类不存在或不属于该板块")

    domain = urlparse(url).netloc.replace("www.", "")

    # Check duplicate
    with db() as conn:
        dup = conn.execute(
            "SELECT id FROM insight_articles WHERE user_id=? AND url=? AND section_id=?",
            (user["id"], url, body.section_id),
        ).fetchone()
        if dup:
            return JSONResponse(
                {"id": dup["id"], "status": "duplicate", "message": "该链接已发布到此板块"},
                status_code=200,
            )

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO insight_articles(user_id,section_id,sub_category_id,url,title,source_domain,content_type,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user["id"], body.section_id, body.sub_category_id, url,
             body.title_hint or url, domain, "url", "pending", now(), now()),
        )
        article_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)",
            (user["id"], "content_publish_url", now()),
        )

    background_tasks.add_task(process_article, article_id, url, body.title_hint)
    return {"id": article_id, "status": "pending", "message": "已提交，正在提取内容并翻译"}


@app.post("/api/v1/content/articles/publish-manual", status_code=201)
def publish_manual_article(
    body: ManualArticlePublish,
    user: sqlite3.Row = Depends(current_user),
):
    """Publish a manually written article with rich text content."""
    # Validate section
    with db() as conn:
        section = conn.execute("SELECT * FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        if not section:
            raise HTTPException(404, "内容板块不存在")
        if body.sub_category_id is not None:
            sub_cat = conn.execute(
                "SELECT * FROM content_categories WHERE id=? AND section_id=?",
                (body.sub_category_id, body.section_id),
            ).fetchone()
            if not sub_cat:
                raise HTTPException(404, "分类不存在或不属于该板块")

    excerpt = body.excerpt or (re.sub(r"<[^>]+>", "", body.manual_content)[:200] if body.manual_content else "")

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO insight_articles(user_id,section_id,sub_category_id,url,title,source_domain,content_type,manual_content,translated_content,excerpt,status,word_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], body.section_id, body.sub_category_id,
             f"insight://manual/{secrets.token_hex(8)}",
             body.title, section["name"], "manual",
             body.manual_content, body.manual_content, excerpt, "ready",
             len(re.sub(r"<[^>]+>", "", body.manual_content).split()),
             now(), now()),
        )
        article_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)",
            (user["id"], "content_publish_manual", now()),
        )

    return {"id": article_id, "status": "ready", "message": "发布成功"}


@app.get("/api/v1/content/articles")
def list_content_articles(
    section_id: int | None = None,
    sub_category_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    """Public listing of published content articles (no auth required for viewing)."""
    conditions = ["a.section_id IS NOT NULL", "a.status = 'ready'"]
    params: list[Any] = []

    if section_id is not None:
        conditions.append("a.section_id = ?")
        params.append(section_id)
    if sub_category_id is not None:
        conditions.append("a.sub_category_id = ?")
        params.append(sub_category_id)
    if search:
        conditions.append("(a.title LIKE ? OR a.excerpt LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM insight_articles a WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT a.id, a.url, a.title, a.subtitle, a.source_domain, a.excerpt, a.status,
                       a.word_count, a.section_id, a.sub_category_id, a.content_type,
                       a.banner_url, a.attachment_url, a.attachment_name,
                       a.content_format, a.doc_kind,
                       a.created_at, a.updated_at,
                       COALESCE(cc.name, '') AS category_name,
                       COALESCE(cs.name, '') AS section_name,
                       u.name AS author_name
                FROM insight_articles a
                LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
                LEFT JOIN content_sections cs ON a.section_id = cs.id
                LEFT JOIN users u ON a.user_id = u.id
                WHERE {where}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        ).fetchall()

    return {"articles": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}

@app.get("/api/v1/content/articles/{article_id}")
def get_content_article(article_id: int):
    """Public detail endpoint used by web and mobile readers."""
    with db() as conn:
        row = conn.execute(
            """SELECT a.*, COALESCE(cc.name, '') AS category_name,
                      COALESCE(cs.name, '') AS section_name, u.name AS author_name
               FROM insight_articles a
               LEFT JOIN content_categories cc ON a.sub_category_id=cc.id
               LEFT JOIN content_sections cs ON a.section_id=cs.id
               LEFT JOIN users u ON a.user_id=u.id
               WHERE a.id=? AND a.section_id IS NOT NULL AND a.status='ready'""",
            (article_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "文章未找到")
    return dict(row)

def generate_one_page_analysis(title: str, content: str) -> str:
    """Generate a concise one-page analysis of the article using LLM."""
    if not content:
        return ""

    settings = get_llm_settings()
    prompt = f"""你是一位资深分析师。请对以下文章做一页纸分析，用中文输出 HTML。

分析要求：
1. 核心观点（2-3句话概括文章主旨）
2. 关键洞察（3-5个要点）
3. 重要数据/案例（如有，列举1-3个）
4. 行动启示（这篇文章对读者有什么启发或可行动的建议）

格式要求：
- 简洁有力，控制在一页纸以内
- 只允许使用 h2、h3、p、ul、ol、li、blockquote、strong、em、code 标签
- 如文章适合用流程/架构表达，可使用一个简单的 ASCII/代码块，不要输出 script、style、iframe 或外部资源
- 只输出 HTML 片段，不要 Markdown、不要 ``` 包裹、不要解释
- 不要复述原文，要提炼和升华

文章标题：{title}

文章内容：
{content[:8000]}"""

    body = {
        "messages": [
            {"role": "system", "content": "你是资深分析师，擅长将长文提炼为一页纸分析。用中文输出，简洁有力。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 3000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    body["model"] = settings["model"]
    api_url = f"{settings['base_url'].rstrip('/')}/{settings['model']}/v1/chat/completions"
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings['api_key']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        result = data["choices"][0]["message"]["content"].strip()
        result = re.sub(r"^```(?:html)?\s*|\s*```$", "", result, flags=re.I)
        # Strip active/remote content before storing model output.
        soup = BeautifulSoup(result, "html.parser")
        for tag in soup(["script", "style", "iframe", "object", "img", "svg"]):
            tag.decompose()
        allowed = {"h2", "h3", "p", "ul", "ol", "li", "blockquote", "strong", "em", "code", "pre", "br"}
        for tag in soup.find_all(True):
            if tag.name not in allowed:
                tag.unwrap()
            else:
                tag.attrs = {}
        return str(soup).strip()
    except Exception:
        return "[一页纸分析生成失败，请稍后重试]"


# ── Content Extraction Pipeline ──

def extract_content_from_url(url: str) -> tuple[str, str, str]:
    """Fetch URL, extract main content. Returns (title, content, source_domain)."""
    domain = urlparse(url).netloc.replace("www.", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "no-cache",
    }
    html = ""
    try:
        # Some protected sites fail the HTTP/2 handshake from the server host.
        # HTTP/1.1 is slower but much more broadly compatible.
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            html = resp.text  # Capture HTML even on non-200 status
    except Exception:
        return "", "", domain

    # X/Twitter is mostly client-rendered, but exposes the post text in metadata.
    if "x.com/" in url or "twitter.com/" in url:
        try:
            soup = BeautifulSoup(html, "lxml")
            title = _extract_title(html)
            # Prefer X's syndication payload: the HTML title is often only a
            # truncated preview and may contain nothing but a t.co link.
            status_match = re.search(r"/status/(\d+)", url)
            if status_match:
                syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={status_match.group(1)}&lang=en"
                with httpx.Client(timeout=20, follow_redirects=True) as client:
                    syndication = client.get(syndication_url, headers={"User-Agent": headers["User-Agent"]})
                if syndication.status_code == 200:
                    payload = syndication.json()
                    tweet_text = str(payload.get("text") or payload.get("full_text") or "").strip()
                    if _is_good_extracted_content(tweet_text):
                        return title, tweet_text, domain
            description = ""
            # X exposes the canonical post text in the <title> even when the
            # description is only a generated preview/title.
            title_match = re.search(r'on X:\s*"(.+?)"\s*/\s*X$', title)
            if title_match:
                description = title_match.group(1).strip()
            for selector in [
                ('meta', {'property': 'og:description'}),
                ('meta', {'name': 'description'}),
                ('meta', {'name': 'twitter:description'}),
            ]:
                node = soup.find(*selector)
                if not description and node and node.get("content"):
                    description = node["content"].strip()
                    if description:
                        break
            if _is_good_extracted_content(description):
                return title, description, domain
        except Exception:
            pass

    # Primary: trafilatura extraction
    try:
        extracted = trafilatura_extract(
            html,
            include_links=False,
            include_images=False,
            include_tables=False,
            include_formatting=False,
            output_format="txt",
            favor_recall=True,
        )
        if _is_good_extracted_content(extracted):
            title = _extract_title(html)
            return title, extracted.strip(), domain
    except Exception:
        pass

    # Fallback: BeautifulSoup simple extraction
    try:
        soup = BeautifulSoup(html, "lxml")
        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            tag.decompose()
        # Find main content
        main = soup.find("main") or soup.find("article") or soup.find(role="main")
        if not main:
            main = soup.body or soup
        # Remove common non-content classes
        for unwanted in main.select(
            ".sidebar, .comments, .comment, .advertisement, .ad, .nav, .menu, .footer, .header, .share, .social, .related, .recommend"
        ):
            unwanted.decompose()
        text = main.get_text(separator="\n", strip=True)
        lines = [l for l in text.split("\n") if l.strip() and len(l.strip()) > 10]
        title = _extract_title(html)
        fallback_text = "\n\n".join(lines)
        if _is_good_extracted_content(fallback_text):
            return title, fallback_text, domain
    except Exception:
        pass

    # Medium frequently responds with a Cloudflare challenge. Jina Reader is
    # used only as a last-resort text reader, so normal pages remain local-first.
    if "medium.com" in domain:
        try:
            reader_url = "https://r.jina.ai/http://" + url.removeprefix("https://").removeprefix("http://")
            with httpx.Client(timeout=90, follow_redirects=True) as client:
                reader = client.get(reader_url, headers={"User-Agent": "Mozilla/5.0"})
            if reader.status_code == 200 and len(reader.text.strip()) > 200:
                text = reader.text.strip()
                title = next((line[7:].strip() for line in text.splitlines() if line.startswith("Title: ")), "")
                if "Markdown Content:" in text:
                    text = text.split("Markdown Content:", 1)[-1]
                return title or _extract_title(html), text.strip(), domain
        except Exception:
            pass

    return "", "", domain


def _is_good_extracted_content(text: str) -> bool:
    """Reject URL-only previews and obvious site chrome before translation."""
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if len(value) < 40:
        return False
    if re.fullmatch(r"(?:https?://|www\.)\S+", value):
        return False
    if value.count("http") >= 2 and len(re.sub(r"https?://\S+", "", value).strip()) < 35:
        return False
    chrome_markers = ("[Sitemap]", "Sign up", "Sign in", "Open in app", "Enable JavaScript", "cookies to continue")
    if sum(marker in value for marker in chrome_markers) >= 2 or "Enable JavaScript" in value:
        return False
    return True


def _extract_title(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
        if soup.title:
            t = soup.title.get_text(strip=True)
            # Clean common title suffixes
            for suffix in [" - X", " | X", " — Medium", " | LinkedIn", " | Twitter"]:
                base_suffix = suffix.split(" |")[0].split(" -")[0]
                if base_suffix and t.endswith(base_suffix):
                    t = t[: -len(base_suffix)].strip()
            return t[:300]
    except Exception:
        pass
    return ""


def extract_with_llm(url: str, raw_html: str) -> tuple[str, str]:
    """Use LLM to extract title and main content when HTML parsing fails."""
    settings = get_llm_settings()

    # Preprocess: strip scripts, styles, nav, header, footer to get more content into the prompt
    try:
        soup = BeautifulSoup(raw_html, "lxml")
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "header", "footer"]):
            tag.decompose()
        # Also try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find(role="main") or soup.body
        if main:
            cleaned = main.get_text(separator="\n", strip=True)
        else:
            cleaned = soup.get_text(separator="\n", strip=True)
        # Take a reasonable chunk (start, middle, end)
        if len(cleaned) > 20000:
            text_snippet = cleaned[:8000] + "\n...[truncated]...\n" + cleaned[-5000:]
        else:
            text_snippet = cleaned[:15000]
    except Exception:
        text_snippet = raw_html[:10000]

    if len(text_snippet.strip()) < 50:
        # Fallback: send raw HTML (truncated larger)
        text_snippet = raw_html[:12000]

    prompt = f"""你是一个网页内容提取器。请从以下网页文本中提取文章的标题和正文内容。

要求：
1. 如果页面是X/Twitter帖子，提取帖子正文内容
2. 忽略导航菜单、广告、评论区、侧边栏、页脚等非正文内容
3. 保持原文格式，不要总结、不要改写、不要遗漏
4. 如果文本中确实有正文内容，务必提取出来
5. 只输出 JSON 格式：{{"title": "文章标题", "content": "正文内容"}}

网页URL: {url}

文本内容:
{text_snippet}"""

    body = {
        "messages": [
            {"role": "system", "content": "你是网页内容提取器。只提取正文，不总结不改写。只输出JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 8000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    body["model"] = settings["model"]
    api_url = f"{settings['base_url'].rstrip('/')}/{settings['model']}/v1/chat/completions"
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings['api_key']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        result_text = data["choices"][0]["message"]["content"]
        # Extract JSON
        match = re.search(r"\{[\s\S]*\}", result_text)
        if match:
            result = json.loads(match.group())
            content = result.get("content", "")
            title = result.get("title", "")
            # If LLM returned content but it's very short (like a JSON error), it's probably not real content
            if content and len(content.strip()) > 50:
                return title, content.strip()
    except Exception:
        pass
    return "", ""


def translate_content(title: str, content: str) -> tuple[str, str]:
    """Translate title and content using LLM. Strict translation, no summarization."""
    if not content:
        return "", ""

    settings = get_llm_settings()

    def _call_llm(system_prompt: str, user_text: str, max_tokens: int) -> str:
        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        body["model"] = settings["model"]
        api_url = f"{settings['base_url'].rstrip('/')}/{settings['model']}/v1/chat/completions"
        req = urllib.request.Request(
            api_url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings['api_key']}"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    # Translate title
    translated_title = ""
    if title:
        try:
            translated_title = _call_llm(
                "你是一个专业翻译。将以下标题翻译成中文。只输出翻译结果，不要任何解释。保持原文的严谨性和语气。",
                title,
                200,
            )
        except Exception:
            translated_title = title

    # Translate content in chunks to respect token limits
    MAX_CHUNK_CHARS = 6000
    paragraphs = content.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if sum(len(p) for p in current_chunk) + len(para) < MAX_CHUNK_CHARS:
            current_chunk.append(para)
        else:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    translated_chunks: list[str] = []
    for chunk in chunks:
        try:
            result = _call_llm(
                "你是一个专业翻译。请将以下英文内容翻译成中文。要求：\n1. 严格翻译，不总结、不提炼、不删减任何内容\n2. 保持原文结构（段落、列表等）\n3. 专业术语保持准确\n4. 保持原文的严谨性和语气\n5. 只输出翻译结果，不要任何解释",
                chunk,
                8000,
            )
            translated_chunks.append(result)
        except Exception:
            translated_chunks.append(f"[翻译失败]\n{chunk[:200]}...")

    return translated_title, "\n\n".join(translated_chunks)


def process_article(
    article_id: int, url: str, title_hint: str = ""
) -> None:
    """Background task: extract content + translate + save to DB."""
    with db() as conn:
        conn.execute(
            "UPDATE insight_articles SET status='extracting', updated_at=? WHERE id=?",
            (now(), article_id),
        )
        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES((SELECT user_id FROM insight_articles WHERE id=?),?,?)",
            (article_id, "insight_extract", now()),
        )

    # Step 1: Extract content
    title, content, domain = extract_content_from_url(url)
    if not content:
        # Try LLM-based extraction
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                raw_html = resp.text
            if raw_html and len(raw_html) > 200:
                title, content = extract_with_llm(url, raw_html)
                if not _is_good_extracted_content(content):
                    title, content = "", ""
        except Exception:
            pass

    if title_hint and (not title):
        title = title_hint

    if not content:
        with db() as conn:
            conn.execute(
                "UPDATE insight_articles SET status='failed', title=?, source_domain=?, updated_at=? WHERE id=?",
                (title or url[:200], domain, now(), article_id),
            )
        return

    word_count = len(content.split())

    # Step 2: Translate
    with db() as conn:
        conn.execute(
            "UPDATE insight_articles SET status='translating', original_content=?, source_domain=?, title=?, word_count=?, updated_at=? WHERE id=?",
            (content, domain, title or url[:200], word_count, now(), article_id),
        )
        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES((SELECT user_id FROM insight_articles WHERE id=?),?,?)",
            (article_id, "insight_translate", now()),
        )

    translated_title, translated_content = translate_content(title, content)
    one_page_summary = generate_one_page_analysis(translated_title or title, translated_content or content)

    # Generate excerpt (first 200 chars of translation)
    excerpt = translated_content[:200].replace("\n", " ").strip() if translated_content else content[:200]

    with db() as conn:
        conn.execute(
            "UPDATE insight_articles SET status='ready', translated_content=?, excerpt=?, one_page_summary=?, title=?, updated_at=? WHERE id=?",
            (translated_content, excerpt, one_page_summary, translated_title or title or url[:200], now(), article_id),
        )


# ── Category APIs ──

@app.get("/api/v1/insight/categories")
def list_categories(user: sqlite3.Row = Depends(current_user)):
    bootstrap_default_categories(user["id"])  # Lazy bootstrap for new users
    bootstrap_sample_articles(user["id"])
    with db() as conn:
        rows = conn.execute(
            "SELECT id, name, icon, sort_order, (SELECT COUNT(*) FROM insight_articles WHERE category_id=insight_categories.id AND status='ready') AS article_count, created_at FROM insight_categories WHERE user_id=? ORDER BY sort_order, id",
            (user["id"],),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/insight/categories", status_code=201)
def create_category(body: InsightCategoryCreate, user: sqlite3.Row = Depends(current_user)):
    bootstrap_default_categories(user["id"])
    with db() as conn:
        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM insight_categories WHERE user_id=?",
            (user["id"],),
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO insight_categories(user_id,name,icon,sort_order,created_at) VALUES(?,?,?,?,?)",
            (user["id"], body.name, body.icon, body.sort_order if body.sort_order > 0 else max_order + 1, now()),
        )
        cat_id = cursor.lastrowid
    return {"id": cat_id, "name": body.name, "icon": body.icon}


@app.put("/api/v1/insight/categories/reorder")
def reorder_categories(
    body: InsightCategoryReorder,
    user: sqlite3.Row = Depends(current_user),
):
    with db() as conn:
        for i, cat_id in enumerate(body.order):
            conn.execute(
                "UPDATE insight_categories SET sort_order=? WHERE id=? AND user_id=?",
                (i, cat_id, user["id"]),
            )
    return {"ok": True}


@app.put("/api/v1/insight/categories/{category_id}")
def update_category(
    category_id: int,
    body: InsightCategoryUpdate,
    user: sqlite3.Row = Depends(current_user),
):
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_categories WHERE id=? AND user_id=?",
            (category_id, user["id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "分类不存在")
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.icon is not None:
            updates["icon"] = body.icon
        if body.sort_order is not None:
            updates["sort_order"] = body.sort_order
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [now(), category_id, user["id"]]
            conn.execute(
                f"UPDATE insight_categories SET {set_clause}, updated_at=? WHERE id=? AND user_id=?",
                values,
            )
    return {"ok": True}


@app.delete("/api/v1/insight/categories/{category_id}")
def delete_category(
    category_id: int,
    user: sqlite3.Row = Depends(current_user),
):
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_categories WHERE id=? AND user_id=?",
            (category_id, user["id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "分类不存在")
        # Move articles to uncategorized (NULL)
        conn.execute(
            "UPDATE insight_articles SET category_id=NULL WHERE category_id=? AND user_id=?",
            (category_id, user["id"]),
        )
        conn.execute(
            "DELETE FROM insight_categories WHERE id=? AND user_id=?",
            (category_id, user["id"]),
        )
    return {"ok": True}


# ── Article APIs ──

@app.post("/api/v1/insight/articles/save", status_code=201)
def save_article(
    body: InsightArticleSave,
    background_tasks: BackgroundTasks,
    user: sqlite3.Row = Depends(current_user),
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "请输入有效的网页链接")

    domain = urlparse(url).netloc.replace("www.", "")
    title_hint = url  # Client may pass a title hint

    # Validate category if specified
    if body.category_id is not None:
        with db() as conn:
            cat = conn.execute(
                "SELECT id FROM insight_categories WHERE id=? AND user_id=?",
                (body.category_id, user["id"]),
            ).fetchone()
            if not cat:
                raise HTTPException(404, "分类不存在")

    # Check duplicate
    with db() as conn:
        dup = conn.execute(
            "SELECT id FROM insight_articles WHERE user_id=? AND url=?",
            (user["id"], url),
        ).fetchone()
        if dup:
            return JSONResponse(
                {"id": dup["id"], "status": "duplicate", "message": "该链接已保存"},
                status_code=200,
            )

    with db() as conn:
        cursor = conn.execute(
            "INSERT INTO insight_articles(user_id,category_id,url,title,source_domain,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (user["id"], body.category_id, url, title_hint, domain, "pending", now(), now()),
        )
        article_id = cursor.lastrowid

    # Process in background
    background_tasks.add_task(process_article, article_id, url, "")

    return {"id": article_id, "status": "pending", "message": "已提交，正在提取内容并翻译"}


@app.post("/api/v1/insight/decode")
def decode_article(
    body: InsightDecodeRequest,
    user: sqlite3.Row = Depends(current_user),
):
    """Synchronous decode: extract → translate → one-page analysis. Returns all results at once."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "请输入有效的网页链接")

    domain = urlparse(url).netloc.replace("www.", "")

    # Validate category
    if body.category_id is not None:
        with db() as conn:
            cat = conn.execute(
                "SELECT id FROM insight_categories WHERE id=? AND user_id=?",
                (body.category_id, user["id"]),
            ).fetchone()
            if not cat:
                raise HTTPException(404, "分类不存在")

    # Step 1: Extract content
    title, content, domain = extract_content_from_url(url)
    if not content:
        # Try LLM-based extraction as fallback
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                title, content = extract_with_llm(url, resp.text)
        except Exception:
            pass

    if not content:
        raise HTTPException(422, "无法提取网页内容，请检查链接是否有效")

    word_count = len(content.split())
    if not title:
        title = url[:200]

    # Step 2: Translate (English → Chinese)
    translated_title = title
    translated_content = content
    needs_translation = any(
        ord(c) < 128 for c in content[:500] if c.isalpha()
    ) and sum(1 for c in content[:500] if '一' <= c <= '鿿') < 10

    if needs_translation:
        translated_title, translated_content = translate_content(title, content)
        if not translated_content:
            translated_content = content  # fallback to original

    # Step 3: One-page analysis (use translated content for Chinese analysis)
    analysis_input = translated_content if translated_content else content
    one_page_summary = generate_one_page_analysis(
        translated_title or title, analysis_input
    )

    # Step 4: Save article to database
    excerpt = (translated_content or content)[:200].replace("\n", " ").strip()
    article_id = None
    with db() as conn:
        dup = conn.execute(
            "SELECT id FROM insight_articles WHERE user_id=? AND url=?",
            (user["id"], url),
        ).fetchone()
        if dup:
            article_id = dup["id"]
            conn.execute(
                "UPDATE insight_articles SET title=?, original_content=?, translated_content=?,"
                " excerpt=?, one_page_summary=?, source_domain=?, word_count=?, status='ready', category_id=COALESCE(?, category_id),"
                " updated_at=? WHERE id=?",
                (translated_title or title, content, translated_content,
                 excerpt, one_page_summary, domain, word_count, body.category_id, now(), article_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO insight_articles(user_id,category_id,url,title,source_domain,"
                "original_content,translated_content,excerpt,one_page_summary,status,word_count,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user["id"], body.category_id, url, translated_title or title, domain,
                 content, translated_content, excerpt, one_page_summary, "ready", word_count, now(), now()),
            )
            article_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)",
            (user["id"], "insight_decode", now()),
        )

    return {
        "url": url,
        "title": translated_title or title,
        "source_domain": domain,
        "word_count": word_count,
        "original_content": content,
        "translated_content": translated_content or content,
        "one_page_summary": one_page_summary,
        "article_id": article_id,
    }


@app.get("/api/v1/insight/articles")
def list_articles(
    category_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    is_read: bool | None = None,
    is_starred: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    user: sqlite3.Row = Depends(current_user),
):
    conditions = ["a.user_id = ?"]
    params: list[Any] = [user["id"]]

    if category_id is not None:
        conditions.append("a.category_id = ?")
        params.append(category_id)
    if status:
        conditions.append("a.status = ?")
        params.append(status)
    if is_read is not None:
        conditions.append("a.is_read = ?")
        params.append(1 if is_read else 0)
    if is_starred is not None:
        conditions.append("a.is_starred = ?")
        params.append(1 if is_starred else 0)
    if search:
        conditions.append("(a.title LIKE ? OR a.excerpt LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)
    offset = (page - 1) * page_size

    with db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM insight_articles a WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT a.id, a.url, a.title, a.source_domain, a.excerpt, a.status,
                       a.is_read, a.is_starred, a.word_count, a.category_id,
                       COALESCE(c.name, '未分类') as category_name,
                       COALESCE(c.icon, '📄') as category_icon,
                       a.created_at, a.updated_at
                FROM insight_articles a
                LEFT JOIN insight_categories c ON a.category_id = c.id
                WHERE {where}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        ).fetchall()

    articles = []
    for r in rows:
        d = dict(r)
        d["is_read"] = bool(d["is_read"])
        d["is_starred"] = bool(d["is_starred"])
        articles.append(d)

    return {"articles": articles, "total": total, "page": page, "page_size": page_size}


@app.get("/api/v1/insight/articles/{article_id}")
def get_article(article_id: int, user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        row = conn.execute(
            """SELECT a.*, COALESCE(c.name, '未分类') as category_name,
                      COALESCE(c.icon, '📄') as category_icon,
                      COALESCE(cs.name, '') as section_name,
                      COALESCE(cc.name, '') as sub_category_name
               FROM insight_articles a
               LEFT JOIN insight_categories c ON a.category_id = c.id
               LEFT JOIN content_sections cs ON a.section_id = cs.id
               LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
               WHERE a.id=? AND a.user_id=?""",
            (article_id, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "文章不存在")

        # Mark as read
        if not row["is_read"]:
            conn.execute(
                "UPDATE insight_articles SET is_read=1, updated_at=? WHERE id=?",
                (now(), article_id),
            )

    result = dict(row)
    result["is_read"] = True  # Already marked
    result["is_starred"] = bool(result["is_starred"])
    return result


@app.patch("/api/v1/insight/articles/{article_id}")
def update_article(
    article_id: int,
    body: InsightArticleUpdate,
    user: sqlite3.Row = Depends(current_user),
):
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_articles WHERE id=? AND user_id=?",
            (article_id, user["id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "文章不存在")

        updates = {"updated_at": now()}
        if body.category_id is not None:
            if body.category_id != 0:
                cat = conn.execute(
                    "SELECT id FROM insight_categories WHERE id=? AND user_id=?",
                    (body.category_id, user["id"]),
                ).fetchone()
                if not cat:
                    raise HTTPException(404, "分类不存在")
                updates["category_id"] = body.category_id
            else:
                updates["category_id"] = None  # 稍后阅读 / uncategorized
        if body.is_read is not None:
            updates["is_read"] = 1 if body.is_read else 0
        if body.is_starred is not None:
            updates["is_starred"] = 1 if body.is_starred else 0

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [article_id, user["id"]]
        conn.execute(
            f"UPDATE insight_articles SET {set_clause} WHERE id=? AND user_id=?",
            values,
        )
    return {"ok": True}


@app.delete("/api/v1/insight/articles/{article_id}")
def delete_article(article_id: int, user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM insight_articles WHERE id=? AND user_id=?",
            (article_id, user["id"]),
        ).fetchone()
        if not existing:
            raise HTTPException(404, "文章不存在")
        conn.execute(
            "DELETE FROM insight_articles WHERE id=? AND user_id=?",
            (article_id, user["id"]),
        )
    return {"ok": True}


@app.get("/api/v1/insight/stats")
def insight_stats(user: sqlite3.Row = Depends(current_user)):
    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE user_id=? AND status='ready'",
            (user["id"],),
        ).fetchone()[0]
        unread = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE user_id=? AND status='ready' AND is_read=0",
            (user["id"],),
        ).fetchone()[0]
        starred = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE user_id=? AND status='ready' AND is_starred=1",
            (user["id"],),
        ).fetchone()[0]
        processing = conn.execute(
            "SELECT COUNT(*) FROM insight_articles WHERE user_id=? AND status IN ('pending','extracting','translating')",
            (user["id"],),
        ).fetchone()[0]
    return {"total": total, "unread": unread, "starred": starred, "processing": processing}


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML


@app.get("/admin/skills", response_class=HTMLResponse)
def admin_skills_page():
    return SKILL_ADMIN_HTML


@app.get("/", response_class=HTMLResponse)
def platform_page():
    return PLATFORM_HTML


@app.get("/project/ai-customer-service", response_class=HTMLResponse)
def project_page():
    return PLATFORM_HTML


@app.get("/research", response_class=HTMLResponse)
def research_page():
    return PLATFORM_HTML


@app.get("/publish", response_class=HTMLResponse)
def publish_page():
    return AGENT_HTML


AGENT_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>内容发布 · InSight</title><style>
*{box-sizing:border-box}body{margin:0;background:#f8f6f2;color:#25211f;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.top{height:68px;background:#fff;border-bottom:1px solid #e7e1dc;display:flex;align-items:center;padding:0 5vw;gap:28px}.brand{font-size:20px;font-weight:700;color:#b95737;text-decoration:none}.top a{color:#6f655f;text-decoration:none}.wrap{width:min(1320px,94vw);margin:28px auto}.switch{display:flex;gap:8px;margin-bottom:18px}.switch button,.toolbar button{border:1px solid #d9cdc5;background:#fff;border-radius:20px;padding:10px 16px;cursor:pointer}.switch .active,.toolbar .primary{background:#b95737;color:#fff;border-color:#b95737}.workspace{display:grid;grid-template-columns:330px 1fr 1.2fr;gap:16px;min-height:650px}.panel{background:#fff;border:1px solid #e7e1dc;border-radius:16px;padding:18px}.panel h2{font-size:17px;margin:0 0 15px}.skills label{display:block;border:1px solid #eee6e0;padding:11px;border-radius:9px;margin:8px 0;cursor:pointer}.skills input{margin-right:8px}.chat{display:flex;flex-direction:column}.messages{flex:1;overflow:auto;min-height:420px}.msg{padding:11px 13px;border-radius:12px;background:#f5f1ed;margin:9px 0;line-height:1.6}.msg.user{background:#fbe8df;margin-left:22px}.chat textarea{width:100%;min-height:85px;border:1px solid #ddd0c7;border-radius:9px;padding:12px;resize:vertical}.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.toolbar input{flex:1;min-width:150px}.editor input,.editor textarea{width:100%;border:1px solid #e1d7d0;border-radius:8px;padding:11px;margin-bottom:12px}.editor textarea{min-height:390px;line-height:1.7}.preview{border-top:1px solid #eee6e0;margin-top:14px;padding-top:15px;line-height:1.8;overflow:auto;max-height:420px}.preview img{max-width:100%}.muted{color:#7b716c}.hidden{display:none}@media(max-width:1000px){.workspace{grid-template-columns:1fr}.messages{min-height:240px}}
</style></head><body><header class="top"><a class="brand" href="/">InSight</a><a href="/">首页</a><a href="/admin/skills">Skill 管理</a></header><main class="wrap"><h1>内容发布</h1><p class="muted">挂载多个 Skill，与 Agent 对话生成并修改文章，确认后再发布。</p><div class="switch"><button id="linkMode" class="active" onclick="setMode('link')">链接解析</button><button id="manualMode" onclick="setMode('manual')">手写博客</button></div><div class="workspace"><section class="panel"><h2>挂载 Skills</h2><div id="skills" class="skills">加载中…</div><div class="toolbar"><input id="file" type="file"><button onclick="uploadFile()">上传文件</button></div><p id="fileMsg" class="muted"></p></section><section class="panel chat"><h2>Agent 对话</h2><div id="messages" class="messages"></div><textarea id="prompt" placeholder="例如：解析这个链接并整理成技术博客，保留原文图片……"></textarea><div class="toolbar"><input id="sourceUrl" placeholder="可选：输入链接"><button class="primary" onclick="sendMessage()">发送</button></div></section><section class="panel editor"><h2>文章草稿</h2><input id="draftTitle" placeholder="文章标题"><textarea id="draftContent" placeholder="Agent 生成的正文 HTML 会显示在这里，也可以直接编辑"></textarea><textarea id="draftSummary" placeholder="一页纸解读 HTML"></textarea><div class="toolbar"><button onclick="renderDraft()">刷新预览</button><button class="primary" onclick="publishDraft()">确认发布</button></div><div id="preview" class="preview"></div><p id="status" class="muted"></p></section></div></main><script>
let token=localStorage.inToken||'',sessionId='',mode='link',draft={};const api=async(p,o={})=>{o.headers={...(o.headers||{}),Authorization:'Bearer '+token,'Content-Type':'application/json'};let r=await fetch(p,o),j=await r.json();if(!r.ok)throw Error(j.detail||'请求失败');return j};const esc=v=>String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function setMode(m){mode=m;linkMode.classList.toggle('active',m==='link');manualMode.classList.toggle('active',m==='manual');prompt.placeholder=m==='link'?'例如：解析这个链接并整理成技术博客，保留原文图片……':'例如：把下面这段内容整理成一篇技术博客……'}
async function init(){if(!token){messages.innerHTML='<div class="msg">请先在首页登录 InSight。</div>';return}let s=await api('/api/v1/agent/skills');skills.innerHTML=s.length?s.map(x=>`<label><input type="checkbox" value="${x.id}">${esc(x.display_name)}<small class="muted"> · ${esc(x.description||x.name)}</small></label>`).join(''):'<p class="muted">暂无可用 Skill，请先在后台上传。</p>';messages.innerHTML='<div class="msg">Agent 已就绪，请选择 Skill 后输入任务。</div>'}
async function ensureSession(){if(sessionId)return;let ids=[...document.querySelectorAll('#skills input:checked')].map(x=>+x.value);let c=await api('/api/v1/agent/sessions',{method:'POST',body:JSON.stringify({mode,skill_ids:ids})});sessionId=c.id}
async function sendMessage(){try{await ensureSession();let text=prompt.value.trim();let url=sourceUrl.value.trim();if(url)text+='\n来源链接：'+url;if(!text)return;messages.innerHTML+=`<div class="msg user">${esc(text)}</div>`;prompt.value='';status.textContent='Agent 正在处理…';let r=await api('/api/v1/agent/sessions/'+sessionId+'/messages',{method:'POST',body:JSON.stringify({content:text})});messages.innerHTML+=`<div class="msg">${esc(r.message)}</div>`;draft=r.draft||{};draftTitle.value=draft.title||'';draftContent.value=draft.content_html||'';draftSummary.value=draft.summary_html||'';renderDraft();status.textContent='已更新草稿'}catch(e){status.textContent=e.message}}
async function uploadFile(){try{await ensureSession();let f=file.files[0];if(!f)return;let fd=new FormData();fd.append('file',f);let r=await fetch('/api/v1/agent/sessions/'+sessionId+'/files',{method:'POST',headers:{Authorization:'Bearer '+token},body:fd});let j=await r.json();if(!r.ok)throw Error(j.detail);fileMsg.textContent=j.message}catch(e){fileMsg.textContent=e.message}}
function renderDraft(){preview.innerHTML='<h1>'+esc(draftTitle.value)+'</h1>'+draftContent.value+'<hr><h2>一页纸解读</h2>'+draftSummary.value}
async function publishDraft(){try{draft={title:draftTitle.value,content_html:draftContent.value,summary_html:draftSummary.value,source_url:sourceUrl.value};await api('/api/v1/agent/sessions/'+sessionId+'/publish',{method:'POST'});status.textContent='已确认发布'}catch(e){status.textContent=e.message}}
init();</script></body></html>'''

SKILL_ADMIN_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Skill 管理 · InSight</title><style>*{box-sizing:border-box}body{margin:0;background:#f5f1ed;color:#29221f;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#fff;border-bottom:1px solid #e6ddd7;padding:20px 6vw;display:flex;gap:22px}header a{color:#b95737;text-decoration:none}main{width:min(960px,90vw);margin:30px auto}.card{background:#fff;border:1px solid #e4d9d2;border-radius:14px;padding:22px;margin-bottom:18px}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.row input{flex:1}.row input,.row button{padding:11px;border:1px solid #d7cbc4;border-radius:8px}.row button{background:#b95737;color:#fff;cursor:pointer}.skill{border-top:1px solid #eee5df;padding:15px 0;display:flex;justify-content:space-between;gap:12px}.skill button{border:1px solid #b95737;color:#b95737;background:#fff;border-radius:7px;padding:7px 10px}.muted{color:#786d67}</style></head><body><header><a href="/admin">管理后台</a><a href="/publish">内容发布</a></header><main><h1>Skill 管理</h1><p class="muted">上传包含 skill.json 和可选 SKILL.md 的 ZIP，供 Agent 会话挂载使用。</p><section class="card"><div class="row"><input id="skillFile" type="file" accept=".zip"><button onclick="upload()">上传 Skill ZIP</button></div><p id="msg" class="muted"></p></section><section class="card"><h2>已安装 Skills</h2><div id="list">加载中…</div></section></main><script>let token=localStorage.inToken||'';const esc=v=>String(v??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));async function load(){let r=await fetch('/api/v1/admin/skills',{headers:{Authorization:'Bearer '+token}});let d=await r.json();if(!r.ok){msg.textContent=d.detail||'请使用管理员账号登录';return}list.innerHTML=d.length?d.map(x=>`<div class="skill"><div><b>${esc(x.display_name)}</b> <span class="muted">v${esc(x.version)} · ${esc(x.skill_type)}</span><br><span class="muted">${esc(x.description)}</span></div><div><button onclick="toggle(${x.id},${!x.enabled})">${x.enabled?'停用':'启用'}</button> <button onclick="removeSkill(${x.id})">删除</button></div></div>`).join(''):'<p class="muted">还没有 Skill</p>'}async function upload(){let f=skillFile.files[0];if(!f)return;let fd=new FormData();fd.append('file',f);let r=await fetch('/api/v1/admin/skills',{method:'POST',headers:{Authorization:'Bearer '+token},body:fd});let d=await r.json();msg.textContent=r.ok?'上传成功：'+d.display_name:d.detail||'上传失败';if(r.ok)load()}async function toggle(id,enabled){await fetch('/api/v1/admin/skills/'+id,{method:'PATCH',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({enabled})});load()}async function removeSkill(id){if(confirm('确定删除该 Skill？')){await fetch('/api/v1/admin/skills/'+id,{method:'DELETE',headers:{Authorization:'Bearer '+token}});load()}}load();</script></body></html>'''

PLATFORM_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>InSight 技术平台</title><style>
:root{--blue:#1a73e8;--ink:#202124;--muted:#5f6368;--line:#dadce0;--paper:#fff;--bg:#f8fafd}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px Arial,"Noto Sans SC",sans-serif}button,input{font:inherit}.shell{min-height:100vh}.topbar{height:72px;padding:0 5vw;display:flex;align-items:center;gap:34px;background:#fff;border-bottom:1px solid #eef0f2;position:sticky;top:0;z-index:5}.brand{display:flex;align-items:center;gap:11px;color:var(--ink);text-decoration:none;font-size:19px;font-weight:600;letter-spacing:-.03em}.brandmark{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--blue);color:#fff;font-size:17px}.nav{display:flex;gap:25px;color:var(--muted)}.nav a{color:inherit;text-decoration:none;padding:25px 0}.nav a:hover{color:var(--blue)}.top-actions{margin-left:auto;display:flex;align-items:center;gap:10px}.top-actions button,.login button,.hero button{border:0;border-radius:24px;padding:10px 18px;background:var(--blue);color:#fff;cursor:pointer}.ghost{background:#fff!important;color:var(--blue)!important;border:1px solid var(--line)!important}.container{width:min(1160px,90vw);margin:auto}.hero{padding:66px 0 42px;display:grid;grid-template-columns:1.15fr .85fr;gap:50px;align-items:center}.eyebrow{font-size:12px;color:var(--blue);letter-spacing:.12em;font-weight:600}.hero h1{font-size:clamp(38px,5vw,66px);line-height:1.08;letter-spacing:-.065em;font-weight:500;margin:18px 0}.hero p{max-width:540px;color:var(--muted);font-size:16px;line-height:1.8;margin:0 0 25px}.hero-art{min-height:290px;border-radius:28px;background:linear-gradient(145deg,#e8f0fe,#fff);border:1px solid #d8e5fb;position:relative;overflow:hidden}.hero-art:before,.hero-art:after{content:"";position:absolute;border:1px solid #9bbdf3;border-radius:50%}.hero-art:before{width:300px;height:300px;right:-70px;top:-15px}.hero-art:after{width:190px;height:190px;right:50px;top:42px}.node{position:absolute;width:13px;height:13px;border-radius:50%;background:var(--blue);box-shadow:0 0 0 9px #d5e5fc}.n1{right:125px;top:105px}.n2{right:245px;top:190px}.n3{right:70px;top:215px}.link{height:1px;background:#79a7e8;position:absolute;transform-origin:left}.l1{width:145px;right:125px;top:111px;transform:rotate(143deg)}.l2{width:160px;right:125px;top:111px;transform:rotate(47deg)}.searchbar{display:flex;gap:9px;max-width:600px;padding:5px 6px 5px 16px;background:#fff;border:1px solid var(--line);border-radius:28px;box-shadow:0 2px 8px #3c40430f}.searchbar input{border:0;outline:0;flex:1;color:var(--ink)}.searchbar button{border:0;background:var(--blue);color:#fff;border-radius:22px;padding:10px 17px;cursor:pointer}.section-head{display:flex;align-items:end;justify-content:space-between;margin:26px 0 18px}.section-head h2{font-size:28px;font-weight:500;margin:7px 0 0;letter-spacing:-.04em}.muted{color:var(--muted)}.chips{display:flex;gap:9px;overflow:auto;padding-bottom:8px}.chip{white-space:nowrap;border:1px solid var(--line);border-radius:20px;background:#fff;color:var(--muted);padding:9px 15px;cursor:pointer}.chip.active{background:#e8f0fe;border-color:#c3d7f7;color:#185abc}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(296px,1fr));gap:20px;padding-bottom:80px}.card{background:#fff;border:1px solid #e3e6e9;border-radius:15px;overflow:hidden;transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s,border-color .22s;cursor:pointer;display:flex;flex-direction:column}.card:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.1);border-color:#c4c8ce}.card-cover{position:relative;aspect-ratio:16/9;overflow:hidden;background:linear-gradient(150deg,color-mix(in srgb,var(--tint,#1a73e8) 17%,#fff),#fff 75%);display:flex;align-items:center;justify-content:center}.card-cover .cover-dots{position:absolute;inset:0;background-image:radial-gradient(color-mix(in srgb,var(--tint,#1a73e8) 22%,transparent) 1px,transparent 1px);background-size:13px 13px;opacity:.45}.card-cover .cover-icon{font-size:48px;opacity:.5;position:relative;z-index:1}.card-cover .cat-badge{position:absolute;left:14px;top:13px;display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;color:var(--tint,#1a73e8)}.card-cover .cat-badge .sq{width:7px;height:7px;border-radius:2px;background:var(--tint,#1a73e8)}.card-cover .card-no{position:absolute;right:14px;top:13px;font-size:10.5px;color:#80868b;font-family:monospace;opacity:.8}.card-cover .srcbar{position:absolute;left:0;right:0;bottom:0;display:flex;align-items:center;gap:7px;padding:7px 13px;background:rgba(255,255,255,.85);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);border-top:1px solid rgba(0,0,0,.06)}.card-cover .srcbar .t{font-size:10px;color:#5f6368}.card-body{padding:16px 17px 15px;display:flex;flex-direction:column;flex:1}.card-body h3{font-size:17px;line-height:1.4;font-weight:600;margin:0 0 9px;letter-spacing:-.005em}.card-body .dek{font-size:13.5px;line-height:1.65;color:#5f6368;margin-bottom:14px;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.card-foot{display:flex;align-items:center;gap:8px;flex-wrap:nowrap;margin-top:auto}.card-foot .foot-tags{display:flex;gap:7px;flex-wrap:wrap;flex:1 1 auto;min-width:0}.card-foot .foot-right{margin-left:auto;white-space:nowrap}.card-foot .when{font-size:10.5px;color:#80868b}.tag-chip{font-size:10.5px;color:#80868b;background:#f1f3f4;border:1px solid #e3e6e9;border-radius:6px;padding:2px 7px;white-space:nowrap}.tag{font-size:11px;color:var(--blue);font-weight:600}.card p{color:var(--muted);line-height:1.7;margin:0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.meta{font-size:11px;color:#80868b;margin-top:17px}.empty{text-align:center;padding:60px;color:var(--muted);grid-column:1/-1}.login{position:fixed;inset:0;background:#20212466;display:grid;place-items:center;z-index:10}.login-box{width:min(410px,90vw);background:#fff;border-radius:20px;padding:30px;box-shadow:0 20px 60px #0003}.login-box h2{margin:0 0 8px;font-weight:500}.login-box input{width:100%;border:1px solid var(--line);border-radius:8px;padding:12px;margin-top:14px}.login-box button{margin-top:16px;width:100%;border:0;border-radius:8px;padding:12px;background:var(--blue);color:#fff;cursor:pointer}.detail{position:fixed;inset:0;background:#fff;z-index:9;overflow:auto}.detail-inner{width:min(820px,88vw);margin:0 auto;padding:40px 0 80px}.detail-close{border:0;background:transparent;color:var(--blue);cursor:pointer;font-size:15px}.detail h1{font-size:44px;line-height:1.15;font-weight:500;letter-spacing:-.05em;margin:38px 0 15px}.article-content{font-size:17px;line-height:1.9;white-space:pre-wrap}.article-content img{max-width:100%}.summary{background:#f1f6fe;border-radius:16px;padding:24px;line-height:1.8}.hidden{display:none!important}@media(max-width:760px){.topbar{padding:0 18px}.nav{display:none}.hero{display:block;padding:42px 0 24px}.hero-art{min-height:190px;margin-top:30px}.grid{grid-template-columns:1fr}.detail h1{font-size:34px}}
</style></head><body><div class="shell"><header class="topbar"><a class="brand" href="/"><span class="brandmark">i</span>InSight</a><nav class="nav"><a href="/">首页</a><a href="/project/ai-customer-service">项目沉淀</a><a href="/research">研究解读</a></nav><div class="top-actions"><button id="loginBtn" onclick="showLogin()">登录</button><span id="userInfo" class="hidden" style="font-size:13px;color:var(--ink);display:flex;align-items:center;gap:8px"><a href="/admin" target="_blank" style="color:var(--blue);text-decoration:none;font-size:13px">⚙️ 后台管理</a><span id="userName"></span><button id="logoutBtn" class="ghost" onclick="logout()">退出</button></span></div></header><main class="container"><section class="hero"><div><span class="eyebrow">TECHNOLOGY, EXPLAINED</span><h1>把复杂技术，<br>讲成可以复用的知识。</h1><p>从收藏的网页、项目经验到 AI 生成的一页纸解读，InSight 帮你建立一座真正可阅读、可检索、可持续积累的技术知识库。</p><div class="searchbar"><input id="search" placeholder="搜索文章、主题或关键词" onkeydown="if(event.key==='Enter')loadArticles()"><button onclick="loadArticles()">搜索</button></div></div><div class="hero-art"><i class="node n1"></i><i class="node n2"></i><i class="node n3"></i><i class="link l1"></i><i class="link l2"></i></div></section><section id="categories"><div class="section-head"><div><span class="eyebrow">EXPLORE</span><h2>按主题探索</h2></div><span id="count" class="muted"></span></div><div id="chips" class="chips"></div></section><section id="latest"><div class="section-head"><div><span class="eyebrow">KNOWLEDGE LIBRARY</span><h2>最新收藏</h2></div></div><div id="grid" class="grid"><div class="empty">登录后即可查看你的技术收藏</div></div></section></main></div><div id="login" class="login hidden"><div class="login-box"><button class="detail-close" onclick="hideLogin()">关闭</button><h2>登录 InSight</h2><p class="muted">登录后查看你的收藏和一页纸解读</p><input id="email" placeholder="邮箱"><input id="password" type="password" placeholder="密码"><button onclick="login()">登录</button><p id="loginMsg" class="muted"></p></div></div><div id="detail" class="detail hidden"><div class="detail-inner"><button class="detail-close" onclick="closeDetail()">← 返回文章列表</button><div id="detailBody"></div></div></div><script>
let token=localStorage.inToken||'',activeCategory=null,allArticles=[];const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const catColor=n=>{const c={'稍后阅读':'#5f6368','工具教程':'#1a73e8','产品发布':'#e37400','商业动态':'#0d652d','研究解读':'#9334e6','项目沉淀':'#188038','认知提升':'#c5221f'};return c[n]||'#1a73e8'};const catIcon=n=>{const c={'稍后阅读':'📥','工具教程':'🛠️','产品发布':'🚀','商业动态':'💼','研究解读':'🔬','项目沉淀':'📐','认知提升':'💡'};return c[n]||'📄'};const fmtDate=s=>{if(!s)return'';let d=new Date(s.replace(' ','T'));if(isNaN(d.getTime()))return s.slice(0,10);let m=d.getMonth()+1,D=d.getDate();return d.getFullYear()+'-'+(m<10?'0'+m:m)+'-'+(D<10?'0'+D:D)};const api=async(p,o={})=>{o.headers={...(o.headers||{}),Authorization:'Bearer '+token,'Content-Type':'application/json'};let r=await fetch(p,o),j=await r.json();if(!r.ok)throw Error(j.detail||'请求失败');return j};function showLogin(){login.classList.remove('hidden')}function hideLogin(){login.classList.add('hidden')}function logout(){token='';localStorage.removeItem('inToken');loginBtn.classList.remove('hidden');userInfo.classList.add('hidden');grid.innerHTML='<div class="empty">登录后即可查看你的技术收藏</div>'}async function login(){loginMsg.textContent='登录中...';try{let r=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email.value,password:password.value})}),j=await r.json();if(!r.ok)throw Error(j.detail||'登录失败');token=j.token;localStorage.inToken=token;hideLogin();loginBtn.classList.add('hidden');userInfo.classList.remove('hidden');userName.textContent=j.user.name;j.user.role==='admin'?document.querySelector('.top-actions a').style.display='':document.querySelector('.top-actions a').style.display='none';await loadCategories();await loadArticles()}catch(e){loginMsg.textContent=e.message}}async function loadCategories(){try{let cats=await api('/api/v1/insight/categories');chips.innerHTML='<button class="chip active" onclick="selectCategory(null,this)">全部</button>'+cats.map(c=>`<button class="chip" onclick="selectCategory(${c.id},this)">${esc(c.name)}</button>`).join('')}catch(e){}}function selectCategory(id,el){activeCategory=id;document.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));el.classList.add('active');loadArticles()}function renderCard(a){let catName=a.section_name||a.category_name||'未分类',icon=catIcon(catName),tint=catColor(catName),domain=esc(a.source_domain||a.section_name||'网页'),title=esc(a.title),excerpt=esc(a.excerpt||''),date=fmtDate(a.created_at),ready=a.status==='ready',subName=a.sub_category_name?`${esc(a.sub_category_name)}`:'',author=a.author_name?` · ${esc(a.author_name)}`:'';return `<article class="card" style="--tint:${tint}" onclick="openArticle(${a.id})"><div class="card-cover"><div class="cover-dots"></div><div class="cat-badge"><span class="sq"></span>${esc(catName)}${subName?' / '+subName:''}</div><div class="card-no">#${a.id}</div><span class="cover-icon">${icon}</span><div class="srcbar"><span class="t">${domain}${author}</span></div></div><div class="card-body"><h3>${title}</h3><p class="dek">${excerpt||'点击阅读正文…'}</p><div class="card-foot"><span class="foot-tags"><span class="tag-chip">${esc(catName)}</span>${subName?`<span class="tag-chip">${subName}</span>`:''}${ready?'':`<span class="tag-chip" style="color:#e37400">处理中</span>`}</span><span class="foot-right"><span class="when">${date}</span></span></div></div></article>`}async function loadArticles(){if(!token){showLogin();return}try{let q=search.value?`&search=${encodeURIComponent(search.value)}`:'';if(activeCategory)q+=`&category_id=${activeCategory}`;let data=await api('/api/v1/insight/articles?page=1&page_size=30'+q);allArticles=data.articles;count.textContent=`${data.total} 篇`;grid.innerHTML=allArticles.length?allArticles.map(renderCard).join(''):'<div class="empty">暂时没有匹配的内容</div>'}catch(e){grid.innerHTML=`<div class="empty">${esc(e.message)}</div>`}}async function openArticle(id){try{let a=await api('/api/v1/insight/articles/'+id);let isManual=a.content_type==='manual';let eyebrow=a.section_name?esc(a.section_name)+(a.sub_category_name?' · '+esc(a.sub_category_name):''):esc(a.source_domain);let content=a.manual_content||a.translated_content||'内容处理中，请稍后再试。';let summaryBlock=a.one_page_summary?`<h2>一页纸解读</h2><div class="summary">${a.one_page_summary}</div>`:'';detailBody.innerHTML=`<span class="eyebrow">${eyebrow}${isManual?' ✍️':''}</span><h1>${esc(a.title)}</h1><p class="muted">正文</p><div class="article-content">${content}</div>${summaryBlock}`;detail.classList.remove('hidden')}catch(e){alert(e.message)}}function closeDetail(){detail.classList.add('hidden')}if(token){loginBtn.classList.add('hidden');userInfo.classList.remove('hidden');api('/api/v1/me').then(me=>{userName.textContent=me.name;if(me.role!=='admin')document.querySelector('.top-actions a').style.display='none'}).catch(()=>{});loadCategories();loadArticles()}
</script></body></html>'''


PLATFORM_HTML = PLATFORM_HTML.replace(
    '</style>',
    '''<style>
.hero-art{background:#cf765f!important;border-color:#b95d4d!important;animation:heroBreath 8s ease-in-out infinite}.hero-art:before{content:"";position:absolute;width:350px;height:240px;right:-75px;top:25px;background:#fff8e9;border-radius:47% 53% 43% 57%/58% 43% 57% 42%;transform:rotate(-11deg);animation:heroCarrier 9s ease-in-out infinite}.hero-art:after{content:"";position:absolute;width:235px;height:165px;right:35px;top:62px;border:4px solid #141413;border-radius:48% 52% 45% 55%/52% 42% 58% 48%;transform:rotate(7deg);animation:heroOrbit 7s ease-in-out infinite}.hero-art .node{z-index:2;background:#e8a36b;border:3px solid #141413;box-shadow:none}.hero-art .link{z-index:2;background:#141413;height:4px;border-radius:4px}.hero-art:global{overflow:hidden}@keyframes heroBreath{50%{background:#bd6d5c}}@keyframes heroCarrier{50%{transform:rotate(-4deg) scale(1.04);border-radius:56% 44% 50% 50%/42% 58% 45% 55%}}@keyframes heroOrbit{50%{transform:rotate(-7deg) scale(.94)}}.route-page{padding:65px 0 100px}.route-page h1{font-size:clamp(40px,5vw,64px);font-weight:500;letter-spacing:-.07em;margin:16px 0}.route-lead{max-width:700px;color:var(--muted);font-size:17px;line-height:1.8}.route-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:40px}.route-panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:25px}.route-panel h3{font-size:20px;font-weight:500;margin:0 0 12px}.route-panel p,.route-panel li{color:var(--muted);line-height:1.8}.publish-form{max-width:700px;background:#fff;border:1px solid var(--line);border-radius:18px;padding:28px;margin-top:35px}.publish-form input,.publish-form textarea{width:100%;border:1px solid var(--line);border-radius:8px;padding:12px;margin:7px 0 14px}.publish-form textarea{min-height:130px;resize:vertical}.publish-tabs{display:flex;gap:0;margin-top:24px}.pub-tab{padding:10px 20px;border:1px solid var(--line);background:#fff;color:var(--muted);cursor:pointer;border-radius:8px 8px 0 0;font-size:14px}.pub-tab.active{background:var(--blue);color:#fff;border-color:var(--blue)}.publish-form label{font-size:13px;color:var(--muted);margin-top:10px}.publish-form select{margin-bottom:7px}.trix-editor{border-radius:8px!important}.trix-editor .trix-button-group{border-color:var(--line)!important}.trix-editor .trix-button{background:#fff!important}.publish-form{margin-top:0;border-radius:0 0 18px 18px}@media(max-width:760px){.route-grid{grid-template-columns:1fr}}\n</style>''',
    1,
)
PLATFORM_HTML = PLATFORM_HTML.replace(
    '</body></html>',
    '''<script>
(function(){
  const path=location.pathname;
  document.querySelector('.nav').innerHTML='<a href="/">首页</a><a href="/project/ai-customer-service">项目沉淀</a><a href="/research">研究解读</a>';
  if(token){try{let me=await api('/api/v1/me');loginBtn.classList.add('hidden');userInfo.classList.remove('hidden');userName.textContent=me.name;if(me.role!=='admin')document.querySelector('.top-actions a').style.display='none'}catch(e){}}
  if(path==='/') return;
  const main=document.querySelector('main');
  if(path.startsWith('/project/')) main.innerHTML='<section class="route-page"><span class="eyebrow">PROJECT NOTES</span><h1>项目沉淀</h1><p class="route-lead">把一次次真实交付中的判断、方案和复盘，整理成团队下一次可以直接复用的工程资产。</p><div class="route-grid"><article class="route-panel"><h3>问题与背景</h3><p>记录业务目标、约束条件和真正需要解决的问题，避免只展示最终结果。</p></article><article class="route-panel"><h3>方案拆解</h3><p>从数据、模型、工具调用到评测，把系统如何工作讲清楚。</p></article><article class="route-panel"><h3>结果与复盘</h3><p>沉淀指标变化、踩坑经验和可以带走的实践清单。</p></article></div><div id="projectGrid" class="grid"><div class="empty">登录后查看项目文章</div></div></section>';
  else if(path==='/research') main.innerHTML='<section class="route-page"><span class="eyebrow">RESEARCH & INTERPRETATION</span><h1>研究解读</h1><p class="route-lead">把论文、技术文章和行业动态转化成结构清晰的一页纸判断，帮助你更快理解，也更快决定是否值得深入。</p><div class="route-grid"><article class="route-panel"><h3>原文正文</h3><p>保留原始上下文、关键图片与引用，适合深入阅读。</p></article><article class="route-panel"><h3>一页纸解读</h3><p>提炼核心观点、关键证据、技术架构和行动启示。</p></article><article class="route-panel"><h3>持续积累</h3><p>按分类检索收藏，把零散链接变成可复用的知识地图。</p></article></div><div id="researchGrid" class="grid"><div class="empty">登录后查看研究文章</div></div></section>';
  else if(path==='/publish'){window.open('/admin','_blank');history.back()}
  if(token){loadRouteArticles()}
})();
async function loadRouteArticles(){try{const sections=await api('/api/v1/content/sections');let target=document.getElementById('projectGrid')||document.getElementById('researchGrid');if(!target)return;let sectionSlug='research';if(document.getElementById('projectGrid'))sectionSlug='project';const sec=sections.find(s=>s.slug===sectionSlug);let d=[];if(sec){const r=await api('/api/v1/content/articles?section_id='+sec.id+'&page=1&page_size=30');d=r.articles}else{const r=await api('/api/v1/content/articles?page=1&page_size=30');d=r.articles}target.innerHTML=d.length?d.map(renderCard).join(''):'<div class="empty">暂无内容</div>'}catch(e){}}
</script></body></html>''',
    1,
)
PLATFORM_HTML = PLATFORM_HTML.replace(
    '</style>',
    '''<style>
.draw-banner{position:absolute;inset:0;width:100%;height:100%;overflow:visible}.draw-banner .carrier{fill:#fff8e9;stroke:none;transform-origin:center;animation:carrierWobble 9s ease-in-out infinite}.draw-banner .ink{fill:none;stroke:#141413;stroke-width:5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:220;stroke-dashoffset:220;animation:handDraw 1.4s cubic-bezier(.4,0,.2,1) forwards}.draw-banner .ink-a{animation-delay:.35s}.draw-banner .ink-b{animation-delay:.8s}.draw-banner .ink-c{animation-delay:1.25s}.draw-banner .ink-d{animation-delay:1.7s}.draw-banner .dot{fill:#e8a36b;stroke:#141413;stroke-width:4;opacity:0;animation:dotAppear .45s ease forwards}.draw-banner .dot-a{animation-delay:1.6s}.draw-banner .dot-b{animation-delay:2.1s}.draw-banner .dot-c{animation-delay:2.5s}.draw-banner .dot-d{animation-delay:2.9s}.draw-banner .scribble{fill:none;stroke:#141413;stroke-width:3;stroke-linecap:round;stroke-dasharray:100;stroke-dashoffset:100;animation:handDraw 1s 2.9s ease forwards}.draw-caption{position:absolute;left:43px;bottom:34px;color:#141413;font:700 11px monospace;letter-spacing:.12em;transform:rotate(-4deg)}@keyframes handDraw{to{stroke-dashoffset:0}}@keyframes dotAppear{to{opacity:1}}@keyframes carrierWobble{50%{transform:rotate(-2deg) scale(1.025)}}@media(prefers-reduced-motion:reduce){.draw-banner *{animation:none!important;stroke-dashoffset:0!important;opacity:1!important}}
</style>''',
    1,
)
PLATFORM_HTML = PLATFORM_HTML.replace(
    '</body></html>',
    '''<script>
(function(){
  if(location.pathname!=='/') return;
  const art=document.querySelector('.hero-art');
  if(!art) return;
  art.innerHTML='<svg class="draw-banner" viewBox="0 0 520 310" role="img" aria-label="把网页链接整理成可复用的知识网络"><path class="carrier" d="M164 57 C245 21 387 35 439 91 C477 132 442 246 350 267 C252 289 112 254 92 170 C77 106 107 76 164 57Z"/><path class="ink ink-a" d="M143 164 C194 121 223 101 280 87"/><path class="ink ink-b" d="M280 87 C337 99 366 121 403 165"/><path class="ink ink-c" d="M280 87 C278 139 270 186 238 227"/><path class="ink ink-d" d="M238 227 C301 228 351 208 403 165"/><circle class="dot dot-a" cx="143" cy="164" r="10"/><circle class="dot dot-b" cx="280" cy="87" r="10"/><circle class="dot dot-c" cx="403" cy="165" r="10"/><circle class="dot dot-d" cx="238" cy="227" r="10"/><path class="scribble" d="M116 251 C134 243 147 249 161 243 M119 261 C140 254 151 260 169 254"/></svg><span class="draw-caption">READ · CONNECT · REUSE</span>';
})();
</script></body></html>''',
    1,
)


PLATFORM_HTML = PLATFORM_HTML.replace(
    '</style>',
    '''<style>
.hero{padding-top:78px}.hero h1{font-size:clamp(44px,6vw,76px);line-height:1.04}.hero p{font-size:17px}.hero-copy{max-width:650px}.home-sections{display:grid;grid-template-columns:1.3fr .7fr;gap:28px;margin:20px 0 80px}.topic-block{background:#fff;border:1px solid var(--line);border-radius:20px;padding:26px}.topic-block h2{font-size:25px;font-weight:500;margin:5px 0 20px}.topic-block .grid{grid-template-columns:repeat(2,1fr);padding:0}.section-link{color:var(--blue);text-decoration:none;font-size:13px}.research-filter{display:flex;gap:9px;overflow:auto;padding:4px 0 16px}.research-filter .chip{background:#fff}.research-filter .chip.active{background:#e8f0fe}.article-content{overflow-wrap:anywhere}.article-content pre{white-space:pre-wrap;overflow:auto;background:#f8fafd;padding:16px;border-radius:10px}.article-content h1,.article-content h2,.article-content h3{line-height:1.35}.summary-block{line-height:1.8}.summary-block h3{margin-top:0;color:var(--blue)}@media(max-width:900px){.home-sections{grid-template-columns:1fr}}@media(max-width:760px){.hero{padding-top:45px}.hero h1{font-size:44px}.topic-block .grid{grid-template-columns:1fr}}
.hero-art:before,.hero-art:after{display:none!important}.publish-tabs{display:flex;gap:0;margin-bottom:0;border-bottom:2px solid var(--line)}.pub-tab{padding:11px 22px;border:0;background:transparent;color:var(--muted);cursor:pointer;border-radius:10px 10px 0 0;font-weight:600;font-size:14px}.pub-tab.active{background:#fff;color:var(--blue);border:2px solid var(--line);border-bottom-color:#fff;margin-bottom:-2px}.publish-form select{width:100%;padding:12px;border:1px solid var(--line);border-radius:8px;margin:7px 0 14px;background:#fff}.publish-form trix-toolbar{background:#f8fafd;border:1px solid var(--line);border-bottom:0;border-radius:8px 8px 0 0}.publish-form trix-editor{min-height:300px;border:1px solid var(--line)!important;border-radius:0 0 8px 8px;padding:12px;background:#fff}@media(max-width:760px){.grid{grid-template-columns:1fr}.card-cover{aspect-ratio:16/9}}
</style>''', 1)
PLATFORM_HTML = PLATFORM_HTML.replace(
    '</body></html>',
    '''<script>
(function(){
  if(location.pathname!=='/') return;
  const hero=document.querySelector('.hero');
  const oldSearch=document.querySelector('.searchbar'); if(oldSearch) oldSearch.remove();
  const latest=document.querySelector('#latest'); const categories=document.querySelector('#categories');
  if(!hero||!latest||!categories) return;
  categories.remove();
  latest.outerHTML='<section class="home-sections"><div class="topic-block"><div class="section-head"><div><span class="eyebrow">LATEST NOTES</span><h2>最新解读</h2></div><a class="section-link" href="/research">查看全部 →</a></div><div id="homeResearch" class="grid"><div class="empty">登录后查看最新文章</div></div></div><div class="topic-block"><div class="section-head"><div><span class="eyebrow">PROJECTS</span><h2>项目沉淀</h2></div><a class="section-link" href="/project/ai-customer-service">进入项目 →</a></div><div id="homeProject" class="grid"><div class="empty">登录后查看项目文章</div></div></div></section>';
  if(token) loadHomeSections();
})();
async function loadHomeSections(){try{const[sections,personal]=await Promise.all([api('/api/v1/content/articles?page=1&page_size=30'),api('/api/v1/insight/articles?page=1&page_size=30')]);const all=[...sections.articles,...personal.articles].sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));document.getElementById('homeResearch').innerHTML=all.slice(0,4).map(a=>renderCard(a)).join('')||'<div class="empty">暂无研究文章</div>';document.getElementById('homeProject').innerHTML=all.slice(0,4).map(a=>renderCard(a)).join('')||'<div class="empty">暂无项目文章</div>'}catch(e){}}
</script></body></html>''', 1)
PLATFORM_HTML = PLATFORM_HTML.replace(
    '</body></html>',
    '''<script>
(function(){if(location.pathname!=='/research')return;const grid=document.getElementById('researchGrid');if(!grid)return;const box=document.createElement('div');box.className='research-filter';box.id='researchFilter';grid.parentNode.insertBefore(box,grid);loadResearchFilters()})();
async function loadResearchFilters(){try{let cats=await api('/api/v1/content/sections');researchFilter.innerHTML='<button class="chip active" onclick="filterResearch(null,this)">全部</button>';for(const s of cats){const tree=await api('/api/v1/content/sections/'+s.id+'/categories-tree');researchFilter.innerHTML+=`<button class="chip" onclick="filterResearch(${s.id},this)" style="font-weight:600">${esc(s.name)}</button>`;for(const c of tree.categories){researchFilter.innerHTML+=`<button class="chip" onclick="filterResearchCategory(${c.id},this)">${esc(c.name)}</button>`}}filterResearch(null,researchFilter.firstElementChild)}catch(e){}}
async function filterResearch(sectionId,el){researchFilter.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));el.classList.add('active');try{let p=sectionId?`&section_id=${sectionId}`:'';let d=await api('/api/v1/content/articles?page=1&page_size=30'+p);let target=document.getElementById('researchGrid');target.innerHTML=d.articles.length?d.articles.map(renderCard).join(''):'<div class="empty">暂无文章</div>'}catch(e){}}
async function filterResearchCategory(catId,el){researchFilter.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));el.classList.add('active');try{let d=await api('/api/v1/content/articles?page=1&page_size=30&sub_category_id='+catId);let target=document.getElementById('researchGrid');target.innerHTML=d.articles.length?d.articles.map(renderCard).join(''):'<div class="empty">该分类暂无文章</div>'}catch(e){}}
</script></body></html>''', 1)


ADMIN_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>InSight 管理台</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f1ed;color:#25211f;font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:#b95737;color:white;padding:16px 5vw;font-size:21px;font-weight:700;display:flex;align-items:center;gap:24px}header a{color:#ffe0d6;text-decoration:none;font-size:13px;font-weight:400}header a:hover{color:#fff}main{max-width:1080px;margin:18px auto;padding:0 20px}.card{background:#fffdfb;border:1px solid #e4d9d2;border-radius:8px;padding:20px;margin-bottom:18px}input,button,select{font:inherit;padding:10px 12px;border-radius:6px;border:1px solid #d8ccc5}button{background:#b95737;color:white;border:0;cursor:pointer}.secondary{background:transparent;color:#b95737;border:1px solid #b95737}.danger{background:#c0392b}.small{padding:5px 10px;font-size:12px}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}.panel-head h2{margin:0}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid #eee4de}.row{display:flex;gap:10px;flex-wrap:wrap}.row input,.row select{flex:1;min-width:140px}.muted{color:#776d68}.stats{display:flex;gap:24px;font-size:18px}.hidden{display:none}.tabs{display:flex;gap:0;margin-bottom:0;border-bottom:2px solid #dec8bc}.tab-btn{padding:10px 20px;border:0;background:transparent;color:#8c7368;cursor:pointer;border-radius:6px 6px 0 0;font-weight:600}.tab-btn.active{background:#fffdfb;color:#b95737;border:2px solid #dec8bc;border-bottom-color:#fffdfb;margin-bottom:-2px}.tab-content{display:none}.tab-content.active{display:block}.section-card{background:#faf7f5;border:1px solid #e8ddd6;border-radius:8px;padding:16px;margin-bottom:12px}.section-card h3{font-size:16px;margin:0 0 8px;display:flex;align-items:center;gap:8px}.section-card h3 .count{font-size:12px;color:#776d68;font-weight:400}.cat-tree{margin:0;padding:0;list-style:none}.cat-tree li{padding:6px 0}.cat-tree .cat-item{display:flex;align-items:center;gap:8px;padding:4px 0}.cat-tree .cat-children{margin-left:24px;border-left:2px solid #dec8bc;padding-left:12px}.cat-name{flex:1}.inline-form{display:flex;gap:6px;align-items:center;margin-top:8px}.inline-form input,.inline-form select{flex:1;min-width:100px;padding:6px 10px}.modal-overlay{position:fixed;inset:0;background:#0006;display:grid;place-items:center;z-index:10}.modal{background:#fffdfb;border-radius:12px;padding:24px;width:min(460px,90vw);box-shadow:0 12px 40px #0003}.modal h3{margin:0 0 14px}.modal .row{margin-bottom:12px}.modal label{display:block;margin-bottom:4px;color:#5f6368;font-size:12px}.modal input,.modal select,.modal textarea{width:100%}textarea{resize:vertical;min-height:60px}.pub-tabs{display:flex;gap:0;margin-bottom:15px;border-bottom:2px solid #dec8bc}.pub-tab{padding:8px 18px;border:0;background:transparent;color:#8c7368;cursor:pointer;border-radius:6px 6px 0 0;font-weight:600;font-size:13px}.pub-tab.active{background:#fffdfb;color:#b95737;border:2px solid #dec8bc;border-bottom-color:#fffdfb;margin-bottom:-2px}.pub-form{padding:0}.pub-form label{display:block;font-size:12px;color:#776d68;margin-bottom:4px}.pub-form .row{margin-bottom:10px}</style></head><body><header>InSight 管理台<a href="/">← 返回首页</a></header><main>
<section id="loginCard" class="card"><h2>管理员登录</h2><div class="row"><input id="email" placeholder="邮箱"><input id="password" type="password" placeholder="密码"><button onclick="adminLogin()">登录</button></div><p id="message" class="muted"></p></section>
<div id="panel" class="hidden"><section class="card panel-head"><div><h2>管理面板</h2><div id="stats" class="stats" style="margin-top:8px"></div></div><button class="secondary" onclick="logout()">退出登录</button></section><div class="tabs"><button class="tab-btn active" onclick="switchTab('users')">用户管理</button><button class="tab-btn" onclick="switchTab('categories')">分类管理</button><button class="tab-btn" onclick="switchTab('publish')">内容发布</button><button class="tab-btn" onclick="switchTab('llm')">大模型配置</button></div><div id="tab-users" class="tab-content active card" style="border-radius:0 0 8px 8px"><table><thead><tr><th>用户</th><th>状态</th><th>收藏</th><th>使用记录</th><th>最近登录/活动</th><th>操作</th></tr></thead><tbody id="users"></tbody></table></div><div id="tab-categories" class="tab-content card" style="border-radius:0 0 8px 8px"><div class="panel-head"><h2>板块与分类管理</h2><button onclick="showAddSection()">+ 新增板块</button></div><div id="sectionsList"></div></div><div id="tab-publish" class="tab-content card" style="border-radius:0 0 8px 8px"><div class="panel-head"><h2>内容发布</h2></div><div class="pub-tabs"><button class="pub-tab active" onclick="adminSwitchPub('url')">🔗 链接发布</button><button class="pub-tab" onclick="adminSwitchPub('manual')">✍️ 手动编辑</button></div><div id="admin-pub-url" class="pub-form"><div class="row"><div style="flex:1"><label>发布到板块</label><select id="adminPubUrlSection" onchange="adminLoadPubCats(+this.value,'adminPubUrlCat')"><option value="">请选择</option></select></div><div style="flex:1"><label>分类</label><select id="adminPubUrlCat"><option value="">可选</option></select></div></div><div class="row"><div style="flex:1"><label>网页链接</label><input id="adminPubUrl" placeholder="https://..." style="width:100%"></div></div><div class="row"><div style="flex:1"><label>补充说明</label><input id="adminPubUrlHint" placeholder="可选" style="width:100%"></div></div><button onclick="adminPublishUrl()">开始提取并发布</button><p id="adminPubUrlMsg" class="muted"></p></div><div id="admin-pub-manual" class="pub-form hidden"><div class="row"><div style="flex:1"><label>发布到板块</label><select id="adminPubManualSection" onchange="adminLoadPubCats(+this.value,'adminPubManualCat')"><option value="">请选择</option></select></div><div style="flex:1"><label>分类</label><select id="adminPubManualCat"><option value="">可选</option></select></div></div><div class="row"><div style="flex:1"><label>文章标题</label><input id="adminPubManualTitle" placeholder="输入标题" style="width:100%"></div></div><div class="row"><div style="flex:1"><label>摘要</label><input id="adminPubManualExcerpt" placeholder="可选" style="width:100%"></div></div><label>正文内容</label><div style="margin:8px 0"><input id="adminPubManualContent" type="hidden"><div id="adminEditorContainer" style="min-height:300px;border:1px solid #d8ccc5;border-radius:6px;padding:1px;background:#fff"></div></div><button onclick="adminPublishManual()">发布文章</button><p id="adminPubManualMsg" class="muted"></p></div></div><div id="tab-llm" class="tab-content card" style="border-radius:0 0 8px 8px"><h2>大模型配置</h2><div class="row" style="margin-top:12px"><input id="base_url" placeholder="Base URL"><input id="model" placeholder="模型"><input id="api_key" placeholder="API Key"><input id="max_tokens" type="number" placeholder="Max tokens"><button onclick="saveLLM()">保存</button></div></div></div></main>
<div id="modal" class="modal-overlay hidden"><div class="modal" id="modalContent"></div></div><script>
let token=localStorage.inToken||'';const statusName={pending:'待审批',approved:'已批准',disabled:'已停用'};const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const api=async(path,opt={})=>{opt.headers={...(opt.headers||{}),Authorization:'Bearer '+token,'Content-Type':'application/json'};const r=await fetch(path,opt);const j=await r.json();if(!r.ok)throw Error(j.detail||'请求失败');return j};
function logout(){token='';localStorage.removeItem('inToken');panel.classList.add('hidden');loginCard.classList.remove('hidden');message.textContent='已退出登录';password.value=''}
function switchTab(tab){const names={users:'用户管理',categories:'分类管理',publish:'内容发布',llm:'大模型配置'};document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.textContent.includes(names[tab])));document.querySelectorAll('.tab-content').forEach(c=>c.classList.toggle('active',c.id==='tab-'+tab));if(tab==='categories')loadSections();if(tab==='publish')initAdminPublish()}
async function adminLogin(){message.textContent='';try{const r=await fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email.value,password:password.value})});const j=await r.json();if(!r.ok)throw Error(j.detail||'登录失败');if(j.user.role!=='admin')throw Error('该账号不是管理员');token=j.token;localStorage.inToken=token;await load()}catch(e){token='';localStorage.removeItem('inToken');message.textContent=e.message}}
async function load(){try{const [u,s,l]=await Promise.all([api('/api/v1/admin/users'),api('/api/v1/admin/stats'),api('/api/v1/admin/llm')]);loginCard.classList.add('hidden');panel.classList.remove('hidden');stats.textContent=`用户 ${Object.values(s.users).reduce((a,b)=>a+b,0)} · 收藏 ${s.articles} 篇 · AI ${s.events.llm||0}`;users.innerHTML=u.map(x=>{const action=x.role==='admin'?'管理员':x.status==='approved'?`<button class="small" onclick="approve(${x.id},'disabled')">停用</button>`:x.status==='disabled'?`<button class="small" onclick="approve(${x.id},'approved')">重新批准</button>`:`<button class="small" onclick="approve(${x.id},'approved')">批准</button> <button class="small danger" onclick="approve(${x.id},'disabled')">拒绝</button>`;return `<tr><td><b>${esc(x.name)}</b><br><span class=muted>${esc(x.email)}</span></td><td>${statusName[x.status]||esc(x.status)}</td><td>${x.article_count} 篇</td><td>AI ${x.llm_count} 次<br>收藏事件 ${x.insight_events} 次</td><td>${esc(x.last_login_at||'未登录')}<br>${esc(x.last_activity_at||'无活动')}</td><td>${action}</td></tr>`}).join('');Object.entries(l).forEach(([k,v])=>{const e=document.getElementById(k);if(e)e.value=v})}catch(e){localStorage.removeItem('inToken');token='';panel.classList.add('hidden');loginCard.classList.remove('hidden');message.textContent=e.message||'登录已失效，请重新登录'}}
async function approve(id,status){try{await api('/api/v1/admin/users/'+id,{method:'PATCH',body:JSON.stringify({status})});await load()}catch(e){message.textContent=e.message}}
async function saveLLM(){await api('/api/v1/admin/llm',{method:'PUT',body:JSON.stringify({base_url:base_url.value,model:model.value,api_key:api_key.value,max_tokens:+max_tokens.value,temperature:0})});alert('已保存')}

// ── Category Management ──
async function loadSections(){try{const ss=await api('/api/v1/admin/sections');let h='';for(const s of ss){h+=`<div class="section-card"><h3>${esc(s.name)} <span class="count">${s.cat_count} 个分类</span><span style="margin-left:auto;font-weight:400;font-size:12px"><button class="small" onclick="showEditSection(${s.id},'${esc(s.name)}','${esc(s.slug)}','${esc(s.description||'')}')">编辑</button> <button class="small danger" onclick="deleteSection(${s.id},'${esc(s.name)}')">删除</button></span></h3><p class="muted">${esc(s.description||'')}</p><div id="cats-${s.id}">加载中…</div><div class="inline-form"><button class="small" onclick="showAddCategory(${s.id},null,'一级')">+ 添加一级分类</button></div></div>`}if(!h)h='<p class="muted">暂无板块，请先添加</p>';sectionsList.innerHTML=h;for(const s of ss)await loadCategories(s.id)}catch(e){sectionsList.innerHTML=`<p class="muted">${esc(e.message)}</p>`}}
async function loadCategories(sectionId){try{const cats=await api('/api/v1/admin/sections/'+sectionId+'/categories');const l1=cats.filter(c=>!c.parent_id);let h='<ul class="cat-tree">';for(const c of l1){const children=cats.filter(ch=>ch.parent_id===c.id);h+=`<li><div class="cat-item"><span>${esc(c.icon)} <b class="cat-name">${esc(c.name)}</b> <span class="muted">(${c.article_count} 篇)</span><button class="small" onclick="showEditCategory(${c.id},'${esc(c.name)}','${esc(c.slug)}','${esc(c.icon)}',${c.section_id},${c.sort_order})">编辑</button><button class="small" onclick="showAddCategory(${sectionId},${c.id},'二级')">+二级</button><button class="small danger" onclick="deleteCategory(${c.id},'${esc(c.name)}')">删除</button></div>`;if(children.length){h+='<ul class="cat-children">';for(const ch of children)h+=`<li><div class="cat-item"><span>${esc(ch.icon)} <span class="cat-name">${esc(ch.name)}</span> <span class="muted">(${ch.article_count} 篇)</span><button class="small" onclick="showEditCategory(${ch.id},'${esc(ch.name)}','${esc(ch.slug)}','${esc(ch.icon)}',${ch.section_id},${ch.sort_order})">编辑</button><button class="small danger" onclick="deleteCategory(${ch.id},'${esc(ch.name)}')">删除</button></div></li>`;h+='</ul>'}h+='</li>'}h+='</ul>';document.getElementById('cats-'+sectionId).innerHTML=h||'<p class="muted">暂无分类</p>'}catch(e){document.getElementById('cats-'+sectionId).innerHTML=`<p class="muted">${esc(e.message)}</p>`}}

function showAddSection(){modalContent.innerHTML=`<h3>新增板块</h3><div class="row"><label>板块名称</label><input id="secName" placeholder="如: 项目沉淀"></div><div class="row"><label>Slug (URL标识)</label><input id="secSlug" placeholder="如: project"></div><div class="row"><label>描述</label><textarea id="secDesc" placeholder="板块描述"></textarea></div><button onclick="addSection()">创建</button> <button class="secondary" onclick="closeModal()">取消</button>`;modal.classList.remove('hidden')}
async function addSection(){try{await api('/api/v1/admin/sections',{method:'POST',body:JSON.stringify({name:secName.value,slug:secSlug.value,description:secDesc.value})});closeModal();await loadSections()}catch(e){alert(e.message)}}
function showEditSection(id,name,slug,desc){modalContent.innerHTML=`<h3>编辑板块</h3><div class="row"><label>名称</label><input id="secName" value="${esc(name)}"></div><div class="row"><label>描述</label><textarea id="secDesc">${esc(desc)}</textarea></div><button onclick="updateSection(${id})">保存</button> <button class="secondary" onclick="closeModal()">取消</button>`;modal.classList.remove('hidden')}
async function updateSection(id){try{await api('/api/v1/admin/sections/'+id,{method:'PUT',body:JSON.stringify({name:secName.value,description:secDesc.value})});closeModal();await loadSections()}catch(e){alert(e.message)}}
async function deleteSection(id,name){if(!confirm(`确定删除板块"${name}"？这将同时删除其下所有分类！`))return;try{await api('/api/v1/admin/sections/'+id,{method:'DELETE'});await loadSections()}catch(e){alert(e.message)}}

function showAddCategory(sectionId,parentId,level){const title=parentId?'添加二级分类':'添加一级分类';modalContent.innerHTML=`<h3>${title}</h3><div class="row"><label>名称</label><input id="catName" placeholder="分类名称"></div><div class="row"><label>Slug</label><input id="catSlug" placeholder="url-slug"></div><div class="row"><label>图标 (emoji)</label><input id="catIcon" value="📄"></div><button onclick="addCategory(${sectionId},${parentId||null})">创建</button> <button class="secondary" onclick="closeModal()">取消</button>`;modal.classList.remove('hidden')}
async function addCategory(sectionId,parentId){try{await api('/api/v1/admin/categories',{method:'POST',body:JSON.stringify({section_id:sectionId,parent_id:parentId,name:catName.value,slug:catSlug.value,icon:catIcon.value})});closeModal();await loadSections()}catch(e){alert(e.message)}}
function showEditCategory(id,name,slug,icon,sectionId,order){modalContent.innerHTML=`<h3>编辑分类</h3><div class="row"><label>名称</label><input id="catName" value="${esc(name)}"></div><div class="row"><label>Slug</label><input id="catSlug" value="${esc(slug)}"></div><div class="row"><label>图标</label><input id="catIcon" value="${esc(icon)}"></div><div class="row"><label>排序</label><input id="catOrder" type="number" value="${order}"></div><button onclick="updateCategory(${id})">保存</button> <button class="secondary" onclick="closeModal()">取消</button>`;modal.classList.remove('hidden')}
async function updateCategory(id){try{await api('/api/v1/admin/categories/'+id,{method:'PUT',body:JSON.stringify({name:catName.value,slug:catSlug.value,icon:catIcon.value,sort_order:+catOrder.value})});closeModal();await loadSections()}catch(e){alert(e.message)}}
async function deleteCategory(id,name){if(!confirm(`确定删除分类"${name}"？`))return;try{await api('/api/v1/admin/categories/'+id,{method:'DELETE'});await loadSections()}catch(e){alert(e.message)}}
function closeModal(){modal.classList.add('hidden')}

// ── Content Publish (Admin) ──
function adminSwitchPub(tab){document.querySelectorAll('.pub-tab').forEach(b=>b.classList.toggle('active',(tab==='url'&&b.textContent.includes('链接'))||(tab==='manual'&&b.textContent.includes('手动'))));document.getElementById('admin-pub-url').classList.toggle('hidden',tab!=='url');document.getElementById('admin-pub-manual').classList.toggle('hidden',tab!=='manual')}
async function initAdminPublish(){try{const ss=await api('/api/v1/content/sections');let opts='<option value="">请选择板块</option>'+ss.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');document.getElementById('adminPubUrlSection').innerHTML=opts;document.getElementById('adminPubManualSection').innerHTML=opts;initAdminEditor()}catch(e){console.error(e)}}
async function adminLoadPubCats(sectionId,targetId){if(!sectionId){document.getElementById(targetId).innerHTML='<option value="">可选</option>';return}try{const d=await api('/api/v1/content/sections/'+sectionId+'/categories-tree');let opts='<option value="">选择分类</option>';for(const c of d.categories){opts+=`<option value="${c.id}">━━ ${esc(c.name)}</option>`;for(const ch of c.children)opts+=`<option value="${ch.id}">　　　${esc(ch.name)}</option>`}document.getElementById(targetId).innerHTML=opts}catch(e){console.error(e)}}
let _adminTrixLoaded=false;function initAdminEditor(){const c=document.getElementById('adminEditorContainer');if(!c)return;if(!document.getElementById('trix-css')){const link=document.createElement('link');link.id='trix-css';link.rel='stylesheet';link.href='https://unpkg.com/trix@2.1.0/dist/trix.css';document.head.appendChild(link)}if(_adminTrixLoaded&&window.Trix){_mountAdminTrix(c);return}const s=document.createElement('script');s.src='https://unpkg.com/trix@2.1.0/dist/trix.umd.min.js';s.onload=()=>{_adminTrixLoaded=true;_mountAdminTrix(c)};document.head.appendChild(s)}
function _mountAdminTrix(container){container.innerHTML=`<trix-toolbar id="adminTrixToolbar"><div class="trix-button-row"><span class="trix-button-group trix-button-group--text-tools"><button type="button" class="trix-button trix-button--icon trix-button--icon-bold" data-trix-attribute="bold" title="粗体"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-italic" data-trix-attribute="italic" title="斜体"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-strike" data-trix-attribute="strike" title="删除线"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-link" data-trix-attribute="href" data-trix-action="link" title="链接"></button></span><span class="trix-button-group trix-button-group--block-tools"><button type="button" class="trix-button trix-button--icon trix-button--icon-heading-1" data-trix-attribute="heading" data-trix-value="h2" title="H2"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-heading-2" data-trix-attribute="heading" data-trix-value="h3" title="H3"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-quote" data-trix-attribute="quote" title="引用"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-bullet-list" data-trix-attribute="bullet" title="无序列表"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-number-list" data-trix-attribute="number" title="有序列表"></button><button type="button" class="trix-button trix-button--icon trix-button--icon-code" data-trix-attribute="code" title="代码"></button></span></div></trix-toolbar><trix-editor toolbar="adminTrixToolbar" input="adminPubManualContent" class="trix-content" style="min-height:260px;padding:12px"></trix-editor>`}
async function adminPublishUrl(){let msg=document.getElementById('adminPubUrlMsg');const sec=+document.getElementById('adminPubUrlSection').value;const url=document.getElementById('adminPubUrl').value.trim();if(!sec){msg.textContent='请选择板块';return}if(!url){msg.textContent='请输入链接';return}msg.textContent='提交中…';try{await api('/api/v1/content/articles/publish-url',{method:'POST',body:JSON.stringify({section_id:sec,sub_category_id:+document.getElementById('adminPubUrlCat').value||null,url:url,title_hint:document.getElementById('adminPubUrlHint').value})});msg.textContent='✅ 已提交，后台正在提取内容';document.getElementById('adminPubUrl').value='';document.getElementById('adminPubUrlHint').value=''}catch(e){msg.textContent=e.message}}
async function adminPublishManual(){let msg=document.getElementById('adminPubManualMsg');const sec=+document.getElementById('adminPubManualSection').value;const title=document.getElementById('adminPubManualTitle').value.trim();const content=document.getElementById('adminPubManualContent').value.trim();if(!sec){msg.textContent='请选择板块';return}if(!title){msg.textContent='请输入标题';return}if(!content){msg.textContent='请输入正文';return}msg.textContent='发布中…';try{await api('/api/v1/content/articles/publish-manual',{method:'POST',body:JSON.stringify({section_id:sec,sub_category_id:+document.getElementById('adminPubManualCat').value||null,title:title,excerpt:document.getElementById('adminPubManualExcerpt').value.trim(),manual_content:content})});msg.textContent='✅ 发布成功！';document.getElementById('adminPubManualTitle').value='';document.getElementById('adminPubManualExcerpt').value='';document.getElementById('adminPubManualContent').value='';const ed=document.querySelector('#adminEditorContainer trix-editor');if(ed)ed.editor.loadHTML('')}catch(e){msg.textContent=e.message}}
if(token)load();
</script></body></html>'''


# ========================================
# Blog Frontend Public APIs
# 博客前端公开 API
# ========================================

@app.get("/api/v1/blog/articles")
def get_public_blog_articles(
    section_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
):
    """公开的文章列表 API - 只返回已发布的文章"""
    return list_content_articles(
        section_id=section_id,
        sub_category_id=category_id,
        search=search,
        page=page,
        page_size=limit
    )


@app.get("/api/v1/blog/articles/{article_id}")
def get_public_blog_article(article_id: int):
    """公开的文章详情 API"""
    with db() as conn:
        row = conn.execute(
            """SELECT a.*, 
                      COALESCE(cs.name, '') as section_name,
                      COALESCE(cc.name, '') as category_name,
                      u.name as author_name
               FROM insight_articles a
               LEFT JOIN content_sections cs ON a.section_id = cs.id
               LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
               LEFT JOIN users u ON a.user_id = u.id
               WHERE a.id=? AND a.status='ready' AND a.section_id IS NOT NULL""",
            (article_id,),
        ).fetchone()
        
        if not row:
            raise HTTPException(404, "文章不存在或未发布")

        # 每访问一次已发布文章，阅读量 +1
        conn.execute(
            "UPDATE insight_articles SET read_count = COALESCE(read_count, 0) + 1 WHERE id=?",
            (article_id,),
        )
        data = dict(row)
        data["read_count"] = (data.get("read_count") or 0) + 1
        return data


@app.get("/api/v1/blog/sections")
def get_public_blog_sections():
    """获取所有板块"""
    with db() as conn:
        rows = conn.execute(
            """SELECT id, name, slug, description, sort_order, created_at, updated_at
               FROM content_sections
               ORDER BY sort_order, id"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/blog/categories")
def get_public_blog_categories(section_id: int | None = None):
    """获取分类列表"""
    conditions = []
    params = []
    
    if section_id is not None:
        conditions.append("section_id = ?")
        params.append(section_id)
    
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    with db() as conn:
        rows = conn.execute(
            f"""SELECT id, section_id, parent_id, name, slug, icon, sort_order,
                       created_at, updated_at
                FROM content_categories
                {where}
                ORDER BY sort_order, id""",
            params
        ).fetchall()
    
    return [dict(r) for r in rows]


@app.get("/api/v1/blog/featured")
def get_featured_blog_articles(limit: int = 6):
    """获取精选文章 - 按星标或其他标准"""
    with db() as conn:
        rows = conn.execute(
            """SELECT a.id, a.url, a.title, a.subtitle, a.source_domain, a.excerpt, a.status,
                      a.word_count, a.section_id, a.sub_category_id, a.content_type,
                      a.banner_url, a.content_format, a.doc_kind,
                      a.created_at, a.updated_at, a.is_starred,
                      COALESCE(cc.name, '') AS category_name,
                      COALESCE(cs.name, '') AS section_name,
                      u.name AS author_name
               FROM insight_articles a
               LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
               LEFT JOIN content_sections cs ON a.section_id = cs.id
               LEFT JOIN users u ON a.user_id = u.id
               WHERE a.status = 'ready' AND a.section_id IS NOT NULL
               ORDER BY a.is_starred DESC, a.created_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
    
    return [dict(r) for r in rows]


@app.get("/api/v1/blog/latest")
def get_latest_blog_articles(limit: int = 10):
    """获取最新文章"""
    with db() as conn:
        rows = conn.execute(
            """SELECT a.id, a.url, a.title, a.subtitle, a.source_domain, a.excerpt, a.status,
                      a.word_count, a.section_id, a.sub_category_id, a.content_type,
                      a.banner_url, a.content_format, a.doc_kind,
                      a.created_at, a.updated_at,
                      COALESCE(cc.name, '') AS category_name,
                      COALESCE(cs.name, '') AS section_name,
                      u.name AS author_name
               FROM insight_articles a
               LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
               LEFT JOIN content_sections cs ON a.section_id = cs.id
               LEFT JOIN users u ON a.user_id = u.id
               WHERE a.status = 'ready' AND a.section_id IS NOT NULL
               ORDER BY a.created_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
    
    return [dict(r) for r in rows]


# ========================================
# Admin Articles Management APIs
# 后台文章管理 API
# ========================================

@app.get("/api/v1/admin/articles")
def get_admin_articles(
    section_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
    user: sqlite3.Row = Depends(admin_user),
):
    """管理员获取所有文章（包括草稿）"""
    conditions = ["a.section_id IS NOT NULL"]
    params: list[Any] = []
    
    if section_id is not None:
        conditions.append("a.section_id = ?")
        params.append(section_id)
    if category_id is not None:
        conditions.append("a.sub_category_id = ?")
        params.append(category_id)
    if status:
        conditions.append("a.status = ?")
        params.append(status)
    if search:
        conditions.append("(a.title LIKE ? OR a.excerpt LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where = " AND ".join(conditions)
    offset = (page - 1) * limit
    
    with db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM insight_articles a WHERE {where}", params
        ).fetchone()[0]
        
        rows = conn.execute(
            f"""SELECT a.*, 
                       COALESCE(cc.name, '') AS category_name,
                       COALESCE(cs.name, '') AS section_name,
                       u.name AS author_name
                FROM insight_articles a
                LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
                LEFT JOIN content_sections cs ON a.section_id = cs.id
                LEFT JOIN users u ON a.user_id = u.id
                WHERE {where}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()
    
    return {
        "articles": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": limit
    }


@app.post("/api/v1/admin/articles", status_code=201)
def create_admin_article(
    body: dict,
    user: sqlite3.Row = Depends(admin_user),
):
    """管理员创建文章"""
    # 实现逻辑类似于 publish-manual
    return {"message": "功能开发中"}


@app.put("/api/v1/admin/articles/{article_id}")
def update_admin_article(
    article_id: int,
    body: dict,
    user: sqlite3.Row = Depends(admin_user),
):
    """管理员更新文章"""
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        
        if not existing:
            raise HTTPException(404, "文章不存在")
        
        # 更新逻辑
        updates = []
        params = []
        
        if "title" in body:
            updates.append("title = ?")
            params.append(body["title"])
        if "excerpt" in body:
            updates.append("excerpt = ?")
            params.append(body["excerpt"])
        if "manual_content" in body:
            updates.append("manual_content = ?")
            params.append(body["manual_content"])
        if "section_id" in body:
            updates.append("section_id = ?")
            params.append(body["section_id"])
        if "sub_category_id" in body:
            updates.append("sub_category_id = ?")
            params.append(body["sub_category_id"])
        
        if updates:
            updates.append("updated_at = ?")
            params.append(now())
            params.append(article_id)
            
            conn.execute(
                f"UPDATE insight_articles SET {', '.join(updates)} WHERE id = ?",
                params
            )
    
    return {"message": "更新成功"}


@app.delete("/api/v1/admin/articles/{article_id}")
def delete_admin_article(
    article_id: int,
    user: sqlite3.Row = Depends(admin_user),
):
    """管理员删除文章"""
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        
        if not existing:
            raise HTTPException(404, "文章不存在")
        
        conn.execute("DELETE FROM insight_articles WHERE id=?", (article_id,))
    
    return {"message": "删除成功"}


@app.patch("/api/v1/admin/articles/{article_id}/publish")
def publish_admin_article(
    article_id: int,
    user: sqlite3.Row = Depends(admin_user),
):
    """发布文章"""
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        
        if not existing:
            raise HTTPException(404, "文章不存在")
        
        conn.execute(
            "UPDATE insight_articles SET status='ready', updated_at=? WHERE id=?",
            (now(), article_id)
        )
    
    return {"message": "发布成功"}


@app.patch("/api/v1/admin/articles/{article_id}/unpublish")
def unpublish_admin_article(
    article_id: int,
    user: sqlite3.Row = Depends(admin_user),
):
    """取消发布文章"""
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM insight_articles WHERE id=?",
            (article_id,),
        ).fetchone()
        
        if not existing:
            raise HTTPException(404, "文章不存在")
        
        conn.execute(
            "UPDATE insight_articles SET status='draft', updated_at=? WHERE id=?",
            (now(), article_id)
        )
    
    return {"message": "已取消发布"}


# ========================================
# Admin Models Management APIs  
# LLM 模型管理 API
# ========================================

# 主流模型供应商预设：前端「快速添加」用，减少手填出错
LLM_PROVIDER_PRESETS = [
    {
        "provider": "openai",
        "label": "OpenAI",
        "api_base_url": "https://api.openai.com/v1",
        "path_style": "openai",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o3-mini"],
    },
    {
        "provider": "anthropic",
        "label": "Anthropic Claude",
        "api_base_url": "https://api.anthropic.com/v1",
        "path_style": "anthropic",
        "models": [
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-1-20250805",
            "claude-3-5-haiku-20241022",
        ],
    },
    {
        "provider": "deepseek",
        "label": "DeepSeek",
        "api_base_url": "https://api.deepseek.com/v1",
        "path_style": "openai",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    {
        "provider": "dashscope",
        "label": "阿里通义千问",
        "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "path_style": "openai",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
    },
    {
        "provider": "moonshot",
        "label": "月之暗面 Kimi",
        "api_base_url": "https://api.moonshot.cn/v1",
        "path_style": "openai",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    {
        "provider": "zhipu",
        "label": "智谱 GLM",
        "api_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "path_style": "openai",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
    },
    {
        "provider": "openai-compatible",
        "label": "自建 / OpenAI 兼容",
        "api_base_url": "http://127.0.0.1:8000/v1",
        "path_style": "openai",
        "models": [],
    },
    {
        "provider": "insight-gateway",
        "label": "内部网关（模型名在路径中）",
        "api_base_url": "http://127.0.0.1:6018",
        "path_style": "model-in-path",
        "models": [],
    },
]

MODEL_PUBLIC_FIELDS = """id, name, provider, model_id, api_base_url, path_style,
        max_tokens, temperature, is_default, enabled,
        last_tested_at, last_test_ok, last_test_message, created_at, updated_at"""


def _model_row_to_dict(row: sqlite3.Row, api_key: str = "") -> dict[str, Any]:
    """Never return the raw api_key; only whether one is set."""
    data = dict(row)
    data.pop("api_key", None)
    data["has_api_key"] = bool(api_key)
    return data


def _resolve_chat_url(base_url: str, model_id: str, path_style: str) -> str:
    base = (base_url or "").rstrip("/")
    if path_style == "model-in-path":
        return f"{base}/{model_id}/v1/chat/completions"
    if path_style == "anthropic":
        return f"{base}/messages"
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _probe_model(
    *,
    model_id: str,
    api_base_url: str,
    api_key: str,
    path_style: str,
    max_tokens: int,
    temperature: float,
    timeout: int = 30,
) -> dict[str, Any]:
    """Send a minimal completion request to verify connectivity."""
    url = _resolve_chat_url(api_base_url, model_id, path_style)
    probe_tokens = max(1, min(int(max_tokens or 16), 16))
    headers = {"Content-Type": "application/json"}

    if path_style == "anthropic":
        payload = {
            "model": model_id,
            "max_tokens": probe_tokens,
            "messages": [{"role": "user", "content": "ping"}],
        }
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        payload = {
            "model": model_id,
            "max_tokens": probe_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": "ping"}],
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read() or b"{}")
        latency_ms = int((time.monotonic() - started) * 1000)
        reply = ""
        if path_style == "anthropic":
            blocks = body.get("content") or []
            if blocks and isinstance(blocks, list):
                reply = (blocks[0] or {}).get("text", "")
        else:
            choices = body.get("choices") or []
            if choices:
                reply = ((choices[0] or {}).get("message") or {}).get("content", "")
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "message": f"连接正常，耗时 {latency_ms}ms",
            "url": url,
            "reply": (reply or "")[:200],
        }
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        detail = ""
        try:
            detail = (exc.read() or b"").decode(errors="ignore")[:300]
        except Exception:
            pass
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "message": f"HTTP {exc.code}: {detail or exc.reason}",
            "url": url,
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "message": f"{type(exc).__name__}: {exc}",
            "url": url,
        }


@app.get("/api/v1/admin/models/presets")
def get_llm_model_presets(_: sqlite3.Row = Depends(admin_user)):
    """主流模型供应商预设"""
    return LLM_PROVIDER_PRESETS


@app.get("/api/v1/admin/models")
def get_llm_models(_: sqlite3.Row = Depends(admin_user)):
    """获取 LLM 模型列表"""
    with db() as conn:
        rows = conn.execute(
            f"SELECT {MODEL_PUBLIC_FIELDS}, api_key FROM llm_models "
            "ORDER BY is_default DESC, id DESC"
        ).fetchall()
    return [_model_row_to_dict(r, r["api_key"]) for r in rows]


@app.post("/api/v1/admin/models", status_code=201)
def create_llm_model(body: dict, _: sqlite3.Row = Depends(admin_user)):
    """创建 LLM 模型配置"""
    name = (body.get("name") or "").strip()
    model_id = (body.get("model_id") or "").strip()
    api_base_url = (body.get("api_base_url") or "").strip()
    if not name:
        raise HTTPException(422, "名称不能为空")
    if not model_id:
        raise HTTPException(422, "模型 ID 不能为空")
    if not api_base_url:
        raise HTTPException(422, "API 地址不能为空")

    timestamp = now()
    with db() as conn:
        is_first = conn.execute("SELECT COUNT(*) FROM llm_models").fetchone()[0] == 0
        is_default = 1 if (body.get("is_default") or is_first) else 0
        if is_default:
            conn.execute("UPDATE llm_models SET is_default=0")
        try:
            cursor = conn.execute(
                """INSERT INTO llm_models
                   (name, provider, model_id, api_base_url, api_key, path_style,
                    max_tokens, temperature, is_default, enabled, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    name,
                    (body.get("provider") or "openai").strip(),
                    model_id,
                    api_base_url,
                    body.get("api_key") or "",
                    (body.get("path_style") or "openai").strip(),
                    int(body.get("max_tokens") or 4096),
                    float(body.get("temperature") or 0),
                    is_default,
                    0 if body.get("enabled") == 0 else 1,
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "同名模型已存在") from exc
        row = conn.execute(
            f"SELECT {MODEL_PUBLIC_FIELDS}, api_key FROM llm_models WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
    return _model_row_to_dict(row, row["api_key"])


@app.put("/api/v1/admin/models/{model_id}")
def update_llm_model(model_id: int, body: dict, _: sqlite3.Row = Depends(admin_user)):
    """更新 LLM 模型配置"""
    editable = {
        "name": str,
        "provider": str,
        "model_id": str,
        "api_base_url": str,
        "path_style": str,
        "max_tokens": int,
        "temperature": float,
        "enabled": int,
    }
    updates: list[str] = []
    params: list[Any] = []
    for field, caster in editable.items():
        if field in body and body[field] is not None:
            updates.append(f"{field} = ?")
            params.append(caster(body[field]))

    # 空字符串表示「不修改密钥」，避免前端回显时把密钥清空
    if body.get("api_key"):
        updates.append("api_key = ?")
        params.append(body["api_key"])

    if not updates:
        raise HTTPException(422, "没有可更新的字段")

    with db() as conn:
        if not conn.execute("SELECT 1 FROM llm_models WHERE id=?", (model_id,)).fetchone():
            raise HTTPException(404, "模型不存在")
        if body.get("is_default"):
            conn.execute("UPDATE llm_models SET is_default=0")
            updates.append("is_default = 1")
        updates.append("updated_at = ?")
        params.append(now())
        params.append(model_id)
        try:
            conn.execute(f"UPDATE llm_models SET {', '.join(updates)} WHERE id=?", params)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "同名模型已存在") from exc
        row = conn.execute(
            f"SELECT {MODEL_PUBLIC_FIELDS}, api_key FROM llm_models WHERE id=?", (model_id,)
        ).fetchone()
    return _model_row_to_dict(row, row["api_key"])


@app.delete("/api/v1/admin/models/{model_id}")
def delete_llm_model(model_id: int, _: sqlite3.Row = Depends(admin_user)):
    """删除 LLM 模型配置"""
    with db() as conn:
        row = conn.execute(
            "SELECT is_default FROM llm_models WHERE id=?", (model_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "模型不存在")
        conn.execute("DELETE FROM llm_models WHERE id=?", (model_id,))
        # 删掉默认模型后，自动把剩下的第一个提为默认，避免没有默认模型
        if row["is_default"]:
            fallback = conn.execute(
                "SELECT id FROM llm_models ORDER BY id LIMIT 1"
            ).fetchone()
            if fallback:
                conn.execute(
                    "UPDATE llm_models SET is_default=1, updated_at=? WHERE id=?",
                    (now(), fallback["id"]),
                )
    return {"message": "已删除"}


@app.patch("/api/v1/admin/models/{model_id}/default")
def set_default_model(model_id: int, _: sqlite3.Row = Depends(admin_user)):
    """设置默认模型"""
    with db() as conn:
        if not conn.execute("SELECT 1 FROM llm_models WHERE id=?", (model_id,)).fetchone():
            raise HTTPException(404, "模型不存在")
        conn.execute("UPDATE llm_models SET is_default=0")
        conn.execute(
            "UPDATE llm_models SET is_default=1, enabled=1, updated_at=? WHERE id=?",
            (now(), model_id),
        )
        row = conn.execute(
            f"SELECT {MODEL_PUBLIC_FIELDS}, api_key FROM llm_models WHERE id=?", (model_id,)
        ).fetchone()
    return _model_row_to_dict(row, row["api_key"])


@app.patch("/api/v1/admin/models/{model_id}/toggle")
def toggle_llm_model(model_id: int, _: sqlite3.Row = Depends(admin_user)):
    """启用/停用模型"""
    with db() as conn:
        row = conn.execute(
            "SELECT enabled, is_default FROM llm_models WHERE id=?", (model_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "模型不存在")
        if row["enabled"] and row["is_default"]:
            raise HTTPException(422, "默认模型不能停用，请先切换默认模型")
        conn.execute(
            "UPDATE llm_models SET enabled=?, updated_at=? WHERE id=?",
            (0 if row["enabled"] else 1, now(), model_id),
        )
        updated = conn.execute(
            f"SELECT {MODEL_PUBLIC_FIELDS}, api_key FROM llm_models WHERE id=?", (model_id,)
        ).fetchone()
    return _model_row_to_dict(updated, updated["api_key"])


@app.post("/api/v1/admin/models/{model_id}/test")
def test_llm_model(model_id: int, _: sqlite3.Row = Depends(admin_user)):
    """在线测试已保存的模型是否连通"""
    with db() as conn:
        row = conn.execute("SELECT * FROM llm_models WHERE id=?", (model_id,)).fetchone()
        if not row:
            raise HTTPException(404, "模型不存在")

    result = _probe_model(
        model_id=row["model_id"],
        api_base_url=row["api_base_url"],
        api_key=row["api_key"],
        path_style=row["path_style"],
        max_tokens=row["max_tokens"],
        temperature=row["temperature"],
    )

    with db() as conn:
        conn.execute(
            """UPDATE llm_models
               SET last_tested_at=?, last_test_ok=?, last_test_message=? WHERE id=?""",
            (now(), 1 if result["ok"] else 0, result["message"], model_id),
        )
    return result


@app.post("/api/v1/admin/models/test")
def test_llm_model_draft(body: dict, _: sqlite3.Row = Depends(admin_user)):
    """测试未保存的草稿配置（新建表单里的「测试连接」）"""
    model_id = (body.get("model_id") or "").strip()
    api_base_url = (body.get("api_base_url") or "").strip()
    if not model_id or not api_base_url:
        raise HTTPException(422, "模型 ID 与 API 地址不能为空")

    api_key = body.get("api_key") or ""
    # 编辑态未重填密钥时，回退到库里已存的密钥
    if not api_key and body.get("id"):
        with db() as conn:
            row = conn.execute(
                "SELECT api_key FROM llm_models WHERE id=?", (body["id"],)
            ).fetchone()
        if row:
            api_key = row["api_key"]

    return _probe_model(
        model_id=model_id,
        api_base_url=api_base_url,
        api_key=api_key,
        path_style=(body.get("path_style") or "openai").strip(),
        max_tokens=int(body.get("max_tokens") or 4096),
        temperature=float(body.get("temperature") or 0),
    )



# ========================================
# Content Publishing v2
# 内容管理 / 发布：媒体上传、Banner 生成、文章 CRUD
# ========================================

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
# Documents are a first-class content type: PDF is read inline in an embedded
# viewer, the rest are converted to sanitised HTML at upload time.
ALLOWED_DOC_TYPES = {
    "application/pdf": (".pdf", "pdf"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx", "docx"),
    "text/markdown": (".md", "markdown"),
    "text/x-markdown": (".md", "markdown"),
    "text/plain": (".txt", "text"),
}
# Browsers are inconsistent about MIME types for .md/.txt, so fall back on suffix.
DOC_SUFFIX_KINDS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
}
MAX_MEDIA_BYTES = 20 * 1024 * 1024


def _store_media(data: bytes, suffix: str, subdir: str) -> str:
    """Persist bytes under data/media/<subdir> and return public URL path."""
    folder = MEDIA_PATH / subdir
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(10)}{suffix}"
    (folder / name).write_bytes(data)
    return f"/media/{subdir}/{name}"


@app.post("/api/v1/admin/media/image", status_code=201)
async def admin_upload_image(file: UploadFile = File(...), _: sqlite3.Row = Depends(admin_user)):
    """Upload a banner / inline image."""
    suffix = ALLOWED_IMAGE_TYPES.get((file.content_type or "").lower())
    if not suffix:
        raise HTTPException(422, "仅支持 PNG / JPG / WebP / GIF / SVG 图片")
    data = await file.read()
    if not data:
        raise HTTPException(422, "文件为空")
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(413, "图片不能超过 20MB")
    url = _store_media(data, suffix, "images")
    return {"url": url, "filename": Path(file.filename or "image").name, "size": len(data)}


PDF_PREVIEW_PAGES = 10
PDF_PREVIEW_CHARS = 12000


def _pdf_preview_text(data: bytes, max_pages: int = PDF_PREVIEW_PAGES) -> str:
    """Extract plain text from the first pages of a PDF.

    Used only to feed title/subtitle/summary generation — the article body stays
    the original PDF, which the reader renders in an embedded viewer. Returns ''
    for scanned PDFs that carry no text layer.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                return ""
        chunks: list[str] = []
        for page in reader.pages[:max_pages]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
            if sum(len(c) for c in chunks) >= PDF_PREVIEW_CHARS:
                break
    except Exception:
        return ""

    text = "\n".join(chunks)
    # PDF extraction leaves hard line wraps mid-sentence; join CJK lines and
    # collapse the rest so the model sees continuous prose.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(?<=[一-鿿，。；：、])\n(?=[一-鿿])", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()[:PDF_PREVIEW_CHARS]


def _docx_to_html(data: bytes) -> str:
    """Convert a .docx to HTML. Images are dropped (mammoth would inline base64)."""
    try:
        import mammoth
    except ImportError:
        raise HTTPException(503, "服务器缺少 Word 解析依赖，请改用 PDF 或 Markdown")
    try:
        result = mammoth.convert_to_html(io.BytesIO(data))
    except Exception:
        raise HTTPException(422, "Word 文档解析失败，请确认是 .docx 格式")
    return sanitize_article_html(result.value or "")


def _markdown_to_html(text: str) -> str:
    try:
        import markdown as md_lib
    except ImportError:
        return _plain_text_to_html(text)
    html = md_lib.markdown(text, extensions=["extra", "sane_lists", "nl2br"])
    return sanitize_article_html(html)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(422, "无法识别文件编码，请另存为 UTF-8")


@app.post("/api/v1/admin/media/document", status_code=201)
async def admin_upload_document(file: UploadFile = File(...), _: sqlite3.Row = Depends(admin_user)):
    """Upload a document (PDF / Word / Markdown / txt) to publish as article body.

    PDF keeps its binary form and is read inline by the frontend viewer.
    The other formats are converted to sanitised HTML here so the reader page
    renders them as normal article content.
    """
    name = Path(file.filename or "document").name
    ext = Path(name).suffix.lower()
    mapped = ALLOWED_DOC_TYPES.get((file.content_type or "").lower())
    kind = mapped[1] if mapped else DOC_SUFFIX_KINDS.get(ext)
    if not kind:
        raise HTTPException(422, "仅支持 PDF / Word(.docx) / Markdown / txt 文档")

    data = await file.read()
    if not data:
        raise HTTPException(422, "文件为空")
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(413, "文档不能超过 20MB")

    suffix = {"pdf": ".pdf", "docx": ".docx", "markdown": ".md", "text": ".txt"}[kind]
    url = _store_media(data, suffix, "documents")

    html = ""
    preview_text = ""
    preview_note = ""
    if kind == "docx":
        html = _docx_to_html(data)
    elif kind == "markdown":
        html = _markdown_to_html(_decode_text(data))
    elif kind == "text":
        html = sanitize_article_html(_plain_text_to_html(_decode_text(data)))
    else:  # pdf — body stays binary; pull text only to drive title/summary generation
        preview_text = _pdf_preview_text(data)
        if not preview_text:
            preview_note = "未能从 PDF 中提取到文字（可能是扫描件），请手动填写标题与摘要"

    return {
        "url": url,
        "filename": name,
        "size": len(data),
        "doc_kind": kind,
        "html": html,
        "preview_text": preview_text,
        "preview_pages": PDF_PREVIEW_PAGES if kind == "pdf" else 0,
        "preview_note": preview_note,
    }


# ── Banner generation (Anthropic editorial style, SVG output) ──

ANTHROPIC_PALETTE = [
    ("clay", "#BD5D3A"),
    ("slate", "#6A7B8C"),
    ("olive", "#7C7F4E"),
    ("plum", "#7A5C7B"),
    ("sand", "#C4A47C"),
    ("teal", "#4F7A75"),
]
INK = "#141413"
IVORY = "#FAF9F5"


def _load_style_spec() -> str:
    try:
        return STYLE_SPEC_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


def _fallback_banner_svg(title: str, subtitle: str, accent_hex: str) -> str:
    """Deterministic hand-drawn-ish SVG used when the model is unavailable."""
    seed = int(hashlib.sha256(f"{title}|{subtitle}".encode()).hexdigest()[:8], 16)

    def jitter(base: float, spread: float, step: int) -> float:
        return round(base + ((seed >> (step * 3)) % (int(spread * 2) + 1)) - spread, 1)

    carrier = (
        f"M {jitter(150, 18, 1)} {jitter(120, 14, 2)} "
        f"C {jitter(360, 30, 3)} {jitter(70, 18, 4)}, {jitter(760, 30, 5)} {jitter(78, 16, 6)}, "
        f"{jitter(1010, 20, 7)} {jitter(126, 14, 8)} "
        f"C {jitter(1090, 22, 9)} {jitter(300, 24, 10)}, {jitter(1082, 20, 11)} {jitter(360, 22, 1)}, "
        f"{jitter(1004, 18, 2)} {jitter(486, 14, 3)} "
        f"C {jitter(740, 30, 4)} {jitter(536, 18, 5)}, {jitter(370, 30, 6)} {jitter(530, 18, 7)}, "
        f"{jitter(154, 20, 8)} {jitter(482, 14, 9)} "
        f"C {jitter(78, 20, 10)} {jitter(360, 22, 11)}, {jitter(82, 18, 1)} {jitter(238, 22, 2)} Z"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" width="1200" height="600" '
        'role="img" aria-label="article banner">'
        f'<rect width="1200" height="600" fill="{accent_hex}"/>'
        f'<path d="{carrier}" fill="{IVORY}"/>'
        f'<g fill="none" stroke="{INK}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round">'
        f'<circle cx="{jitter(470, 12, 4)}" cy="{jitter(300, 12, 5)}" r="{jitter(104, 8, 6)}"/>'
        f'<path d="M {jitter(600, 10, 7)} {jitter(300, 10, 8)} '
        f'C {jitter(690, 16, 9)} {jitter(214, 16, 10)}, {jitter(788, 16, 11)} {jitter(214, 14, 1)}, '
        f'{jitter(866, 12, 2)} {jitter(300, 10, 3)}"/>'
        f'<path d="M {jitter(600, 10, 4)} {jitter(300, 10, 5)} '
        f'C {jitter(690, 16, 6)} {jitter(388, 16, 7)}, {jitter(788, 16, 8)} {jitter(388, 14, 9)}, '
        f'{jitter(866, 12, 10)} {jitter(300, 10, 11)}"/>'
        f'<path d="M {jitter(470, 12, 2)} {jitter(196, 10, 3)} L {jitter(470, 12, 4)} {jitter(404, 10, 5)}"/>'
        "</g></svg>"
    )


def _llm_candidates() -> list[dict[str, Any]]:
    """Models to try, in order: default first, then the rest of the enabled ones.

    Falls back to the legacy settings/env config when 模型管理 has no usable row,
    so existing installations keep working.
    """
    candidates: list[dict[str, Any]] = []
    try:
        with db() as conn:
            rows = conn.execute(
                "SELECT name, model_id, api_base_url, api_key, path_style, temperature, max_tokens "
                "FROM llm_models WHERE enabled=1 ORDER BY is_default DESC, id ASC"
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        if not row["api_base_url"] or not row["model_id"]:
            continue
        candidates.append({
            "name": row["name"],
            "model": row["model_id"],
            "base_url": row["api_base_url"],
            "api_key": row["api_key"],
            "path_style": row["path_style"] or "openai",
            "temperature": row["temperature"],
            "max_tokens": row["max_tokens"] or 4096,
        })

    if not candidates:
        settings = get_llm_settings()
        if settings.get("base_url") and settings.get("model"):
            candidates.append({
                "name": settings["model"],
                "model": settings["model"],
                "base_url": settings["base_url"],
                "api_key": settings.get("api_key", ""),
                "path_style": settings.get("path_style", "model-in-path"),
                "temperature": settings.get("temperature", 0),
                "max_tokens": settings.get("max_tokens", 5000),
            })
    return candidates


def _chat_once(candidate: dict[str, Any], system_prompt: str, user_prompt: str,
               max_tokens: int, timeout: int = 120) -> str:
    """One completion call against a single model. Raises on transport/API errors."""
    url = _resolve_chat_url(candidate["base_url"], candidate["model"], candidate["path_style"])
    tokens = min(max_tokens, int(candidate.get("max_tokens") or max_tokens))
    headers = {"Content-Type": "application/json"}

    if candidate["path_style"] == "anthropic":
        payload = {
            "model": candidate["model"],
            "max_tokens": tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers["x-api-key"] = candidate.get("api_key", "")
        headers["anthropic-version"] = "2023-06-01"
    else:
        payload = {
            "model": candidate["model"],
            "max_tokens": tokens,
            "temperature": candidate.get("temperature", 0),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if candidate.get("api_key"):
            headers["Authorization"] = f"Bearer {candidate['api_key']}"

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read() or b"{}")

    if candidate["path_style"] == "anthropic":
        blocks = body.get("content") or []
        return ((blocks[0] or {}).get("text") or "") if blocks else ""
    choices = body.get("choices") or []
    return (((choices[0] or {}).get("message") or {}).get("content") or "") if choices else ""


def _llm_text_ex(system_prompt: str, user_prompt: str, max_tokens: int = 3000,
                 timeout: int = 120) -> tuple[str, str]:
    """Try each configured model until one answers. Returns (text, model_name)."""
    for candidate in _llm_candidates():
        try:
            text = (_chat_once(candidate, system_prompt, user_prompt, max_tokens, timeout) or "").strip()
        except Exception:
            continue  # unreachable / rejected model — fall through to the next one
        if text:
            return text, candidate["name"]
    return "", ""


def _llm_text(system_prompt: str, user_prompt: str, max_tokens: int = 3000) -> str:
    """Single-shot text completion. Returns '' when no configured model answers."""
    return _llm_text_ex(system_prompt, user_prompt, max_tokens)[0]


_SVG_ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline",
    "polygon", "text", "tspan", "defs", "title", "desc",
}


def _sanitize_svg(raw: str) -> str:
    """Keep only a safe drawing subset: no script, no external refs, no event handlers."""
    match = re.search(r"<svg[\s\S]*</svg>", raw, re.IGNORECASE)
    if not match:
        return ""
    soup = BeautifulSoup(match.group(), "html.parser")
    svg = soup.find("svg")
    if svg is None:
        return ""
    for node in svg.find_all(True):
        if node.name.lower() not in _SVG_ALLOWED_TAGS:
            node.decompose()
    for node in [svg, *svg.find_all(True)]:
        for attr in list(node.attrs):
            low = attr.lower()
            if low.startswith("on") or low in {"href", "xlink:href", "style", "filter"}:
                del node.attrs[attr]
        for attr, value in list(node.attrs.items()):
            if isinstance(value, str) and re.search(r"url\s*\(|javascript:", value, re.IGNORECASE):
                del node.attrs[attr]
    svg.attrs.setdefault("xmlns", "http://www.w3.org/2000/svg")
    svg.attrs["viewBox"] = svg.attrs.get("viewbox") or svg.attrs.get("viewBox") or "0 0 1200 600"
    svg.attrs.pop("viewbox", None)
    svg.attrs["width"] = "1200"
    svg.attrs["height"] = "600"
    return str(svg)


class BannerGenerateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subtitle: str = ""
    accent: str | None = None
    extra_prompt: str = ""


@app.post("/api/v1/admin/banner/generate", status_code=201)
def admin_generate_banner(body: BannerGenerateRequest, _: sqlite3.Row = Depends(admin_user)):
    """Generate an editorial banner from title/subtitle following anthropic-style.md."""
    accent_name, accent_hex = ANTHROPIC_PALETTE[
        int(hashlib.sha256(body.title.encode()).hexdigest()[:6], 16) % len(ANTHROPIC_PALETTE)
    ]
    if body.accent:
        for name, hex_value in ANTHROPIC_PALETTE:
            if body.accent.lower() in (name, hex_value.lower()):
                accent_name, accent_hex = name, hex_value
                break

    spec = _load_style_spec()
    system_prompt = (
        "你是遵循 Anthropic 编辑插画视觉语言的插画师。你只输出一个完整的 SVG 文档，"
        "不要输出解释、不要 Markdown 代码块。禁止使用 script、image、外部引用、滤镜、渐变和阴影。"
    )

    # Two passes: first turn the title/subtitle into a concrete visual metaphor,
    # then draw it. A single pass tends to produce generic circles-and-lines.
    concept = ""
    if body.title:
        concept = _llm_text(
            "你是编辑插画的创意指导。你只输出一句中文描述，不要解释、不要列表、不超过 60 字。",
            f"""这是一篇文章的标题和副标题：
标题：{body.title}
副标题：{body.subtitle or "（无）"}

请为它构思一个用于封面插画的核心视觉隐喻。要求：
1. 用一个具体的、可以用几笔粗线条画出来的实物或几何构造来表达文章主题，
   例如：层层堆叠的方块、被打通的隧道、分叉的路径、装配中的齿轮、正在拼合的碎片。
2. 说明这个主体的形状和构图位置，不要写颜色，不要出现文字或字母。
3. 只输出这一句描述。""",
            max_tokens=300,
        ).strip()

    user_prompt = f"""参考以下视觉规范：

{spec}

请为这篇文章生成 banner 配图（SVG，viewBox="0 0 1200 600"）：
标题：{body.title}
副标题：{body.subtitle or "（无）"}
核心视觉隐喻：{concept or "（请自行根据标题提炼一个具体的视觉隐喻）"}
补充要求：{body.extra_prompt or "（无）"}

硬性约束：
1. 第一个元素是铺满整个画布的不透明背景矩形，颜色为 {accent_hex}（{accent_name}），不允许透明或白色外框。
2. 背景之上放一个不规则的象牙色载体形状，填充 {IVORY}，用 path 的曲线绘制，边缘要不规则。
3. 载体形状之上用 {INK} 的粗描边（stroke-width 10-18，stroke-linecap="round"）画出上面的核心视觉隐喻，
   只用一个主体，形状要能在缩略图尺寸下辨认，留出充足空白。
4. 扁平二维，无渐变、无阴影、无写实细节。不要写任何文字、字母或数字。
5. 只允许 svg/g/path/rect/circle/ellipse/line/polyline/polygon 这些标签。

只输出 SVG。"""

    raw, model_name = _llm_text_ex(system_prompt, user_prompt, max_tokens=4000)
    svg = _sanitize_svg(raw)
    source = "llm"
    if not svg or len(svg) < 200:
        svg = _fallback_banner_svg(body.title, body.subtitle, accent_hex)
        source = "fallback"
        model_name = ""

    url = _store_media(svg.encode("utf-8"), ".svg", "banners")
    return {
        "url": url,
        "accent": accent_hex,
        "accent_name": accent_name,
        "source": source,
        "model": model_name,
        "concept": concept,
    }


# ── Content optimisation (typography pass) ──

class ContentOptimizeRequest(BaseModel):
    content: str = Field(min_length=1)
    content_format: str = "richtext"  # richtext | html | markdown


_HTML_ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "em", "i",
    "u", "s", "del", "ins", "blockquote", "pre", "code", "ul", "ol", "li", "a",
    "img", "figure", "figcaption", "table", "thead", "tbody", "tfoot", "tr", "th",
    "td", "span", "div", "small", "sup", "sub",
}
# Extra tags kept only for extracted web pages (content_format == 'link'), where the
# point is to reproduce the original article including its media.
_MEDIA_ALLOWED_TAGS = {"video", "audio", "source", "track", "iframe", "picture"}
_MEDIA_ALLOWED_ATTRS = {
    "video": {"src", "poster", "controls", "width", "height", "preload", "loop", "muted", "playsinline"},
    "audio": {"src", "controls", "preload", "loop", "muted"},
    "source": {"src", "srcset", "type", "media", "sizes"},
    "track": {"src", "kind", "srclang", "label", "default"},
    "iframe": {"src", "width", "height", "title", "allow", "allowfullscreen", "loading", "frameborder"},
    "picture": set(),
    # Extracted pages often use responsive images and lazy-loading placeholders.
    "img": {"src", "srcset", "sizes", "alt", "title", "width", "height", "loading"},
}
_HTML_ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "th": {"colspan", "rowspan", "scope"},
    "td": {"colspan", "rowspan"},
    "code": {"class"},
    "pre": {"class"},
}

# 行内样式只放行「纯视觉」的安全 CSS 属性：颜色、字体、间距、边框、圆角等。
# url()/expression 之类会被 _safe_inline_style 拒绝，杜绝通过样式注入脚本或外链。
_SAFE_INLINE_PROPS = {
    "color", "background", "background-color", "background-image", "opacity",
    "font", "font-family", "font-size", "font-weight", "font-style", "font-variant",
    "line-height", "letter-spacing", "text-align", "text-decoration", "text-transform",
    "word-spacing", "white-space",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-color", "border-style", "border-width", "border-radius",
    "box-shadow", "display", "width", "max-width", "height", "max-height",
    "float", "clear", "vertical-align", "overflow",
}


def _safe_inline_style(value: str) -> str:
    """Keep only visual, non-executable inline CSS declarations.

    Drops url()/data: references and anything matching the JS-ish patterns, and
    keeps only whitelisted properties, so AI-polished colour and spacing survive
    publishing without opening an injection vector.
    """
    if not value:
        return ""
    cleaned = re.sub(r"url\s*\([^)]*\)", "", value, flags=re.IGNORECASE)
    if _CSS_FORBIDDEN.search(cleaned):
        return ""
    kept: list[str] = []
    for decl in cleaned.split(";"):
        decl = decl.strip()
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = (prop or "").strip().lower()
        if prop not in _SAFE_INLINE_PROPS:
            continue
        val = val.strip()
        if not val or _CSS_FORBIDDEN.search(val):
            continue
        kept.append(f"{prop}: {val}")
    return "; ".join(kept)


# Video embeds from trusted platforms are kept as iframes; anything else is dropped.
_EMBED_HOST_ALLOWLIST = (
    "youtube.com", "youtube-nocookie.com", "youtu.be", "player.vimeo.com", "vimeo.com",
    "player.bilibili.com", "bilibili.com", "v.qq.com", "player.youku.com",
)


def _is_allowed_embed(src: str) -> bool:
    """True when an iframe/video URL points at a known video host over https."""
    try:
        parsed = urllib.parse.urlparse(src)
    except Exception:
        return False
    if parsed.scheme not in {"https", "http"}:
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return any(host == h or host.endswith("." + h) for h in _EMBED_HOST_ALLOWLIST)


def sanitize_article_html(raw: str, allow_media: bool = False) -> str:
    """Strip scripts, event handlers and unsafe URLs from author-supplied HTML.

    With allow_media=True (used for extracted web pages) native <video>/<audio>
    elements and iframe embeds from known video hosts survive, so a reposted
    article keeps the media the original had. Everything else is still removed.
    """
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    kill = ["script", "style", "object", "embed", "form", "link", "meta"]
    if allow_media:
        # Keep whitelisted video embeds, drop the rest of the iframes.
        for node in soup.find_all("iframe"):
            if not _is_allowed_embed(str(node.attrs.get("src") or "")):
                node.decompose()
    else:
        kill.append("iframe")
    for node in soup.find_all(kill):
        node.decompose()
    allowed_tags = _HTML_ALLOWED_TAGS | _MEDIA_ALLOWED_TAGS if allow_media else _HTML_ALLOWED_TAGS
    attr_map = {**_HTML_ALLOWED_ATTRS, **_MEDIA_ALLOWED_ATTRS} if allow_media else _HTML_ALLOWED_ATTRS

    for node in soup.find_all(True):
        name = node.name.lower()
        if name not in allowed_tags:
            node.unwrap()
            continue
        allowed = attr_map.get(name, set())
        # 行内样式在删除循环前先取出：它不在白名单属性里，但要单独做安全过滤后保留，
        # 这样 AI 润色出的配色/间距能存活入库并被前端渲染。
        style_val = node.attrs.get("style")
        for attr in list(node.attrs):
            if attr.lower() not in allowed:
                del node.attrs[attr]
        if isinstance(style_val, str):
            safe_style = _safe_inline_style(style_val)
            if safe_style:
                node.attrs["style"] = safe_style
            else:
                node.attrs.pop("style", None)
        for attr in ("href", "src", "poster"):
            value = node.attrs.get(attr)
            if isinstance(value, str) and re.match(r"\s*(javascript|data|vbscript):", value, re.IGNORECASE):
                if not value.lower().startswith("data:image/"):
                    del node.attrs[attr]
        if name == "a" and node.attrs.get("target") == "_blank":
            node.attrs["rel"] = "noopener noreferrer"
        if name == "iframe":
            # Defence in depth: an embed that lost its src is just an empty box.
            if not _is_allowed_embed(str(node.attrs.get("src") or "")):
                node.decompose()
                continue
            node.attrs["loading"] = "lazy"
            node.attrs["allowfullscreen"] = ""
    return str(soup).strip()


_CSS_FORBIDDEN = re.compile(
    r"(javascript\s*:|vbscript\s*:|expression\s*\(|behavior\s*:|-moz-binding)", re.IGNORECASE
)


def _sanitize_css(css: str) -> str:
    """Drop the handful of CSS constructs that can execute script in old engines.

    Everything else is kept verbatim: authors publishing a full HTML page rely on
    their own custom properties, media queries and pseudo-elements.
    """
    cleaned = re.sub(r"</\s*style", "", css or "", flags=re.IGNORECASE)
    return "" if _CSS_FORBIDDEN.search(cleaned) else cleaned.strip()


def sanitize_full_page_html(raw: str) -> str:
    """Sanitise an author-supplied standalone HTML page, keeping its styling.

    Unlike `sanitize_article_html` this preserves <style> blocks plus class/style/id
    attributes, because the whole point of the `html` content type is to publish a
    self-contained designed page. Script execution is removed instead: script /
    iframe / object / embed / form tags, on* handlers and script-ish URLs all go.
    The result is rendered inside a sandboxed srcdoc iframe on the reader page, so
    it cannot restyle or read the surrounding app.
    """
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")

    for node in soup.find_all(["script", "iframe", "object", "embed", "form", "base"]):
        node.decompose()
    # <link rel=stylesheet> would pull in remote CSS we cannot inspect; font imports
    # inside <style> are kept, so authors don't lose their typography.
    for node in soup.find_all("link"):
        node.decompose()
    for node in soup.find_all("meta"):
        if (node.attrs.get("http-equiv") or "").lower() == "refresh":
            node.decompose()

    for node in soup.find_all("style"):
        css = _sanitize_css(node.string or node.get_text() or "")
        if css:
            node.string = css
        else:
            node.decompose()

    for node in soup.find_all(True):
        for attr in list(node.attrs):
            lowered = attr.lower()
            if lowered.startswith("on") or lowered in {"srcdoc", "formaction", "ping"}:
                del node.attrs[attr]
                continue
            if lowered == "style":
                safe = _sanitize_css(str(node.attrs[attr]))
                if safe:
                    node.attrs[attr] = safe
                else:
                    del node.attrs[attr]
        for attr in ("href", "src", "action", "data", "poster"):
            value = node.attrs.get(attr)
            if isinstance(value, str) and re.match(r"\s*(javascript|vbscript):", value, re.IGNORECASE):
                del node.attrs[attr]
        if node.name == "a" and node.attrs.get("href"):
            # The page runs in a sandboxed frame; open links in the real top window.
            node.attrs["target"] = "_blank"
            node.attrs["rel"] = "noopener noreferrer"

    return str(soup).strip()


def _plain_text_to_html(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    out = []
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if all(re.match(r"^[-*+]\s+", l) for l in lines):
            items = "".join(f"<li>{_escape_html(re.sub(r'^[-*+]\s+', '', l))}</li>" for l in lines)
            out.append(f"<ul>{items}</ul>")
        elif all(re.match(r"^\d+[.)]\s+", l) for l in lines):
            items = "".join(f"<li>{_escape_html(re.sub(r'^\d+[.)]\s+', '', l))}</li>" for l in lines)
            out.append(f"<ol>{items}</ol>")
        elif len(lines) == 1 and re.match(r"^#{1,4}\s+", lines[0]):
            level = min(len(re.match(r"^#+", lines[0]).group()) + 1, 6)
            out.append(f"<h{level}>{_escape_html(re.sub(r'^#+\s+', '', lines[0]))}</h{level}>")
        else:
            out.append("<p>" + "<br>".join(_escape_html(l) for l in lines) + "</p>")
    return "".join(out)


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


@app.post("/api/v1/admin/content/optimize")
def admin_optimize_content(body: ContentOptimizeRequest, _: sqlite3.Row = Depends(admin_user)):
    """Normalise author content into clean semantic HTML, with an LLM typography pass."""
    source = body.content.strip()
    looks_like_html = bool(re.search(r"<(p|div|h[1-6]|ul|ol|table|blockquote|pre|img|br)\b", source, re.IGNORECASE))

    base_html = sanitize_article_html(source) if looks_like_html else _plain_text_to_html(source)

    polished, model_name = _llm_text_ex(
        "你是中文技术博客的资深排版设计师。你只输出 HTML 片段，不要 Markdown 代码块，不要任何解释文字。",
        f"""请把下面的文章正文润色成一篇排版精美、有色彩层次感的技术博客 HTML 片段，让它直接阅读就有设计感。

先做的排版（始终要做）：
1. 划分层次：给内容分段，为每个主题块补上恰当的 <h2>/<h3> 小标题（小标题必须来自原文内容，不要编造）。
2. 拆分长段：一段只讲一件事，过长段落按语义切开。
3. 结构化表达：并列要点改写成 <ul>/<ol>；成组对比数据改写成 <table>；命令、配置、代码放进 <pre><code>；
   关键结论用 <strong> 标出，但不要滥用。
4. 中文与英文/数字之间补一个空格，统一中文标点，清理多余空行与重复空格。

再用行内样式（style 属性）做出精致的视觉层次——配色统一、克制、有高级感：
1. 小标题：给一个稳重的品牌色（如深蓝/墨绿/酒红），可加下边框或左侧竖条装饰，加大字号与间距；
2. 段落正文：舒适的 line-height（1.7 左右）、合适字号、柔和的中性文字色；
3. 关键结论/重点句：用 <strong> 加与品牌色呼应的文字色，或极浅的背景高亮（如 #f0f7ff）；
4. 代码块 <pre><code>：浅灰背景、圆角、细边框、等宽字体，代码文字深色；
5. 引用 <blockquote>：左侧强调色边框 + 极浅背景色；
6. 列表：适当行距；表格：表头用品牌色背景白字，单元格加细边框和内边距。

技术约束（务必遵守）：
1. 样式只允许写在元素的行内 style 属性里，值一律是静态的纯色、字号、间距、边框等基础 CSS；
   不要 <style> 标签、不要 class、不要 id、不要外链资源、不要 script、不要 background-image/url()。
2. 不要 style 之外的任何 class/id；不要 <html>/<head>/<body> 外壳，只要 <body> 内的片段。
3. 不要增删或改写事实、数字、结论，不要添加原文没有的观点，不要写引言/总结/编者按。

正文：
{base_html}""",
        max_tokens=8000,
        timeout=300,
    )

    optimized = sanitize_article_html(polished) if polished else ""
    # Guard against the model truncating or summarising instead of reformatting.
    if not optimized or len(re.sub(r"<[^>]+>", "", optimized)) < len(re.sub(r"<[^>]+>", "", base_html)) * 0.6:
        optimized = base_html
        optimized_by = "local"
        model_name = ""
    else:
        optimized_by = "llm"

    plain = re.sub(r"<[^>]+>", " ", optimized)
    plain = re.sub(r"\s+", " ", plain).strip()
    return {
        "html": optimized,
        "optimized_by": optimized_by,
        "model": model_name,
        "word_count": len(plain),
        "excerpt": plain[:200],
    }


# ── Metadata extraction (title / subtitle / excerpt from the body) ──

TITLE_MIN_CHARS = 10
SUBTITLE_MIN_CHARS = 50
EXCERPT_MIN_CHARS = 80


class MetadataExtractRequest(BaseModel):
    content: str = ""
    content_format: str = "richtext"
    doc_name: str = ""
    is_plain_text: bool = False  # PDF 抽取出的纯文本，不含 HTML 标签
    doc_url: str = ""  # /media/... 的 PDF 地址；给定时服务端重新解析前若干页


def _read_media_pdf(doc_url: str) -> bytes:
    """Read a previously uploaded PDF from the media directory.

    Only accepts /media/documents/<name> and resolves inside MEDIA_PATH to keep
    this from becoming a path-traversal read primitive.
    """
    if not doc_url.startswith("/media/documents/"):
        raise HTTPException(422, "文档地址无效")
    name = Path(doc_url[len("/media/documents/"):]).name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(422, "只能重新解析 PDF 文档")
    target = (MEDIA_PATH / "documents" / name).resolve()
    if not str(target).startswith(str((MEDIA_PATH / "documents").resolve()) + os.sep):
        raise HTTPException(422, "文档地址无效")
    if not target.is_file():
        raise HTTPException(404, "文档文件不存在")
    return target.read_bytes()


def _cjk_len(value: str) -> int:
    """Approximate the '字数' a Chinese author counts: CJK chars plus latin words."""
    text = (value or "").strip()
    cjk = len(re.findall(r"[一-鿿]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9]+", text))
    return cjk + latin_words


def _strip_tags(html: str) -> str:
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()


def _first_sentences(text: str, min_chars: int, max_chars: int) -> str:
    """Greedily accumulate sentences until min_chars, capped at max_chars."""
    parts = re.split(r"(?<=[。！？；.!?;])\s*", text)
    out = ""
    for part in parts:
        if not part.strip():
            continue
        if out and _cjk_len(out) >= min_chars:
            break
        candidate = (out + part).strip()
        if len(candidate) > max_chars:
            if out:
                break
            return candidate[:max_chars].rstrip()
        out = candidate
    return out or text[:max_chars].strip()


class UrlExtractRequest(BaseModel):
    url: str = Field(min_length=1)


def _detect_language(text: str) -> str:
    """Detect if text is primarily English or Chinese. Returns 'en' or 'zh'."""
    try:
        from langdetect import detect
        sample = text[:2000]  # Use first 2000 chars for detection
        lang = detect(sample)
        return 'en' if lang == 'en' else 'zh'
    except Exception:
        # Fallback: count English vs CJK characters
        cjk = len(re.findall(r'[一-鿿]', text))
        eng = len(re.findall(r'[a-zA-Z]+', text))
        return 'en' if eng > cjk * 2 else 'zh'


# Media elements are swapped for opaque tokens before translation, then restored.
# Without this the model rewrites src attributes, "translates" filenames, or quietly
# drops <img>/<iframe> tags it considers decoration.
_MEDIA_TOKEN = "@@MEDIA{}@@"
_MEDIA_TOKEN_RE = re.compile(r"@@MEDIA(\d+)@@")


def _shield_media(html: str) -> tuple[str, list[str]]:
    """Replace media tags with placeholder tokens. Returns (html, originals)."""
    soup = BeautifulSoup(html, "html.parser")
    originals: list[str] = []
    for node in soup.find_all(["img", "video", "audio", "iframe", "picture", "figure"]):
        # figure wraps img+caption: keep the caption translatable, shield only the media
        if node.name == "figure":
            continue
        originals.append(str(node))
        node.replace_with(soup.new_string(_MEDIA_TOKEN.format(len(originals) - 1)))
    return str(soup), originals


def _restore_media(html: str, originals: list[str]) -> str:
    """Put the shielded media tags back, appending any the model dropped."""
    seen: set[int] = set()

    def sub(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        if idx >= len(originals):
            return ""
        seen.add(idx)
        return originals[idx]

    out = _MEDIA_TOKEN_RE.sub(sub, html)
    # A dropped token would silently lose an image, so re-attach what is missing.
    missing = [originals[i] for i in range(len(originals)) if i not in seen]
    if missing:
        out += "".join(missing)
    return out


def _split_html_blocks(html: str, max_chars: int) -> list[str]:
    """Split HTML into chunks on top-level block boundaries, each under max_chars."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = [str(child) for child in soup.children if str(child).strip()]
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if current and len(current) + len(block) > max_chars:
            chunks.append(current)
            current = block
        else:
            current += block
    if current:
        chunks.append(current)
    return chunks or [html]


_TRANSLATE_SYSTEM = """你是专业的英译中翻译。你会收到 HTML 格式的英文文章正文，请把它翻译成中文。

严格要求：
1. 只翻译标签之间的可见文字，HTML 标签、属性、层级结构一律保持原样。
2. 形如 @@MEDIA3@@ 的占位符是图片或视频，必须原封不动保留在原来的位置，不要翻译、不要删除、不要改写、不要调整顺序。
3. 忠实翻译，不做提炼、概括、扩写或润色，不增删段落，不合并或拆分段落，保持原文的信息量和严谨性。
4. <pre> 和 <code> 里的代码、命令、标识符保持英文原样。
5. 专有名词、产品名、公司名、论文名保留英文；技术术语用中文技术社区的通行译法，首次出现可用「中文（English）」的形式。
6. 只输出翻译后的 HTML 片段，不要 Markdown 代码块，不要任何解释。"""

# Chunk size is a compromise: large enough to keep paragraph context for the
# translator, small enough that the reply fits in a single completion.
_TRANSLATE_CHUNK_CHARS = 6000


def _translate_html_to_chinese(html: str) -> tuple[str, str]:
    """Translate English article HTML to Chinese, preserving structure and media.

    Media tags are shielded behind placeholders so the model cannot rewrite or drop
    them, and long articles are translated chunk by chunk so nothing is truncated to
    fit a completion limit. Returns (translated_html, model_name); ('', '') when no
    configured model answers, so the caller can fall back to the original text.
    """
    if not html.strip():
        return "", ""

    shielded, media = _shield_media(html)
    chunks = _split_html_blocks(shielded, _TRANSLATE_CHUNK_CHARS)

    out_parts: list[str] = []
    model_used = ""
    for index, chunk in enumerate(chunks):
        hint = f"（第 {index + 1}/{len(chunks)} 段，直接续译，不要写任何过渡说明）" if len(chunks) > 1 else ""
        translated, model_name = _llm_text_ex(
            _TRANSLATE_SYSTEM,
            f"请把下面的英文 HTML 翻译成中文{hint}：\n\n{chunk}",
            max_tokens=8000,
            timeout=300,
        )
        if not translated:
            # One failed chunk should not lose the article: keep the English source
            # for that part so the editor can fix it by hand.
            out_parts.append(chunk)
            continue
        translated = re.sub(r"^```(?:html)?\s*", "", translated.strip(), flags=re.IGNORECASE)
        translated = re.sub(r"\s*```$", "", translated.strip())
        out_parts.append(translated.strip())
        model_used = model_used or model_name

    if not model_used:
        return "", ""
    return _restore_media("".join(out_parts), media), model_used


_LAZY_MEDIA_ATTRS = (
    "data-src", "data-original", "data-lazy-src", "data-actualsrc", "data-url",
    "data-original-src", "data-hi-res-src", "data-lazy", "data-original-url",
    "data-source", "data-echo", "data-thumb", "data-img",
)
_LAZY_SRCSET_ATTRS = ("data-srcset", "data-lazy-srcset", "data-original-srcset", "data-src-set")


def _to_int(value: Any) -> int | None:
    try:
        return int(float(str(value or "").strip().replace("px", "")))
    except (ValueError, TypeError):
        return None


def _resolve_lazy_media(node: Any, base_url: str) -> None:
    """Promote lazy-loading placeholder attributes into a real src/srcset, resolved
    against the page URL. Without this, JS-rendered pages lose most of their images
    because the browser never runs their loader script."""
    if node.name == "img":
        src = (node.attrs.get("src") or "").strip()
        if not src:
            for attr in _LAZY_MEDIA_ATTRS:
                if node.attrs.get(attr, "").strip():
                    node.attrs["src"] = node.attrs[attr]
                    break
        srcset = node.attrs.get("srcset")
        if not (isinstance(srcset, str) and srcset.strip()):
            for attr in _LAZY_SRCSET_ATTRS:
                if node.attrs.get(attr, "").strip():
                    node.attrs["srcset"] = node.attrs[attr]
                    break
    elif node.name in ("video", "audio", "iframe", "source"):
        src = (node.attrs.get("src") or "").strip()
        if not src:
            for attr in _LAZY_MEDIA_ATTRS:
                if node.attrs.get(attr, "").strip():
                    node.attrs["src"] = node.attrs[attr]
                    break
        if node.name == "source":
            srcset = node.attrs.get("srcset")
            if not (isinstance(srcset, str) and srcset.strip()):
                for attr in _LAZY_SRCSET_ATTRS:
                    if node.attrs.get(attr, "").strip():
                        node.attrs["srcset"] = node.attrs[attr]
                        break
    if node.name == "video":
        poster = (node.attrs.get("poster") or "").strip()
        if not poster:
            for attr in ("data-poster", "data-poster-url", "data-thumb"):
                if node.attrs.get(attr, "").strip():
                    node.attrs["poster"] = node.attrs[attr]
                    break


def _reader_extract_html(raw_html: str, base_url: str) -> str:
    """Readable-mode HTML extraction that reliably keeps images and videos.

    Trafilatura is a great text extractor but routinely drops <img>/<video> from its
    output even with include_images=True, so a reposted article silently loses its
    figures. This pass parses the page with BeautifulSoup, keeps the main content
    container, resolves lazy-loaded media into real absolute URLs, and returns an HTML
    fragment that keeps figures and embeds roughly in their original position.

    The result is later scrubbed by sanitize_article_html(allow_media=True), so all
    we do here is pick a body and normalise media — no script or event handlers survive.
    """
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "lxml")
    except Exception:
        soup = BeautifulSoup(raw_html, "html.parser")

    # Strip site chrome and anything that cannot carry article content.
    for node in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "link", "meta"]):
        node.decompose()

    main = soup.find("main") or soup.find("article") or soup.find(role="main") or soup.body or soup
    for node in main.select(
        ".sidebar, .comments, #comments, .comment, .advertisement, .ads, .ad, .nav, .menu, "
        ".footer, .header, .share, .social, .related, .recommend, .recommended, .taboola, "
        ".newsletter, .subscribe, .breadcrumb, .social-share, .byline, .author-box, .promo"
    ):
        node.decompose()
    for node in main.find_all(["button", "input", "select", "textarea", "form"]):
        node.decompose()

    # Promote lazy-loaded media before we decide what to keep.
    for node in main.find_all(["img", "video", "audio", "iframe", "source"]):
        _resolve_lazy_media(node, base_url)

    # Edge: images can live in <picture> <source> or a plain <img>; keep the real ones.
    # Drop tiny icons, transparent pixels and tracking beacons that are not content.
    for img in list(main.find_all("img")):
        src = (img.get("src") or "").strip()
        low = src.lower()
        if not src:
            img.decompose()
            continue
        if any(t in low for t in ("1x1", "pixel.gif", "spacer", "transparent.gif", "blank.gif", "data:image/gif;base64,r0lg")):
            img.decompose()
            continue
        w, h = _to_int(img.get("width")), _to_int(img.get("height"))
        if (w and w < 30 and h and h < 30):
            img.decompose()

    return str(main)


def _choose_extraction(traf_html: str, reader_html: str) -> str:
    """Decide which extraction to keep so we don't trade clean structure for media.

    Prefer trafilatura when its output is acceptable and kept the page's media; fall
    back to the BeautifulSoup reader (which preserves figures) when trafilatura lost
    media the page clearly had, or when trafilatura produced nothing usable.
    """
    traf_ok = _is_good_extracted_content(_strip_tags(traf_html))
    reader_ok = _is_good_extracted_content(_strip_tags(reader_html))
    if not traf_ok:
        return reader_html if reader_ok else traf_html or reader_html
    if not reader_ok:
        return traf_html
    traf_media = _count_media(traf_html)
    reader_media = _count_media(reader_html)
    if traf_media["images"] > 0 or reader_media["images"] == 0:
        return traf_html
    # The page had figures that trafilatura dropped — keep the reader's version.
    if reader_media["images"] >= traf_media["images"]:
        return reader_html
    return traf_html


def _absolutize_media(html: str, base_url: str) -> str:
    """Rewrite relative img/video/iframe URLs against the source page.

    Extracted pages routinely use "/img/a.png" or "//cdn/a.png"; left as-is those
    resolve against our own host and render as broken images. Also promotes the
    common lazy-loading attributes to a real src.
    """
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(["img", "video", "audio", "source", "iframe"]):
        # Lazy-loaded images keep the real URL in a data-* attribute.
        if node.name == "img" and not (node.attrs.get("src") or "").strip():
            for alt_attr in ("data-src", "data-original", "data-lazy-src", "data-actualsrc"):
                if node.attrs.get(alt_attr):
                    node.attrs["src"] = node.attrs[alt_attr]
                    break
        for attr in ("src", "poster"):
            value = node.attrs.get(attr)
            if isinstance(value, str) and value.strip() and not value.startswith("data:"):
                node.attrs[attr] = urllib.parse.urljoin(base_url, value.strip())
        # srcset is a comma separated list of "url [descriptor]" pairs.
        srcset = node.attrs.get("srcset")
        if isinstance(srcset, str) and srcset.strip():
            parts = []
            for item in srcset.split(","):
                item = item.strip()
                if not item:
                    continue
                bits = item.split(None, 1)
                resolved = urllib.parse.urljoin(base_url, bits[0])
                parts.append(resolved + (" " + bits[1] if len(bits) > 1 else ""))
            node.attrs["srcset"] = ", ".join(parts)
    for node in soup.find_all("a"):
        href = node.attrs.get("href")
        if isinstance(href, str) and href.strip() and not href.startswith(("#", "mailto:", "data:")):
            node.attrs["href"] = urllib.parse.urljoin(base_url, href.strip())
            node.attrs["target"] = "_blank"
            node.attrs["rel"] = "noopener noreferrer"
    return str(soup)


def _count_media(html: str) -> dict[str, int]:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "images": len(soup.find_all("img")),
        "videos": len(soup.find_all(["video", "iframe"])),
    }


@app.post("/api/v1/admin/content/extract-url")
def admin_extract_url(body: UrlExtractRequest, _: sqlite3.Row = Depends(admin_user)):
    """Extract the main content of a web page for republishing, translating if needed.

    The goal is a faithful reproduction, not a summary: trafilatura pulls the article
    body, relative media URLs are resolved against the source, images and whitelisted
    video embeds are preserved, and English text is translated verbatim into Chinese.
    """
    url = body.url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(422, "请提供有效的 HTTP/HTTPS 网址")

    host = (urlparse(url).hostname or "").lower()
    # Fetching arbitrary operator-supplied URLs is a server-side request; block the
    # obvious loopback/metadata targets so this cannot be used to probe the host.
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254", "metadata.google.internal"}:
        raise HTTPException(422, "不支持抓取本机或内网地址")

    try:
        import trafilatura
        from trafilatura.settings import use_config

        config = use_config()
        config.set("DEFAULT", "EXTRACT_IMAGES", "yes")
        config.set("DEFAULT", "EXTRACT_VIDEOS", "yes")

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise HTTPException(422, "无法访问该网址，请检查链接是否有效或网络是否连通")

        # Trafilatura frequently drops <img>/<video> even with include_images=True and
        # can raise on unusual DOMs, so treat its output as best-effort, never fatal.
        extracted = ""
        try:
            candidate = trafilatura.extract(
                downloaded,
                output_format="html",
                include_images=True,
                include_links=True,
                include_tables=True,
                include_formatting=True,
                config=config,
                favor_recall=True,
            )
            if candidate and _is_good_extracted_content(_strip_tags(candidate)):
                extracted = candidate
        except HTTPException:
            raise
        except Exception:
            extracted = ""
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, f"提取内容时出错：{exc}")

    # Run a secondary reader pass that keeps figures and embeds, then pick whichever
    # preserved the page's content best (reader wins when trafilatura lost the media).
    try:
        reader_html = _reader_extract_html(downloaded, url)
        picked = _choose_extraction(extracted, reader_html)
    except Exception:
        picked = extracted
    if not _is_good_extracted_content(_strip_tags(picked)):
        picked = extracted
    if not _is_good_extracted_content(_strip_tags(picked)):
        raise HTTPException(422, "未能从该网页提取到有效内容，可能是该页面结构不支持自动提取或需登录")

    # Resolve media/link URLs before sanitising, so nothing points at our own host.
    content_html = sanitize_article_html(_absolutize_media(picked, url), allow_media=True)
    media = _count_media(content_html)

    plain_text = _strip_tags(content_html)
    detected_lang = _detect_language(plain_text)

    translated = False
    translation_model = ""
    warnings: list[str] = []
    if detected_lang == "en":
        translated_html, translation_model = _translate_html_to_chinese(content_html)
        if translated_html:
            content_html = sanitize_article_html(translated_html, allow_media=True)
            translated = True
            after = _count_media(content_html)
            if after["images"] < media["images"] or after["videos"] < media["videos"]:
                warnings.append("翻译过程中有部分图片或视频未能保留，请在预览中确认")
            media = after
            plain_text = _strip_tags(content_html)
        else:
            warnings.append("未连通配置的大模型，正文保持英文原文，请手动处理或稍后重试")

    return {
        "content_html": content_html,
        "source_url": url,
        "detected_language": detected_lang,
        "translated": translated,
        "translation_model": translation_model,
        "word_count": _cjk_len(plain_text),
        "char_count": len(plain_text),
        "image_count": media["images"],
        "video_count": media["videos"],
        "warnings": warnings,
    }


# ========================================
# Skill-based URL extraction (agent skill execution)
# 网页链接提取不再走服务端抓取/翻译代码，而是把 URL 交给
# url-to-article Agent Skill 执行，产出一篇幅 HTML 正文、
# 一页纸 HTML 解读，以及 1~2 张候选 banner 图。
# ========================================

# 任务表：job_id -> job dict（运行中后台线程写回，GET 轮询读取）
_SKILL_JOBS: dict[str, dict] = {}
_SKILL_JOBS_LOCK = threading.Lock()


def _find_skill_python() -> str:
    """找一个能跑提取技能（含 playwright / PIL）的 Python 解释器。

    服务器 venv 未装 playwright，技能实际是用系统 Python 跑的，
    所以依次探测候选解释器，选第一个能 import playwright/PIL 的。
    """
    candidates = [
        sys.executable,
        "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        shutil.which("python3") or "python3",
    ]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            probe = subprocess.run(
                [cand, "-c", "import playwright, PIL, requests"],
                capture_output=True,
                timeout=20,
            )
            if probe.returncode == 0:
                return cand
        except Exception:
            continue
    return candidates[0] or "python3"


def _banner_task_id(name: str) -> str:
    """从 banner 文件名提取所属任务 id：banner_article_<id>.<ext> / banner_summary_<id>.<ext>"""
    name = name[len("banner_"):] if name.startswith("banner_") else name
    for prefix in ("article_", "summary_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.split(".")[0]


def _read_newest_skill_outputs(skill_dir: Path) -> dict:
    """收集该技能最近一次运行的输出：正文 HTML、一页纸 HTML、候选 banner。"""
    out_dir = skill_dir / "output"
    results: dict = {"content_html": "", "summary_html": "", "metadata": {}, "banners": []}
    if not out_dir.is_dir():
        return results

    def newest(pattern: str):
        matches = [p for p in out_dir.glob(pattern) if p.is_file()]
        return max(matches, key=lambda p: p.stat().st_mtime) if matches else None

    for key, pattern in (("content_html", "article_*.html"), ("summary_html", "summary_*.html")):
        f = newest(pattern)
        if f:
            try:
                results[key] = f.read_text(encoding="utf-8")
            except Exception:
                pass

    meta = newest("metadata_*.json")
    if meta:
        try:
            results["metadata"] = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            pass

    # banner 图：每类（原文图 / 一页纸截图）取最近一次运行生成的一张，最多两张
    def banner_kind(name: str) -> str | None:
        # 形如 banner_article_<id>.webp 或 banner_summary_<id>.png（老版本为 banner_<id>.ext）
        body = name[len("banner_"):] if name.startswith("banner_") else name
        for kind in ("article", "summary"):
            if body.startswith(kind + "_"):
                return kind
        return None

    banner_files = [
        p for p in list(out_dir.glob("banner_*.[Pp][Nn][Gg]"))
        + list(out_dir.glob("banner_*.[Ww][Ee][Bb][Pp]"))
        + list(out_dir.glob("banner_*.[Jj][Pp][Gg]"))
        + list(out_dir.glob("banner_*.[Jj][Pp][Ee][Gg]"))
        if p.is_file()
    ]
    best_by_kind: dict[str, Path] = {}
    for p in banner_files:
        kind = banner_kind(p.name)
        if kind is None:
            continue
        if kind not in best_by_kind or p.stat().st_mtime > best_by_kind[kind].stat().st_mtime:
            best_by_kind[kind] = p
    for kind in ("article", "summary"):
        p = best_by_kind.get(kind)
        if not p:
            continue
        try:
            url = _store_media(p.read_bytes(), Path(p.name).suffix, "images")
            results["banners"].append({"url": url, "name": p.name, "kind": kind})
        except Exception:
            continue
    return results


def _run_skill(url: str, log: Callable[[str], None] | None = None) -> dict:
    """在后台线程里执行 URL 提取技能——这里就是“执行 agent skill”的入口。

    log 回调会把技能子进程的 stdout/stderr 逐行转发出去（由调用方写入任务日志，
    前端轮询即可实时看到技能执行进度，不再是黑盒）。
    """
    def _say(msg: str) -> None:
        if log is not None:
            log(msg)

    skill_dir = Path(__file__).parent.parent / "skills" / "url-to-article"
    if not (skill_dir / "src" / "main.py").exists():
        raise HTTPException(422, "未找到 URL 提取技能（url-to-article），请先将其安装到 server/skills 目录")

    python = _find_skill_python()
    _say(f"启动技能：url-to-article（Python: {python}）")

    # 用 Popen 按行读取子进程输出，才能把进度实时流式推送，而不是等全部跑完
    proc = subprocess.Popen(
        [python, "-m", "src.main", url],
        cwd=str(skill_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    combined_lines: list[str] = []
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.rstrip("\n").rstrip("\r")
            combined_lines.append(line)
            stripped = line.strip()
            if stripped:
                _say(stripped)
    finally:
        proc.stdout.close()

    proc.wait()
    combined = "\n".join(combined_lines).strip()
    if proc.returncode != 0:
        tail = re.sub(r"\s+", " ", combined)[-300:]
        raise HTTPException(422, f"技能运行失败（退出码 {proc.returncode}）：{tail or '无输出'}")
    _say("技能子进程已正常退出")

    res = _read_newest_skill_outputs(skill_dir)
    if not res["content_html"]:
        raise HTTPException(422, "未能从该网页提取到有效内容，请检查链接是否有效或需登录")

    meta = res.get("metadata") or {}
    return {
        "content_html": res["content_html"],
        "summary_html": res["summary_html"],
        "url": url,
        "title": (meta.get("title") or "").strip(),
        "detected_language": meta.get("language", ""),
        "translated": bool(meta.get("translated", False)),
        "image_count": meta.get("image_count", 0),
        "banners": res["banners"],
    }


class SkillExtractRequest(BaseModel):
    url: str = Field(min_length=1)


@app.post("/api/v1/admin/content/skill-extract", status_code=201)
def admin_skill_extract(body: SkillExtractRequest, _: sqlite3.Row = Depends(admin_user)):
    """启动一次 URL 提取任务（异步，返回 job_id，前端轮询状态接口）。"""
    url = body.url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(422, "请提供有效的 HTTP/HTTPS 网址")
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254", "metadata.google.internal"}:
        raise HTTPException(422, "不支持抓取本机或内网地址")

    job_id = secrets.token_hex(8)
    job: dict = {
        "id": job_id,
        "url": url,
        "status": "running",
        "error": "",
        "result": None,
        "started_at": now(),
        "logs": [],
    }
    with _SKILL_JOBS_LOCK:
        _SKILL_JOBS[job_id] = job

    def _append_log(level: str, msg: str) -> None:
        with _SKILL_JOBS_LOCK:
            job["logs"].append({"ts": now(), "level": level, "msg": msg})

    def _runner():
        _append_log("info", f"开始提取文章：{url}")
        try:
            job["result"] = _run_skill(url, lambda msg: _append_log("info", msg))
            job["status"] = "done"
            _append_log("success", "✅ 技能执行完成，正文 / 一页纸 / banner 已生成")
        except HTTPException as exc:
            job["status"] = "error"
            job["error"] = str(exc.detail)
            _append_log("error", f"❌ {exc.detail}")
        except Exception as exc:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = f"技能执行失败：{exc}"
            _append_log("error", f"❌ 技能执行失败：{exc}")

    threading.Thread(target=_runner, daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/v1/admin/content/skill-extract/{job_id}")
def admin_skill_extract_status(job_id: str, _: sqlite3.Row = Depends(admin_user)):
    """轮询 URL 提取任务状态；done 时返回完整结果（正文/一页纸/banner）。"""
    with _SKILL_JOBS_LOCK:
        job = _SKILL_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在或已过期")
    with _SKILL_JOBS_LOCK:
        logs = list(job.get("logs") or [])
    return {
        "id": job["id"],
        "url": job["url"],
        "status": job["status"],
        "error": job["error"],
        "result": job.get("result"),
        "started_at": job.get("started_at"),
        "logs": logs,
    }


# ========================================
# 移动端「解读」：用户级 URL → 文章（复用 url-to-article 技能）
# 与 web 端管理后台“内容管理-发布内容-网页链接发布”一致：
# 1) 把链接交给 url-to-article 技能提取，得到 HTML 正文、一页纸解读、
#    以及 1~2 张候选 banner 图（英文自动翻译成中文）；
# 2) 复用「模型管理」里配置的大模型，再从正文提取标题（≥10 字）、
#    副标题（≥50 字）与摘要；
# 3) 由用户自选 banner 与分类后调用发布，落库为正式内容文章。
# 这些接口不要求 admin，登录用户即可使用（复用 _run_skill / _SKILL_JOBS）。
# ========================================

class InsightUrlDecodeRequest(BaseModel):
    url: str = Field(min_length=1)
    title_hint: str = ""


class InsightUrlDecodePublish(BaseModel):
    job_id: str
    url: str = ""
    section_id: int
    sub_category_id: int | None = None
    banner_url: str = ""
    title: str = ""
    subtitle: str = ""
    excerpt: str = ""


def _decode_metadata_local(text: str, doc_name: str = "") -> tuple[str, str, str]:
    """本地兜底提取标题 / 副标题 / 摘要（与后台 metadata 接口保持一致）。"""
    local_title = (doc_name or "").strip() or _first_sentences(text, TITLE_MIN_CHARS, 60)
    title = re.sub(r"\s+", " ", local_title).strip() or text[:40].strip()
    subtitle = _first_sentences(text, SUBTITLE_MIN_CHARS, 200)
    if _cjk_len(subtitle) < SUBTITLE_MIN_CHARS:
        subtitle = text[: int(SUBTITLE_MIN_CHARS * 1.5)].strip()
    excerpt = _first_sentences(text, EXCERPT_MIN_CHARS, 300)
    if _cjk_len(excerpt) < EXCERPT_MIN_CHARS:
        excerpt = text[:300].strip()
    return title, subtitle, excerpt


def _decode_metadata_llm(content_html: str, doc_name: str = "") -> dict:
    """用模型管理里配置的大模型，从正文提取标题 / 副标题 / 摘要。"""
    text = re.sub(r"\s+", " ", _strip_tags(content_html)).strip()
    title = subtitle = excerpt = ""
    source = "local"
    model_name = ""
    if text:
        llm_out, model_name = _llm_text_ex(
            "你是中文技术博客的资深编辑。你会收到一篇文章的正文（HTML 或纯文本），请提炼出：\n"
            "1. 文章标题：具体、准确、吸引人，贴合正文内容，不少于 10 个中文字（或等量中英混合）；\n"
            "2. 副标题：50 字以上，补充说明文章的价值与阅读期待，不是标题的简单重复；\n"
            "3. 摘要：80 字以上，用两三句话概括文章的核心内容与结论。\n"
            '只输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释。格式：{"title":"...","subtitle":"...","excerpt":"..."}',
            f"文章标题参考（可能为空）：{doc_name or ''}\n\n正文：\n{text[:12000]}",
            max_tokens=1500,
            timeout=120,
        )
        if llm_out:
            parsed = _parse_meta_json(llm_out)
            title = str(parsed.get("title") or "").strip()
            subtitle = str(parsed.get("subtitle") or "").strip()
            excerpt = str(parsed.get("excerpt") or "").strip()
            if _cjk_len(title) >= TITLE_MIN_CHARS and _cjk_len(subtitle) >= SUBTITLE_MIN_CHARS:
                source = "llm"
            else:
                title = subtitle = excerpt = ""
                model_name = ""
    if not title:
        title, subtitle, excerpt = _decode_metadata_local(text, doc_name)
    return {
        "title": title,
        "subtitle": subtitle,
        "excerpt": excerpt,
        "source": source,
        "model": model_name,
        "title_min": TITLE_MIN_CHARS,
        "subtitle_min": SUBTITLE_MIN_CHARS,
    }


@app.post("/api/v1/insight/decode-url", status_code=201)
def insight_decode_url(body: InsightUrlDecodeRequest, user: sqlite3.Row = Depends(current_user)):
    """移动端：把网页链接交给 url-to-article 技能提取（异步任务，返回 job_id）。"""
    url = body.url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(422, "请提供有效的 HTTP/HTTPS 网址")
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254", "metadata.google.internal"}:
        raise HTTPException(422, "不支持抓取本机或内网地址")

    job_id = secrets.token_hex(8)
    job: dict = {
        "id": job_id,
        "url": url,
        "status": "running",
        "error": "",
        "result": None,
        "started_at": now(),
        "logs": [],
        "user_id": user["id"],
    }
    with _SKILL_JOBS_LOCK:
        _SKILL_JOBS[job_id] = job

    def _append_log(level: str, msg: str) -> None:
        with _SKILL_JOBS_LOCK:
            job["logs"].append({"ts": now(), "level": level, "msg": msg})

    def _runner():
        _append_log("info", f"开始提取文章：{url}")
        try:
            res = _run_skill(url, lambda msg: _append_log("info", msg))
            # 复用模型管理里配置的大模型，从正文提取标题 / 副标题 / 摘要
            meta = _decode_metadata_llm(res.get("content_html", ""), res.get("title", ""))
            res["metadata_meta"] = meta
            job["result"] = res
            job["status"] = "done"
            _append_log("success", "✅ 技能执行完成，正文 / 一页纸 / banner 与标题均已生成")
        except HTTPException as exc:
            job["status"] = "error"
            job["error"] = str(exc.detail)
            _append_log("error", f"❌ {exc.detail}")
        except Exception as exc:  # noqa: BLE001
            job["status"] = "error"
            job["error"] = f"技能执行失败：{exc}"
            _append_log("error", f"❌ 技能执行失败：{exc}")

    threading.Thread(target=_runner, daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/v1/insight/decode-url/{job_id}")
def insight_decode_url_status(job_id: str, user: sqlite3.Row = Depends(current_user)):
    """移动端：轮询解读任务状态；done 时返回完整结果（正文/一页纸/banner/标题）。"""
    with _SKILL_JOBS_LOCK:
        job = _SKILL_JOBS.get(job_id)
    if not job or job.get("user_id") != user["id"]:
        raise HTTPException(404, "任务不存在或已过期")
    with _SKILL_JOBS_LOCK:
        logs = list(job.get("logs") or [])
    return {
        "id": job["id"],
        "url": job["url"],
        "status": job["status"],
        "error": job["error"],
        "result": job.get("result"),
        "logs": logs,
    }


@app.post("/api/v1/insight/decode-url/publish", status_code=201)
def insight_decode_publish(body: InsightUrlDecodePublish, user: sqlite3.Row = Depends(current_user)):
    """移动端：从解读任务结果发布为正式内容文章（用户自选 banner 与分类）。"""
    if not body.section_id:
        raise HTTPException(422, "请选择发布板块")
    _validate_section_category(body.section_id, body.sub_category_id)

    if not body.job_id:
        raise HTTPException(422, "解读任务不存在，请先解读后再发布")
    with _SKILL_JOBS_LOCK:
        job = _SKILL_JOBS.get(body.job_id)
    if not job or job.get("user_id") != user["id"] or job["status"] != "done":
        raise HTTPException(422, "解读任务不存在或尚未完成，请重新解读后再发布")

    res = job.get("result") or {}
    content_html = res.get("content_html", "")
    summary_html = res.get("summary_html", "")
    if not content_html:
        raise HTTPException(422, "未找到解读正文，请重新解读")

    meta = res.get("metadata_meta") or {}
    title = (body.title or "").strip() or str(meta.get("title") or "").strip()
    subtitle = (body.subtitle or "").strip() or str(meta.get("subtitle") or "").strip()
    if _cjk_len(title) < TITLE_MIN_CHARS:
        raise HTTPException(422, f"标题不少于 {TITLE_MIN_CHARS} 个字")
    if _cjk_len(subtitle) < SUBTITLE_MIN_CHARS:
        raise HTTPException(422, f"副标题不少于 {SUBTITLE_MIN_CHARS} 个字")
    excerpt = (body.excerpt or "").strip() or _first_sentences(
        re.sub(r"\s+", " ", _strip_tags(content_html)), EXCERPT_MIN_CHARS, 300
    )

    url = (body.url or "").strip() or str(res.get("url") or "")
    with db() as conn:
        sec = conn.execute("SELECT name FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        cursor = conn.execute(
            """INSERT INTO insight_articles(
                 user_id, section_id, sub_category_id, url, title, subtitle, source_domain,
                 content_type, content_format, manual_content, excerpt, summary_content, banner_url,
                 status, word_count, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["id"], body.section_id, body.sub_category_id,
                url or f"insight://decode/{secrets.token_hex(8)}",
                title, subtitle,
                sec["name"] if sec else (urlparse(url).hostname or ""),
                "link", "html", content_html, excerpt[:300], summary_html,
                (body.banner_url or "").strip(),
                "ready", _cjk_len(_strip_tags(content_html)), now(), now(),
            ),
        )
        article_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)",
            (user["id"], "insight_decode_publish", now()),
        )

    with _SKILL_JOBS_LOCK:
        _SKILL_JOBS.pop(body.job_id, None)
    return {"id": article_id, "status": "ready", "message": "发布成功", "excerpt": excerpt}


# ========================================
# 分享页「一键保存」：后台全程自动执行（用户无需等待）
# 复用 url-to-article 技能 + 模型提取主副标题 + 自动选 banner + 自动发布。
# 分享页点「保存」后立刻返回（status=pending），技能在服务端后台线程执行，
# 完成后自动把正文 / 一页纸 / banner / 标题写入正式内容文章。
# ========================================

class SharedArticleSave(BaseModel):
    url: str = Field(min_length=1)
    section_id: int
    sub_category_id: int | None = None
    title_hint: str = ""


def _pick_auto_banner(banners: list) -> str:
    """从技能生成的候选 banner 里自动挑一张最合适的。

    优先使用技能从原文提取的配图（kind=article），作为发布文章的主 banner；
    仅当没有原文配图时，才退回使用技能用 SVG 生成的一页纸 banner（kind=summary）。
    """
    if not banners:
        return ""
    for b in banners:
        if (b.get("kind") or "") == "article" and b.get("url"):
            return b["url"]
    for b in banners:
        if (b.get("kind") or "") == "summary" and b.get("url"):
            return b["url"]
    for b in banners:
        if b.get("url"):
            return b["url"]
    return ""


@app.post("/api/v1/insight/articles/shared-save", status_code=201)
def shared_article_save(body: SharedArticleSave, user: sqlite3.Row = Depends(current_user)):
    """分享页一键保存：返回即代表已入队，技能在后台自动完成解读并发布，无需等待。"""
    url = body.url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(422, "请提供有效的 HTTP/HTTPS 网址")
    host = (urlparse(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254", "metadata.google.internal"}:
        raise HTTPException(422, "不支持抓取本机或内网地址")

    if not body.section_id:
        raise HTTPException(422, "请选择发布板块")
    _validate_section_category(body.section_id, body.sub_category_id)

    with db() as conn:
        sec = conn.execute("SELECT name FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        dup = conn.execute(
            "SELECT id FROM insight_articles WHERE user_id=? AND url=? AND section_id=?",
            (user["id"], url, body.section_id),
        ).fetchone()
        if dup:
            return JSONResponse(
                {"id": dup["id"], "status": "pending", "message": "该链接已发布到此板块"},
                status_code=200,
            )
        cursor = conn.execute(
            "INSERT INTO insight_articles(user_id,section_id,sub_category_id,url,title,source_domain,"
            "content_type,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (user["id"], body.section_id, body.sub_category_id, url,
             (body.title_hint or "").strip() or url, sec["name"] if sec else (urlparse(url).hostname or ""),
             "skill", "pending", now(), now()),
        )
        article_id = cursor.lastrowid
        conn.execute("INSERT INTO events(user_id,kind,created_at) VALUES(?,?,?)", (user["id"], "insight_shared_save", now()))

    def _runner(article_id: int):
        try:
            res = _run_skill(url)
            content_html = res.get("content_html", "")
            summary_html = res.get("summary_html", "")
            if not content_html:
                with db() as conn:
                    conn.execute("UPDATE insight_articles SET status='failed', updated_at=? WHERE id=?", (now(), article_id))
                return
            meta = _decode_metadata_llm(content_html, res.get("title", ""))
            title = str(meta.get("title") or "").strip() or res.get("title", "") or url[:200]
            subtitle = str(meta.get("subtitle") or "").strip()
            excerpt = str(meta.get("excerpt") or "").strip() or _first_sentences(
                re.sub(r"\s+", " ", _strip_tags(content_html)), EXCERPT_MIN_CHARS, 300
            )
            word_count = _cjk_len(_strip_tags(content_html))
            has_banner = False
            with db() as conn:
                conn.execute(
                    """UPDATE insight_articles SET title=?, subtitle=?, status='ready',
                       content_type='skill', content_format='html',
                       manual_content=?, translated_content=?, original_content=?,
                       summary_content=?, one_page_summary=?, banner_url=?,
                       excerpt=?, word_count=?, updated_at=?
                       WHERE id=?""",
                    (title, subtitle, content_html, content_html, content_html,
                     summary_html, summary_html, _pick_auto_banner(res.get("banners", [])),
                     excerpt, word_count, now(), article_id),
                )
                row = conn.execute("SELECT banner_url FROM insight_articles WHERE id=?", (article_id,)).fetchone()
                has_banner = bool(row and row["banner_url"])
            if not has_banner:
                # 没有 banner 也正常，阅读端用默认封面色块
                pass
        except Exception:  # noqa: BLE001
            try:
                with db() as conn:
                    conn.execute("UPDATE insight_articles SET status='failed', updated_at=? WHERE id=?", (now(), article_id))
            except Exception:
                pass

    threading.Thread(target=_runner, args=(article_id,), daemon=True).start()
    return {"id": article_id, "status": "pending", "message": "已提交，后台正在调用技能自动解读并发布，可稍后到 App 查看"}


# ========================================
# Admin Content Management APIs (editor)
# 后台内容编辑器 API：metadata 提取 + 文章增删改查
# ========================================

def _parse_meta_json(raw: str) -> dict:
    """Robustly parse a JSON object from model output, falling back to key=value."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    out: dict[str, str] = {}
    for key in ("title", "subtitle", "excerpt"):
        m = re.search(rf'"{key}"\s*:\s*"([^"]*)"', raw)
        if m:
            out[key] = m.group(1)
    return out


@app.post("/api/v1/admin/content/metadata")
def admin_extract_metadata(body: MetadataExtractRequest, _: sqlite3.Row = Depends(admin_user)):
    """Extract title / subtitle / excerpt from the article body.

    Tries the configured LLM first, then falls back to a local first-sentence
    heuristic when no model answers. A previously uploaded PDF (doc_url) is
    re-read server-side and its first pages parsed for plain text.
    """
    warnings: list[str] = []

    if body.doc_url:
        try:
            pdf_bytes = _read_media_pdf(body.doc_url)
            text = _strip_tags(_pdf_preview_text(pdf_bytes))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, f"重新解析 PDF 失败：{exc}")
    elif body.is_plain_text:
        text = (body.content or "").strip()
    else:
        text = _strip_tags(body.content)

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise HTTPException(422, "没有可提取的文字内容，请检查正文或文档")

    source: str = "local"
    model_name: str = ""
    title = subtitle = excerpt = ""

    llm_out, model_name = _llm_text_ex(
        "你是中文技术博客的资深编辑。你会收到一篇文章的正文（HTML 或纯文本），请提炼出：\n"
        "1. 文章标题：具体、准确、吸引人，贴合正文内容，不少于 10 个中文字（或等量中英混合）；\n"
        "2. 副标题：50 字以上，补充说明文章的价值与阅读期待，不是标题的简单重复；\n"
        "3. 摘要：80 字以上，用两三句话概括文章的核心内容与结论。\n"
        '只输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释。格式：{"title":"...","subtitle":"...","excerpt":"..."}',
        f"文章标题参考（可能为空）：{body.doc_name or ''}\n\n正文：\n{text[:12000]}",
        max_tokens=1500,
        timeout=120,
    )
    if llm_out:
        parsed = _parse_meta_json(llm_out)
        title = str(parsed.get("title") or "").strip()
        subtitle = str(parsed.get("subtitle") or "").strip()
        excerpt = str(parsed.get("excerpt") or "").strip()
        if _cjk_len(title) >= TITLE_MIN_CHARS and _cjk_len(subtitle) >= SUBTITLE_MIN_CHARS:
            source = "llm"
        else:
            warnings.append("大模型返回的标题或副标题不完整，已改用本地提取")
            title = subtitle = excerpt = ""
            model_name = ""

    # Local fallback (also used when no configured model answers).
    if not title:
        local_title = (body.doc_name or "").strip() or _first_sentences(text, TITLE_MIN_CHARS, 60)
        title = re.sub(r"\s+", " ", local_title).strip() or text[:40].strip()
    if not subtitle:
        subtitle = _first_sentences(text, SUBTITLE_MIN_CHARS, 200)
        if _cjk_len(subtitle) < SUBTITLE_MIN_CHARS:
            subtitle = text[: int(SUBTITLE_MIN_CHARS * 1.5)].strip()
    if not excerpt:
        excerpt = _first_sentences(text, EXCERPT_MIN_CHARS, 300)
        if _cjk_len(excerpt) < EXCERPT_MIN_CHARS:
            excerpt = text[:300].strip()

    if source == "local":
        warnings.append("未连通配置的大模型，已按正文本地提取，请人工检查标题与副标题")

    return {
        "title": title,
        "subtitle": subtitle,
        "excerpt": excerpt,
        "source": source,
        "model": model_name,
        "warnings": warnings,
        "title_min": TITLE_MIN_CHARS,
        "subtitle_min": SUBTITLE_MIN_CHARS,
    }


class SummaryGenerateRequest(BaseModel):
    """Generate a one-page overview summary (HTML) from the article body."""
    content: str = ""
    content_format: str = "richtext"
    title: str = ""
    is_plain_text: bool = False  # PDF 抽取出的纯文本，不含 HTML 标签
    doc_url: str = ""  # /media/... 的 PDF 地址；给定时服务端重新解析前若干页


def _html_escape(v: str) -> str:
    return (
        (v or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _li_html(items: list[str]) -> str:
    return "".join(
        f"<li style='margin-bottom:6px'>{_html_escape(str(x))}</li>" for x in items
    )


def _build_summary_html(data: dict) -> str:
    """Turn structured model output into a consistently-styled one-page brief."""
    conclusion = _html_escape(data.get("conclusion") or "")
    key_points = [str(x).strip() for x in (data.get("key_points") or []) if str(x).strip()]
    details = [str(x).strip() for x in (data.get("details") or []) if str(x).strip()]
    takeaways = [str(x).strip() for x in (data.get("takeaways") or []) if str(x).strip()]

    parts: list[str] = [
        "<div style='font-family:-apple-system,BlinkMacSystemFont,\"PingFang SC\","
        "\"Microsoft YaHei\",sans-serif;font-size:15px;line-height:1.9;color:#1f2937;'>",
        "<div style='display:flex;align-items:baseline;gap:10px;padding-bottom:10px;"
        "border-bottom:2px solid #1a73e8;margin-bottom:16px;'>"
        "<span style='font-size:17px;font-weight:700;color:#1a73e8;'>一页纸解读</span>"
        "<span style='font-size:12px;color:#9ca3af;letter-spacing:.12em;'>ONE-PAGE BRIEF</span></div>",
    ]
    if conclusion:
        parts.append(
            "<div style='background:#eef4ff;border:1px solid #dbe7ff;border-left:4px solid #1a73e8;"
            "border-radius:8px;padding:14px 16px;margin:0 0 16px;'>"
            "<div style='font-weight:700;color:#1a73e8;margin-bottom:6px;'>核心结论</div>"
            f"<div>{conclusion}</div></div>"
        )
    if key_points:
        parts.append("<h3 style='font-size:15px;font-weight:700;color:#111827;margin:0 0 8px;'>关键要点</h3>")
        parts.append(f"<ul style='margin:0 0 16px;padding-left:20px;'>{_li_html(key_points)}</ul>")
    if details:
        parts.append("<h3 style='font-size:15px;font-weight:700;color:#111827;margin:0 0 8px;'>技术细节亮点</h3>")
        parts.append(f"<ul style='margin:0 0 16px;padding-left:20px;'>{_li_html(details)}</ul>")
    if takeaways:
        parts.append(
            "<div style='background:#f9f5ff;border:1px solid #ece4ff;border-left:4px solid #7c3aed;"
            "border-radius:8px;padding:14px 16px;'>"
            "<div style='font-weight:700;color:#7c3aed;margin-bottom:6px;'>行动启示</div>"
            f"<ul style='margin:0;padding-left:20px;'>{_li_html(takeaways)}</ul></div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _parse_summary_json(raw: str) -> dict:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            for key in ("key_points", "details", "takeaways"):
                v = obj.get(key)
                if isinstance(v, str):
                    obj[key] = [v]
                elif isinstance(v, list):
                    obj[key] = [str(x) for x in v]
                else:
                    obj[key] = []
            if not isinstance(obj.get("conclusion"), str):
                obj["conclusion"] = ""
            return obj
    except Exception:
        pass
    return {}


def _fallback_summary_html(text: str, title: str = "") -> str:
    t = (title or "").strip()
    text = re.sub(r"\s+", " ", text or "").strip()
    lead = text[:220] + ("…" if len(text) > 220 else "")
    prefix = f"《{t}》" if t else "本文"
    return _build_summary_html({
        "conclusion": f"{prefix}围绕主题展开，以下概要帮助你快速把握整体脉络，再决定是否深入阅读正文。",
        "key_points": [lead] if lead else [],
        "details": [],
        "takeaways": ["建议结合自身场景，把文中思路落地到实际项目中实践验证。"],
    })


@app.post("/api/v1/admin/content/summary", status_code=201)
def admin_generate_summary(body: SummaryGenerateRequest, _: sqlite3.Row = Depends(admin_user)):
    """Generate an aesthetic one-page overview summary (HTML) from the article body.

    供富文本 / HTML 源码 / 文档三种模式在「标题与配图」步骤自动或手动生成一页纸解读；
    「网页链接」模式由 url-to-article 技能自行产出，不调用此接口。
    """
    if body.doc_url:
        try:
            pdf_bytes = _read_media_pdf(body.doc_url)
            text = _strip_tags(_pdf_preview_text(pdf_bytes))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, f"重新解析 PDF 失败：{exc}")
    elif body.is_plain_text:
        text = (body.content or "").strip()
    else:
        text = _strip_tags(body.content)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise HTTPException(422, "没有可生成摘要的正文内容，请先填好正文或上传文档")

    title = (body.title or "").strip()
    system_prompt = (
        "你是资深技术编辑，擅长把一篇长文提炼成一页纸概要解读，供读者在阅读正文前快速掌握全貌。"
        "只输出一个 JSON 对象，不要 Markdown 代码块，不要任何解释。"
    )
    user_prompt = f"""请为下面的{'文档' if body.is_plain_text else '文章'}生成一页纸解读，用中文，输出 JSON：
{{
  "conclusion": "核心结论，2—3 句话概括主旨与最重要判断",
  "key_points": ["3—5 条关键要点"],
  "details": ["2—4 条技术细节或亮点（涉及具体机制、数据、方案时保留）"],
  "takeaways": ["2—3 条对读者的行动启示"]
}}
要求：每条 30—80 字；提炼，不复述原文；让读者不读正文也能大致了解内容。

文章标题：{title or '（无）'}

正文：
{text[:8000]}"""
    raw, model_name = _llm_text_ex(system_prompt, user_prompt, max_tokens=2500, timeout=120)
    source = "llm"
    if not raw:
        html = sanitize_article_html(_fallback_summary_html(text, title))
        source = "fallback"
        model_name = ""
    else:
        data = _parse_summary_json(raw)
        if not (data.get("conclusion") or data.get("key_points")):
            html = sanitize_article_html(_fallback_summary_html(text, title))
            source = "fallback"
            model_name = ""
        else:
            html = sanitize_article_html(_build_summary_html(data))
    return {"html": html, "source": source, "model": model_name}


class AdminContentArticleIn(BaseModel):
    """Create/update payload for the content editor (mirrors frontend AdminArticlePayload)."""
    title: str = ""
    subtitle: str = ""
    section_id: int = 0
    sub_category_id: int | None = None
    content_html: str = ""
    content_format: str = "richtext"
    excerpt: str = ""
    summary_html: str = ""  # 一页纸解读（HTML）
    content_type: str = ""  # manual | link | document（补充语义，留给 link-from-skill）
    banner_url: str = ""
    attachment_url: str = ""
    attachment_name: str = ""
    doc_kind: str = ""
    source_url: str = ""
    status: str = "draft"


def _validate_section_category(section_id: int, sub_category_id: int | None) -> None:
    """Raise a 404 with a clear message when the section or its category is missing."""
    with db() as conn:
        sec = conn.execute("SELECT id, name FROM content_sections WHERE id=?", (section_id,)).fetchone()
        if not sec:
            raise HTTPException(404, "内容板块不存在")
        if sub_category_id is not None:
            cat = conn.execute(
                "SELECT id FROM content_categories WHERE id=? AND section_id=?",
                (sub_category_id, section_id),
            ).fetchone()
            if not cat:
                raise HTTPException(404, "分类不存在或不属于该板块")


@app.get("/api/v1/admin/content/articles/{article_id}")
def admin_get_content_article(article_id: int, _: sqlite3.Row = Depends(admin_user)):
    """Get a single article (including drafts) for the editor."""
    with db() as conn:
        row = conn.execute(
            """SELECT a.*, COALESCE(cc.name, '') AS category_name,
                      COALESCE(cs.name, '') AS section_name, u.name AS author_name
               FROM insight_articles a
               LEFT JOIN content_categories cc ON a.sub_category_id = cc.id
               LEFT JOIN content_sections cs ON a.section_id = cs.id
               LEFT JOIN users u ON a.user_id = u.id
               WHERE a.id = ?""",
            (article_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "文章不存在")
    return dict(row)


@app.post("/api/v1/admin/content/articles", status_code=201)
def admin_create_content_article(body: AdminContentArticleIn, user: sqlite3.Row = Depends(admin_user)):
    """Create an article (draft or ready) from the content editor."""
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(422, "请填写文章标题")
    if not body.section_id:
        raise HTTPException(422, "请选择发布板块")
    _validate_section_category(body.section_id, body.sub_category_id)

    content_html = body.content_html or ""
    content_format = (body.content_format or "richtext").strip() or "richtext"
    # 白名单过滤后入库（保留 AI 润色的行内样式）；整页 html 模式在阅读端用独立 sandbox 渲染
    if content_format != "html":
        content_html = sanitize_article_html(content_html)
    # 一页纸解读：整页 HTML 时保留作者样式（sandbox 渲染），否则白名单过滤
    summary_html = body.summary_html or ""
    if summary_html and content_format != "html":
        summary_html = sanitize_article_html(summary_html)
    source_url = (body.source_url or "").strip()
    content_type = body.content_type or {"link": "link", "document": "document"}.get(content_format, "manual")
    if content_type not in ("manual", "link", "document"):
        content_type = "manual"
    if content_format == "link" and not source_url:
        source_url = f"insight://link/{secrets.token_hex(8)}"
    url = source_url or f"insight://manual/{secrets.token_hex(8)}"
    excerpt = (body.excerpt or "").strip() or (re.sub(r"<[^>]+>", " ", _strip_tags(content_html))[:200].strip())
    status = body.status if body.status in ("ready", "draft") else "draft"
    word_count = _cjk_len(_strip_tags(content_html))

    with db() as conn:
        sec = conn.execute("SELECT name FROM content_sections WHERE id=?", (body.section_id,)).fetchone()
        cursor = conn.execute(
            """INSERT INTO insight_articles(
                 user_id, section_id, sub_category_id, url, title, subtitle, source_domain,
                 content_type, content_format, manual_content, excerpt, summary_content, banner_url,
                 attachment_url, attachment_name, doc_kind, status, word_count, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["id"], body.section_id, body.sub_category_id, url,
                title, (body.subtitle or "").strip(),
                sec["name"] if sec else (urlparse(url).hostname or ""),
                content_type, content_format, content_html, excerpt, summary_html,
                (body.banner_url or "").strip(),
                (body.attachment_url or "").strip(), (body.attachment_name or "").strip(),
                (body.doc_kind or "").strip(), status, word_count, now(), now(),
            ),
        )
        article_id = cursor.lastrowid

    message = "已发布" if status == "ready" else "已保存为草稿"
    return {"id": article_id, "status": status, "message": message}


@app.put("/api/v1/admin/content/articles/{article_id}")
def admin_update_content_article(article_id: int, body: AdminContentArticleIn, _: sqlite3.Row = Depends(admin_user)):
    """Update an article from the content editor (full-payload semantics)."""
    with db() as conn:
        existing = conn.execute("SELECT * FROM insight_articles WHERE id=?", (article_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "文章不存在")
        if body.section_id:
            _validate_section_category(body.section_id, body.sub_category_id)

        content_format = (body.content_format or "richtext").strip() or "richtext"
        content_html = body.content_html or ""
        if content_format != "html":
            content_html = sanitize_article_html(content_html)
        summary_html = body.summary_html or ""
        if summary_html and content_format != "html":
            summary_html = sanitize_article_html(summary_html)
        content_type = body.content_type or {"link": "link", "document": "document"}.get(content_format, "manual")
        if content_type not in ("manual", "link", "document"):
            content_type = "manual"
        fields: dict[str, Any] = {
            "title": (body.title or "").strip(),
            "subtitle": (body.subtitle or "").strip(),
            "manual_content": content_html,
            "content_format": content_format,
            "excerpt": (body.excerpt or "").strip(),
            "summary_content": summary_html,
            "content_type": content_type,
            "banner_url": (body.banner_url or "").strip(),
            "attachment_url": (body.attachment_url or "").strip(),
            "attachment_name": (body.attachment_name or "").strip(),
            "doc_kind": (body.doc_kind or "").strip(),
            "status": body.status if body.status in ("ready", "draft") else existing["status"],
        }
        if body.section_id:
            fields["section_id"] = body.section_id
        if body.sub_category_id:
            fields["sub_category_id"] = body.sub_category_id
        if body.source_url:
            fields["url"] = body.source_url.strip()
        fields["updated_at"] = now()

        sets = ", ".join(f"{key}=?" for key in fields)
        conn.execute(f"UPDATE insight_articles SET {sets} WHERE id=?", (*fields.values(), article_id))

    return {"id": article_id, "status": fields["status"], "message": "保存成功"}
