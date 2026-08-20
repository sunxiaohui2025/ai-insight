# 快速参考指南

## 核心功能

### 1. 提取文章内容
```python
from src.main import ArticleExtractor

extractor = ArticleExtractor()
result = extractor.process_url("https://example.com/article")
```

### 2. 返回数据结构
```python
{
    "success": True,
    "platform": "generic",  # 或 "x.com"
    "language": "en",       # 检测到的语言
    "full_text": "...",     # 正文内容
    "metadata": {
        "title": "...",
        "author": "...",
        "url": "...",
        "created_at": "..."
    },
    "media": {
        "images": ["url1", "url2"],
        "videos": ["url1"]
    },
    "large_image": {        # 新增：大尺寸Banner图片
        "url": "...",
        "width": 1200,
        "height": 800
    },
    "saved_files": {
        "json": "output/extract_xxx.json",
        "markdown": "output/extract_xxx.md"
    }
}
```

## 完整工作流程

### Step 1: 提取内容（本skill）
```bash
python -m src.main "https://example.com/article"
```

或在代码中：
```python
from src.main import ArticleExtractor
extractor = ArticleExtractor()
result = extractor.process_url(url)
```

### Step 2: 翻译（如果需要）
检查语言并翻译：
```python
if result['language'] == 'en':
    # 使用 prompts/translate.md
    # 通过LLM翻译 result['full_text']
    pass
```

### Step 3: 生成一页纸解读HTML
```python
# 使用 prompts/summary_html.md
# 生成HTML，包含 <!--BANNER_SLOT--> 占位符
```

### Step 4: 生成Banner

**Banner 1: 从原文提取（已自动完成）**
```python
if result.get('large_image'):
    banner1 = f'<img src="{result["large_image"]["url"]}" />'
else:
    banner1 = None  # 没有找到合适的图片
```

**Banner 2: SVG生成（需要LLM）**
```python
# 使用 prompts/banner_svg.md
# 生成SVG代码
```

### Step 5: 组装最终HTML
```python
# 将Banner插入到HTML的占位符位置
if banner1:
    final_html = summary_html.replace('<!--BANNER_SLOT-->', banner1)
else:
    final_html = summary_html.replace('<!--BANNER_SLOT-->', svg_banner)
```

## 命令行使用

```bash
# 提取普通网页
python -m src.main "https://example.com/article"

# 提取X/Twitter
python -m src.main "https://x.com/username/status/123456"

# 查看结果
cat output/extract_*.md
```

## 工具函数

### 图片处理
```python
from src.utils.image_utils import get_first_large_image

# 获取第一张大于640的图片
large_image = get_first_large_image(image_urls, min_width=640, min_height=640)
```

### 语言检测
```python
from src.utils.language_utils import detect_language, is_english

lang = detect_language(text, default='en')
if is_english(text):
    print("需要翻译")
```

## 配置

编辑 `src/config.py`:
```python
class Config:
    X_HEADLESS = True      # 浏览器无头模式
    X_TIMEOUT = 30000      # 超时时间（毫秒）
    X_WAIT_TIME = 5000     # 等待时间（毫秒）
    OUTPUT_DIR = "output"  # 输出目录
```

## Prompts模板

| 文件 | 用途 | 输入 | 输出 |
|-----|------|------|------|
| `translate.md` | 翻译英文到中文 | 原文 | 中文译文 |
| `summary_html.md` | 生成一页纸解读 | 正文 | HTML |
| `banner_svg.md` | 生成SVG Banner | 标题 | SVG代码 |
| `x_thread.md` | 整合推文串 | 推文列表 | 整合文本 |
| `full_article_html.md` | 完整文章HTML | 正文 | HTML |

## 故障排查

### 问题：未找到大尺寸图片
**原因：** 文章中没有大于640的图片
**解决：** 使用SVG Banner（选项2）

### 问题：语言检测不准确
**原因：** 文本太短或混合语言
**解决：** 
```python
from src.utils.language_utils import detect_language
lang = detect_language(text, default='en')  # 指定默认语言
```

### 问题：图片无法访问
**原因：** 防盗链或需要登录
**解决：** 检查图片URL，可能需要下载后本地使用

### 问题：X平台抓取失败
**原因：** 登录墙或网络限制
**解决：** 自动切换到备用方案（fxtwitter/vxtwitter）

## 输出文件说明

### JSON文件 (`extract_xxx.json`)
完整的结构化数据，包含所有提取信息

### Markdown文件 (`extract_xxx.md`)
易读的素材文件，包含：
- 元数据
- 正文
- 媒体资源
- Banner图片（如果有）
- 生成说明

## 最佳实践

1. **优先使用提取的图片作为Banner**
   - 如果 `result['large_image']` 存在，优先使用
   - 这样可以保持原文的视觉风格

2. **检查语言后再翻译**
   - 使用 `result['language']` 判断
   - 避免翻译已经是中文的内容

3. **处理失败时检查备用方案**
   - X平台会自动切换备用方案
   - 查看日志了解失败原因

4. **保存生成的HTML**
   - 将最终HTML保存到文件
   - 便于预览和分享

## 示例代码

完整示例见 `example_usage.py`
