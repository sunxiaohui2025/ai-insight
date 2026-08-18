# InSight Blog 开发文档

InSight Blog 是 InSight 生态中的**技术博客系统**（React 前端 + 复用 InSight 云后端），支持两种内容来源：

1. **项目沉淀** — 手写技术博客总结与实践经验。
2. **研究解读** — 基于第三方链接或文件，经 AI Agent 辅助生成的深度解读。

统一采用 **Material Design（Google 风格）** 设计语言。

> 本文件整合了原 `QUICKSTART.md`、`PROJECT_COMPLETE.md`、`SUMMARY.md` 的内容，是博客系统的**唯一设计+进度文档**。项目整体入口见 [README.md](./README.md)。

---

## 技术架构

### 前端（`web/`，React SPA）

- **框架**：React 19 + TypeScript（CRA，`react-scripts`）
- **UI**：Material UI（Google Material Design 风格）
- **路由**：React Router v6 ｜ **状态**：React Context ｜ **HTTP**：Axios
- **编辑/渲染**：TipTap（富文本）、React Markdown、pdfjs-dist（PDF 解析）

### 后端（复用 `server/` 的 FastAPI + SQLite）

- **框架**：FastAPI + Python 3.11+，SQLite（raw sqlite3，无 ORM），单文件 `app/main.py`（约 3900 行）。
- **认证**：JWT（scrypt 加盐哈希）；管理员/普通用户角色。
- **异步任务**：FastAPI BackgroundTasks（可扩展 Celery）。
- **Agent 引擎**：自建轻量级引擎（预留 Claude Agent SDK 扩展）。
- `blog_routes.py` 目前是**骨架/参考**（公开 blog API 的落点），实际内容 API 已在 `main.py` 中实现（`/api/v1/content/*`）。

---

## 数据库设计（核心表）

```sql
users(id, email, name, password_hash, status, role, created_at, last_login_at)

content_sections(id, name, slug, description, sort_order, ...)          -- 板块：项目沉淀/研究解读
content_categories(id, section_id, parent_id, name, slug, icon, sort_order, ...)  -- 分类（支持层级）

insight_articles(
  id, user_id, section_id, category_id, sub_category_id,
  url, title, source_domain,
  content_type,            -- 'url' | 'manual'
  original_content, translated_content, manual_content,
  excerpt, summary_content,               -- summary = 一页纸解读
  status,                  -- pending|translating|ready|failed|draft|published
  is_read, is_starred, word_count, created_at, updated_at, published_at)

agent_sessions(id, user_id, mode, title, draft_json, status, ...)       -- mode: 'link'|'manual'
agent_messages(id, session_id, role, content, created_at)
agent_skills(id, name, display_name, version, description, skill_type, manifest_json, storage_path, enabled, ...)
agent_session_skills(session_id, skill_id)
agent_files(id, session_id, filename, mime_type, storage_path, created_at)
```

---

## 开发进度

### 前端（`web/`）

| 模块 | 状态 |
|------|------|
| 首页 `/`、项目沉淀 `/projects`、研究解读 `/insights`、文章详情 `/article/:id`（双阅读模式）、登录 `/login` | ✅ 完成 |
| 后台布局/导航、概览 `/admin`、AgentChat 组件 | ✅ 完成 |
| 内容发布 `/admin/publish`、内容管理 `/admin/articles`、分类管理 `/admin/categories`、模型管理 `/admin/models` | ✅ 已有页面（`ContentPublish/ContentManagement/CategoryManagement/Models.tsx`） |
| API 服务层（auth/blog/adminArticle/adminCategory/adminSection/adminUser/agent/skill/model）、AuthContext、主题 | ✅ 完成 |

### 后端（`server/`）

| 模块 | 状态 |
|------|------|
| 认证（注册/登录/权限） | ✅ 完成（继承自 InSight） |
| 公开 Blog API、后台文章/分类/板块管理 API | ✅ 完成 |
| Agent 会话/消息/文件 API 框架 | ✅ 完成 |
| Skills 上传/管理（zip + skill.json，`/api/v1/admin/skills`） | ✅ 完成 |
| Agent 引擎核心逻辑（消息处理/Skill 执行/草稿生成） | 🚧 待完善（`blog_routes.py` 为骨架） |
| 模型管理（多 LLM 配置/默认模型） | 🚧 待完善 |

**总体完成度约 60%**；核心待办：Agent 引擎实现、Skills 沙箱执行、管理端少量页面收尾。

---

## 快速启动

### 后端

