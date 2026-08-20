"""语言检测工具函数"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def detect_language(text: str, default: str = 'en') -> str:
    """
    检测文本语言，带完善的错误处理
    
    Args:
        text: 要检测的文本
        default: 检测失败时的默认语言
        
    Returns:
        语言代码（如 'en', 'zh-cn' 等）
    """
    if not text or len(text.strip()) < 10:
        logger.debug(f"文本太短，无法准确检测语言，返回默认值: {default}")
        return default
    
    try:
        import langdetect
        # 设置随机种子以提高稳定性
        langdetect.DetectorFactory.seed = 0
        lang = langdetect.detect(text)
        logger.debug(f"检测到语言: {lang}")
        return lang
    except ImportError:
        logger.warning("langdetect 未安装，返回默认语言")
        return default
    except Exception as e:
        logger.debug(f"语言检测失败: {e}，返回默认值: {default}")
        return default


def is_english(text: str) -> bool:
    """
    判断文本是否为英文
    
    Args:
        text: 要检测的文本
        
    Returns:
        是否为英文
    """
    lang = detect_language(text)
    return lang.startswith('en')


def needs_translation(text: str, target_lang: str = 'zh') -> bool:
    """
    判断文本是否需要翻译
    
    Args:
        text: 要检测的文本
        target_lang: 目标语言
        
    Returns:
        是否需要翻译
    """
    detected_lang = detect_language(text)
    
    # 如果检测到的语言不是目标语言，则需要翻译
    if detected_lang.startswith(target_lang):
        return False
    
    return True
