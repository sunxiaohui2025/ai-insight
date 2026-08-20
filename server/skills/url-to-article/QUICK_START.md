# 快速开始指南

## 一分钟上手

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 运行抓取 + 提取
```bash
python -m src.main "https://x.com/hwchase17/status/2085780032031760694"
```

### 3. 查看素材
生成的文件在 `output/` 目录：
- `extract_*.json` - 结构化提取结果（正文、元数据、媒体、语言）
- `extract_*.md` - 易读的 Markdown 素材

宿主 agent 会读取这些素材，参照 `prompts/` 模板生成最终成品：
- 完整文章 HTML（Medium 风格）
- 一页纸解读 HTML（顶部 16:9 Banner）
- 中英翻译 / 推文串整合

## 使用你自己的 URL

```bash
python -m src.main "你的X链接或文章URL"
```

例如：
```bash
python -m src.main "https://x.com/username/status/1234567890"
```

## Python API 使用

```python
from src.main import ArticleExtractor

# 创建提取器（skill 只做抓取 + 解析，不直连大模型）
extractor = ArticleExtractor()

# 处理 URL
result = extractor.process_url(
    url="https://x.com/username/status/123456789",
    save_to_file=True
)

# 查看结果
print(f"平台: {result['platform']}")
print(f"语言: {result['language']}")
print(f"文件保存位置:")
for key, path in result['saved_files'].items():
    print(f"  {key}: {path}")
```

## 配置说明

本 skill **不需要也不允许**配置任何 LLM 模型——模型由宿主 agent 提供，
翻译 / HTML 生成等 LLM 任务直接由 agent 完成（见 `prompts/` 模板）。

运行参数（浏览器、输出等）在 `src/config.py` 中调整：

```python
# X 平台配置
X_HEADLESS = False  # True=无头模式, False=显示浏览器

# 输出配置
OUTPUT_DIR = "./output"  # 保存目录
```

## 常见问题

### Q: 为什么显示登录墙？
A: X 平台有访问限制。系统会自动切换到 fxtwitter 备用方案，无需担心。

### Q: 处理需要多长时间？
A: 通常抓取 + 解析在数秒到数十秒，取决于页面大小与网络。

### Q: 支持推文串吗？
A: 支持，提取结果中的 `tweets` 数组与 `is_thread` 字段会标识推文串，
宿主 agent 可据此整合。

### Q: 需要配置 LLM API 吗？
A: 不需要。本 skill 不直连任何大模型，LLM 任务由宿主 agent 完成，
因此不会（也不应）在仓库中配置或提交任何模型 / 密钥。

## 输出示例

### 提取素材（skill 产出）
- ✅ 结构化 JSON + 易读 Markdown
- ✅ 正文 / 元数据 / 媒体 / 语言
- ✅ 推文串标识

### 成品（宿主 agent 依据 prompts/ 生成）
- ✅ Medium 风格完整文章 HTML
- ✅ 一页纸解读 HTML（顶部 16:9 Banner）
- ✅ 中英文翻译（如原文为英文）

## 下一步

- 📖 阅读 [README.md](README.md) 了解详细文档
- 📄 查看 [prompts/](prompts/) 中的 LLM 提示词模板
- 🔧 修改 `src/config.py` 调整运行参数
- 🚀 开始处理你的 URL！

## 获取帮助

遇到问题？检查以下内容：
1. 是否安装了所有依赖？
2. Playwright 浏览器是否安装？
3. 网络连接是否正常？
4. 素材是否已正确生成在 `output/`？

祝使用愉快！🎉
