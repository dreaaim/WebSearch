from typing import List
from .intent_analyzer import QueryIntent, IntentResult

class QueryExpander:
    DIVERGENCE_STRATEGIES = {
        QueryIntent.FACTUAL_QUERY: [
            "直接查询",
            "官方来源",
            "最新动态",
            "多角度"
        ],
        QueryIntent.NEWS_QUERY: [
            "最新新闻",
            "深度报道",
            "专家评论",
            "官方声明"
        ],
        QueryIntent.RESEARCH_QUERY: [
            "学术论文",
            "行业报告",
            "权威分析",
            "数据统计"
        ],
        QueryIntent.OPINION_QUERY: [
            "专家观点",
            "民间看法",
            "对比分析",
            "历史观点"
        ],
        QueryIntent.COMPARISON_QUERY: [
            "A方观点",
            "B方观点",
            "第三方观点",
            "综合对比"
        ],
        QueryIntent.HOWTO_QUERY: [
            "基础指南",
            "高级技巧",
            "常见问题",
            "视频教程"
        ]
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def expand(self, query: str, intent_result: IntentResult) -> List[str]:
        strategies = self.DIVERGENCE_STRATEGIES.get(
            intent_result.intent_type,
            ["直接查询"]
        )
        return [query]

    def expand_sync(self, query: str, intent_result: IntentResult) -> List[str]:
        return [query]
