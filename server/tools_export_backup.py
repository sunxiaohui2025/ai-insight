#!/usr/bin/env python3
"""Standalone 本地数据备份导出（不依赖服务运行）

用法:
    python3 tools_export_backup.py [输出 zip 路径]
默认输出: ./insight-backup-<时间戳>.zip
生成 zip 内包含:
  - insight.db   : 脱敏数据库（不含 llm_models 大模型连接配置 / API Key 数据）
  - media/...    : 文章引用的媒体文件（标题图 / 正文图）
"""
import io, os, re, sqlite3, sys, tempfile, time, zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent           # server/
DB_PATH = BASE / "data" / "insight.db"
MEDIA_PATH = BASE / "data" / "media"
EXCLUDE = {"llm_models", "sqlite_sequence"}
REF_PATTERN = re.compile(r"/media/((?:banners|images|documents)/[A-Za-z0-9._-]+)")
FIELDS = ["banner_url","attachment_url","original_content","translated_content","manual_content","excerpt","one_page_summary"]

def build_db_bytes():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False); tmp.close()
    try:
        dst = sqlite3.connect(tmp.name)
        src = sqlite3.connect(str(DB_PATH))
        for t, in src.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            if t == "sqlite_sequence":
                continue
            ddl = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
            if ddl and ddl[0]:
                dst.execute(ddl[0])
            if t in EXCLUDE:
                continue
            cols = [c[1] for c in src.execute(f'PRAGMA table_info("{t}")')]
            rows = src.execute(f'SELECT * FROM "{t}"').fetchall()
            if rows and cols:
                q = ", ".join(f'"{c}"' for c in cols); ph = ", ".join("?" for _ in cols)
                dst.executemany(f'INSERT INTO "{t}" ({q}) VALUES ({ph})', [tuple(r) for r in rows])
        dst.commit(); src.close(); dst.close()
        return Path(tmp.name).read_bytes()
    finally:
        try: os.unlink(tmp.name)
        except OSError: pass

def referenced_media():
    refs = set()
    src = sqlite3.connect(str(DB_PATH))
    for f in FIELDS:
        for (v,) in src.execute(f"SELECT {f} FROM insight_articles"):
            if v: refs.update(REF_PATTERN.findall(v))
    src.close()
    base = MEDIA_PATH.resolve(); out = []
    for rel in refs:
        p = (MEDIA_PATH / rel).resolve()
        try: p.relative_to(base)
        except ValueError: continue
        if p.is_file(): out.append(p)
    return out

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else f"insight-backup-{int(time.time())}.zip"
    if not DB_PATH.exists():
        print(f"未找到本地数据库: {DB_PATH}"); sys.exit(1)
    media = referenced_media()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("insight.db", build_db_bytes())
        for p in media:
            zf.write(str(p), arcname="media/" + str(p.relative_to(MEDIA_PATH.resolve())))
    print(f"已生成备份: {out} ({os.path.getsize(out)/1024/1024:.1f} MB, {len(media)} 个媒体文件)")

if __name__ == "__main__":
    main()
