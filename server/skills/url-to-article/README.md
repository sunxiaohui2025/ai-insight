# URL 转文章提取器 Skill

一个用于「URL → 结构化素材」的 skill：抓取 URL（X 平台推文、技术博客、新闻等），
解析出正文、元数据、媒体与语言，输出原始素材；再由宿主 agent 参照 `prompts/`
模板生成中文译文、完整文章 HTML 与一页纸解读。

> **分工原则**：本 skill **只做抓取与解析，内部不直连任何大模型**。
> 所有 LLM 任务由宿主 agent 完成（模型能力由 agent 提供），
> 因此代码内不硬编码、不提交任何模型地址 / 名称 / API 密钥，可安全提交到公共仓库。

## 功能特点

✅ **智能内容提取** - 自动识别并提取正文，去除广告 / 导航 / 登录墙等杂质
✅ **媒体保留** - 保留图片与视频链接
✅ **语言检测** - 自动检测正文语言（解析逻辑，非 LLM）
✅ **备用方案** - 遇到 X 登录墙时自动切换到 fxtwitter JSON API
✅ **输出原始素材** - JSON + Markdown 双格式，便于宿主 agent 后续加工
✅ **LLM 交给 agent** - 翻译 / HTML / Banner 由宿主 agent 参照 `prompts/` 完成

## 系统架构（分工）

```
输入 URL
  ↓  [skill: 抓取 + 解析]
抓取页面 (Playwright + 备用服务)
  ↓  [skill: 提取]
提取正文 / 元数据 / 媒体 / 语言
  ↓  [skill: 保存]
输出 output/extract_*.{json,md} 原始素材
  ↓  [宿主 agent: 参照 prompts/ 模板]
翻译 / 推文串整合 / 完整文章 HTML / 一页纸解读 / Banner
```

## 技术栈

- **抓取**: Playwright（浏览器自动化）+ fxtwitter/vxtwitter（备用）
- **解析**: BeautifulSoup4, lxml, trafilatura
- **语言检测**: langdetect
- **LLM**: 由宿主 agent 提供（skill 内不配置、不直连）

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### 宿主 agent 环境（推荐）

宿主 agent 用 `run_skill.py` 的 `generate` / `run` 入口调用（该文件位于 skill 根目录，
已解决 `src/main.py` 无法作为脚本入口导入的问题）：

```python
import run_skill
result = run_skill.generate(url="https://x.com/username/status/123456789")
```

### 命令行使用

```bash
# 经 run_skill.py 入口
python run_skill.py "https://x.com/username/status/123456789"
# 或直接运行模块
python -m src.main "https://x.com/username/status/123456789"
```

### Python API 使用

```python
from src.main import ArticleExtractor

extractor = ArticleExtractor()
result = extractor.process_url(url="https://x.com/username/status/123456789", save_to_file=True)

print("平台:", result["platform"])
print("语言:", result["language"])
print("素材文件:", result["saved_files"])
```

## 输出示例

skill 处理后会在 `output/` 生成：

```
output/
├── extract_123456789_20260818_101112.json   # 结构化提取结果
└── extract_123456789_20260818_101112.md     # 易读的 Markdown 素材
```

宿主 agent 依据上述素材，参照 `prompts/` 模板生成成品：

| 成品 | 说明 |
|------|------|
| 完整文章 HTML | Medium 风格，保留全部内容与图片 |
| 一页纸解读 HTML | 现代化 Tech 主题、卡片布局、顶部 16:9 Banner |
| Banner SVG | Anthropic 风格手绘插画（16:9） |
| 中英翻译 | 英文内容翻译成中文 |

## 配置

本 skill 不硬编码任何 LLM 模型。运行参数（浏览器无头、输出目录等）在 `src/config.py` 中调整：

```python
    # X 平台配置
    X_HEADLESS = True   # True=无头模式(后台运行不弹窗), False=显示浏览器
    X_TIMEOUT = 30000   # 超时时间（毫秒）

    # 输出配置
    OUTPUT_DIR = "./output"  # 保存目录
```

## 工作原理

### 1. 内容抓取
- **主方案**: 使用 Playwright 浏览器自动化直接访问 X
- **备用方案**: 遇到登录墙时自动切换到 fxtwitter/vxtwitter 服务

### 2. 内容提取
- 识别推文 / 正文元素，去除广告、评论等杂质
- 提取正文、元数据（作者、时间）、媒体（图片、视频）

### 3. 语言检测
- 使用 langdetect 检测语言（解析逻辑，非 LLM）

### 4. 保存素材 + agent 加工
- 保存 `output/extract_*` 原始素材
- 宿主 agent 参照 `prompts/` 模板完成翻译与 HTML / Banner 生成

## 项目结构

```
url-to-article/
├── run_skill.py               # skill 根目录入口（导出 generate/run，供宿主 agent 脚本运行器调用）
├── src/
│   ├── config.py              # 配置管理（无 LLM 硬编码凭据）
│   ├── main.py                # 抓取 + 提取 + 保存素材
│   ├── fetchers/
│   │   ├── x_fetcher.py       # X 平台（Playwright）
│   │   ├── x_fetcher_backup.py# X 备用方案（fxtwitter）
│   │   └── generic_fetcher.py # 通用网页
│   └── extractors/
│       ├── x_extractor.py     # X 平台内容解析
│       └── generic_extractor.py # 通用网页内容解析
├── prompts/                   # 宿主 agent 生成内容所用的 LLM 提示词模板
├── output/                    # 输出素材目录（被 .gitignore 排除）
├── requirements.txt           # Python 依赖
└── README.md                  # 本文档
```

## 限制与注意事项

- 目前支持 X (Twitter) 与通用网页
- Playwright 首次运行会下载浏览器（约 100MB）
- X 平台有严格访问限制，必要时会使用备用方案
- 本 skill 不直连大模型，LLM 由宿主 agent 完成

## 扩展开发

1. 在 `fetchers/` 添加新的抓取器
2. 在 `extractors/` 添加对应的提取器
3. 在 `main.py` 中注册新平台

## License

MIT License
# url-to-article
