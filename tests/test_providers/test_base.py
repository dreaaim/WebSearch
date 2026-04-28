import pytest
from abc import ABC
from web_search.providers.base import SearchProvider
from web_search.core.models import SearchOptions, SearchResponse, SearchResult

def test_search_provider_is_abc():
    assert issubclass(SearchProvider, ABC)

def test_search_provider_has_name_property():
    class DummyProvider(SearchProvider):
        @property
        def name(self) -> str:
            return "dummy"
        def search(self, query, options=None):
            return SearchResponse(query=query, results=[], total_count=0, search_time=0.0)
        def validate_config(self):
            return True

    provider = DummyProvider()
    assert provider.name == "dummy"

def test_search_provider_has_supported_engines():
    class DummyProvider(SearchProvider):
        @property
        def name(self) -> str:
            return "dummy"
        def search(self, query, options=None):
            return SearchResponse(query=query, results=[], total_count=0, search_time=0.0)
        def validate_config(self):
            return True

    provider = DummyProvider()
    assert provider.supported_engines == []