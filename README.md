# InSight（深度收藏 / 智能阅读生态）

InSight 是一套以 **"深度收藏 + AI 阅读"** 为核心的跨端产品生态，目前包含两大模块，共享同一套 FastAPI 云服务：

1. **深度收藏（InSight Cloud）** — 从网页/App 一键收藏文章，服务端自动提取正文并全文翻译成中文，分类归档随时阅读。
2. **InSight Blog** — 一个技术博客系统（React 前端 + 同一后端），支持手写技术博客与 AI Agent 辅助生成深度解读，并具备后台管理。

采用 **cloud-first** 架构：内容提取、翻译、生成都在服务端完成，客户端（Chrome 插件 / iOS App / React 前端）只负责交互与阅读。

---

## 核心能力

### 1. 深度收藏（Chrome 插件 + iOS App + Share Extension）

- **Chrome 插件**：一键保存当前页面 URL，选择分类目录；支持分类管理、最近收藏列表、注册/登录/记住密码、收藏统计。
- **iOS App**：SwiftUI + SwiftData（iOS 17+），分类管理（自定义图标/排序）、文章列表（分类筛选/全文搜索/分页）、阅读器（原文/译文双栏、字号可调）、未读/已读/星标标记。
- **Share Extension**：从 X、Safari 等任意 App 分享链接，直接选择分类保存。
- **稍后阅读**：未分类默认队列（📥）。
- **云服务**：FastAPI + SQLite；三级内容提取流水线 + 全文严格翻译（不总结、不提炼、不删减）；管理员控制台（用户审批、收藏统计、LLM 配置）。

### 2. InSight Blog（React 前端）

- **双模式发布**：富文本编辑器手写 / AI Agent 对话辅助生成。
- **两个板块**：项目沉淀（手写技术博客）、研究解读（基于链接/文件的 AI 深度解读）。
- **双阅读模式**：正文模式 / 一页纸解读。
- **AI Agent 系统**：可挂接第三方 Skills（zip 上传）、多 LLM 模型配置、文件上传解析、草稿实时预览。
- **后台管理**：内容发布/管理、分类管理、Skills 管理、模型管理等。

---

## 系统架构

```text
深度收藏:
Chrome 插件（chrome.storage.local） ─┐
iOS App（SwiftData） ────────────────┼── HTTPS ── InSight API ── SQLite
iOS Share Extension ────────────────┘              ├── 管理员控制台
                                                  └── vLLM 翻译服务
Blog:
React 前端（web/） ── HTTPS ── InSight API ── SQLite（同一后端）
```

- 内容提取流水线（服务端）：**trafilatura**（主）→ **BeautifulSoup**（备用）→ **LLM**（兜底）。
- 全文翻译：分段（6000 字符/段），严格保持原文结构和语气，不总结不提炼。
- LLM 代理：代理 OpenAI 兼容 vLLM 接口，强制 `temperature=0`、`enable_thinking=false`；**API Key 只保存在服务端，绝不下发客户端**。

---

## 目录结构

```text
ai-inslight/
├── start-all.sh       # ★ 一键启动（后端 :3002 + 前端 :3000）
├── stop-all.sh        # ★ 一键停止
├── insight/           # Chrome Manifest V3 插件（无需构建，直接加载已解压）
├── InsightIOS/        # SwiftUI + SwiftData iOS App + Share Extension
├── server/            # FastAPI + SQLite 云服务（单文件 main.py + blog_routes.py）
│   ├── app/main.py    # 主应用（收藏 + 博客 + Agent/Skills API）
│   ├── .venv / requirements.txt / Dockerfile / docker-compose.yml
│   └── install.sh / backup.sh / .env(.local/.example)
├── web/               # React 博客前端（web/README.md）
│   └── src/           # App、pages（Home/ArticleList/ArticleDetail/Login/admin/*）、services、types、contexts、utils
├── docs               # 设计图纸等
├── README.md          # 本文件（项目总入口）
├── BLOG_DEVELOPMENT.md# 博客系统设计 + 开发进度（开发必读）
├── CLAUDE.md          # Claude Code AI 开发指引
├── AGENTS.md          # Codex 等 AI 开发指引
└── LICENCE.md         # 商业源代码许可（BSL 1.1）
```

---

## 快速开始

### 1. 首次安装依赖（只需一次）

需要 Python 3.11+ 和 Node.js：

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 首次创建配置：cp .env.example .env.local，然后编辑 .env.local
cd ../web && npm install
```

编辑 `server/.env.local`，至少配置：

```dotenv
INSIGHT_SECRET=请替换为足够长的随机字符串
INSIGHT_ADMIN_EMAIL=admin@example.com
INSIGHT_ADMIN_PASSWORD=请替换为强密码
INSIGHT_LLM_BASE_URL=http://127.0.0.1:6018
INSIGHT_LLM_MODEL=你的模型名称
INSIGHT_LLM_API_KEY=你的API密钥
```

### 2. 一键启动（项目根目录）

```bash
./start-all.sh     # 同时启动后端(:3002) + 前端(:3000)
./stop-all.sh      # 同时停止
```

常用入口：

- 前端界面：`http://localhost:3000`
- 后端健康：`http://localhost:3002/health`（`/admin` 管理台，`/docs` OpenAPI）
- Blog API：`http://localhost:3002/api/v1/blog/...`

### 2. 加载 Chrome 插件

