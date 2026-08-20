"""通用网页抓取器 - 支持普通网页内容获取"""

import requests
import time

# Playwright 为可选项：静态网页优先用 requests，动态网页才需要浏览器。
# 未安装时 _fetch_with_browser 会抛出明确错误。
try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False


class GenericFetcher:
    """通用网页抓取器，支持静态和动态网页"""
    
    def __init__(self, use_browser: bool = False, headless: bool = True, timeout: int = 30000):
        """
        初始化通用网页抓取器
        
        Args:
            use_browser: 是否使用浏览器（用于动态网页）
            headless: 是否无头模式
            timeout: 超时时间（毫秒）
        """
        self.use_browser = use_browser
        self.headless = headless
        self.timeout = timeout
    
    def fetch(self, url: str) -> str:
        """
        抓取网页内容
        
        Args:
            url: 网页 URL
            
        Returns:
            str: HTML 内容
            
        Raises:
            Exception: 抓取失败时抛出异常
        """
        # 先尝试简单的 requests
        try:
            return self._fetch_with_requests(url)
        except Exception as e:
            print(f"Requests 抓取失败，尝试使用浏览器: {e}")
            # 如果失败，使用浏览器
            return self._fetch_with_browser(url)
    
    def _fetch_with_requests(self, url: str) -> str:
        """使用 requests 抓取（适合静态网页）"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        return response.text
    
    def _fetch_with_browser(self, url: str) -> str:
        """使用 Playwright 浏览器抓取（适合动态网页）"""
        if not _PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright 未安装（缺少依赖 playwright / chromium 浏览器），"
                "无法抓取动态网页。静态网页会通过 requests 正常抓取。"
            )

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='zh-CN',
                timezone_id='Asia/Shanghai'
            )
            
            # 隐藏 webdriver 属性
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = context.new_page()
            
            try:
                page.goto(url, wait_until='networkidle', timeout=self.timeout)
                time.sleep(2)  # 等待动态内容加载
                
                html = page.content()
                return html
                
            finally:
                browser.close()
