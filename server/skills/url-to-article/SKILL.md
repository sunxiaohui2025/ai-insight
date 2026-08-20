# URL 转文章提取器 Skill

将任何 URL（X 平台推文、技术博客等）抓取、解析为结构化素材，再由宿主 agent
基于这些素材生成精美的中文文章和一页纸总结。

> **分工原则**：本 skill 只负责「抓取 + 解析」，内部**不直连任何大模型**。
> 翻译、推文串整合、HTML 生成、Banner 等 LLM 任务全部由宿主 agent 完成
> （模型能力由 agent 提供），并参照 `prompts/` 目录下的模板执行。
> 因此仓库内不硬编码、不提交任何模型地址 / 名称 / API 密钥。

## 功能描述

- 从 X (Twitter) 平台和普通网页抓取内容
- 提取正文、元数据、媒体资源，并自动检测语言
- 自动去除广告、导航、登录墙等杂质（遇到登录墙自动回退备用方案）
- 将提取结果保存为 JSON + Markdown 素材（`output/extract_*.{json,md}`）
- 宿主 agent 基于素材进一步生成：
  - 推文串整合 / 中英翻译
  - 完整文章 HTML（Medium 风格）
  - 一页纸解读 HTML（顶部 16:9 banner + 长文解读排版）

## 使用方法

### 宿主 agent 环境（推荐，脚本运行器）

宿主 agent 通过 `run_skill.py`（skill 根目录入口，导出 `generate`/`run`）调用：

```python
# run_skill.generate / run 接收 url 参数，返回提取结果与素材路径
result = run_skill.generate(url="https://x.com/hwchase17/status/2085780032031760694")
```

```bash
# 等价命令行
python run_skill.py "<URL>"
```

> `run_skill.py` 会把 skill 根目录加入 sys.path，从而解决
> `src/main.py` 无法作为入口导入的问题（`No module named 'src'`）。

### 终端直接运行（本地调试）

```bash
python -m src.main "<URL>"
```

两种方式运行后都会得到原始素材（`output/extract_*.json` 与 `output/extract_*.md`），
宿主 agent 读取素材并按 `prompts/` 模板生成最终成品。

## 输出说明

skill 每次运行在 `output/` 目录生成：

1. **extract_[id]_[timestamp].json** - 结构化提取结果
   - URL、平台、标题、作者、发布时间、语言、媒体、正文/推文

2. **extract_[id]_[timestamp].md** - 易读的 Markdown 素材
   - 宿主 agent 生成内容的输入源（正文、推文串、媒体列表、元数据）

宿主 agent 依据素材生成的成品：
- **完整文章 HTML** - Medium 风格的现代设计，保留全部内容与图片
- **一页纸解读 HTML** - 现代化 Tech 主题：#F8FAFC 背景、主色 #2563EB、
  卡片式布局、圆角与微阴影、一句话总结、亮点卡片、对比表、Callout、
  "这意味着什么"结尾，顶部为 16:9 Banner，整体 1-3 屏/页
- **Banner SVG / 分享图** - Anthropic 风格手绘插画（16:9）

## 环境要求

### 依赖安装

```bash
pip install -r requirements.txt
playwright install chromium
```

### 配置

- 无需也不允许在代码中配置任何 LLM 模型（地址 / 名称 / 密钥一律不硬编码）
- 浏览器无头、输出目录等运行参数在 `src/config.py` 中配置

## 技术特点

### 智能抓取
- **X 平台**：Playwright 优先，失败时回退到 fxtwitter JSON API
  - JSON API 能拿到 X Article 长文全文（`article.content.blocks`）和长推文
- **普通网页**：自动识别正文，过滤杂质

### 解析
- BeautifulSoup4 / trafilatura 提取正文、元数据与媒体
- langdetect 检测语言（解析逻辑，非 LLM）

### LLM 由宿主 agent 完成（prompts/）
- `prompts/x_thread.md`：推文串整合
- `prompts/translate.md`：翻译
- `prompts/full_article_html.md`：完整文章 HTML
- `prompts/summary_html.md`：一页纸解读 HTML
- `prompts/banner_svg.md`：16:9 Banner SVG

### 容错机制
- 遇到登录墙自动切换备用方案
- 多种内容提取策略
- 完善的错误处理

## 支持的平台

- ✅ X (Twitter) - 单条推文和推文串
- ✅ 技术博客（Medium、个人博客等）
- ✅ 新闻网站
- ✅ 文档和教程网站
- ✅ 任何包含文章内容的网页

## 技术架构

```
run_skill.py           # skill 根目录入口（导出 generate/run，供宿主 agent 脚本运行器调用）
src/
├── config.py          # 配置管理（无任何 LLM 硬编码凭据）
├── main.py            # 抓取 + 提取 + 保存素材
├── fetchers/          # 内容抓取器
│   ├── x_fetcher.py          # X 平台（Playwright）
│   ├── x_fetcher_backup.py   # X 备用方案（fxtwitter）
│   └── generic_fetcher.py    # 通用网页
└── extractors/        # 内容提取器
    ├── x_extractor.py        # X 平台内容解析
    └── generic_extractor.py  # 通用网页内容解析
prompts/               # 宿主 agent 生成内容所用的 LLM 提示词模板
output/                # 输出素材目录（被 .gitignore 排除）
```

## 注意事项

1. 首次运行需要下载 Chromium 浏览器（`playwright install chromium`）
2. 本 skill 不直连大模型，LLM 由宿主 agent 完成，无需配置任何模型
3. 某些网站可能有反爬虫机制
4. 生成的素材可直接在浏览器中打开或由 agent 继续加工

## 扩展开发

可以轻松扩展支持更多平台：
1. 在 `fetchers/` 添加新的抓取器
2. 在 `extractors/` 添加对应的提取器
3. 在 `main.py` 中注册新平台

## License

MIT