```bash
# 项目根目录一键启动后端(:3002) + 前端(:3000)
./start-all.sh
./stop-all.sh
# 后端: http://localhost:3002   API 文档: http://localhost:3002/docs
```

### 前端

```bash
cd web
npm install
npm start                        # http://localhost:3000
```

### 访问

- 前端首页：`http://localhost:3000`
- 项目沉淀：`http://localhost:3000/projects` ｜ 研究解读：`http://localhost:3000/insights`
- 后台管理：`http://localhost:3000/admin`（需登录；管理员账号见 `server/.env.local`）
- API 文档：`http://localhost:8000/docs`

---

## API 一览

### 公开 API
```
GET  /api/v1/blog/articles            # 文章列表（section_id/category_id/search/page/limit）
GET  /api/v1/blog/articles/:id        # 文章详情
GET  /api/v1/blog/sections            # 板块列表
GET  /api/v1/blog/categories          # 分类列表（section_id）
GET  /api/v1/blog/featured            # 精选文章
GET  /api/v1/blog/latest?limit=N      # 最新文章
```

### 后台管理 API
```
GET/POST/PUT/DELETE  /api/v1/admin/articles
PATCH  /api/v1/admin/articles/:id/publish | /unpublish
GET/POST/PUT/DELETE  /api/v1/admin/categories
GET/POST/PUT/DELETE  /api/v1/admin/sections
GET    /api/v1/admin/skills           # Skills 列表
POST   /api/v1/admin/skills           # 上传 Skill zip
PUT/DELETE  /api/v1/admin/skills/:id  # 更新/删除
PATCH  /api/v1/admin/skills/:id/toggle # 启用/禁用
GET/PUT  /api/v1/admin/llm            # LLM 配置
GET/PATCH  /api/v1/admin/users        # 用户管理
GET    /api/v1/admin/stats            # 使用统计
```

### Agent API
```
POST/GET  /api/v1/agent/sessions              # 创建/列出会话
GET/DELETE  /api/v1/agent/sessions/:id        # 详情/删除
POST  /api/v1/agent/sessions/:id/chat | /files | /publish   # 对话/上传/发布
GET   /api/v1/agent/sessions/:id/messages | /article        # 历史/草稿
POST  /api/v1/agent/sessions/:id/regenerate    # 重新生成
```

---

## Agent 系统设计

### 引擎核心流程（`class AgentEngine`）

```python
async def process_message(message, files=None):
    # 1. 识别消息类型（链接/文件/文本）
    # 2. 调用相关 Skills（link_parser / file_parser / web_search / code_analyzer）
    # 3. 收集 Skill 结果 -> 构建 LLM prompt
    # 4. 调用 LLM 生成回复
    # 5. 从响应更新草稿（title/content/excerpt/summary）
```

### Skill 规范

每个 Skill 是 zip 包：`manifest.json`（配置）+ `handler.py`（入口函数）+ 可选 `requirements.txt` / `README.md`。

**manifest.json** 关键字段：`name`、`display_name`、`version`、`description`、`skill_type`、`entry`（如 `handler.py`）、`function`（如 `parse_link`）、`config`；服务端使用 `skill.json`（`_safe_skill_manifest` 校验 name，重复 name 则更新）。

**handler.py** 约定：接收 `(url 或文件路径, config)`，返回 `{title, content, author, publish_date, success}` 等结构化结果（`skill_type: prompt` 类型的 Skills 也可由 LLM 直接执行）。

---

## 设计规范

- **颜色**：Primary `#1a73e8`（Google Blue）、Secondary `#34a853`、Error `#ea4335`、Warning `#fbbc04`。
- **圆角** 8–12px；**阴影** Material 标准；**字体** Google Sans / Roboto。
- 组件 hover 上移 4px + 增强阴影，平滑过渡；TypeScript 类型安全、响应式、ARIA 无障碍。

---

## 注意事项

1. **Skills 安全**：用户上传的 Skills 需沙箱执行，防恶意代码。
2. **API Key 安全**：LLM API Key 只保存在服务端，不下发客户端。
3. **文件上传**：限制大小与类型。
4. **并发控制**：Agent 会话可能消耗大量 LLM tokens，需控并发。
5. **SEO**：前端需 SSR 或预渲染以提升 SEO。

---

## 常见问题

- **前端连不上后端**：检查 `web/.env` 的 `REACT_APP_API_BASE_URL`。
- **登录失败**：检查 `server/.env.local` 管理员账号。
- **数据库在哪/重置**：`server/insight.db`；删除后重启服务自动重建。
- **Agent 不工作**：当前仅 API 框架，Agent 引擎核心逻辑待实现。
