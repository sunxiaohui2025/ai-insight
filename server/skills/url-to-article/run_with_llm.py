"""完整工作流示例 - 集成LLM调用

这个脚本演示如何调用LLM完成翻译、SVG生成和HTML生成。
你需要根据实际情况修改LLM调用部分。
"""
from src.workflow import ArticleWorkflow
from pathlib import Path
import sys


def load_prompt(prompt_file: str) -> str:
    """加载提示词模板"""
    prompt_path = Path(__file__).parent / "prompts" / prompt_file
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def call_llm(prompt: str, user_message: str) -> str:
    """
    调用LLM的函数（需要根据实际情况修改）
    
    这里只是一个占位符，你需要替换成实际的LLM调用代码，例如：
    - 使用 Anthropic Claude API
    - 使用 OpenAI API
    - 或其他LLM服务
    """
    # TODO: 替换成实际的LLM调用
    # 示例（使用Anthropic Claude）:
    # import anthropic
    # client = anthropic.Anthropic(api_key="your-api-key")
    # response = client.messages.create(
    #     model="claude-3-5-sonnet-20241022",
    #     max_tokens=4000,
    #     messages=[
    #         {"role": "user", "content": f"{prompt}\n\n{user_message}"}
    #     ]
    # )
    # return response.content[0].text
    
    raise NotImplementedError(
        "请在这里实现实际的LLM调用逻辑！\n"
        "参考上面的注释，根据你使用的LLM服务修改代码。"
    )


def translate_text(text: str) -> str:
    """翻译函数"""
    prompt = load_prompt("translate.md")
    return call_llm(prompt, text)


def generate_svg_banner(data: dict) -> str:
    """生成SVG Banner"""
    prompt = load_prompt("banner_svg.md")
    
    user_message = f"""
请根据以下信息生成SVG Banner：

标题：{data['title']}
内容片段：{data['content']}

请直接输出SVG代码，不要包含任何markdown标记。
"""
    return call_llm(prompt, user_message)


def generate_summary_html(data: dict) -> str:
    """生成一页纸解读HTML"""
    prompt = load_prompt("summary_html.md")
    
    user_message = f"""
请根据以下信息生成一页纸解读HTML：

标题：{data['title']}
作者：{data['author']}
发布时间：{data['created_at']}
原文链接：{data['url']}

正文内容：
{data['content']}

请直接输出HTML代码，第一行即 <!DOCTYPE html>，不要包含markdown标记。
记得在顶部保留 <div class="banner"><!--BANNER_SLOT--></div> 结构。
"""
    return call_llm(prompt, user_message)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python run_with_llm.py <URL>")
        print("\n注意: 请先修改 call_llm() 函数，实现实际的LLM调用逻辑")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print("=" * 80)
    print("完整工作流 - 集成LLM")
    print("=" * 80)
    print(f"\nURL: {url}\n")
    
    try:
        # 检查LLM函数是否已实现
        workflow = ArticleWorkflow()
        
        result = workflow.process(
            url=url,
            llm_translate_func=translate_text,
            llm_summary_html_func=generate_summary_html,
            llm_banner_svg_func=generate_svg_banner
        )
        
        if result['success']:
            print("\n" + "=" * 80)
            print("✅ 处理完成！")
            print("=" * 80)
            
            print("\n📊 结果摘要:")
            print(f"  - 平台: {result['extraction']['platform']}")
            print(f"  - 语言: {result['extraction']['language']}")
            print(f"  - 是否翻译: {'是' if result['translated_text'] else '否'}")
            
            print("\n🎨 Banner文件:")
            if result['banners']['saved_files'].get('banner_image'):
                print(f"  - 图片Banner: {result['banners']['saved_files']['banner_image']}")
            if result['banners']['saved_files'].get('banner_svg'):
                print(f"  - SVG Banner: {result['banners']['saved_files']['banner_svg']}")
            
            print("\n📄 HTML文件:")
            if result['html']['summary']:
                print(f"  - 一页纸解读: {result['html']['summary']}")
            
            print("\n📁 所有生成的文件:")
            for key, path in result['all_files'].items():
                if path:
                    print(f"  - {key}: {path}")
            
            print("\n✨ 所有文件已保存到 output/ 目录")
        else:
            print(f"\n❌ 处理失败: {result.get('error', 'Unknown error')}")
    
    except NotImplementedError as e:
        print(f"\n⚠️  {e}")
        print("\n请按照以下步骤操作：")
        print("1. 编辑 run_with_llm.py 文件")
        print("2. 找到 call_llm() 函数")
        print("3. 根据你使用的LLM服务（Claude/GPT等）实现调用逻辑")
        print("4. 配置API密钥")
        print("5. 重新运行此脚本")
    
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
