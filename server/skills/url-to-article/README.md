# URL 转文章提取器 (X 平台专用)

一个强大的 AI 驱动工具，可以从 X (Twitter) 链接中提取内容，翻译成中文，并生成美观的 HTML 文章和一页纸总结。

## 功能特点

✅ **智能内容提取** - 自动识别并提取推文内容，去除无关信息
✅ **自动翻译** - 检测英文内容并自动翻译成中文
✅ **双重输出** - 生成完整文章 HTML 和一页纸总结 HTML
✅ **媒体保留** - 保留图片和视频链接
✅ **备用方案** - 遇到登录墙时自动切换到第三方服务
✅ **美观排版** - 现代化、响应式的 HTML 设计

## 系统架构

```
输入 URL
  ↓
抓取页面 (Playwright + 备用服务)
  ↓
提取内容 (BeautifulSoup)
  ↓
检测语言 & 翻译 (your-model)
  ↓
生成完整文章 HTML (your-model)
  ↓
生成一页纸总结 HTML (your-model)
  ↓
保存到本地文件
```

## 技术栈

- **抓取**: Playwright (浏览器自动化) + fxtwitter/vxtwitter (备用)
- **解析**: BeautifulSoup4, lxml, trafilatura
- **LLM**: your-model (本地部署)
- **语言检测**: langdetect

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 安装 Playwright 浏览器：
```bash
playwright install chromium
```

## 使用方法

### 命令行使用

```bash
python -m src.main "https://x.com/username/status/123456789"
```

### Python API 使用

```python
from src.main import ArticleExtractor

extractor = ArticleExtractor()
result = extractor.process_url(
    url="https://x.com/username/status/123456789",
    save_to_file=True
)

print(f"成功! 文章已保存到: {result['saved_files']['full_article']}")
```

## 输出示例

处理一个 X 链接后，会生成以下文件：

```
output/
├── article_123456789_20260808_123456.html    # 完整文章
├── summary_123456789_20260808_123456.html    # 一页纸总结
└── metadata_123456789_20260808_123456.json   # 元数据
```

### 完整文章 HTML
- 现代、简洁的 Medium 风格设计
- 包含标题、作者、日期等元数据
- 保留所有原文内容和图片
- 支持代码高亮和响应式布局

### 一页纸总结 HTML
- 提炼核心观点和技术要点
- 卡片式、紧凑的设计
- 包含主要内容、技术亮点、总结与启示
- 适合快速理解文章精髓

## 配置

编辑 `src/config.py` 来修改配置：

```python
class Config:
    # LLM 配置
    KIMI_API_BASE = "http://your-llm-server:port/v1/chat/completions"
    KIMI_MODEL = "your-model"
    KIMI_API_KEY = "your-api-key"
    
    # X 平台配置
    X_HEADLESS = False  # True=无头模式, False=显示浏览器
    X_TIMEOUT = 30000   # 超时时间（毫秒）
    
    # 输出配置
    OUTPUT_DIR = "./output"  # 保存目录
```

## 工作原理

### 1. 内容抓取
- **主方案**: 使用 Playwright 浏览器自动化直接访问 X
- **备用方案**: 如果遇到登录墙，自动切换到 fxtwitter/vxtwitter 服务

### 2. 内容提取
- 识别推文元素（文本、图片、视频）
- 去除导航栏、广告、评论等杂质
- 提取元数据（作者、时间等）

### 3. 内容处理
- 检测语言（英文/中文等）
- 如果是英文，调用 your-model 翻译成中文
- 整合推文串（如果有多条）

### 4. HTML 生成
- 调用 your-model 生成美观的完整文章 HTML
- 调用 your-model 生成一页纸总结 HTML
- 保存到本地文件

## 测试示例

```bash
# 测试提供的链接
python -m src.main "https://x.com/hwchase17/status/2085780032031760694"
```

输出：
```
============================================================
开始处理 URL: https://x.com/hwchase17/status/2085780032031760694
============================================================

识别平台: x.com

[步骤 1/6] 抓取页面内容...
[步骤 2/6] 提取推文内容...
[步骤 3/6] 整合推文内容...
[步骤 4/6] 检查是否需要翻译...
[步骤 5/6] 生成完整文章 HTML...
[步骤 6/6] 生成一页纸总结 HTML...

============================================================
处理完成！
============================================================

处理结果摘要:
  - 平台: x.com
  - 语言: en
  - 已翻译: True
  - 推文数: 1
  - 保存文件:
    * full_article: /path/to/output/article_*.html
    * summary: /path/to/output/summary_*.html
    * metadata: /path/to/output/metadata_*.json
```

## 项目结构

```
explain-url-to-article/
├── src/
│   ├── config.py              # 配置管理
│   ├── fetchers/
│   │   ├── x_fetcher.py      # Playwright 抓取器
│   │   └── x_fetcher_backup.py # 备用抓取器
│   ├── extractors/
│   │   └── x_extractor.py    # 内容提取器
│   ├── llm_client.py         # Kimi API 客户端
│   ├── llm_services.py       # LLM 服务层
│   └── main.py               # 主入口
├── output/                    # 输出目录
├── requirements.txt          # Python 依赖
└── README.md                 # 本文档
```

## 限制与注意事项

- 目前仅支持 X (Twitter) 平台
- 需要稳定的网络连接
- Playwright 首次运行会下载浏览器（约 100MB）
- X 平台有严格的访问限制，建议使用备用方案
- LLM API 调用需要一定时间（约 10-30 秒）

## 未来扩展

- [ ] 支持更多平台（知乎、微博、Medium 等）
- [ ] 支持推文串的完整提取
- [ ] 添加 PDF 输出格式
- [ ] 支持批量处理
- [ ] 添加缓存机制
- [ ] 支持自定义 HTML 模板

## 开发测试

```bash
# 测试抓取器
python test_fetch.py

# 测试备用抓取器
python test_backup.py
```

## License

MIT License

## 作者

由 Claude (Opus 5) 开发
