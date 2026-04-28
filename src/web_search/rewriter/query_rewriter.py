from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json
import re
from .intent_analyzer import IntentAnalyzer, IntentResult, QueryIntent
from .query_expander import QueryExpander
from .query_enhancer import QueryEnhancer

@dataclass
class StructuredQuery:
    query: str
    query_type: str
    description: str
    time_range: Optional[str] = None

@dataclass
class QueryRewriteResult:
    original_query: str
    rewritten_queries: List[str]
    intent: str
    entities: List[str]
    reasoning: str = ""
    inferred_entities: List[str] = field(default_factory=list)
    time_range: Optional[str] = None
    structured_queries: List[StructuredQuery] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "rewritten_queries": self.rewritten_queries,
            "intent": self.intent,
            "entities": self.entities,
            "reasoning": self.reasoning,
            "inferred_entities": self.inferred_entities,
            "time_range": self.time_range,
            "structured_queries": [
                {"query": sq.query, "query_type": sq.query_type, "description": sq.description, "time_range": sq.time_range}
                for sq in self.structured_queries
            ] if self.structured_queries else []
        }


QUERY_REWRITE_PROMPT_TEMPLATE = """你是一个专业的搜索查询改写专家。你的任务是将用户输入的原始查询改写为多个可直接执行的搜索查询。

## 输入信息
原始查询: {original_query}

## 核心原则
**在改写之前，必须先进行逻辑推理，展开原始查询中的隐含实体。**
很多原始查询引用的是间接实体（如"竞品"、"竞争对手"、"相关公司"），这些在搜索引擎中匹配效果很差。
正确的做法是：先推理出这些间接实体具体是什么，再用具体名称进行搜索。

## 任务步骤

### 步骤1: 深度意图分析
分析用户查询的：
- 核心主题是什么
- 需要查找的实体类型（公司/人/产品/技术等）
- 查询的时间范围
- 期望的结果类型

### 步骤2: 隐含实体推理（关键步骤）
对于引用间接实体的查询，必须先推理出具体实体：

**示例推理过程：**
原始查询: "某科技公司竞品的最新动态"
推理过程:
- 竞品是指与某科技公司在同一市场直接竞争的企业
- 科技行业主要玩家：某科技公司主要竞争对手等
- 因此应查询：竞品公司最新动态、竞品公司最新商业动作 等

**常见的间接实体映射：**
- "竞品/竞争对手" → 推理出的具体公司名称
- "某公司的新产品" → 具体产品名称
- "某行业的趋势" → 具体公司/产品的发展动态
- "某技术的替代方案" → 具体替代技术名称

### 步骤3: 多样化查询改写 (必须生成至少10条)
基于推理出的具体实体，生成以下类型的查询：

**a) 核心查询 (core)**
- 保留推理后查询的核心语义

**b) 精确匹配 (exact_match)**
- 使用引号强制匹配关键短语

**c) 具体实体查询 (entity_specific)**
- 用推理出的具体公司/产品名称直接查询
- 示例: 竞品公司最新商业动态

**d) 细化主题 (specific)**
- 聚焦于某个具体子主题

**e) 相关概念扩展 (related)**
- 扩展到相关但不完全相同的领域

**f) 定向源查询 (source_limited)**
- 添加权威信息源约束

**g) 时间范围查询 (time_limited)**
- 添加时间范围约束

**h) 对比/竞品对比查询 (compare)**
- 针对竞品分析场景，生成对比查询
- 示例: 某科技公司 vs 竞品公司 最新动态

### 4. 约束策略
根据意图类型应用不同约束：
- news: 必须添加时间约束
- research: 必须添加 site:arxiv.org 或 site:github.com
- factual: 添加精确匹配约束

## 输出格式
请以JSON格式输出，务必严格遵循以下格式：

```json
{{
    "intent": "意图类型",
    "entities": ["实体1", "实体2", "实体3"],
    "reasoning": "你的推理过程说明",
    "inferred_entities": ["通过推理得出的具体实体列表"],
    "time_range": "时间范围描述",
    "structured_queries": [
        {{
            "query": "改写后的查询语句",
            "query_type": "core|exact_match|entity_specific|specific|related|source_limited|time_limited|compare",
            "description": "这个查询的类型说明",
            "time_range": "day|month|year 枚举值, 表示搜索的时间范围约束"
        }}
    ]
}}
```

## 重要提醒
1. 必须生成至少8条、最多12条多样化查询
2. 对于 entity_specific 类型，每条查询应该使用推理出的具体实体名称
3. 必须包含 reasoning 字段说明你的推理过程
4. 必须包含 inferred_entities 字段列出所有推理出的具体实体
5. 输出必须是有效的JSON格式，不要包含任何其他文字
"""

