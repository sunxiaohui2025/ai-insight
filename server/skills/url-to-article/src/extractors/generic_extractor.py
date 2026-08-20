"""通用网页内容提取器 - 使用多种策略提取网页正文内容"""

from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


class GenericExtractor:
    """通用网页内容提取器"""
    
    def extract(self, html: str, url: str) -> dict:
        """
        从 HTML 中提取文章内容
        
        Args:
            html: HTML 内容
            url: 原始 URL
            
        Returns:
            dict: 包含提取的内容
                - title: 文章标题
                - content: 文章正文（HTML格式）
                - text: 纯文本内容
                - images: 图片列表
                - metadata: 元数据
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # 提取标题
        title = self._extract_title(soup)
        
        # 提取正文内容
        content_html, content_text = self._extract_content(soup, url)
        
        # 提取图片
        images = self._extract_images(soup, url)
        
        # 提取元数据
        metadata = self._extract_metadata(soup)
        
        return {
            'title': title,
            'content': content_html,
            'text': content_text,
            'images': images,
            'metadata': metadata,
            'url': url
        }
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题"""
        # 尝试多种方式获取标题
        
        # 1. og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        # 2. <title> 标签
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # 去掉常见的网站后缀
            title = re.split(r'[-_|]', title)[0].strip()
            return title
        
        # 3. h1 标签
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
        
        return "未知标题"
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> tuple:
        """提取正文内容，返回 (HTML, 纯文本)"""
        
        # 移除不需要的元素
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # 尝试找到主要内容区域
        content_element = None

        # 1. 尝试常见的文章容器选择器
        # 注意：优先级很重要。结构化的 main/article/[role=main] 等放在最前面，
        # 避免后面的模糊类名选择器（如 .content）误匹配到页面上无关的小元素。
        selectors = [
            'article',
            'main',
            '[role="main"]',
            'article[class*="content"]',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.blog-post',
            '.markdown-body',
            '.prose',
            'main[class]',
            '.content',
            '#content',
        ]

        for selector in selectors:
            if selector.startswith('.'):
                # 类名选择器：按完整类名 token 精确匹配，
                # 避免子串匹配导致误选中包含 "content" 字样的小元素
                # （例如 class="icon_wrap u-display-contents" 会被误判为 .content）
                class_token = selector[1:]
                content_element = self._find_by_class_token(soup, class_token)
            elif selector.startswith('#'):
                content_element = soup.find(id=selector[1:])
            elif selector.startswith('['):
                # 属性选择器，例如 [role="main"]、article[class*="content"]
                if '[class*="' in selector:
                    tag, _, class_part = selector.partition('[')
                    class_frag = class_part.split('"')[1]
                    node = soup.find(tag) if tag else None
                    if node is not None:
                        for elem in (soup.find_all(tag) if tag else []):
                            cls = ' '.join(elem.get('class', [])) if elem.get('class') else ''
                            if class_frag in cls:
                                content_element = elem
                                break
                    elif not tag:
                        content_element = soup.find(attrs={
                            'class': class_frag
                        })
                else:
                    match = re.match(r'\[(\w+)="([^"]+)"\]', selector)
                    if match:
                        attr, value = match.groups()
                        content_element = soup.find(attrs={attr: value})
            else:
                content_element = soup.find(selector)

            # 跳过没有任何文本内容的误匹配元素，继续尝试下一个选择器
            if content_element is not None and self._content_candidate_has_text(content_element):
                break
        else:
            content_element = None
        
        # 2. 如果没找到，使用启发式方法
        if not content_element:
            content_element = self._find_main_content_heuristic(soup)
        
        # 3. 如果还是没找到，使用 body
        if not content_element:
            content_element = soup.find('body')
        
        if not content_element:
            return "", ""
        
        # 清理内容
        content_clone = BeautifulSoup(str(content_element), 'lxml')
        
        # 移除评论、广告等
        for element in content_clone.find_all(class_=re.compile(r'comment|ad|advertisement|social|share|related', re.I)):
            element.decompose()
        
        # 处理图片 URL
        for img in content_clone.find_all('img'):
            # 处理多种图片源属性
            src = (
                img.get('src') or
                img.get('data-src') or
                img.get('data-lazy-src') or
                img.get('data-original')
            )
            if src:
                img['src'] = urljoin(url, src)
            elif img.get('data-srcset'):
                # 处理data-srcset
                srcset = img.get('data-srcset', '')
                candidates = [item.strip().split()[0] for item in srcset.split(',') if item.strip()]
                if candidates:
                    img['src'] = urljoin(url, candidates[-1])
        
        # 处理链接
        for a in content_clone.find_all('a'):
            if a.get('href'):
                a['href'] = urljoin(url, a['href'])
        
        content_html = str(content_clone)
        content_text = content_clone.get_text(separator='\n', strip=True)
        
        return content_html, content_text
    
    def _find_by_class_token(self, soup: BeautifulSoup, class_token: str):
        """按完整类名 token 精确匹配元素。

        使用正规的 class 属性值（空格分隔的类名列表）进行精确匹配，
        而不是对整个 class 字符串做子串匹配，避免误匹配
        （例如 class="u-display-contents" 不应被视为 .content）。
        """
        for elem in soup.find_all(class_=True):
            classes = set(elem.get('class', []))
            if class_token in classes:
                return elem
        return None

    def _content_candidate_has_text(self, element) -> bool:
        """判断候选元素是否具有实际的可读正文文本。

        过滤掉像 <div class="icon_wrap u-display-contents"> 这样的空壳包装元素，
        保证我们不会把没有正文的小元素当作正文容器。
        """
        text = element.get_text(' ', strip=True)
        if not text:
            return False
        # 至少需要一些非装饰性的文本（避免只包含 icon 等无意义内容）
        return len(text) >= 10

    def _find_main_content_heuristic(self, soup: BeautifulSoup):
        """使用启发式方法找到主要内容区域"""
        # 找到段落最多的容器
        max_paragraphs = 0
        best_element = None
        
        for element in soup.find_all(['div', 'section', 'article']):
            paragraphs = len(element.find_all('p'))
            if paragraphs > max_paragraphs:
                max_paragraphs = paragraphs
                best_element = element
        
        return best_element
    
    def _extract_images(self, soup: BeautifulSoup, url: str) -> list:
        """提取图片列表，支持多种懒加载方式"""
        images = []
        seen = set()

        for img in soup.find_all('img'):
            # 尝试多种图片URL属性
            src = (
                img.get('src') or
                img.get('data-src') or
                img.get('data-lazy-src') or
                img.get('data-original') or
                img.get('data-srcset', '').split(',')[0].split()[0] if img.get('data-srcset') else None
            )

            # 处理srcset属性（取最大的图片）
            if not src and img.get('srcset'):
                srcset = img.get('srcset', '')
                # srcset格式: "url1 1x, url2 2x" 或 "url1 100w, url2 200w"
                candidates = []
                for item in srcset.split(','):
                    parts = item.strip().split()
                    if parts:
                        candidates.append(parts[0])
                if candidates:
                    src = candidates[-1]  # 取最后一个（通常是最大的）

            if src:
                full_url = urljoin(url, src)
                if full_url not in seen:
                    seen.add(full_url)
                    images.append({
                        'url': full_url,
                        'alt': img.get('alt', '')
                    })

        return images
    
    def _extract_metadata(self, soup: BeautifulSoup) -> dict:
        """提取元数据"""
        metadata = {}
        
        # Open Graph 元数据
        for meta in soup.find_all('meta', property=re.compile(r'^og:')):
            key = meta['property'].replace('og:', '')
            metadata[f'og_{key}'] = meta.get('content', '')
        
        # Twitter Card 元数据
        for meta in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')}):
            key = meta['name'].replace('twitter:', '')
            metadata[f'twitter_{key}'] = meta.get('content', '')
        
        # 描述
        description = soup.find('meta', attrs={'name': 'description'})
        if description:
            metadata['description'] = description.get('content', '')
        
        # 作者
        author = soup.find('meta', attrs={'name': 'author'})
        if author:
            metadata['author'] = author.get('content', '')
        
        # 发布时间
        for meta in soup.find_all('meta', property=re.compile(r'published_time|article:published_time')):
            metadata['published_time'] = meta.get('content', '')
            break
        
        return metadata
