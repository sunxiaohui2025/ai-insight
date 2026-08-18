"""测试抓取 X 页面"""
from src.fetchers.x_fetcher import XFetcher
from bs4 import BeautifulSoup

url = "https://x.com/hwchase17/status/2085780032031760694"

fetcher = XFetcher()
html = fetcher.fetch(url)

# 保存原始 HTML
with open("debug_page.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✓ HTML 已保存到 debug_page.html")

# 分析内容
soup = BeautifulSoup(html, 'lxml')

# 检查是否有登录提示
login_texts = ["Log in", "Sign up", "Don't miss what's happening"]
has_login_wall = any(text in html for text in login_texts)
print(f"检测到登录墙: {has_login_wall}")

# 查找推文相关元素
articles = soup.select('article[data-testid="tweet"]')
print(f"找到的 article 元素数量: {len(articles)}")

tweet_texts = soup.select('div[data-testid="tweetText"]')
print(f"找到的 tweetText 元素数量: {len(tweet_texts)}")

# 打印部分文本内容
if tweet_texts:
    print("\n找到的推文文本:")
    for idx, text in enumerate(tweet_texts[:3]):
        print(f"\n推文 {idx+1}:")
        print(text.get_text()[:200])
else:
    print("\n⚠ 未找到推文文本")
    
    # 尝试其他选择器
    all_text = soup.get_text()
    if "Log in" in all_text or "Sign up" in all_text:
        print("✗ 页面显示了登录墙，需要登录才能查看内容")
