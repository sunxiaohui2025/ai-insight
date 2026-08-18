# InSight Blog 前端

基于 React + TypeScript + Material UI 的博客系统前端。

## 功能架构

### 已完成的前端页面和组件

#### 公开展示页面
- ✅ **首页** (`/`) - 展示最新文章、项目沉淀精选、研究解读精选
- ✅ **项目沉淀** (`/projects`) - 项目技术博客列表，支持分类筛选和搜索
- ✅ **研究解读** (`/insights`) - 第三方链接解析的技术博客列表
- ✅ **文章详情** (`/article/:id`) - 支持正文和一页纸解读两种阅读模式
- ✅ **登录页面** (`/login`) - 管理员登录

#### 后台管理页面
- ✅ **管理布局** - 侧边栏导航
- ✅ **概览** (`/admin`) - 统计面板
- 🚧 **内容发布** (`/admin/publish`) - 富文本编辑器 + AI Agent 辅助创作
- 🚧 **内容管理** (`/admin/articles`) - 文章列表、编辑、删除
- 🚧 **分类管理** (`/admin/categories`) - 板块和分类管理
- 🚧 **Agent 配置** (`/admin/agent`) - Agent 会话管理
- 🚧 **Skills 管理** (`/admin/skills`) - Skills 上传和配置
- 🚧 **模型管理** (`/admin/models`) - LLM 模型配置
- 🚧 **用户管理** (`/admin/users`) - 用户审批和管理

#### 核心组件
- ✅ **Navbar** - 顶部导航栏
- ✅ **ArticleCard** - 文章卡片组件（Material Design 风格）
- ✅ **AdminLayout** - 后台管理布局
- ✅ **AgentChat** - AI Agent 对话组件（核心功能）

### API 服务层
- ✅ 认证 API (authApi)
- ✅ 公开博客 API (blogApi)
- ✅ 后台文章管理 API (adminArticleApi)
- ✅ 后台分类管理 API (adminCategoryApi)
- ✅ 后台板块管理 API (adminSectionApi)
- ✅ 后台用户管理 API (adminUserApi)
- ✅ Agent API (agentApi)
- ✅ Skills 管理 API (skillApi)
- ✅ 模型管理 API (modelApi)

### 状态管理
- ✅ AuthContext - 用户认证状态管理

### 主题和样式
- ✅ Material Design 主题配置
- ✅ Google 风格的颜色和组件样式

## 技术栈

- **React 19** + **TypeScript**
- **Material UI** - UI 组件库（Google Material Design 风格）
- **React Router v6** - 路由管理
- **Axios** - HTTP 客户端
- **React Markdown** - Markdown 渲染
- **TipTap** - 富文本编辑器

## 开发指南

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm start
```

访问 http://localhost:3000

### 环境变量配置

创建 `.env` 文件：

```
REACT_APP_API_BASE_URL=http://localhost:8000
```

### 构建生产版本

```bash
npm run build
```

## 待开发页面（优先级）

### 高优先级
1. **内容发布页面** (`/admin/publish`)
   - 富文本编辑器模式
   - AI Agent 辅助创作模式（左侧对话，右侧预览）
   - 分类选择、标签输入
   - 发布/保存草稿功能

2. **内容管理页面** (`/admin/articles`)
   - 文章列表表格
   - 筛选（状态、分类、日期）
   - 编辑/删除操作
   - 批量操作

3. **Agent 配置页面** (`/admin/agent`)
   - 创建新会话
   - 会话列表
   - 进入 AgentChat 对话界面

### 中优先级
4. **分类管理页面** (`/admin/categories`)
   - 板块列表
   - 分类树形结构展示
   - 创建/编辑/删除分类
   - 排序功能

5. **Skills 管理页面** (`/admin/skills`)
   - Skills 列表
   - 上传 Skill（zip 文件）
   - 启用/禁用 Skills
   - 配置 Skill 参数

6. **模型管理页面** (`/admin/models`)
   - LLM 模型列表
   - 添加/编辑/删除模型
   - 设置默认模型
   - API Key 安全输入

### 低优先级
7. **用户管理页面** (`/admin/users`)
   - 用户列表
   - 审批用户
   - 修改用户状态

## 设计规范

### Material Design 风格
- 使用 Material UI 组件
- 圆角卡片布局（borderRadius: 8-12px）
- 阴影效果：`0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15)`
- 颜色：
  - Primary: `#1a73e8` (Google Blue)
  - Secondary: `#34a853` (Google Green)
  - Error: `#ea4335` (Google Red)
  - Warning: `#fbbc04` (Google Yellow)

### 排版
- 字体：Google Sans / Roboto
- 标题权重：500-600
- 按钮文字不大写（textTransform: 'none'）

### 交互
- 卡片 hover 效果：上移 4px + 增强阴影
- 平滑过渡动画
- 点击反馈

## 目录结构

```
src/
├── components/          # 公共组件
│   ├── Navbar.tsx
│   ├── ArticleCard.tsx
│   └── AdminLayout.tsx
├── pages/              # 页面组件
│   ├── Home.tsx
│   ├── ArticleList.tsx
│   ├── ArticleDetail.tsx
│   ├── Login.tsx
│   └── admin/          # 后台管理页面
│       ├── Dashboard.tsx
│       └── AgentChat.tsx
├── services/           # API 服务
│   └── api.ts
├── types/             # TypeScript 类型定义
│   └── index.ts
├── contexts/          # React Context
│   └── AuthContext.tsx
├── utils/             # 工具函数
│   └── theme.ts
├── App.tsx            # 主应用
└── index.tsx          # 入口文件
```

## 后端 API 状态

### 已实现
- ✅ 用户认证 (`/api/v1/auth/*`)
- ✅ 公开文章列表 (`/api/v1/blog/articles`)
- ✅ 文章详情 (`/api/v1/blog/articles/:id`)
- ✅ 板块列表 (`/api/v1/blog/sections`)
- ✅ 分类列表 (`/api/v1/blog/categories`)
- ✅ 精选文章 (`/api/v1/blog/featured`)
- ✅ 最新文章 (`/api/v1/blog/latest`)
- ✅ 后台文章管理 (`/api/v1/admin/articles/*`)
- ✅ 后台分类管理 (`/api/v1/admin/categories/*`)
- ✅ 后台板块管理 (`/api/v1/admin/sections/*`)
- ✅ Agent 会话管理 (`/api/v1/agent/sessions/*`)
- ✅ Skills 管理 (`/api/v1/admin/skills/*`)
- ✅ 用户管理 (`/api/v1/admin/users/*`)

### Agent 功能
- ✅ 创建会话
- ✅ 发送消息
- ✅ 上传文件
- ✅ 获取对话历史
- ✅ 生成文章草稿
- ✅ 发布文章
- 🚧 Skills 执行引擎（需要实现具体的 Skills）

## 下一步开发建议

1. 完成**内容发布页面**，这是核心功能
2. 实现**Agent 对话**的完整流程
3. 完善**内容管理页面**
4. 添加**文章编辑**功能
5. 实现**Skills 上传和管理**界面

## 注意事项

- 所有管理页面需要管理员权限
- API 请求自动添加 Bearer Token
- 401 错误自动跳转登录页
- 文件上传使用 FormData
- Agent 对话支持实时更新（可考虑 WebSocket）
