from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)


class JsRenderer:
    JS_RENDER_DOMAINS = {
        "baijiahao.baidu.com",
        "toutiao.com",
        "weibo.com",
        "zhihu.com",
        "douban.com",
        "youku.com",
        "iqiyi.com",
        "v.qq.com",
        "v.so.com",
        "vzkoo.com",
        "so.com",
        "wenku.so.com",
        "iask.sina.com.cn",
        "news.sina.com.cn",
    }

    def __init__(
        self,
        timeout: float = 30.0,
        wait_time: float = 5.0,
        enable_headless: bool = True,
        max_retries: int = 2,
    ):
        self.timeout = timeout
        self.wait_time = wait_time
        self.enable_headless = enable_headless
        self.max_retries = max_retries
        self._driver = None
        self._last_error: Optional[str] = None

    def needs_js_rendering(self, url: str) -> bool:
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            for js_domain in self.JS_RENDER_DOMAINS:
                if domain.endswith(js_domain) or domain == js_domain:
                    return True
            return False
        except Exception:
            return False

    def render(self, url: str) -> Optional[str]:
        if not self.needs_js_rendering(url):
            return None

        self._last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                html_content = self._try_undetected_chromedriver(url)
                if html_content:
                    return html_content
            except Exception as e:
                self._last_error = f"undetected-chromedriver: {e}"
                logger.debug(f"Attempt {attempt + 1} failed with undetected-chromedriver: {e}")

            try:
                html_content = self._try_playwright(url)
                if html_content:
                    return html_content
            except Exception as e:
                self._last_error = f"playwright: {e}"
                logger.debug(f"Attempt {attempt + 1} failed with playwright: {e}")

            if attempt < self.max_retries:
                time.sleep(1)

        logger.warning(f"JS rendering failed for {url} after {self.max_retries + 1} attempts. Last error: {self._last_error}")
        return None

    def _try_undetected_chromedriver(self, url: str) -> Optional[str]:
        try:
            import undetected_chromedriver as uc
        except ImportError:
            return None

        try:
            if self._driver is None:
                options = uc.ChromeOptions()
                if self.enable_headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-infobars")
                options.add_argument("--start-maximized")
                options.add_argument("--disable-web-security")
                options.add_argument("--disable-features=IsolateOrigins,site-per-process")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
                prefs = {
                    "profile.default_content_setting_values.notifications": 2,
                    "profile.default_content_settings": {"images": 2},
                }
                options.add_experimental_option("prefs", prefs)

                self._driver = uc.Chrome(options=options, version_main=None)
                self._driver.set_page_load_timeout(self.timeout)
                self._driver.implicitly_wait(self.wait_time)

            self._driver.get(url)

            time.sleep(2)

            self._scroll_page()

            time.sleep(self.wait_time)

            html_content = self._driver.page_source

            if not html_content or len(html_content) < 500:
                raise ValueError("Page source too short or empty")

            if self._is_blocked_page(html_content):
                raise ValueError("Page is blocked, captcha or verification required")

            if self._is_no_content_page(html_content):
                raise ValueError("Page shows 404, paywall or no content")

            return html_content

        except Exception:
            self._driver = None
            raise

    def _scroll_page(self):
        if self._driver is None:
            return
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            for _ in range(3):
                self._driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(0.5)
            self._driver.execute_script("window.scrollTo(0, 0);")
        except Exception:
            pass

    def _try_playwright(self, url: str) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.enable_headless,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle", retries=2)
            except Exception as e:
                raise ValueError(f"Page load failed: {e}")
            page.wait_for_timeout(self.wait_time * 1000)
            html_content = page.content()

            if not html_content or len(html_content) < 500:
                raise ValueError("Page source too short or empty")

            if self._is_no_content_page(html_content):
                raise ValueError("Page shows 404, paywall or no content")

            browser.close()
            return html_content

    def _is_no_content_page(self, html_content: str) -> bool:
        no_content_patterns = [
            "404",
            "not found",
            "不存在",
            "无法访问",
            "访问出错",
            "page not found",
            "对不起，您访问的地址不存在",
            "请登录",
            "登录后可见",
            "付费",
            "购买",
            "开通会员",
            "vip",
            "剩余",
            "未读",
            "免费试读",
            "end of free preview",
            "paywall",
        ]
        html_lower = html_content.lower()
        for pattern in no_content_patterns:
            if pattern.lower() in html_lower:
                return True
        return False

    def _is_blocked_page(self, html_content: str) -> bool:
        blocked_patterns = [
            "操作太频繁",
            "请稍后再试",
            "访问被拒绝",
            "访问受限",
            "验证码",
            "captcha",
            "security check",
            "unusual traffic",
            "需要验证",
            "安全验证",
            "账号异常",
            "流量异常",
            "frequency",
            "blocked",
        ]
        html_lower = html_content.lower()
        for pattern in blocked_patterns:
            if pattern.lower() in html_lower:
                return True
        return False

    def close(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __del__(self):
        self.close()


def render_js_page(url: str, timeout: float = 20.0, wait_time: float = 3.0) -> Optional[str]:
    renderer = JsRenderer(timeout=timeout, wait_time=wait_time)
    try:
        return renderer.render(url)
    finally:
        renderer.close()