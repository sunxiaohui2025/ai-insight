"""Banner生成器 - 保存两个banner"""
from pathlib import Path
from typing import Optional, Dict
import json
import logging

logger = logging.getLogger(__name__)


class BannerGenerator:
    """负责生成和保存两个Banner"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.banner_dir = output_dir / "banners"
        self.banner_dir.mkdir(exist_ok=True)
    
    def save_banners(
        self, 
        file_id: str,
        large_image: Optional[Dict] = None,
        svg_banner: Optional[str] = None
    ) -> Dict[str, str]:
        """
        保存两个Banner并返回路径
        
        Args:
            file_id: 文件标识（如 extract_123456）
            large_image: 提取的大尺寸图片信息
            svg_banner: 生成的SVG代码
            
        Returns:
            保存的文件路径字典
        """
        saved = {}
        
        # Banner 1: 保存图片URL信息（如果有）
        if large_image:
            banner1_path = self.banner_dir / f"{file_id}_banner_image.json"
            with open(banner1_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "type": "image",
                    "url": large_image['url'],
                    "width": large_image['width'],
                    "height": large_image['height']
                }, f, ensure_ascii=False, indent=2)
            saved['banner_image'] = str(banner1_path)
            logger.info(f"✓ Banner 1 (图片) 已保存: {banner1_path}")
        else:
            logger.info("⚠ Banner 1: 未找到大尺寸图片")
        
        # Banner 2: 保存SVG代码（如果有）
        if svg_banner:
            banner2_path = self.banner_dir / f"{file_id}_banner_svg.svg"
            with open(banner2_path, 'w', encoding='utf-8') as f:
                f.write(svg_banner)
            saved['banner_svg'] = str(banner2_path)
            logger.info(f"✓ Banner 2 (SVG) 已保存: {banner2_path}")
        else:
            logger.info("⚠ Banner 2: 未生成SVG")
        
        return saved
    
    def generate_banner_html(
        self,
        large_image: Optional[Dict] = None,
        svg_banner: Optional[str] = None,
        prefer_image: bool = True
    ) -> str:
        """
        生成用于插入HTML的Banner代码
        
        Args:
            large_image: 图片信息
            svg_banner: SVG代码
            prefer_image: 优先使用图片还是SVG
            
        Returns:
            HTML代码
        """
        # 优先使用图片banner
        if prefer_image and large_image:
            return f'<img src="{large_image["url"]}" alt="Banner" style="width: 100%; height: auto; display: block;" />'
        
        # 使用SVG banner
        if svg_banner:
            return svg_banner
        
        # 如果都没有，使用图片（如果有）
        if large_image:
            return f'<img src="{large_image["url"]}" alt="Banner" style="width: 100%; height: auto; display: block;" />'
        
        # 都没有，返回空占位符
        return '<!-- No banner available -->'
