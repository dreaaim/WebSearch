from dataclasses import dataclass
from typing import List

@dataclass
class RelevanceResult:
    score: float
    reason: str
    key_match_points: List[str]

class RelevanceScorer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    RELEVANCE_PROMPT_TEMPLATE = """查询意图: {intent}
用户查询: {original_query}

搜索结果:
- Title: {title}
- Content: {content}
- URL: {url}

请判断该搜索结果与用户查询的相关性：

评分标准:
- 10分: 完全匹配，直接回答用户问题
- 7-9分: 高度相关，包含用户查询的关键信息
- 4-6分: 中度相关，提供部分有用信息
- 1-3分: 低度相关，信息有限
- 0分: 完全不相关

请输出 JSON:
{{
    "score": 0-10,
    "reason": "评分理由",
    "key_match_points": ["匹配点1", "匹配点2"]
}}
"""

    async def score(
        self,
        title: str,
        content: str,
        url: str,
        original_query: str,
        intent: str = "factual"
    ) -> RelevanceResult:
        prompt = self.RELEVANCE_PROMPT_TEMPLATE.format(
            intent=intent,
            original_query=original_query,
            title=title,
            content=content[:500] if content else "",
            url=url
        )

        if self.llm_client:
            response = await self.llm_client.complete(prompt)
            return self._parse_response(response)

        return RelevanceResult(
            score=5.0,
            reason="No LLM client available",
            key_match_points=[]
        )

    def _parse_response(self, response: str) -> RelevanceResult:
        import json
        import re

        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return RelevanceResult(
                    score=data.get("score", 5.0),
                    reason=data.get("reason", ""),
                    key_match_points=data.get("key_match_points", [])
                )
        except:
            pass

        return RelevanceResult(
            score=5.0,
            reason="Failed to parse response",
            key_match_points=[]
        )