import pytest
from unittest.mock import Mock, patch
from web_search.providers.searxng import SearXNGProvider
from web_search.core.models import SearchResponse, SearchOptions

def test_searxng_provider_name():
    provider = SearXNGProvider()
    assert provider.name == "searxng"

def test_searxng_provider_supported_engines():
    provider = SearXNGProvider()
    assert "google" in provider.supported_engines
    assert "bing" in provider.supported_engines
    assert "duckduckgo" in provider.supported_engines

def test_searxng_provider_default_engines():
    provider = SearXNGProvider()
    assert provider.default_engines == ["google", "bing"]

def test_searxng_provider_custom_engines():
    provider = SearXNGProvider(default_engines=["baidu"])
    assert provider.default_engines == ["baidu"]

def test_searxng_extract_domain():
    provider = SearXNGProvider()
    assert provider._extract_domain("https://www.google.com/search") == "www.google.com"
    assert provider._extract_domain("http://example.com") == "example.com"

def test_searxng_infer_source_type():
    provider = SearXNGProvider()
    from web_search.core.models import SourceType
    item = {"url": "https://www.gov.cn"}
    assert provider._infer_source_type(item) == SourceType.OFFICIAL
    item = {"url": "https://www.example.com"}
    assert provider._infer_source_type(item) == SourceType.MEDIA

def test_searxng_infer_source_level():
    provider = SearXNGProvider()
    item = {"url": "https://www.example.com"}
    assert provider._infer_source_level(item).value == "municipal"