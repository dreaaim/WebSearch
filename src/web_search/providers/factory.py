from enum import Enum
from typing import Optional, Dict, Type
from .base import SearchProvider
from .searxng import SearXNGProvider
from ..core.exceptions import ProviderNotFoundException

class ProviderType(Enum):
    SEARXNG = "searxng"
    TAVILY = "tavily"
    EXA = "exa"
    BING = "bing"

class SearchProviderFactory:
    _providers: Dict[str, Type[SearchProvider]] = {
        ProviderType.SEARXNG.value: SearXNGProvider,
    }

    @classmethod
    def register(cls, name: str, provider_class: Type[SearchProvider]):
        cls._providers[name.lower()] = provider_class

    @classmethod
    def create(
        cls,
        name: str,
        **kwargs
    ) -> SearchProvider:
        provider_class = cls._providers.get(name.lower())
        if not provider_class:
            raise ProviderNotFoundException(f"Unknown provider: {name}")
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())
