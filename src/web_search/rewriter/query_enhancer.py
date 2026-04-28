from typing import List, Optional
from .intent_analyzer import IntentResult

class QueryEnhancer:
    SYNTAX_RULES = {
        "site": "site:{domain}",
        "after": "after:{date}",
        "before": "before:{date}",
        "exact": '"{phrase}"',
        "exclude": "-{word}"
    }

    def __init__(self):
        pass

    async def enhance(
        self,
        queries: List[str],
        intent_result: IntentResult
    ) -> List[str]:
        return self._enhance_sync(queries, intent_result)

    def _enhance_sync(
        self,
        queries: List[str],
        intent_result: IntentResult
    ) -> List[str]:
        enhanced = []
        for query in queries:
            enhanced_query = self._add_time_range(query, intent_result.time_range)
            enhanced_query = self._add_exact_match(enhanced_query, intent_result.key_entities)
            enhanced.append(enhanced_query)
        return enhanced

    def _add_time_range(self, query: str, time_range: str) -> str:
        if time_range == "任意":
            return query

        time_map = {
            "最近一周": "7",
            "最近一月": "30",
            "最近一年": "365"
        }

        days = time_map.get(time_range)
        if days:
            return f"{query} after:2024-01-01"
        return query

    def _add_exact_match(self, query: str, entities: List[str]) -> str:
        if entities:
            main_entity = entities[0] if entities else ""
            if len(main_entity) > 2:
                return f'"{main_entity}" {query}'
        return query
