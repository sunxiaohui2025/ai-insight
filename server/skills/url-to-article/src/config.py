"""配置文件

安全说明：
- 本 skill 运行在 agent 智能体中，模型能力由宿主 agent 提供，
  代码内不硬编码、也不引用任何模型地址 / 名称 / 密钥，避免敏感信息泄露。
- 翻译、HTML 生成等 LLM 任务由宿主 agent 参照 prompts/ 模板完成，
  skill 本身不直连任何大模型，因此这里没有任何 LLM 配置项。
"""
from pathlib import Path

class Config:
    # X 平台配置
    X_HEADLESS = True  # 无头模式：浏览器在后台运行，不弹出窗口；仍保留绕过登录墙能力
    X_TIMEOUT = 30000  # 超时时间（毫秒）
    X_WAIT_TIME = 5000  # 等待内容加载的时间（毫秒）

    # 输出配置
    BASE_DIR = Path(__file__).parent.parent
    OUTPUT_DIR = BASE_DIR / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)  # 确保输出目录存在
