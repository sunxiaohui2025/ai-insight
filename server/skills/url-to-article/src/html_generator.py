"""HTML生成器 - 负责生成一页纸解读HTML"""
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class HtmlGenerator:
    """负责生成和保存HTML文件"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.html_dir = output_dir / "html"
        self.html_dir.mkdir(exist_ok=True)
    
    def save_summary_html(
        self,
        file_id: str,
        summary_html: str,
        banner_html: Optional[str] = None
    ) -> str:
        """
        保存一页纸解读HTML，自动填充Banner
        
        Args:
            file_id: 文件标识
            summary_html: LLM生成的HTML（包含<!--BANNER_SLOT-->占位符）
            banner_html: Banner的HTML代码
            
        Returns:
            保存的文件路径
        """
        # 替换Banner占位符
        if banner_html:
            final_html = summary_html.replace('<!--BANNER_SLOT-->', banner_html)
            logger.info("✓ Banner已填充到HTML中")
        else:
            # 如果没有banner，保留占位符或删除
            final_html = summary_html.replace('<!--BANNER_SLOT-->', '<!-- No banner -->')
            logger.warning("⚠ 没有可用的Banner，使用空占位符")
        
        # 保存文件
        html_path = self.html_dir / f"{file_id}_summary.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
        
        logger.info(f"✓ 一页纸HTML已保存: {html_path}")
        return str(html_path)
    
    def save_full_article_html(
        self,
        file_id: str,
        full_html: str
    ) -> str:
        """
        保存完整文章HTML
        
        Args:
            file_id: 文件标识
            full_html: 完整的HTML代码
            
        Returns:
            保存的文件路径
        """
        html_path = self.html_dir / f"{file_id}_full.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        logger.info(f"✓ 完整文章HTML已保存: {html_path}")
        return str(html_path)
