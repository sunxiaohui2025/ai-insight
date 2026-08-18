# 快速开始指南

## 一分钟上手

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 运行测试
```bash
python -m src.main "https://x.com/hwchase17/status/2085780032031760694"
```

### 3. 查看结果
生成的文件在 `output/` 目录：
- `article_*.html` - 完整文章（在浏览器中打开）
- `summary_*.html` - 一页纸总结（在浏览器中打开）
- `metadata_*.json` - 元数据

## 使用你自己的 X 链接

```bash
python -m src.main "你的X链接"
```

例如：
```bash
python -m src.main "https://x.com/username/status/1234567890"
```

## Python API 使用

```python
from src.main import ArticleExtractor

# 创建提取器
extractor = ArticleExtractor()

# 处理 URL
result = extractor.process_url(
    url="https://x.com/username/status/123456789",
    save_to_file=True
)

# 查看结果
print(f"标题: {result['metadata']['title']}")
print(f"语言: {result['language']}")
print(f"已翻译: {result['translated']}")
print(f"文件保存位置:")
for key, path in result['saved_files'].items():
    print(f"  {key}: {path}")
```

## 配置修改

编辑 `src/config.py` 来修改设置：

```python
# LLM 配置
KIMI_API_BASE = "你的API地址"
KIMI_MODEL = "模型名称"
KIMI_API_KEY = "你的API密钥"

# X 平台配置
X_HEADLESS = False  # True=无头模式, False=显示浏览器

# 输出配置
OUTPUT_DIR = "./output"  # 保存目录
```

## 常见问题

### Q: 为什么显示登录墙？
A: X 平台有访问限制。系统会自动切换到 fxtwitter 备用方案，无需担心。

### Q: 处理需要多长时间？
A: 通常 10-30 秒，取决于内容长度和 LLM API 响应速度。

### Q: 支持推文串吗？
A: 支持，系统会自动检测并整合推文串。

### Q: 可以批量处理吗？
A: 目前需要逐个处理，批量功能在规划中。

## 输出示例

### 完整文章特点
- ✅ Medium 风格的现代设计
- ✅ 中英文翻译（如果需要）
- ✅ 包含所有图片和视频
- ✅ 代码高亮支持
- ✅ 响应式布局

### 一页纸总结特点
- ✅ 核心观点提炼
- ✅ 主要内容要点（3-5 个）
- ✅ 技术亮点分析
- ✅ 总结与启示
- ✅ 紧凑的卡片式设计

## 下一步

- 📖 阅读 [README.md](README.md) 了解详细文档
- 📊 查看 [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) 了解项目架构
- 🔧 修改 `src/config.py` 自定义配置
- 🚀 开始处理你的 X 链接！

## 获取帮助

遇到问题？检查以下内容：
1. 是否安装了所有依赖？
2. Playwright 浏览器是否安装？
3. LLM API 是否可访问？
4. 网络连接是否正常？

祝使用愉快！🎉
