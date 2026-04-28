import pytest
from web_search.providers.factory import SearchProviderFactory, ProviderType
from web_search.providers.searxng import SearXNGProvider
from web_search.core.exceptions import ProviderNotFoundException

def test_provider_type_values():
    assert ProviderType.SEARXNG.value == "searxng"
    assert ProviderType.TAVILY.value == "tavily"

def test_factory_create_searxng():
    provider = SearchProviderFactory.create("searxng", base_url="http://localhost:8080")
    assert isinstance(provider, SearXNGProvider)
    assert provider.name == "searxng"

def test_factory_register():
    class CustomProvider:
        pass
    SearchProviderFactory.register("custom", CustomProvider)
    assert "custom" in SearchProviderFactory._providers

def test_factory_list_providers():
    providers = SearchProviderFactory.list_providers()
    assert "searxng" in providers

def test_factory_unknown_provider_raises():
    with pytest.raises(ProviderNotFoundException):
        SearchProviderFactory.create("unknown_provider")