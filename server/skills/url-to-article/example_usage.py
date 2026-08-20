"""完整使用示例 - 演示整个工作流程"""
from src.main import ArticleExtractor
import json


def main():
    """演示完整的文章提取和处理流程"""
    
    # 示例URL（你可以替换成实际的URL）
    test_urls = [
        "https://example.com/article",  # 通用网页
        # "https://x.com/username/status/123456",  # X平台
    ]
    
    extractor = ArticleExtractor()
    
    for url in test_urls:
        print(f"\n{'='*80}")
        print(f"处理URL: {url}")
        print(f"{'='*80}\n")
        
        try:
            result = extractor.process_url(url)
            
            if result['success']:
                print("\n✅ 提取成功！")
                print(f"\n📊 基本信息:")
                print(f"  - 平台: {result['platform']}")
                print(f"  - 语言: {result['language']}")
                print(f"  - 标题: {result['metadata'].get('title', 'N/A')[:50]}...")
                print(f"  - 正文长度: {len(result['full_text'])} 字符")
                
                print(f"\n🖼️  媒体资源:")
                print(f"  - 图片数量: {len(result['media']['images'])}")
                print(f"  - 视频数量: {len(result['media']['videos'])}")
                
                # 检查Banner图片
                if result.get('large_image'):
                    img = result['large_image']
                    print(f"\n🎨 找到Banner图片:")
                    print(f"  - URL: {img['url'][:60]}...")
                    print(f"  - 尺寸: {img['width']}x{img['height']}")
                    print(f"  ✅ 可以直接使用此图片作为Banner")
                else:
                    print(f"\n⚠️  未找到大尺寸图片")
                    print(f"  💡 建议: 使用 prompts/banner_svg.md 生成SVG Banner")
                
                print(f"\n📁 保存的文件:")
                for file_type, file_path in result['saved_files'].items():
                    print(f"  - {file_type}: {file_path}")
                
                print(f"\n📝 下一步操作:")
                print(f"  1. 如果语言是英文 ({result['language']}), 使用 prompts/translate.md 翻译")
                print(f"  2. 使用 prompts/summary_html.md 生成一页纸解读HTML")
                print(f"  3. Banner选项:")
                if result.get('large_image'):
                    print(f"     - 选项1: 使用提取的图片 ({result['large_image']['width']}x{result['large_image']['height']})")
                else:
                    print(f"     - 选项1: 未找到合适图片，跳过")
                print(f"     - 选项2: 使用 prompts/banner_svg.md 生成SVG")
                
            else:
                print("\n❌ 提取失败")
                print(f"错误: {result.get('error', 'Unknown error')}")
                if result.get('hint'):
                    print(f"提示: {result['hint']}")
                    
        except Exception as e:
            print(f"\n❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
