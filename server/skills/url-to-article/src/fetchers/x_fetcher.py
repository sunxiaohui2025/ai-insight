"""X (Twitter) 平台内容抓取器"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from src.config import Config
import time


class XFetcher:
    def __init__(self):
        self.headless = Config.X_HEADLESS
        self.timeout = Config.X_TIMEOUT
        self.wait_time = Config.X_WAIT_TIME
    
    def fetch(self, url: str) -> str:
        """
        使用 Playwright 抓取 X 页面内容

        Args:
            url: X 推文链接

        Returns:
            str: 页面 HTML 内容
        """
        print(f"开始抓取 X 页面: {url}")

        with sync_playwright() as p:
            # 启动浏览器，添加更多参数以绕过检测
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )

            # 创建上下文，设置更完整的浏览器特征
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

            page = context.new_page()

            # 隐藏 webdriver 特征
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                # 访问页面，使用更宽松的等待策略
                print("正在访问页面...")
                page.goto(url, timeout=60000, wait_until='domcontentloaded')

                # 等待推文内容加载
                print("等待推文内容加载...")
                try:
                    # 尝试等待推文元素出现
                    page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
                    print("✓ 推文元素已加载")
                except:
                    print("⚠ 未检测到推文元素，继续尝试...")

                # 额外等待时间让动态内容加载
                time.sleep(5)

                # 尝试滚动页面以加载更多内容（如果是推文串）
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(3)
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(2)
                except:
                    pass

                # 获取页面内容
                html = page.content()

                # 检查是否有实际内容
                if len(html) < 1000:
                    print("⚠ 警告: 页面内容过少，可能未正确加载")

                print(f"✓ 页面内容抓取成功，HTML 大小: {len(html)} 字符")
                return html

            except PlaywrightTimeout:
                print("✗ 页面加载超时")
                # 尝试获取当前已加载的内容
                try:
                    html = page.content()
                    if html and len(html) > 1000:
                        print("⚠ 使用部分加载的内容")
                        return html
                except:
                    pass
                raise

            except Exception as e:
                print(f"✗ 抓取失败: {e}")
                raise

            finally:
                browser.close()
