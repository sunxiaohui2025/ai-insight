# CLAUDE.md

本文件为 Claude Code 在处理本仓库（url-to-article skill）时提供指引。

## 项目定位

这是一个「URL 转文章」skill：抓取网页/推文 → 提取正文与元数据，
再由宿主 agent 参照 `prompts/` 模板完成翻译、完整文章 HTML、一页纸解读与 Banner。

**架构原则**：
- skill 只保留「抓取 + 解析」逻辑，内部不直连任何大模型；
- LLM 任务全部由宿主 agent 完成（模型能力由 agent 提供），
- 因此仓库内不得硬编码、也不得提交任何模型地址 / 名称 / API 密钥。

## 目录结构

```
run_skill.py           # skill 根目录入口（导出 generate/run，供宿主 agent 脚本运行器调用）
src/
├── config.py           # 配置（无任何 LLM 硬编码凭据）
├── main.py             # 抓取 + 提取 + 保存原始素材
├── fetchers/
│   ├── x_fetcher.py          # X 平台（Playwright）
│   ├── x_fetcher_backup.py   # X 备用方案（fxtwitter JSON API）
│   └── generic_fetcher.py    # 通用网页
└── extractors/
    ├── x_extractor.py        # X 平台内容解析
    └── generic_extractor.py  # 通用网页内容解析
prompts/                # 宿主 agent 生成内容所用的 LLM 提示词模板
output/                 # 输出目录（被 .gitignore 排除）
```

## 常用命令

```bash
# 宿主 agent 经脚本运行器调用（推荐）：
#   result = run_skill.generate(url="<URL>")

# 抓取并提取（保存原始素材到 output/）
python run_skill.py "<URL>"        # 等价 python -m src.main "<URL>"

# 运行环境
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 数据流

1. 识别平台（x.com / generic）
2. 抓取页面（X 有登录墙时自动回退到 fxtwitter 备用方案）
3. 提取内容（正文、元数据、媒体、语言）
4. 保存为 `output/extract_<id>_<ts>.{json,md}` 原始素材
5. 宿主 agent 读取素材，按 `prompts/` 模板生成：
   - 推文串整合 / 中英翻译
   - 完整文章 HTML（Medium 风格）
   - 一页纸解读 HTML（顶部 16:9 Banner）
   - Banner SVG（Anthropic 风格手绘插画）

## 安全红线

- 严禁在代码或文档中硬编码/提交任何 LLM 服务地址、模型名、API 密钥。
- 敏感配置一律走环境变量或宿主 agent 注入；`.env` 已被 `.gitignore` 排除。
- 提交公共仓库前，用 `grep` 检查是否残留内网地址 / 模型 / 密钥（见下方检查命令）。

```bash
grep -rniE "api[_-]?key|token|secret|http://[0-9]+\.[0-9]+" --include="*.py" --include="*.md" .
```

## 工作方式

- **改前先想**：说明假设，有疑问先问。
- **简洁优先**：最小改动，不做投机性功能。
- **精准改动**：只动必要的部分，贴合现有风格。
- **目标驱动**：对照 README.md / SKILL.md 的验收标准验证。
