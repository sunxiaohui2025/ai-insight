"""skill 根目录入口 —— 供宿主 agent 的脚本运行器调用

背景：宿主环境下，脚本运行器要求目标脚本位于 skill 根目录，
且必须导出 generate(**kwargs) 或 run(**kwargs)。
src/main.py 位于 src/ 子目录，直接作为入口时无法 import（No module named 'src'）。

本文件把 skill 根目录加入 sys.path，并导出 run/generate 两个入口，
宿主 agent 用 generate(url="...") 调用即可完成「抓取 + 解析 + 保存素材」。

LLM 任务（翻译 / 完整文章 HTML / 一页纸解读 / Banner）由宿主 agent
参照 prompts/ 模板自行完成，本入口不直连任何大模型。
"""
import sys
from pathlib import Path

# 确保 skill 根目录在 sys.path 上，使 from src.main import ... 可正常工作
SKILL_ROOT = Path(__file__).resolve().parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from src.main import ArticleExtractor  # noqa: E402


def run(url: str = "", **kwargs) -> dict:
    """抓取 + 解析指定的 URL，返回提取结果与素材保存路径。

    Args:
        url: 待处理的文章 / 推文链接
        save_to_file: 是否把素材写入 output/（默认 True）

    Returns:
        dict: 与 src.main.process_url 一致的提取结果
    """
    if not url:
        return {"success": False, "error": "缺少必填参数 url"}

    save_to_file = bool(kwargs.get("save_to_file", True))
    extractor = ArticleExtractor()
    return extractor.process_url(url, save_to_file=save_to_file)


def generate(url: str = "", **kwargs) -> dict:
    """与 run 等价，兼容「产物型脚本」接口，直接返回提取素材。

    素材已由内部保存到 output/extract_*.{json,md}；
    宿主 agent 读取该素材后，按 prompts/ 模板生成最终文章。
    """
    return run(url=url, **kwargs)


if __name__ == "__main__":
    # 兼容命令行直接运行：python run_skill.py "<URL>"
    if len(sys.argv) > 1:
        result = run(url=sys.argv[1])
        print(result)
    else:
        print("用法: python run_skill.py <URL> 或由宿主 agent 调用 generate(url=...)")
