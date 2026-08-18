"""主入口文件"""
from src.fetchers.x_fetcher import XFetcher
from src.fetchers.x_fetcher_backup import XFetcherBackup
from src.fetchers.generic_fetcher import GenericFetcher
from src.extractors.x_extractor import XExtractor
from src.extractors.generic_extractor import GenericExtractor
from src.llm_services import LLMService
from src.config import Config
from pathlib import Path
from typing import Dict
import re
from datetime import datetime
import json
import hashlib
import requests


class ArticleExtractor:
    def __init__(self):
        self.x_fetcher = XFetcher()
        self.x_fetcher_backup = XFetcherBackup()
        self.x_extractor = XExtractor()
        self.generic_fetcher = GenericFetcher()
        self.generic_extractor = GenericExtractor()
        self.llm_service = LLMService()
    
    def process_url(self, url: str, save_to_file: bool = True) -> dict:
        """
        处理 URL，提取并生成文章
        
        Args:
            url: 文章链接
            save_to_file: 是否保存到文件
            
        Returns:
            dict: 处理结果
        """
        print(f"\n{'='*60}")
        print(f"开始处理 URL: {url}")
        print(f"{'='*60}\n")
        
        # 1. 识别平台
        platform = self._identify_platform(url)
        print(f"识别平台: {platform}")
        
        if platform == "x.com":
            return self._process_x_url(url, save_to_file)
        elif platform == "generic":
            return self._process_generic_url(url, save_to_file)
        else:
            raise ValueError(f"暂不支持的平台: {platform}")
    
    def _identify_platform(self, url: str) -> str:
        """识别 URL 平台"""
        if "x.com" in url or "twitter.com" in url:
            return "x.com"
        return "generic"
    
    def _process_x_url(self, url: str, save_to_file: bool) -> dict:
        """处理 X 平台 URL"""

        # 1. 抓取页面 - 先尝试直接抓取，如果失败则使用备用方案
        print("\n[步骤 1/7] 抓取页面内容...")

        extracted = None
        use_backup = False

        try:
            html = self.x_fetcher.fetch(url)
            print(f"✓ 页面抓取完成，HTML 大小: {len(html)} 字符")

            # 2. 提取内容
            print("\n[步骤 2/7] 提取推文内容...")
            extracted = self.x_extractor.extract(html, url)

            # 检查是否成功提取到内容
            if not extracted['tweets'] or not extracted['full_text']:
                print("⚠ 未提取到推文内容，可能遇到登录墙")
                print("切换到备用方案...")
                use_backup = True
        except Exception as e:
            print(f"✗ 直接抓取失败: {e}")
            print("切换到备用方案...")
            use_backup = True

        # 使用备用方案
        if use_backup:
            print("\n[使用备用抓取方案]")
            backup_result = self.x_fetcher_backup.fetch(url)

            # 构造 extracted 数据结构
            extracted = {
                'tweets': [{
                    'order': 1,
                    'text': backup_result['text'],
                    'images': backup_result['images'],
                    'videos': backup_result['videos']
                }],
                'full_text': backup_result['text'],
                'metadata': {
                    'url': url,
                    'author': backup_result.get('author', ''),
                    'author_handle': re.search(r'x\.com/([^/]+)/', url).group(1) if re.search(r'x\.com/([^/]+)/', url) else '',
                    'created_at': backup_result.get('created_at', ''),
                    'title': backup_result.get('title') or (
                        backup_result['text'][:100] + '...'
                        if len(backup_result['text']) > 100
                        else backup_result['text']
                    )
                },
                'media': {
                    'images': backup_result['images'],
                    'videos': backup_result['videos']
                },
                'language': 'unknown',
                'is_thread': False
            }

            # 检测语言（优先使用 API 返回的 lang 字段）
            if backup_result.get('lang'):
                extracted['language'] = backup_result['lang']
            else:
                try:
                    import langdetect
                    extracted['language'] = langdetect.detect(extracted['full_text'])
                except:
                    extracted['language'] = 'en'  # 默认英文

            print(f"  正文长度: {len(extracted['full_text'])} 字符")

        print(f"✓ 提取完成:")
        print(f"  - 推文数量: {len(extracted['tweets'])}")
        print(f"  - 是否为推文串: {extracted['is_thread']}")
        print(f"  - 检测语言: {extracted['language']}")
        print(f"  - 图片数量: {len(extracted['media']['images'])}")
        print(f"  - 视频数量: {len(extracted['media']['videos'])}")
        
        # 3. 整合推文（如果是推文串）
        print("\n[步骤 3/7] 整合推文内容...")
        if extracted['is_thread'] and len(extracted['tweets']) > 1:
            content = self.llm_service.process_x_thread(
                extracted['tweets'],
                extracted['metadata']
            )
            print(f"✓ 推文串整合完成")
        else:
            content = extracted['full_text']
            print(f"✓ 使用原始推文内容")
        
        # 4. 翻译（如果需要）
        is_translated = False
        print("\n[步骤 4/7] 检查是否需要翻译...")
        if extracted['language'] == 'en':
            print("检测到英文内容，开始翻译...")
            content = self.llm_service.translate_to_chinese(content)
            is_translated = True
            print("✓ 翻译完成")
        else:
            print(f"✓ 内容为 {extracted['language']}，无需翻译")
        
        # 5. 生成完整文章 HTML
        print("\n[步骤 5/7] 生成完整文章 HTML...")
        full_html = self.llm_service.generate_full_article_html(
            content,
            extracted['metadata'],
            extracted['media'],
            is_translated
        )
        print("✓ 完整文章 HTML 生成完成")
        
        # 先获取文件 ID
        match = re.search(r'/status/(\d+)', url)
        tweet_id = match.group(1) if match else datetime.now().strftime("%Y%m%d%H%M%S")

        # 6. 生成 16:9 Banner SVG（放在一页纸解读顶部）
        print("\n[步骤 6/7] 生成 16:9 Banner...")
        banner_svg = self._generate_banner_svg(content, extracted['metadata'], tweet_id)

        # 7. 生成一页纸解读 HTML（顶部嵌入 banner）
        print("\n[步骤 7/7] 生成一页纸解读 HTML...")
        summary_html = self.llm_service.generate_summary_html(
            content,
            extracted['metadata'],
            banner_svg
        )
        print("✓ 一页纸解读 HTML 生成完成")

        # Banner 1: 从原文提取图片（可选）
        banner_article = self._download_article_banner(extracted['media'], tweet_id)

        # Banner 2: 从一页纸顶部区域截图（用于分享）
        banner_summary = self._capture_summary_banner(summary_html, tweet_id)

        # 保存到文件
        saved_files = {}
        if save_to_file:
            print("\n[保存文件]")
            saved_files = self._save_files(url, full_html, summary_html, extracted)
            if banner_article:
                saved_files['banner_article'] = banner_article
            if banner_summary:
                saved_files['banner_summary'] = banner_summary
            print(f"✓ 文件已保存到: {Config.OUTPUT_DIR}")
        
        # 返回结果
        result = {
            "success": True,
            "platform": "x.com",
            "metadata": extracted['metadata'],
            "language": extracted['language'],
            "translated": is_translated,
            "is_thread": extracted['is_thread'],
            "tweet_count": len(extracted['tweets']),
            "full_article_html": full_html,
            "summary_html": summary_html,
            "media": extracted['media'],
            "saved_files": saved_files
        }

        print(f"\n{'='*60}")
        print("处理完成！")
        print(f"{'='*60}\n")

        return result

    def _process_generic_url(self, url: str, save_to_file: bool) -> dict:
        """处理普通网页 URL"""

        # 1. 抓取页面
        print("\n[步骤 1/7] 抓取页面内容...")
        try:
            html = self.generic_fetcher.fetch(url)
            print(f"✓ 页面抓取完成，HTML 大小: {len(html)} 字符")
        except Exception as e:
            print(f"✗ 页面抓取失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        # 2. 提取内容
        print("\n[步骤 2/7] 提取文章内容...")
        try:
            extracted = self.generic_extractor.extract(html, url)
            print(f"✓ 提取完成:")
            print(f"  - 标题: {extracted['title'][:50]}...")
            print(f"  - 正文长度: {len(extracted['text'])} 字符")
            print(f"  - 图片数量: {len(extracted['images'])}")
        except Exception as e:
            print(f"✗ 内容提取失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        # 3. 检测语言
        print("\n[步骤 3/7] 检测语言...")
        try:
            import langdetect
            language = langdetect.detect(extracted['text'])
            print(f"✓ 检测语言: {language}")
        except Exception as e:
            print(f"⚠ 语言检测失败: {e}，默认为英文")
            language = 'en'

        # 4. 翻译（如果需要）
        is_translated = False
        content = extracted['text']
        print("\n[步骤 4/7] 检查是否需要翻译...")
        if language == 'en':
            print("检测到英文内容，开始翻译...")
            try:
                content = self.llm_service.translate_to_chinese(content)
                is_translated = True
                print("✓ 翻译完成")
            except Exception as e:
                print(f"⚠ 翻译失败: {e}，使用原文")
                content = extracted['text']
        else:
            print(f"✓ 内容为 {language}，无需翻译")

        # 5. 生成完整文章 HTML
        print("\n[步骤 5/7] 生成完整文章 HTML...")
        try:
            # 构造 metadata 和 media 结构
            metadata = {
                'title': extracted['title'],
                'url': url,
                'author': extracted['metadata'].get('author', ''),
                'created_at': extracted['metadata'].get('published_time', ''),
            }

            media = {
                'images': [img['url'] for img in extracted['images']],
                'videos': []
            }

            full_html = self.llm_service.generate_full_article_html(
                content,
                metadata,
                media,
                is_translated
            )
            print("✓ 完整文章 HTML 生成完成")
        except Exception as e:
            print(f"✗ HTML 生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        # 先获取文件 ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # 6. 生成 16:9 Banner SVG（放在一页纸解读顶部）
        print("\n[步骤 6/7] 生成 16:9 Banner...")
        banner_svg = self._generate_banner_svg(content, metadata, url_hash)

        # 7. 生成一页纸解读 HTML（顶部嵌入 banner）
        print("\n[步骤 7/7] 生成一页纸解读 HTML...")
        try:
            summary_html = self.llm_service.generate_summary_html(
                content,
                metadata,
                banner_svg
            )
            print("✓ 一页纸解读 HTML 生成完成")
        except Exception as e:
            print(f"⚠ 解读生成失败: {e}")
            summary_html = ""

        # Banner 1: 从原文提取图片（可选）
        banner_article = self._download_article_banner(media, url_hash)

        # Banner 2: 从一页纸截图（必须）
        banner_summary = ""
        if summary_html:
            banner_summary = self._capture_summary_banner(summary_html, url_hash)

        # 保存到文件
        saved_files = {}
        if save_to_file:
            print("\n[保存文件]")
            saved_files = self._save_generic_files(url, full_html, summary_html, extracted, language, is_translated)
            if banner_article:
                saved_files['banner_article'] = banner_article
            if banner_summary:
                saved_files['banner_summary'] = banner_summary
            print(f"✓ 文件已保存到: {Config.OUTPUT_DIR}")

        # 返回结果
        result = {
            "success": True,
            "platform": "generic",
            "metadata": metadata,
            "language": language,
            "translated": is_translated,
            "full_article_html": full_html,
            "summary_html": summary_html,
            "media": media,
            "saved_files": saved_files
        }

        print(f"\n{'='*60}")
        print("处理完成！")
        print(f"{'='*60}\n")

        return result

    def _save_files(self, url: str, full_html: str, summary_html: str, extracted: dict) -> dict:
        """保存文件到本地"""
        # 从 URL 提取 ID
        match = re.search(r'/status/(\d+)', url)
        tweet_id = match.group(1) if match else datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"article_{tweet_id}_{timestamp}.html"
        summary_filename = f"summary_{tweet_id}_{timestamp}.html"
        meta_filename = f"metadata_{tweet_id}_{timestamp}.json"
        
        # 保存文件
        full_path = Config.OUTPUT_DIR / full_filename
        summary_path = Config.OUTPUT_DIR / summary_filename
        meta_path = Config.OUTPUT_DIR / meta_filename
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_html)
        
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                "url": url,
                "metadata": extracted['metadata'],
                "language": extracted['language'],
                "is_thread": extracted['is_thread'],
                "tweet_count": len(extracted['tweets']),
                "media_count": {
                    "images": len(extracted['media']['images']),
                    "videos": len(extracted['media']['videos'])
                }
            }, f, ensure_ascii=False, indent=2)
        
        return {
            "full_article": str(full_path),
            "summary": str(summary_path),
            "metadata": str(meta_path)
        }

    def _save_generic_files(self, url: str, full_html: str, summary_html: str, extracted: dict, language: str, is_translated: bool) -> dict:
        """保存普通网页文件到本地"""
        # 使用 URL 哈希作为 ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_filename = f"article_{url_hash}_{timestamp}.html"
        summary_filename = f"summary_{url_hash}_{timestamp}.html"
        meta_filename = f"metadata_{url_hash}_{timestamp}.json"

        # 保存文件
        full_path = Config.OUTPUT_DIR / full_filename
        summary_path = Config.OUTPUT_DIR / summary_filename
        meta_path = Config.OUTPUT_DIR / meta_filename

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(full_html)

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_html)

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                "url": url,
                "title": extracted['title'],
                "language": language,
                "translated": is_translated,
                "metadata": extracted['metadata'],
                "image_count": len(extracted['images']),
                "timestamp": timestamp
            }, f, ensure_ascii=False, indent=2)

        return {
            "full_article": str(full_path),
            "summary": str(summary_path),
            "metadata": str(meta_path)
        }

    def _generate_banner_svg(self, content: str, metadata: Dict, file_id: str) -> str:
        """
        生成 16:9 的 Banner SVG，并单独保存一份 .svg 文件

        Args:
            content: 文章内容
            metadata: 元数据
            file_id: 文件 ID（用于命名）

        Returns:
            str: SVG 代码，失败时返回空字符串
        """
        try:
            banner_svg = self.llm_service.generate_banner_svg(content, metadata)

            if not banner_svg or '<svg' not in banner_svg:
                print("⚠ Banner 生成结果不是合法 SVG，跳过")
                return ""

            banner_path = Config.OUTPUT_DIR / f"banner_{file_id}.svg"
            with open(banner_path, 'w', encoding='utf-8') as f:
                f.write(banner_svg)

            print(f"✓ Banner SVG 已保存: {banner_path.name}")
            return banner_svg

        except Exception as e:
            print(f"⚠ Banner 生成失败: {e}")
            return ""

    def _download_article_banner(self, media: Dict, file_id: str) -> str:
        """
        从原文提取合适的图片作为 Banner 1

        Args:
            media: 媒体资源
            file_id: 文件 ID（用于命名）

        Returns:
            str: Banner 文件路径，如果没有合适的图片返回空字符串
        """
        print("\n[提取原文 Banner 图片]")

        # 尝试从原文图片中找到合适的 banner
        candidates = (media.get('images') or [])[:Config.BANNER_MAX_CANDIDATES]

        if not candidates:
            print("原文无图片")
            return ""

        for idx, image_url in enumerate(candidates, 1):
            print(f"[候选 {idx}/{len(candidates)}] {image_url[:80]}...")

            try:
                response = requests.get(image_url, timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                response.raise_for_status()

                # 校验尺寸，过滤 logo / 头像 / 竖图
                ok, reason, ext = self._validate_banner_image(response.content)
                if not ok:
                    print(f"  ✗ 跳过：{reason}")
                    continue

                banner_filename = f"banner_article_{file_id}.{ext}"
                banner_path = Config.OUTPUT_DIR / banner_filename

                with open(banner_path, 'wb') as f:
                    f.write(response.content)

                print(f"  ✓ 原文 Banner 已保存: {banner_filename}（{reason}）")
                return str(banner_path)

            except Exception as e:
                print(f"  ✗ 下载失败: {e}")
                continue

        print("未找到尺寸合适的图片")
        return ""

    def _capture_summary_banner(self, summary_html: str, file_id: str) -> str:
        """
        从一页纸解读顶部的 banner 区域截图，生成 16:9 分享图

        Args:
            summary_html: 一页纸 HTML 内容
            file_id: 文件 ID（用于命名）

        Returns:
            str: Banner 文件路径
        """
        print("\n[生成一页纸 Banner 截图]")

        try:
            from playwright.sync_api import sync_playwright
            import tempfile

            # 保存临时 HTML 文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(summary_html)
                temp_html_path = f.name

            banner_filename = f"banner_summary_{file_id}.png"
            banner_path = Config.OUTPUT_DIR / banner_filename

            # 使用 Playwright 截图
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={'width': 1600, 'height': 900},
                    device_scale_factor=2
                )
                page.goto(f'file://{temp_html_path}')
                page.wait_for_timeout(2000)  # 等待渲染完成

                # 优先只截取 banner 区域，保证输出是 16:9
                banner = page.query_selector('.banner') or page.query_selector('.banner svg')
                if banner:
                    banner.screenshot(path=str(banner_path))
                    print("  （截取 banner 区域）")
                else:
                    page.screenshot(path=str(banner_path), full_page=False)
                    print("  （未找到 banner 容器，截取首屏）")

                browser.close()

            # 删除临时文件
            import os
            os.unlink(temp_html_path)

            print(f"✓ 一页纸 Banner 已保存: {banner_filename}")
            return str(banner_path)

        except Exception as e:
            print(f"✗ 截图失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _validate_banner_image(self, image_bytes: bytes) -> tuple:
        """
        校验图片是否适合作为 Banner

        过滤掉 logo、头像、图标等小尺寸图片，以及竖图和方图。

        Args:
            image_bytes: 图片二进制数据

        Returns:
            tuple: (是否合格, 说明文字, 文件扩展名)
        """
        from io import BytesIO
        from PIL import Image

        try:
            img = Image.open(BytesIO(image_bytes))
        except Exception as e:
            return False, f"无法解析图片: {e}", ""

        width, height = img.size
        ext = (img.format or 'JPEG').lower()
        if ext == 'jpeg':
            ext = 'jpg'

        size_desc = f"{width}x{height}"

        if width < Config.BANNER_MIN_WIDTH:
            return False, f"宽度不足 {size_desc}，疑似 logo 或图标", ext

        if height < Config.BANNER_MIN_HEIGHT:
            return False, f"高度不足 {size_desc}", ext

        aspect = width / height if height else 0
        if aspect < Config.BANNER_MIN_ASPECT:
            return False, f"宽高比 {aspect:.2f} 过窄 {size_desc}，疑似头像或竖图", ext

        return True, f"{size_desc}，宽高比 {aspect:.2f}", ext


def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m src.main <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    
    extractor = ArticleExtractor()
    result = extractor.process_url(url)
    
    if result['success']:
        print("\n处理结果摘要:")
        print(f"  - 平台: {result['platform']}")
        print(f"  - 语言: {result['language']}")
        print(f"  - 已翻译: {result['translated']}")
        if result['platform'] == 'x.com':
            print(f"  - 推文数: {result['tweet_count']}")
        print(f"  - 保存文件:")
        for key, path in result['saved_files'].items():
            print(f"    * {key}: {path}")


if __name__ == "__main__":
    main()

