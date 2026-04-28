"""
DEPRECATED: Use extractor.FactExtractor instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated fact extraction via FactExtractor.
"""
from typing import List
from ..core.models import SearchResult, Claim
from datetime import datetime

class ClaimExtractor:
    """Claim声明提取器"""

    def extract(self, result: SearchResult) -> List[Claim]:
        """从搜索结果中提取声明"""
        statement = result.snippet[:200] if result.snippet else ""
        if not statement:
            statement = result.title

        claim = Claim(
            result=result,
            statement=statement,
            key_facts=self._extract_key_facts(result),
            timestamp=datetime.now()
        )
        return [claim]

    def _extract_key_facts(self, result: SearchResult) -> List[str]:
        """提取关键事实点"""
        facts = []
        if result.title:
            facts.append(result.title)
        if result.snippet:
            facts.append(result.snippet[:100])
        return facts