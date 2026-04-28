from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import json
import re

from .nli_analyzer import NLIAnalyzer
from .spo_extractor import SPOExtractor, SPOTriple
from .value_extractor import ValueExtractor, NumericValue, DatetimeValue
from ..trust.trust_rank_ladder import TrustRankScore
from ..core.llm_client import LLMClientBase, create_llm_client
from ..config.settings import Settings


@dataclass
class ExtractedFact:
    fact_id: str
    statement: str
    spo_triple: Optional[SPOTriple] = None
    nli_label: Optional[str] = None
    numeric_values: List[NumericValue] = field(default_factory=list)
    datetime_values: List[DatetimeValue] = field(default_factory=list)
    confidence_score: float = 0.0
    confidence_reason: str = ""
    source: Optional[TrustRankScore] = None

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "statement": self.statement,
            "spo_triple": self.spo_triple.to_dict() if self.spo_triple else None,
            "nli_label": self.nli_label,
            "numeric_values": [nv.to_dict() for nv in self.numeric_values],
            "datetime_values": [dv.to_dict() for dv in self.datetime_values],
            "confidence_score": self.confidence_score,
            "confidence_reason": self.confidence_reason,
            "source": self.source.to_dict() if self.source else None
        }


class FactExtractor:
    FACT_EXTRACTION_PROMPT = """请从以下内容中提取所有可验证的事实信息。

来源域名: {source_domain}
用户查询: {query}

内容:
---
{content}
---

请提取内容中与用户查询问题相关的所有事实，**只提取密切相关的事实**，忽略无关内容。

判断相关性的标准：
- 事实与查询主题直接相关
- 事实能够回答或验证查询问题
- 排除元信息（如上传时间、下载积分、浏览量等与内容主题无关的信息）

请提取内容中的相关事实，包括:
1. **事件**: 谁做了什么？何时何地发生的？
2. **数据**: 具体的数字、百分比、统计数据
3. **声明/观点**: 某人对某事的表态（区分事实与观点）
4. **关系**: 实体之间的关系（公司收购、人员变动等）

输出格式要求:
- 每条事实应该简洁、完整、可独立验证
- 包含具体的时间、地点、人物、数据等关键信息
- 避免模糊的表述如"可能"、"也许"、"大概"
- 标注每条事实的置信度(0.0-1.0)

请以JSON数组格式输出:
[
    {{
        "fact_id": "fact_001",
        "statement": "2024年3月15日，苹果公司宣布推出新款iPhone",
        "confidence": 0.95,
        "has_numeric": true,
        "has_datetime": true
    }},
    ...
]

请输出JSON数组，不要有多余文本。"""

    def __init__(
        self,
        nli_analyzer: Optional[NLIAnalyzer] = None,
        spo_extractor: Optional[SPOExtractor] = None,
        value_extractor: Optional[ValueExtractor] = None,
        llm_client: Optional[LLMClientBase] = None,
        settings: Optional[Settings] = None,
        min_confidence_threshold: float = 0.3,
        max_facts_per_content: int = 50,
        use_llm_extraction: bool = True
    ):
        self._nli_analyzer = nli_analyzer or NLIAnalyzer()
        self._spo_extractor = spo_extractor or SPOExtractor()
        self._value_extractor = value_extractor or ValueExtractor()
        self._llm_client = llm_client
        self._settings = settings
        self._min_confidence_threshold = min_confidence_threshold
        self._max_facts_per_content = max_facts_per_content
        self._use_llm_extraction = use_llm_extraction

    def extract(self, content: str, source_domain: str) -> List[ExtractedFact]:
        return self.extract_sync(content, source_domain)

    def extract_sync(self, content: str, source_domain: str, query: str = "") -> List[ExtractedFact]:
        if self._use_llm_extraction and self._llm_client:
            return self._extract_with_llm(content, source_domain, query)

        return self._extract_with_rules(content, source_domain)

    async def extract_async(self, content: str, source_domain: str, query: str = "") -> List[ExtractedFact]:
        if self._use_llm_extraction and self._llm_client:
            return await self._extract_with_llm_async(content, source_domain, query)

        return self._extract_with_rules(content, source_domain)

    def _extract_with_llm(self, content: str, source_domain: str, query: str) -> List[ExtractedFact]:
        if not content or len(content.strip()) < 50:
            return []

        prompt = self.FACT_EXTRACTION_PROMPT.format(
            source_domain=source_domain,
            query=query or "通用事实提取",
            content=content[:8000]
        )

        try:
            response = self._llm_client.complete_sync(prompt)
            return self._parse_llm_facts(response, source_domain)
        except Exception as e:
            return self._extract_with_rules(content, source_domain)

    async def _extract_with_llm_async(self, content: str, source_domain: str, query: str) -> List[ExtractedFact]:
        if not content or len(content.strip()) < 50:
            return []

        prompt = self.FACT_EXTRACTION_PROMPT.format(
            source_domain=source_domain,
            query=query or "通用事实提取",
            content=content[:8000]
        )

        try:
            response = await self._llm_client.complete(prompt)
            return self._parse_llm_facts(response, source_domain)
        except Exception as e:
            return self._extract_with_rules(content, source_domain)

    def _parse_llm_facts(self, response: str, source_domain: str) -> List[ExtractedFact]:
        facts = []

        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            statement = item.get("statement", "")
                            if statement and len(statement) > 10:
                                fact_id = self._generate_fact_id()
                                confidence = float(item.get("confidence", 0.5))

                                has_numeric = item.get("has_numeric", False)
                                has_datetime = item.get("has_datetime", False)

                                reason = "LLM提取"
                                if has_numeric:
                                    reason += ", 包含数值"
                                if has_datetime:
                                    reason += ", 包含时间"

                                fact = ExtractedFact(
                                    fact_id=fact_id,
                                    statement=statement,
                                    confidence_score=confidence,
                                    confidence_reason=reason
                                )

                                facts.append(fact)
        except Exception:
            pass

        return facts

    def _extract_with_rules(self, content: str, source_domain: str) -> List[ExtractedFact]:
        sentences = self._split_into_sentences(content)
        facts: List[ExtractedFact] = []

        for sentence in sentences:
            if not self._is_factual_sentence(sentence):
                continue

            spo_triples = self._spo_extractor.extract_spo_sync(sentence)
            numeric_values, datetime_values = self._value_extractor.extract_values_sync(sentence)

            for triple in spo_triples:
                fact = self._create_fact_from_triple(
                    triple=triple,
                    source_domain=source_domain,
                    original_sentence=sentence
                )
                fact.numeric_values = numeric_values
                fact.datetime_values = datetime_values
                facts.append(fact)

            if not spo_triples and (numeric_values or datetime_values):
                fact = self._create_fact_from_values(
                    sentence=sentence,
                    numeric_values=numeric_values,
                    datetime_values=datetime_values,
                    source_domain=source_domain
                )
                facts.append(fact)

            if len(facts) >= self._max_facts_per_content:
                break

        facts = self._compute_confidence_scores(facts)
        facts = [f for f in facts if f.confidence_score >= self._min_confidence_threshold]
        return facts

    def _split_into_sentences(self, content: str) -> List[str]:
        content = content.replace('\n', ' ').replace('\r', '')
        sentence_endings = re.compile(r'(?<=[。！？；?!.?!;])\s+')
        sentences = sentence_endings.split(content)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        return sentences

    def _is_factual_sentence(self, sentence: str) -> bool:
        if len(sentence) < 10 or len(sentence) > 500:
            return False

        non_factual_patterns = [
            r'^请问',
            r'^如果',
            r'^虽然',
            r'^但是',
            r'^然而',
            r'^可能',
            r'^也许',
            r'^大概',
            r'吗\?$',
            r'呢\?$',
            r'？$',
        ]
        for pattern in non_factual_patterns:
            if re.search(pattern, sentence):
                return False

        factual_indicators = [
            r'\d+',
            r'年',
            r'月',
            r'日',
            r'据',
            r'报道',
            r'表示',
            r'说',
            r'宣布',
            r'证实',
            r'确认',
        ]
        for indicator in factual_indicators:
            if re.search(indicator, sentence):
                return True

        return False

    def _create_fact_from_triple(
        self,
        triple: SPOTriple,
        source_domain: str,
        original_sentence: str
    ) -> ExtractedFact:
        statement = str(triple)
        fact_id = self._generate_fact_id()

        return ExtractedFact(
            fact_id=fact_id,
            statement=statement,
            spo_triple=triple,
            numeric_values=[],
            datetime_values=[]
        )

    def _create_fact_from_values(
        self,
        sentence: str,
        numeric_values: List[NumericValue],
        datetime_values: List[DatetimeValue],
        source_domain: str
    ) -> ExtractedFact:
        fact_id = self._generate_fact_id()

        return ExtractedFact(
            fact_id=fact_id,
            statement=sentence,
            spo_triple=None,
            numeric_values=numeric_values,
            datetime_values=datetime_values
        )

    def _generate_fact_id(self) -> str:
        return f"fact_{uuid.uuid4().hex[:12]}"

    def _compute_confidence_scores(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        for fact in facts:
            score = 0.5
            reasons = []

            if fact.spo_triple:
                score += 0.15
                reasons.append("包含完整的SPO三元组结构")

            if fact.numeric_values:
                score += 0.1
                reasons.append(f"包含{len(fact.numeric_values)}个数值")

            if fact.datetime_values:
                score += 0.1
                reasons.append(f"包含{len(fact.datetime_values)}个时间信息")

            if fact.nli_label == "entailment":
                score += 0.15
                reasons.append("NLI分析为 entailment")
            elif fact.nli_label == "contradiction":
                score -= 0.2
                reasons.append("NLI分析为 contradiction")

            subject = fact.spo_triple.subject if fact.spo_triple else ""
            if self._is_specific_entity(subject):
                score += 0.1
                reasons.append("主语为具体实体")

            score = max(0.0, min(1.0, score))

            fact.confidence_score = score
            fact.confidence_reason = "; ".join(reasons) if reasons else "基础置信度"

        return facts

    def _is_specific_entity(self, text: str) -> bool:
        if not text:
            return False
        if len(text) < 2:
            return False
        if text[0].isupper() and len(text) > 2:
            return True
        if re.search(r'[\u4e00-\u9fff]', text):
            return len(text) >= 2
        return False

    def analyze_nli_pair(self, statement1: str, statement2: str) -> str:
        return self._nli_analyzer.analyze_nli_sync(statement1, statement2)

    def set_trust_score(self, fact: ExtractedFact, trust_score: TrustRankScore) -> None:
        fact.source = trust_score

    def batch_extract(
        self,
        contents: List[str],
        source_domains: List[str]
    ) -> List[List[ExtractedFact]]:
        if len(contents) != len(source_domains):
            raise ValueError("contents and source_domains must have the same length")

        results = []
        for content, domain in zip(contents, source_domains):
            results.append(self.extract_sync(content, domain))
        return results

    def extract_with_nli_context(
        self,
        content: str,
        source_domain: str,
        context_statement: Optional[str] = None
    ) -> List[ExtractedFact]:
        facts = self.extract_sync(content, source_domain)

        if context_statement:
            for fact in facts:
                if fact.statement:
                    label = self._nli_analyzer.analyze_nli_sync(context_statement, fact.statement)
                    fact.nli_label = label

        return facts

    def get_extraction_stats(self, facts: List[ExtractedFact]) -> Dict[str, Any]:
        if not facts:
            return {
                "total_facts": 0,
                "avg_confidence": 0.0,
                "facts_with_spo": 0,
                "facts_with_numeric": 0,
                "facts_with_datetime": 0,
                "high_confidence_facts": 0
            }

        return {
            "total_facts": len(facts),
            "avg_confidence": sum(f.confidence_score for f in facts) / len(facts),
            "facts_with_spo": sum(1 for f in facts if f.spo_triple is not None),
            "facts_with_numeric": sum(1 for f in facts if len(f.numeric_values) > 0),
            "facts_with_datetime": sum(1 for f in facts if len(f.datetime_values) > 0),
            "high_confidence_facts": sum(1 for f in facts if f.confidence_score >= 0.7)
        }