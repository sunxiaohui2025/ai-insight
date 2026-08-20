"""配置文件"""
import os
from pathlib import Path

class Config:
    # LLM 配置
    KIMI_API_BASE = "http://1.181.141.96:6018/kimi-k2.6/v1/chat/completions"
    KIMI_MODEL = "Kimi-K2.6"
    KIMI_API_KEY = "123"

    # 上下文与输出长度
    # 服务端 max_model_len = 1048576（1M），这里不再对输入做截断
    MAX_CONTEXT_TOKENS = 1_000_000
    MAX_INPUT_CHARS = 800_000      # 仅作为极端情况的兜底保护
    MAX_OUTPUT_TOKENS = 64_000     # 单次生成的输出上限，避免 HTML 被截断
    LLM_TIMEOUT = 600              # 长文生成需要更长超时（秒）

    # X 平台配置
    X_USE_PLAYWRIGHT = True
    X_HEADLESS = False  # 非无头模式，尝试绕过登录墙
    X_TIMEOUT = 30000
    X_WAIT_TIME = 5000  # 等待内容加载的时间（毫秒）
    
    # 输出配置
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "output"
    SAVE_MEDIA = False

    # Banner 配置
    BANNER_MIN_WIDTH = 600      # 候选图最小宽度（像素），低于此值视为 logo/头像
    BANNER_MIN_HEIGHT = 300     # 候选图最小高度（像素）
    BANNER_MIN_ASPECT = 1.2     # 最小宽高比，过滤竖图和方图（头像多为 1:1）
    BANNER_MAX_CANDIDATES = 5   # 最多尝试前 N 张图片
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)
