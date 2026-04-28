from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

class QueryIntent(Enum):
    FACTUAL_QUERY = "factual"
    OPINION_QUERY = "opinion"
    COMPARISON_QUERY = "compare"
    HOWTO_QUERY = "howto"
    NEWS_QUERY = "news"
    RESEARCH_QUERY = "research"

@dataclass
class IntentResult:
    intent_type: QueryIntent
    key_entities: List[str]
    time_range: str
    specific_requirements: List[str]

class IntentAnalyzer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def analyze(self, query: str) -> IntentResult:
        return self._analyze_sync(query)

    def _analyze_sync(self, query: str) -> IntentResult:
        intent_type = self._infer_intent(query)
        entities = self._extract_entities(query)

        return IntentResult(
            intent_type=intent_type,
            key_entities=entities,
            time_range=self._infer_time_range(query),
            specific_requirements=[]
        )

    def _infer_intent(self, query: str) -> QueryIntent:
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["怎么", "如何", "方法", "步骤", "教程"]):
            return QueryIntent.HOWTO_QUERY
        if any(kw in query_lower for kw in ["最新", "新闻", "今日", "报道", "消息"]):
            return QueryIntent.NEWS_QUERY
        if any(kw in query_lower for kw in ["对比", "比较", "区别", "差异", "哪个好"]):
            return QueryIntent.COMPARISON_QUERY
        if any(kw in query_lower for kw in ["觉得", "认为", "看法", "观点", "意见"]):
            return QueryIntent.OPINION_QUERY
        if any(kw in query_lower for kw in ["研究", "论文", "学术", "分析", "报告"]):
            return QueryIntent.RESEARCH_QUERY

        return QueryIntent.FACTUAL_QUERY

    def _extract_entities(self, query: str) -> List[str]:
        words = query.split()
        entities = [w for w in words if len(w) > 2]
        return entities[:5]

    def _infer_time_range(self, query: str) -> str:
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["今天", "今日", "最近"]):
            return "最近一周"
        if any(kw in query_lower for kw in ["本月", "这个月"]):
            return "最近一月"
        if any(kw in query_lower for kw in ["今年"]):
            return "最近一年"
        return "任意"
