"""完整工作流 - 从URL到最终HTML的完整流程"""
from src.main import ArticleExtractor
from src.banner_generator import BannerGenerator
from src.html_generator import HtmlGenerator
from src.config import Config
from pathlib import Path
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class ArticleWorkflow:
    """完整的文章处理工作流"""
    
    def __init__(self):
        self.extractor = ArticleExtractor()
        self.banner_gen = BannerGenerator(Config.OUTPUT_DIR)
        self.html_gen = HtmlGenerator(Config.OUTPUT_DIR)
    
    def process(
        self, 
        url: str,
        llm_translate_func=None,
        llm_summary_html_func=None,
        llm_banner_svg_func=None
    ) -> dict:
        """
        完整处理流程
        
        Args:
            url: 文章URL
            llm_translate_func: 翻译函数 (text) -> translated_text
            llm_summary_html_func: 生成摘要HTML函数 (data) -> html
            llm_banner_svg_func: 生成SVG Banner函数 (data) -> svg
            
        Returns:
            完整的处理结果
        """
        print(f"\n{'='*80}")
        print(f"开始完整工作流处理")
        print(f"URL: {url}")
        print(f"{'='*80}\n")
        
        # Step 1: 提取内容
        print("\n[步骤 1/5] 提取文章内容...")
        result = self.extractor.process_url(url)
        
        if not result['success']:
            return result
        
        # 生成文件ID
        if result['platform'] == 'x.com':
            match = re.search(r'/status/(\d+)', url)
            file_id = match.group(1) if match else datetime.now().strftime("%Y%m%d%H%M%S")
        else:
            import hashlib
            file_id = hashlib.md5(url.encode()).hexdigest()[:8]
        
        file_id = f"extract_{file_id}"
        
        # Step 2: 翻译（如果需要且提供了函数）
        translated_text = None
        if result['language'] == 'en' and llm_translate_func:
            print("\n[步骤 2/5] 翻译英文内容...")
            try:
                translated_text = llm_translate_func(result['full_text'])
                print(f"✓ 翻译完成，长度: {len(translated_text)} 字符")
            except Exception as e:
                logger.error(f"翻译失败: {e}")
                print(f"✗ 翻译失败: {e}，将使用原文")
        else:
            print("\n[步骤 2/5] 跳过翻译（已是中文或未提供翻译函数）")
        
        # 使用翻译后的文本或原文
        content_for_html = translated_text or result['full_text']
        
        # Step 3: 生成SVG Banner（如果提供了函数）
        svg_banner = None
        if llm_banner_svg_func:
            print("\n[步骤 3/5] 生成SVG Banner...")
            try:
                banner_data = {
                    'title': result['metadata'].get('title', ''),
                    'url': url,
                    'content': content_for_html[:200]  # 提供部分内容用于生成意象
                }
                svg_banner = llm_banner_svg_func(banner_data)
                print(f"✓ SVG Banner生成成功，长度: {len(svg_banner)} 字符")
            except Exception as e:
                logger.error(f"SVG生成失败: {e}")
                print(f"✗ SVG生成失败: {e}")
        else:
            print("\n[步骤 3/5] 跳过SVG生成（未提供生成函数）")
        
        # Step 4: 保存两个Banner
        print("\n[步骤 4/5] 保存Banner文件...")
        banner_files = self.banner_gen.save_banners(
            file_id=file_id,
            large_image=result.get('large_image'),
            svg_banner=svg_banner
        )
        
        # 生成用于插入HTML的Banner代码（优先使用SVG）
        banner_html = self.banner_gen.generate_banner_html(
            large_image=result.get('large_image'),
            svg_banner=svg_banner,
            prefer_image=False  # 优先使用SVG
        )
        
        # Step 5: 生成一页纸解读HTML（如果提供了函数）
        summary_html_path = None
        if llm_summary_html_func:
            print("\n[步骤 5/5] 生成一页纸解读HTML...")
            try:
                html_data = {
                    'title': result['metadata'].get('title', ''),
                    'author': result['metadata'].get('author', ''),
                    'created_at': result['metadata'].get('created_at', ''),
                    'url': url,
                    'content': content_for_html,
                    'language': result['language']
                }
                summary_html = llm_summary_html_func(html_data)
                
                # 自动填充Banner并保存
                summary_html_path = self.html_gen.save_summary_html(
                    file_id=file_id,
                    summary_html=summary_html,
                    banner_html=banner_html
                )
                print(f"✓ 一页纸HTML生成成功: {summary_html_path}")
            except Exception as e:
                logger.error(f"HTML生成失败: {e}")
                print(f"✗ HTML生成失败: {e}")
        else:
            print("\n[步骤 5/5] 跳过HTML生成（未提供生成函数）")
        
        # 返回完整结果
        print(f"\n{'='*80}")
        print("✅ 工作流处理完成")
        print(f"{'='*80}\n")
        
        return {
            'success': True,
            'extraction': result,
            'translated_text': translated_text,
            'banners': {
                'large_image': result.get('large_image'),
                'svg_banner': svg_banner,
                'saved_files': banner_files
            },
            'html': {
                'summary': summary_html_path
            },
            'all_files': {
                **result.get('saved_files', {}),
                **banner_files,
                'summary_html': summary_html_path
            }
        }


def main():
    """命令行入口 - 只执行提取步骤，LLM步骤需要外部提供"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m src.workflow <URL>")
        print("\n注意: 此脚本只执行提取和保存步骤")
        print("翻译、HTML生成、SVG生成需要通过API调用LLM完成")
        sys.exit(1)
    
    url = sys.argv[1]
    
    workflow = ArticleWorkflow()
    
    # 只执行提取步骤
    result = workflow.process(url)
    
    if result['success']:
        print("\n📊 处理结果摘要:")
        print(f"  - 平台: {result['extraction']['platform']}")
        print(f"  - 语言: {result['extraction']['language']}")
        print(f"  - 标题: {result['extraction']['metadata'].get('title', 'N/A')[:50]}...")
        
        print(f"\n📁 生成的文件:")
        for key, path in result['all_files'].items():
            if path:
                print(f"  - {key}: {path}")
        
        print(f"\n💡 下一步:")
        print(f"  需要调用LLM完成:")
        if result['extraction']['language'] == 'en':
            print(f"  1. 翻译（使用 prompts/translate.md）")
        print(f"  2. 生成SVG Banner（使用 prompts/banner_svg.md）")
        print(f"  3. 生成一页纸HTML（使用 prompts/summary_html.md）")


if __name__ == "__main__":
    main()
