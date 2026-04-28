import pytest
from unittest.mock import patch, MagicMock
from web_search.fetcher.content_fetcher import ContentFetcher, ContentFetchResult
from web_search.fetcher.text_extractor import TextExtractor, TextExtractionResult
from web_search.fetcher.js_renderer import JsRenderer
from web_search.core.models import SearchResult, SourceType, SourceLevel, Classification


def create_search_result(url="https://example.com"):
    return SearchResult(
        title="Test Result",
        url=url,
        snippet="Test snippet",
        source_name="Test Source",
        source_domain="example.com",
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.NATIONAL,
        classification=Classification.WHITE
    )


class TestTextExtractor:
    def setup_method(self):
        self.extractor = TextExtractor(min_text_length=50, max_text_length=1000)

    def test_text_extraction_from_html(self):
        html_content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <main>
                <h1>Main Title</h1>
                <p>This is a paragraph with enough text to pass the minimum length check.
                It contains multiple sentences to ensure the text extraction works properly.
                The quick brown fox jumps over the lazy dog.</p>
            </main>
        </body>
        </html>
        """
        result = self.extractor.extract_text(html_content)
        assert result.success is True
        assert "Main Title" in result.text
        assert "paragraph" in result.text

    def test_text_extraction_min_length(self):
        short_html = "<html><body><p>Short content.</p></body></html>"
        result = self.extractor.extract_text(short_html)
        assert result.success is False
        assert "too short" in result.error_reason


class TestContentFetcher:
    def setup_method(self):
        self.fetcher = ContentFetcher(timeout=5.0, min_text_length=50, max_content_length=1000)

    def test_content_fetch_success(self):
        result = create_search_result()
        html_content = """
        <html>
        <body>
            <main>
                <h1>Test Article</h1>
                <p>This is the article content that should be extracted successfully.
                It has enough text to pass the minimum length requirement of the extractor.
                Multiple lines of content ensure we meet the threshold.</p>
            </main>
        </body>
        </html>
        """

        with patch.object(self.fetcher, '_download_url', return_value=html_content):
            fetch_result = self.fetcher._fetch_single(result)
            assert fetch_result.fetch_success is True
            assert fetch_result.content != ""
            assert fetch_result.result == result

    def test_content_fetch_timeout(self):
        result = create_search_result()

        with patch.object(self.fetcher, '_download_url', return_value=None):
            fetch_result = self.fetcher._fetch_single(result)
            assert fetch_result.fetch_success is False
            assert fetch_result.content == ""
            assert fetch_result.error_reason == "Failed to download URL"

    def test_content_fetch_empty_content(self):
        result = create_search_result()

        with patch.object(self.fetcher, '_download_url', return_value=""):
            fetch_result = self.fetcher._fetch_single(result)
            assert fetch_result.fetch_success is False
            assert fetch_result.content == ""
            assert fetch_result.error_reason == "Empty or None HTML content"

    def test_content_fetch_success_status(self):
        result = create_search_result()
        html_content = """
        <html>
        <body>
            <main>
                <p>This is valid content that should be extracted successfully.
                It contains enough text to pass the minimum length requirement.
                The extractor should process this and return success.</p>
            </main>
        </body>
        </html>
        """

        with patch.object(self.fetcher, '_download_url', return_value=html_content):
            fetch_result = self.fetcher._fetch_single(result)
            assert fetch_result.fetch_success is True
            assert isinstance(fetch_result, ContentFetchResult)


class TestJsRenderer:
    def setup_method(self):
        self.renderer = JsRenderer()

    def test_needs_js_rendering_known_domains(self):
        js_domains = [
            "https://baijiahao.baidu.com/s?id=123",
            "https://www.toutiao.com/article/456",
            "https://www.vzkoo.com/test",
            "https://wenku.so.com/test",
        ]
        for url in js_domains:
            assert self.renderer.needs_js_rendering(url) is True, f"Expected {url} to need JS rendering"

    def test_needs_js_rendering_normal_domains(self):
        normal_domains = [
            "https://www.example.com/page",
            "https://news.cctv.com/test",
            "https://www.xinhuanet.com/test",
        ]
        for url in normal_domains:
            assert self.renderer.needs_js_rendering(url) is False, f"Expected {url} NOT to need JS rendering"

    def test_js_rendering_disabled_domains(self):
        disabled_domains = [
            "https://www.gov.cn/test",
            "https://www.baidu.com/s?wd=test",
        ]
        for url in disabled_domains:
            assert self.renderer.needs_js_rendering(url) is False


class TestContentFetcherJsRendering:
    def setup_method(self):
        self.fetcher = ContentFetcher(
            timeout=5.0,
            min_text_length=50,
            max_content_length=1000,
            enable_js_rendering=True
        )

    def test_js_rendering_on_known_domain(self):
        result = create_search_result(url="https://baijiahao.baidu.com/s?id=123")
        html_content = """
        <html>
        <body>
            <main>
                <p>This is JS rendered content that should be extracted.
                It contains enough text to pass the minimum length requirement.
                The extractor should process this and return success.</p>
            </main>
        </body>
        </html>
        """

        with patch.object(self.fetcher, '_download_url', return_value=None):
            with patch.object(self.fetcher, '_fetch_with_js_rendering') as mock_js:
                mock_js.return_value = ContentFetchResult(
                    result=result,
                    content="JS rendered content",
                    fetch_success=True,
                    used_js_rendering=True
                )
                fetch_result = self.fetcher._fetch_single(result)
                assert mock_js.called is True

    def test_js_rendering_not_triggered_for_normal_urls(self):
        result = create_search_result(url="https://www.example.com/page")
        html_content = """
        <html>
        <body>
            <main>
                <p>Normal page content with enough text to pass the minimum length.
                This should be extracted without triggering JS rendering.</p>
            </main>
        </body>
        </html>
        """

        with patch.object(self.fetcher, '_download_url', return_value=html_content):
            with patch.object(self.fetcher, '_fetch_with_js_rendering') as mock_js:
                fetch_result = self.fetcher._fetch_single(result)
                assert mock_js.called is False
                assert fetch_result.fetch_success is True

    def test_js_rendering_disabled(self):
        fetcher_no_js = ContentFetcher(
            timeout=5.0,
            min_text_length=50,
            max_content_length=1000,
            enable_js_rendering=False
        )
        result = create_search_result(url="https://baijiahao.baidu.com/s?id=123")

        with patch.object(fetcher_no_js, '_download_url', return_value=None):
            with patch.object(fetcher_no_js, '_fetch_with_js_rendering') as mock_js:
                fetch_result = fetcher_no_js._fetch_single(result)
                assert mock_js.called is False
                assert fetch_result.fetch_success is False
                assert "Failed to download URL" in fetch_result.error_reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])