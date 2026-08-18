"""LLM 服务层 - 处理翻译、生成等任务"""
from src.llm_client import LLMClient
from typing import Dict, List
import json
import re


class LLMService:
    def __init__(self):
        self.client = LLMClient()
    
    def translate_to_chinese(self, content: str) -> str:
        """
        将英文内容翻译成中文
        
        Args:
            content: 英文内容
            
        Returns:
            str: 中文翻译
        """
        prompt = f"""你是一个专业的技术文档翻译专家。请将以下英文内容翻译成中文。

要求：
1. 保持技术术语的准确性
2. 保持原文的格式和结构
3. 翻译要专业、流畅、易读
4. 不要添加额外的解释或评论
5. 直接输出翻译结果

英文内容：
{content}

请直接输出中文翻译："""

        return self.client.chat_simple(prompt, temperature=0.3)
    
    def generate_full_article_html(
        self,
        content: str,
        metadata: Dict,
        media: Dict,
        is_translated: bool = False
    ) -> str:
        """
        生成完整的文章 HTML
        
        Args:
            content: 文章内容
            metadata: 元数据
            media: 媒体资源
            is_translated: 是否已翻译
            
        Returns:
            str: HTML 内容
        """
        media_json = json.dumps(media, ensure_ascii=False)
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        
        prompt = f"""你是一个专业的网页设计师。请根据以下内容生成一个美观的 HTML 页面。

文章内容：
{content}

元数据：
{metadata_json}

媒体资源：
{media_json}

要求：
1. 使用现代、简洁、专业的设计风格
2. 保留所有原文内容，不要删减任何信息
3. 在适当位置嵌入图片（使用提供的图片 URL）
4. 使用响应式设计，适配移动端
5. 包含标题、作者、日期等元数据
6. 使用良好的排版和间距
7. 代码块使用等宽字体和语法高亮样式
8. 整体风格类似 Medium 或现代技术博客
9. 只输出完整的 HTML 代码，从 <!DOCTYPE html> 开始，不要添加任何 markdown 代码块标记
10. 使用中文界面（如"作者"、"发布时间"等标签）

注意：
- 绝对不要在 HTML 代码前后添加 ```html 或 ``` 标记
- 直接输出纯 HTML 代码，第一行就是 <!DOCTYPE html>

请直接输出完整的 HTML 代码："""

        response = self.client.chat_simple(prompt, temperature=0.5)
        # 清理可能的 markdown 代码块标记
        response = response.strip()
        if response.startswith('```html'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        return response.strip()
    
    def generate_summary_html(
        self,
        content: str,
        metadata: Dict,
        banner_svg: str = ""
    ) -> str:
        """
        生成"一页纸解读"HTML

        这里的"一页纸"指的是对原文的高度提炼与解读文章，
        而不是限制在一屏之内的内容。页面顶部会放置一张 16:9 的 banner。

        Args:
            content: 文章内容
            metadata: 元数据
            banner_svg: 16:9 banner 的 SVG 代码，会内联到页面顶部

        Returns:
            str: 解读文章 HTML
        """
        metadata_json = json.dumps(metadata, ensure_ascii=False)

        banner_instruction = """
【Banner 区域】
页面最顶部必须预留一个 16:9 的 banner 容器，请严格使用如下结构，
并在其中原样保留占位标记 <!--BANNER_SLOT-->（系统会替换为真实 banner）：

<div class="banner">
  <!--BANNER_SLOT-->
</div>

banner 容器的 CSS 要求：
- 宽度撑满内容区，使用 aspect-ratio: 16 / 9 保证比例
- overflow: hidden，圆角约 12px
- 内部的 svg 使用 width:100%; height:100%; display:block
- banner 下方紧接标题区
"""

        prompt = f"""你是一个资深的技术内容编辑。请阅读以下原文，写一篇"一页纸解读"，并输出为一个完整的 HTML 页面。

原文内容：
{content}

元数据：
{metadata_json}

## 什么是"一页纸解读"

它是对原文的高度提炼和深度解读，读者读完这一篇就能掌握原文的全部要点，
不需要再回去读原文。

重要：不要为了塞进一屏而压缩内容。页面可以向下滚动，长度以说清楚为准
（正文建议 1200–2500 字），排版要便于阅读。

## 内容要求

1. 开头用 2–4 句话讲清楚"这篇讲了什么、为什么重要"（TL;DR）
2. 用 3–6 个带小标题的章节展开核心内容，每节都要有实质信息：
   - 具体的数字、指标、技术名称、版本号等细节必须保留
   - 解释清楚"是什么"和"为什么这么做"，而不是罗列关键词
3. 如果原文有对比数据、性能指标或参数，用表格呈现
4. 如果原文有关键技术点，单独设一节做拆解
5. 结尾写"这意味着什么"：影响、局限、值得关注的点
6. 只基于原文事实写作，不要编造原文中没有的数据
7. 使用中文，语言专业、平实、不夸张

## 排版要求

{banner_instruction}

正文排版：
- 正文最大宽度约 760px，居中，左右留白充足
- 正文字号 17–18px，行高 1.8，段落间距明显
- 小标题层级清晰（h2 用于章节，h3 用于子项）
- 关键结论使用引用块（blockquote）或浅色背景卡片突出
- 表格有边框和斑马纹，表头有底色
- 关键术语可以用 <strong> 强调，克制使用
- 配色克制专业：浅色背景（#faf9f5 或 #ffffff），正文近黑色（#1f1f1f），
  一个强调色即可
- 响应式设计，移动端正文左右留 20px 内边距
- 标题区包含标题、作者、日期、原文链接

## 技术规范

- 输出完整 HTML，第一行必须是 <!DOCTYPE html>
- 所有 CSS 内联在 <style> 标签中，不引用外部资源
- 绝对不要在 HTML 代码前后添加 ```html 或 ``` 标记
- 必须原样保留 <!--BANNER_SLOT--> 占位标记

请直接输出完整的 HTML 代码："""

        response = self.client.chat_simple(prompt, temperature=0.6)
        # 清理可能的 markdown 代码块标记
        response = response.strip()
        if response.startswith('```html'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        response = response.strip()

        if banner_svg:
            response = self._inject_banner(response, banner_svg)

        return response

    def _inject_banner(self, html: str, banner_svg: str) -> str:
        """
        将 banner SVG 注入到解读页面顶部

        优先替换 <!--BANNER_SLOT--> 占位标记；
        如果模型没有保留占位标记，则回退到在 <body> 开头插入 banner 容器。
        """
        if '<!--BANNER_SLOT-->' in html:
            return html.replace('<!--BANNER_SLOT-->', banner_svg, 1)

        # 回退方案：自带样式的 banner 容器插到 body 最前面
        fallback = f'''<div style="max-width:900px;margin:0 auto 32px;aspect-ratio:16/9;overflow:hidden;border-radius:12px;">
{banner_svg}
</div>'''

        match = re.search(r'<body[^>]*>', html, re.IGNORECASE)
        if match:
            insert_at = match.end()
            return html[:insert_at] + '\n' + fallback + html[insert_at:]

        return fallback + html
    
    def process_x_thread(
        self,
        tweets: List[Dict],
        metadata: Dict
    ) -> str:
        """
        将 X 推文串整合成流畅的文章
        
        Args:
            tweets: 推文列表
            metadata: 元数据
            
        Returns:
            str: 整合后的文章内容
        """
        tweets_text = "\n\n".join([
            f"[推文 {t['order']}]\n{t['text']}"
            for t in tweets
        ])
        
        prompt = f"""你是一个专业的内容编辑。我将提供一串 X (Twitter) 推文，这是一个完整的技术分享。

请将这些推文整合成一篇流畅、连贯的文章。

推文内容：
{tweets_text}

要求：
1. 保持原意，不要删减任何技术细节
2. 将推文风格转换为文章风格（去除"🧵"、"1/"等符号）
3. 保持逻辑清晰，段落分明
4. 添加适当的小标题组织内容（如果推文较多）
5. 使文章读起来自然流畅，而不是碎片化的推文
6. 保留重要的强调和格式
7. 不要添加自己的评论或解释
8. 直接输出整合后的文章内容（纯文本，不是 HTML）

请输出整合后的文章："""

        return self.client.chat_simple(prompt, temperature=0.4)

    def generate_banner_svg(
        self,
        content: str,
        metadata: Dict
    ) -> str:
        """
        生成文章 Banner SVG 图片

        Args:
            content: 文章内容
            metadata: 元数据

        Returns:
            str: SVG 代码
        """
        # 先提取文章主题和关键标题
        extract_prompt = f"""请分析以下文章内容，提取关键信息用于生成配图。

文章内容：
{content[:2000]}

文章标题：
{metadata.get('title', '')}

请以 JSON 格式输出：
{{
  "theme": "文章主题（简短，5-10字）",
  "visual_metaphor": "核心视觉隐喻（描述一个具体的视觉画面，15-30字）",
  "title": "适合做图片标题的简短版本（8-15字）",
  "subtitle": "副标题（可选，10-20字，如果不需要则为空字符串）"
}}

只输出 JSON，不要其他内容。"""

        extract_result = self.client.chat_simple(extract_prompt, temperature=0.3)

        # 解析 JSON
        try:
            # 清理可能的 markdown 标记
            extract_result = extract_result.strip()
            if extract_result.startswith('```json'):
                extract_result = extract_result[7:]
            if extract_result.startswith('```'):
                extract_result = extract_result[3:]
            if extract_result.endswith('```'):
                extract_result = extract_result[:-3]
            extract_result = extract_result.strip()

            theme_info = json.loads(extract_result)
        except:
            # 如果解析失败，使用默认值
            theme_info = {
                "theme": metadata.get('title', '技术文章')[:20],
                "visual_metaphor": "抽象的技术元素围绕中心主题展开",
                "title": metadata.get('title', '技术文章')[:15],
                "subtitle": ""
            }

        # 构建生图提示词
        svg_prompt = f"""请根据以下参数生成一幅 16:9 的独立 SVG 编辑插画。

【主题】
{theme_info['theme']}

【核心视觉隐喻】
{theme_info['visual_metaphor']}

【使用场景】
技术博客主视觉、文章配图、社交媒体分享图

【画面文字】
标题：{theme_info['title']}
副标题：{theme_info['subtitle'] if theme_info['subtitle'] else '无'}
所有文字必须逐字准确，不得改写、错别字或增加额外文字。

---

## 视觉方向

采用 Anthropic 风格的手绘编辑插画语言，但不要复制任何现有插画中的具体对象、构图或布局。只继承其视觉系统：

- 粗重、圆润、略有不均匀的近黑色手绘线条
- 连续、自然、带轻微晃动感的手势轮廓
- 简化的二维象征性对象
- 有意识的不对称构图
- 象牙白的不规则承载形状
- 扁平、克制、有限的配色
- 用重叠关系表达连接、协作、支撑、转化或引导
- 画面应具有编辑插画和技术论文配图的清晰度
- 缩小到缩略图后，仍然能够一眼理解主题

## 画布与构图

- 输出比例必须为 16:9
- SVG 必须使用以下画布设置：

```svg
viewBox="0 0 1600 900"
width="1600"
height="900"
```

- 画面必须是横向构图
- 视觉主体占画面约 55%–75%
- 四周至少保留 8%–12% 的呼吸空间
- 如果存在标题和副标题，优先将文字放在左侧，将视觉主体放在右侧
- 如果没有文字，可将主体置于中央或略微偏移
- 不要使用复杂背景、多个小场景或密集装饰
- 只使用一个核心视觉隐喻和一个主要视觉关系

## 三层画面结构

必须严格保持以下三层：

### 第一层：满版背景

使用一种覆盖整个画布的纯色不透明背景，四个角落必须完全填充，不得透明，不得出现白色边框。

从以下配色中选择一种：

- cactus：`#BCD1CA`，适合思考、信任、系统、机构
- heather：`#CBCADB`，适合全球化、技术、研究、反思
- oat：`#E3DACC`，适合人性化、平静、运营、合作
- clay：`#D97757`，适合发布、紧迫感、能量、强调
- olive：`#788C5D`，适合成长、韧性、环境
- sky：`#6A9BCC`，适合开放、基础设施、通信
- fig：`#C46686`，适合创造力、文化、身份
- coral：`#EBCECE`，适合关怀、社区、可访问性

默认优先选择 `#CBCADB` 或 `#BCD1CA`。除非主题明确要求，否则不要使用高饱和颜色。

### 第二层：象牙白承载形状

在背景内部放置一个大型、不规则、扁平的象牙白承载形状：

- 颜色必须为 `#FAF9F5`
- 占画布约 55%–80%
- 轮廓应自然、不规则、有轻微手绘感
- 不要使用标准圆角矩形、完美圆形或机械几何图形
- 承载形状用于承接核心对象和手绘线条
- 可以略微倾斜或偏移
- 不要让它看起来像一个普通卡片、面板或 UI 容器

### 第三层：近黑色手绘线条

在象牙白承载形状上绘制核心视觉隐喻：

- 主线条颜色：`#141413`
- 线条宽度建议为 8–18
- 使用 `stroke-linecap="round"`
- 使用 `stroke-linejoin="round"`
- 线条宽度可以有轻微变化
- 允许少量黑色线条越过象牙白承载形状边界
- 可以加入少量实心黑色圆点作为节点、重点或节奏元素
- 不要使用完美几何线条、网格、工程制图风格或精细技术线稿

## SVG 技术要求

请直接输出一个完整、可运行的 SVG 文件，不要输出解释文字、Markdown 代码围栏或生成过程。

必须满足：

- 使用标准 SVG XML 语法
- 根节点包含 `xmlns="http://www.w3.org/2000/svg"`
- 使用 `viewBox="0 0 1600 900"`
- 所有视觉内容必须由 SVG 原生元素构成，例如：
  - `path`
  - `ellipse`
  - `circle`
  - `rect`
  - `line`
  - `text`
  - `g`
- 不要嵌入 PNG、JPG、WebP 或 Base64 图片
- 不要使用外部图片、外部字体、外部 CSS 或 JavaScript
- 不要使用渐变、阴影、发光、纹理或滤镜
- 不要使用透明外画布
- 背景必须覆盖整个 `1600 × 900` 画布
- 所有文字必须是真实 SVG `<text>` 元素，而不是路径模拟文字
- 文字应优先使用以下字体栈：

```text
font-family="Arial, 'Microsoft YaHei', 'PingFang SC', sans-serif"
```

## 文字排版要求

如果有标题：

- 标题应清晰、醒目、适合 PPT 或网页主视觉
- 中文标题建议使用 52–80 像素
- 副标题建议使用 24–36 像素
- 标题与副标题之间保留清晰间距
- 不要让标题被视觉主体遮挡
- 不要自动添加英文标题、Logo、品牌名、日期或装饰性文案
- 不要让文字发生重叠、裁切或超出画布

## 禁止内容

不要出现：

- 透明背景
- 白色外画布
- 黑色外画布
- 棋盘格背景
- 摄影写实
- 3D
- 渐变
- 阴影
- 高光
- 玻璃质感
- 金属质感
- 复杂透视
- 写实人体
- 复杂机械细节
- 企业图库式矢量风格
- 完美几何图形堆叠
- 过多对象
- 彩虹配色
- Logo
- 水印
- 未提供的文字
- 复制房屋、地球、灯泡或其他参考图的具体构图

## 最终质量检查

生成前确认：

1. 四个角落是否全部使用了不透明背景色。
2. 是否只有一个主要视觉隐喻。
3. 象牙白承载形状是否明显且不规则。
4. 黑色线条是否粗重、圆润并具有手绘感。
5. 是否只使用黑色、象牙白和一种背景强调色。
6. 标题和副标题是否准确、清晰、没有错别字。
7. SVG 是否可以直接保存为 `.svg` 文件并在浏览器中打开。
8. 缩小后是否仍然能够读懂主题。

现在请直接输出完整的 SVG 代码，不要添加任何 markdown 代码块标记："""

        svg_result = self.client.chat_simple(svg_prompt, temperature=0.7)

        # 清理可能的 markdown 标记
        svg_result = svg_result.strip()
        if svg_result.startswith('```svg'):
            svg_result = svg_result[6:]
        if svg_result.startswith('```xml'):
            svg_result = svg_result[6:]
        if svg_result.startswith('```'):
            svg_result = svg_result[3:]
        if svg_result.endswith('```'):
            svg_result = svg_result[:-3]

        return svg_result.strip()