class QueryRewriter:
    def __init__(
        self,
        llm_client=None,
        intent_analyzer: IntentAnalyzer = None,
        query_expander: QueryExpander = None,
        query_enhancer: QueryEnhancer = None
    ):
        self.llm_client = llm_client
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(llm_client)
        self.query_expander = query_expander or QueryExpander(llm_client)
        self.query_enhancer = query_enhancer or QueryEnhancer()

    def _build_prompt(self, query: str) -> str:
        return QUERY_REWRITE_PROMPT_TEMPLATE.format(original_query=query)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        try:
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            return json.loads(json_str)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            return self._fallback_parse(response)

    def _fallback_parse(self, query: str) -> Dict[str, Any]:
        year_match = re.search(r'202[0-9]', query)
        year = year_match.group() if year_match else "2024"

        queries = [
            {"query": query, "query_type": "core", "description": "原始查询"},
            {"query": f'"{year}" "AI大模型" 最新进展', "query_type": "exact_match", "description": "精确匹配"},
            {"query": f'{year}年LLM最新进展', "query_type": "synonym", "description": "同义词改写"},
            {"query": f'{year}年大模型训练进展', "query_type": "specific", "description": "细化主题"},
            {"query": f'{year}年LLM顶会论文', "query_type": "related", "description": "相关扩展"},
            {"query": f'site:arxiv.org {year}年LLM', "query_type": "source_limited", "description": "学术源"},
            {"query": f'"{year}年" "LLM" after:{year}-01-01', "query_type": "time_limited", "description": "时间范围"},
            {"query": f'{year}年AI大模型技术突破', "query_type": "technical", "description": "技术突破"},
        ]

        intent = "factual"
        if any(kw in query.lower() for kw in ["最新", "新闻", "今日", "报道"]):
            intent = "news"
        elif any(kw in query.lower() for kw in ["研究", "论文", "学术"]):
            intent = "research"
        elif any(kw in query.lower() for kw in ["对比", "比较", "区别"]):
            intent = "compare"
        elif any(kw in query.lower() for kw in ["怎么", "如何", "方法", "步骤"]):
            intent = "howto"
        elif any(kw in query.lower() for kw in ["觉得", "认为", "看法"]):
            intent = "opinion"

        entities = []
        for word in query.split():
            if len(word) > 2 and not re.match(r'^20\d{2}|年|的|是|在|了', word):
                entities.append(word)
                if len(entities) >= 5:
                    break

        return {
            "intent": intent,
            "entities": entities,
            "time_range": "任意",
            "structured_queries": queries
        }

    async def rewrite(self, query: str) -> QueryRewriteResult:
        prompt = self._build_prompt(query)

        if self.llm_client:
            response = await self.llm_client.complete(prompt)
            parsed = self._parse_llm_response(response)
        else:
            parsed = self._fallback_parse(query)

        structured_queries = []
        for sq_data in parsed.get("structured_queries", []):
            time_range = sq_data.get("time_range")
            if time_range and time_range not in ["day", "month", "year"]:
                time_range = None
            structured_queries.append(StructuredQuery(
                query=sq_data.get("query", ""),
                query_type=sq_data.get("query_type", "core"),
                description=sq_data.get("description", ""),
                time_range=time_range
            ))

        rewritten_queries = [sq.query for sq in structured_queries]

        return QueryRewriteResult(
            original_query=query,
            rewritten_queries=rewritten_queries,
            intent=parsed.get("intent", "factual"),
            entities=parsed.get("entities", []),
            reasoning=parsed.get("reasoning", ""),
            inferred_entities=parsed.get("inferred_entities", []),
            time_range=parsed.get("time_range"),
            structured_queries=structured_queries
        )

    def rewrite_sync(self, query: str) -> QueryRewriteResult:
        prompt = self._build_prompt(query)

        if self.llm_client:
            response = self.llm_client.complete_sync(prompt)
            if response:
                parsed = self._parse_llm_response(response)
            else:
                parsed = self._fallback_parse(query)
        else:
            parsed = self._fallback_parse(query)

        structured_queries = []
        for sq_data in parsed.get("structured_queries", []):
            time_range = sq_data.get("time_range")
            if time_range and time_range not in ["day", "month", "year"]:
                time_range = None
            structured_queries.append(StructuredQuery(
                query=sq_data.get("query", ""),
                query_type=sq_data.get("query_type", "core"),
                description=sq_data.get("description", ""),
                time_range=time_range
            ))

        rewritten_queries = [sq.query for sq in structured_queries]

        return QueryRewriteResult(
            original_query=query,
            rewritten_queries=rewritten_queries,
            intent=parsed.get("intent", "factual"),
            entities=parsed.get("entities", []),
            reasoning=parsed.get("reasoning", ""),
            inferred_entities=parsed.get("inferred_entities", []),
            time_range=parsed.get("time_range"),
            structured_queries=structured_queries
        )