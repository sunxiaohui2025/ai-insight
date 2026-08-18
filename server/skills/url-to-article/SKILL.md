# URL 转文章提取器 Skill

将任何 URL（X 平台推文、技术博客等）转换为精美的中文文章和一页纸总结。

## 功能描述

这是一个智能内容提取和转换工具，可以：
- 从 X (Twitter) 平台和普通网页抓取内容
- 自动检测语言并将英文翻译成中文
- 生成两种格式的 HTML 输出：
  - 完整文章（Medium 风格）
  - 一页纸解读（顶部 16:9 banner + 长文解读排版）
- 保留所有图片和视频
- 自动去除广告、导航等杂质内容

## 使用方法

### 基本用法

```bash
python -m src.main "<URL>"
```

### 示例

```bash
# 处理 X 平台推文
python -m src.main "https://x.com/hwchase17/status/2085780032031760694"

# 处理普通网页
python -m src.main "https://www.kimi.com/blog/kimi-k3"

# 处理技术博客
python -m src.main "https://example.com/article"
```

## 输出说明

每次运行会在 `output/` 目录生成以下文件：

1. **article_[id]_[timestamp].html** - 完整文章
   - Medium 风格的现代设计
   - 包含所有内容、图片和视频
   - 如果原文是英文，显示中文翻译

2. **summary_[id]_[timestamp].html** - 一页纸解读
   - 顶部是一张 16:9 的 banner（内联 SVG）
   - 正文是对原文的高度提炼和解读，1200–2500 字
   - 不限制在一屏内，页面可滚动，排版以易读为准
   - 包含 TL;DR、3–6 个章节、数据表格、"这意味着什么"结尾

3. **banner_[id].svg** - 16:9 Banner 源文件（Anthropic 风格手绘插画）

4. **banner_summary_[id].png** - 一页纸 banner 区域截图（1440×810，用于分享）

5. **banner_article_[id].[ext]** - 从原文提取的配图（如果原文有合适尺寸的图片）

6. **metadata_[id]_[timestamp].json** - 元数据
   - URL、标题、语言等信息
   - 图片和视频数量统计

### 关于"一页纸"

"一页纸"指的是"一篇就够"的解读文章，不是把内容压缩到一屏之内。
目标是读者读完这一篇就掌握原文全部要点，不必回头读原文。

## 环境要求

### 依赖安装

```bash
pip install -r requirements.txt
playwright install chromium
```

### 配置

在 `src/config.py` 中配置：
- LLM API 地址和密钥（用于翻译和 HTML 生成）
- 输出目录路径
- 浏览器设置

## 技术特点

### 智能抓取
- **X 平台**：Playwright 优先，失败时回退到 fxtwitter JSON API
  - JSON API 能拿到 X Article 长文全文（`article.content.blocks`）和长推文，
    而 `og:description` 会被 X 截断到 200 字符左右
- **普通网页**：自动识别正文，过滤杂质

### AI 驱动
- 使用 your-model 模型进行翻译（服务端上下文 1M tokens）
- 显式设置 `max_tokens`（默认 64000），避免长 HTML 被截断
- 输出触及长度上限时会打印告警，便于定位内容不全
- LLM 生成美观的 HTML 页面和 16:9 SVG banner

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

## 适用场景

1. **技术学习** - 保存和整理技术文章
2. **内容归档** - 将网页内容永久保存
3. **知识管理** - 提炼关键信息
4. **快速浏览** - 一页纸总结快速了解内容
5. **语言学习** - 中英对照阅读

## 示例输出

### X 平台推文
输入：`https://x.com/hwchase17/status/2085780032031760694`

输出：
- 提取推文内容："Why managed agents are the next big thing..."
- 翻译成中文
- 生成完整文章和一页纸总结

### 技术博客
输入：`https://www.kimi.com/blog/kimi-k3`

输出：
- 提取 17,647 字符的正文内容
- 保留 7 张图片
- 翻译成中文并生成精美 HTML

## 技术架构

```
src/
├── config.py          # 配置管理
├── llm_client.py      # LLM API 客户端
├── llm_services.py    # LLM 服务层（翻译、生成 HTML）
├── main.py            # 主入口和流程编排
├── fetchers/          # 内容抓取器
│   ├── x_fetcher.py          # X 平台（Playwright）
│   ├── x_fetcher_backup.py   # X 备用方案（fxtwitter）
│   └── generic_fetcher.py    # 通用网页
└── extractors/        # 内容提取器
    ├── x_extractor.py        # X 平台内容解析
    └── generic_extractor.py  # 通用网页内容解析
```

## 注意事项

1. 首次运行需要下载 Chromium 浏览器（`playwright install chromium`）
2. 需要配置有效的 LLM API 密钥
3. 某些网站可能有反爬虫机制
4. 生成的 HTML 文件可以直接在浏览器中打开查看

## 扩展开发

可以轻松扩展支持更多平台：
1. 在 `fetchers/` 添加新的抓取器
2. 在 `extractors/` 添加对应的提取器
3. 在 `main.py` 中注册新平台

## License

MIT
