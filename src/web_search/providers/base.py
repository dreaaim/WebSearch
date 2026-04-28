from abc import ABC, abstractmethod
from typing import Optional, List
from ..core.models import SearchResponse, SearchOptions

class SearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def supported_engines(self) -> List[str]:
        return []

    @abstractmethod
    def search(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> SearchResponse:
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        pass
