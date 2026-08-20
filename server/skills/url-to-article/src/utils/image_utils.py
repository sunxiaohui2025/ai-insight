"""图片处理工具函数"""
import requests
from io import BytesIO
from PIL import Image
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def get_image_size(image_url: str, timeout: int = 10) -> Optional[Tuple[int, int]]:
    """
    获取图片尺寸
    
    Args:
        image_url: 图片URL
        timeout: 超时时间（秒）
        
    Returns:
        (width, height) 或 None（如果失败）
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(image_url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # 只读取部分数据来获取尺寸，提高效率
        img = Image.open(BytesIO(response.content))
        return img.size
    except Exception as e:
        logger.debug(f"无法获取图片尺寸 {image_url}: {e}")
        return None


def filter_images_by_size(image_urls: List[str], min_width: int = 640, min_height: int = 640) -> List[Dict[str, any]]:
    """
    过滤出符合尺寸要求的图片
    
    Args:
        image_urls: 图片URL列表
        min_width: 最小宽度
        min_height: 最小高度
        
    Returns:
        符合条件的图片列表，包含url和尺寸信息
    """
    filtered_images = []
    
    for url in image_urls:
        size = get_image_size(url)
        if size:
            width, height = size
            if width >= min_width or height >= min_height:
                filtered_images.append({
                    'url': url,
                    'width': width,
                    'height': height
                })
                logger.debug(f"✓ 图片符合尺寸要求: {url} ({width}x{height})")
            else:
                logger.debug(f"✗ 图片尺寸不足: {url} ({width}x{height})")
    
    return filtered_images


def get_first_large_image(image_urls: List[str], min_width: int = 640, min_height: int = 640) -> Optional[Dict[str, any]]:
    """
    获取第一张大于指定尺寸的图片
    
    Args:
        image_urls: 图片URL列表
        min_width: 最小宽度
        min_height: 最小高度
        
    Returns:
        第一张符合条件的图片信息，或None
    """
    for url in image_urls:
        size = get_image_size(url)
        if size:
            width, height = size
            if width >= min_width or height >= min_height:
                logger.info(f"✓ 找到符合尺寸的图片: {url} ({width}x{height})")
                return {
                    'url': url,
                    'width': width,
                    'height': height
                }
            else:
                logger.debug(f"跳过尺寸不足的图片: {url} ({width}x{height})")
    
    logger.info("未找到符合尺寸要求的图片")
    return None