1. 打开 `chrome://extensions/` → 开启开发者模式。
2. “加载已解压的扩展程序” → 选择 `insight/` 目录。
3. 点击插件图标 → 设置服务器地址 → 注册 → 等管理员审批 → 登录 → 打开网页一键保存。

### 3. 运行 iOS App

1. 用 Xcode 创建 SwiftUI 项目，开启 SwiftData。
2. 配置 Bundle Identifier 与 App Groups（`group.com.sun.insight`）。
3. 主 App 添加 `InsightIOS/InsightIOS/` 源文件；新增 Share Extension target 并添加 `InsightIOS/InsightShare/`。
4. Signing & Capabilities 选择开发者 Team → Build & Run。模拟器用 `127.0.0.1`，真机用 Mac 局域网 IP。

### 4. 启动 Blog 前端

```bash
cd web
npm install
npm start                 # 开发服务器 http://localhost:3000
npm run build             # 生产构建，部署 build/
```

### Docker 启动（云服务）

```bash
cd server
cp .env.example .env      # 修改密钥、管理员密码、LLM 配置
docker compose up -d --build
docker compose ps
docker compose logs -f insight
```

---

## 内容处理流程

```
用户保存链接 → 去重检查 → status=pending
    ↓
后台任务: trafilatura 提取正文 → 成功 → status=translating
    ↓（失败则 BeautifulSoup 备用；仍失败则 LLM 从 HTML 提取）
LLM 全文翻译（分段，6000 字符/段）
    ↓
保存到数据库 → status=ready（失败则 failed）
```

- **严格翻译**：不总结、不提炼、不删减；保持段落、列表等原文结构和语气；专业术语保持准确。

---

## API 文档

### 认证 / 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册（状态 pending，需管理员审批） |
| POST | `/api/v1/auth/login` | 登录 → token |
| GET | `/api/v1/me` | 当前用户信息 |
| POST | `/api/v1/llm/chat` | LLM 代理（注入 temperature=0、enable_thinking=false） |

### 深度收藏（InSight）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/v1/insight/categories` | 分类列表 / 创建分类 |
| PUT | `/api/v1/insight/categories/reorder` | 排序分类 |
| PUT/DELETE | `/api/v1/insight/categories/{id}` | 更新 / 删除分类 |
| POST | `/api/v1/insight/articles/save` | 保存文章（异步提取+翻译） |
| GET | `/api/v1/insight/articles` | 文章列表（分类/状态/搜索/分页） |
| GET | `/api/v1/insight/articles/{id}` | 文章详情（自动标记已读） |
| PATCH/DELETE | `/api/v1/insight/articles/{id}` | 更新（分类/已读/星标）/ 删除 |
| GET | `/api/v1/insight/stats` | 统计信息 |

### Blog（公开）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/blog/articles` | 文章列表 |
| GET | `/api/v1/blog/articles/{id}` | 文章详情 |
| GET | `/api/v1/blog/sections` | 板块列表 |
| GET | `/api/v1/blog/categories` | 分类列表 |
| GET | `/api/v1/blog/featured` | 精选文章 |
| GET | `/api/v1/blog/latest` | 最新文章 |

### Blog（后台 / Agent / Skills）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST/PUT/DELETE | `/api/v1/admin/articles` | 文章管理 |
| PATCH | `/api/v1/admin/articles/{id}/publish` `/unpublish` | 发布/取消发布 |
| GET/POST/PUT/DELETE | `/api/v1/admin/categories` `/admin/sections` | 分类/板块管理 |
| POST/GET/DELETE | `/api/v1/agent/sessions...` | Agent 会话、对话、文件 |
| GET/POST/PUT/DELETE | `/api/v1/admin/skills` | Skills 上传与管理 |
| GET/PUT | `/api/v1/admin/llm` | LLM 配置 |
| GET/PATCH | `/api/v1/admin/users` | 用户管理 |
| GET | `/api/v1/admin/stats` | 使用统计 |

---

## 文档导航（AI 开发者从这几份开始）

| 文档 | 内容 | 面向 |
|------|------|------|
| **README.md** | 项目全貌、特性、架构、快速开始、API | 所有人 / 用户 |
| **BLOG_DEVELOPMENT.md** | 博客系统详细设计、数据库、进度 | 开发博客的人 |
| **CLAUDE.md** | 服务器/插件/iOS 代码约定、环境变量 | Claude Code |
| **AGENTS.md** | 仓库布局与开发约定 | Codex |
| **web/README.md** | 博客前端开发指南 | 前端开发者 |
| **LICENCE.md** | 许可证 | — |

---

## 常见问题

- **手机连不上本地服务**：手机与 Mac 同一网络；填 Mac 局域网 IP（`ipconfig getifaddr en0`）而非 `127.0.0.1`；确认 `--host 0.0.0.0` 启动；检查 macOS 防火墙。
- **注册后无法登录**：新账号默认 `pending`，需在 `/admin` 批准为 `approved`。
- **改代码后 Chrome 没变化**：`chrome://extensions/` 里刷新插件，必要时关闭重开（MV3 service worker 缓存）。
- **文章提取失败**：三级策略 trafilatura → BeautifulSoup → LLM 全失败则标记 `failed`。
- **前端连不上后端**：检查 `web/.env` 的 `REACT_APP_API_BASE_URL`。
- **重置数据库**：删除 `server/insight.db` 后重启服务自动重建。

---

## License

本项目使用 **Business Source License 1.1**。个人、学术和非营利用途可按许可证使用；商业用途需单独授权。详见 [LICENCE.md](./LICENCE.md)。
# ai-insight
