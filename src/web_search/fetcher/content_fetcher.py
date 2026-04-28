from typing import List, Optional
from dataclasses import dataclass
import logging

from ..core.models import SearchResult
from .text_extractor import TextExtractor, TextExtractionResult
from .js_renderer import JsRenderer

logger = logging.getLogger(__name__)


@dataclass
class ContentFetchResult:
    result: SearchResult
    content: str
    fetch_success: bool
    error_reason: Optional[str] = None
    used_js_rendering: bool = False


class ContentFetcher:
    def __init__(
        self,
        timeout: float = 10.0,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        max_content_length: int = 100000,
        min_text_length: int = 100,
        enable_js_rendering: bool = True,
        js_render_timeout: float = 30.0,
        js_render_wait: float = 5.0,
        js_max_retries: int = 2,
    ):
        self.timeout = timeout
        self.user_agent = user_agent
        self.max_content_length = max_content_length
        self.min_text_length = min_text_length
        self.enable_js_rendering = enable_js_rendering
        self.text_extractor = TextExtractor(
            min_text_length=min_text_length,
            max_text_length=max_content_length
        )
        self._js_renderer: Optional[JsRenderer] = None
        self._js_render_timeout = js_render_timeout
        self._js_render_wait = js_render_wait
        self._js_max_retries = js_max_retries

    def fetch(self, results: List[SearchResult]) -> List[ContentFetchResult]:
        fetch_results: List[ContentFetchResult] = []

        for result in results:
            content_result = self._fetch_single(result)
            fetch_results.append(content_result)

            if not content_result.fetch_success:
                logger.warning(
                    f"Failed to fetch content from {result.url}: {content_result.error_reason}"
                )

        return fetch_results

    def _get_js_renderer(self) -> Optional[JsRenderer]:
        if not self.enable_js_rendering:
            return None
        if self._js_renderer is None:
            self._js_renderer = JsRenderer(
                timeout=self._js_render_timeout,
                wait_time=self._js_render_wait,
                max_retries=self._js_max_retries,
            )
        return self._js_renderer

    def _fetch_single(self, result: SearchResult) -> ContentFetchResult:
        try:
            html_content = self._download_url(result.url)
            if html_content is None:
                if self.enable_js_rendering and self._needs_js_rendering(result.url):
                    return self._fetch_with_js_rendering(result)
                return ContentFetchResult(
                    result=result,
                    content="",
                    fetch_success=False,
                    error_reason="Failed to download URL"
                )

            extraction_result = self.text_extractor.extract_text(html_content)
            if not extraction_result.success:
                if self.enable_js_rendering and self._needs_js_rendering(result.url):
                    return self._fetch_with_js_rendering(result)
                return ContentFetchResult(
                    result=result,
                    content="",
                    fetch_success=False,
                    error_reason=extraction_result.error_reason
                )

            return ContentFetchResult(
                result=result,
                content=extraction_result.text,
                fetch_success=True
            )

        except Exception as e:
            return ContentFetchResult(
                result=result,
                content="",
                fetch_success=False,
                error_reason=f"Unexpected error: {str(e)}"
            )

    def _needs_js_rendering(self, url: str) -> bool:
        renderer = self._get_js_renderer()
        if renderer:
            return renderer.needs_js_rendering(url)
        return False

    def _fetch_with_js_rendering(self, result: SearchResult) -> ContentFetchResult:
        renderer = self._get_js_renderer()
        if not renderer:
            return ContentFetchResult(
                result=result,
                content="",
                fetch_success=False,
                error_reason="JS renderer not available"
            )

        html_content = renderer.render(result.url)
        if html_content is None:
            return ContentFetchResult(
                result=result,
                content="",
                fetch_success=False,
                error_reason="JS rendering failed to get content",
                used_js_rendering=True
            )

        extraction_result = self.text_extractor.extract_text(html_content)
        if not extraction_result.success:
            return ContentFetchResult(
                result=result,
                content="",
                fetch_success=False,
                error_reason=f"JS rendered content too short: {extraction_result.error_reason}",
                used_js_rendering=True
            )

        return ContentFetchResult(
            result=result,
            content=extraction_result.text,
            fetch_success=True,
            used_js_rendering=True
        )

    def _download_url(self, url: str) -> Optional[str]:
        import urllib.request
        import urllib.error

        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent}
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    logger.debug(f"Skipping non-HTML content type: {content_type}")
                    return None

                charset = self._extract_charset(response.headers)
                html_content = response.read()

                if charset:
                    try:
                        html_content = html_content.decode(charset)
                    except UnicodeDecodeError:
                        html_content = html_content.decode("utf-8", errors="replace")
                else:
                    html_content = html_content.decode("utf-8", errors="replace")

                return html_content

        except urllib.error.URLError as e:
            logger.debug(f"URL error for {url}: {e}")
            return None
        except TimeoutError:
            logger.debug(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.debug(f"Error downloading {url}: {e}")
            return None

    def _extract_charset(self, headers) -> Optional[str]:
        content_type = headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
            return charset
        return None

    def close(self):
        if self._js_renderer:
            self._js_renderer.close()
            self._js_renderer = None

    def __del__(self):
        self.close()