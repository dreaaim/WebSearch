"""
DEPRECATED: Use filter.HybridFilterEngine for v3 filtering instead.

This module is part of the v2 architecture and will be removed in a future version.
v3 provides more sophisticated filtering via HybridFilterEngine (Embedding + BM25).
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from collections import defaultdict

class SourceType(Enum):
    OFFICIAL = "official"
    MEDIA = "media"
    KOL = "kol"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"

class Classification(Enum):
    WHITE = "white"
    GRAY = "gray"
    BLACK = "black"

@dataclass
class SourceInfo:
    source_name: str
    source_type: SourceType
    source_domain: str
    author: Optional[str] = None
    is_verified: bool = False

@dataclass
class ClassifiedResult:
    result: any
    source_info: SourceInfo
    classification: Classification
    relevance_score: float
    relevance_reason: Optional[str] = None
    whitelist_level: Optional[str] = None
    is_blacklisted: bool = False

class BlacklistChecker:
    def __init__(self, rules: List[dict] = None):
        self.rules = rules or []

    async def check(self, source_domain: str, source_name: str = None) -> bool:
        domain_lower = source_domain.lower()
        for rule in self.rules:
            if "domain" in rule and domain_lower == rule["domain"].lower():
                return True
            if "domain_pattern" in rule:
                import re
                pattern = rule["domain_pattern"].lower().replace("*", ".*")
                if re.match(pattern, domain_lower):
                    return True
        return False

    def check_sync(self, source_domain: str, source_name: str = None) -> bool:
        domain_lower = source_domain.lower()
        for rule in self.rules:
            if "domain" in rule and domain_lower == rule["domain"].lower():
                return True
            if "domain_pattern" in rule:
                import re
                pattern = rule["domain_pattern"].lower().replace("*", ".*")
                if re.match(pattern, domain_lower):
                    return True
        return False

class WhitelistChecker:
    def __init__(self, rules: List[dict] = None):
        self.rules = rules or []

    async def check(self, source_domain: str, source_name: str = None) -> dict:
        domain_lower = source_domain.lower()
        for rule in self.rules:
            if "domain" in rule and domain_lower == rule["domain"].lower():
                return {
                    "in_whitelist": True,
                    "whitelist_level": rule.get("level", "national"),
                    "tags": rule.get("tags", [])
                }
            if "domain_suffix" in rule:
                suffix = rule["domain_suffix"].lower()
                if domain_lower.endswith(suffix):
                    return {
                        "in_whitelist": True,
                        "whitelist_level": rule.get("level", "national"),
                        "tags": rule.get("tags", [])
                    }
        return {"in_whitelist": False, "whitelist_level": None, "tags": []}

    def check_sync(self, source_domain: str, source_name: str = None) -> dict:
        domain_lower = source_domain.lower()
        for rule in self.rules:
            if "domain" in rule and domain_lower == rule["domain"].lower():
                return {
                    "in_whitelist": True,
                    "whitelist_level": rule.get("level", "national"),
                    "tags": rule.get("tags", [])
                }
            if "domain_suffix" in rule:
                suffix = rule["domain_suffix"].lower()
                if domain_lower.endswith(suffix):
                    return {
                        "in_whitelist": True,
                        "whitelist_level": rule.get("level", "national"),
                        "tags": rule.get("tags", [])
                    }
        return {"in_whitelist": False, "whitelist_level": None, "tags": []}

class LLMSourceClassifier:
    UNIFIED_CLASSIFICATION_PROMPT = """请从以下搜索结果中提取信息并评估其与查询的相关性，输出单个JSON对象:

{{
    "source_name": "信息源名称",
    "source_type": "official|media|kol|individual|unknown",
    "source_domain": "主要域名",
    "author": "作者/发布者 (如有)",
    "is_verified": true/false,
    "relevance_reason": "相关性评判依据",
    "relevance_score": 0.0-10.0 (基于信源类型与查询意图的匹配度)
}}

评估标准:
- relevance_score 应考虑信源类型与查询意图的匹配度
- 事实性查询应优先考虑官方/权威媒体 (source_type=official/media)
- 观点性查询可考虑KOL或专业媒体 (source_type=kol)
- 10分: 完全匹配，直接回答用户问题
- 7-9分: 高度相关，包含用户查询的关键信息
- 4-6分: 中度相关，提供部分有用信息
- 1-3分: 低度相关，信息有限
- 0分: 完全不相关

原始用户查询: {original_query}
检索查询: {search_query}

搜索结果:
- Title: {title}
- Content: {content}
- URL: {url}

当前时间: {current_time}

请输出单个JSON对象，不要有多余文本。"""

    UNIFIED_BATCH_CLASSIFICATION_PROMPT = """请从以下搜索结果列表中提取信息并评估其与查询的相关性，输出JSON数组:

输出要求:
- 输出JSON数组，数组顺序与输入对应
- 每个元素包含: index, source_name, source_type, source_domain, author, is_verified, relevance_reason, relevance_score
- relevance_score: 0.0-10.0
- source_type: official|media|kol|individual|unknown
- relevance_reason: 简短的评分理由

原始用户查询: {original_query}
检索查询: {search_query}
当前时间: {current_time}

{results_json}

请输出单个JSON数组，不要有多余文本。"""

    def __init__(
        self,
        llm_client=None,
        blacklist_checker: BlacklistChecker = None,
        whitelist_checker: WhitelistChecker = None,
        relevance_scorer = None,
        min_relevance_score: float = 3.0
    ):
        self.llm_client = llm_client
        self.blacklist_checker = blacklist_checker or BlacklistChecker()
        self.whitelist_checker = whitelist_checker or WhitelistChecker()
        self.relevance_scorer = relevance_scorer
        self.min_relevance_score = min_relevance_score

    async def classify(
        self,
        result: any,
        original_query: str,
        search_query: str = None,
        intent: str = "factual"
    ) -> ClassifiedResult:
        source_info, relevance_score, relevance_reason = await self._extract_source_info(result, original_query, search_query)

        is_blacklisted = await self.blacklist_checker.check(
            source_info.source_domain,
            source_info.source_name
        )

        if is_blacklisted:
            return ClassifiedResult(
                result=result,
                source_info=source_info,
                classification=Classification.BLACK,
                relevance_score=0.0,
                relevance_reason=relevance_reason,
                is_blacklisted=True
            )

        whitelist_result = await self.whitelist_checker.check(
            source_info.source_domain,
            source_info.source_name
        )

        if whitelist_result["in_whitelist"]:
            return ClassifiedResult(
                result=result,
                source_info=source_info,
                classification=Classification.WHITE,
                relevance_score=max(relevance_score, 7.0),
                relevance_reason=relevance_reason,
                whitelist_level=whitelist_result["whitelist_level"]
            )

        return ClassifiedResult(
            result=result,
            source_info=source_info,
            classification=Classification.GRAY,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason
        )

    async def classify_batch(
        self,
        results: List[any],
        original_query: str,
        search_query: str = None,
        intent: str = "factual"
    ) -> List[ClassifiedResult]:
        classified = []
        for result in results:
            classified_result = await self.classify(result, original_query, search_query, intent)
            classified.append(classified_result)
        return sorted(classified, key=lambda x: x.relevance_score, reverse=True)

    async def _extract_source_info(
        self,
        result: any,
        original_query: str = None,
        search_query: str = None
    ) -> tuple:
        title = result.title if hasattr(result, 'title') else ""
        snippet = result.snippet if hasattr(result, 'snippet') else ""
        url = result.url if hasattr(result, 'url') else ""

        if hasattr(result, 'source_name') and result.source_name:
            source_name = result.source_name
        else:
            source_name = self._extract_domain_from_url(url)

        if hasattr(result, 'source_domain') and result.source_domain:
            source_domain = result.source_domain
        else:
            source_domain = self._extract_domain_from_url(url)

        default_source_info = SourceInfo(
            source_name=source_name,
            source_type=SourceType.UNKNOWN,
            source_domain=source_domain
        )
        default_relevance_score = 5.0
        default_relevance_reason = None

        if self.llm_client:
            try:
                prompt = self.UNIFIED_CLASSIFICATION_PROMPT.format(
                    original_query=original_query or "",
                    search_query=search_query or "",
                    title=title,
                    content=snippet[:500] if snippet else "",
                    url=url,
                    current_time=datetime.now().isoformat()
                )
                response = await self.llm_client.complete(prompt)
                return self._parse_unified_response(response, source_name, source_domain)
            except Exception:
                pass

        return (default_source_info, default_relevance_score, default_relevance_reason)

    def _build_batch_results_json(self, results: List[Any]) -> str:
        import json
        items = []
        for i, result in enumerate(results):
            title = result.title if hasattr(result, 'title') else ""
            snippet = result.snippet if hasattr(result, 'snippet') else ""
            url = result.url if hasattr(result, 'url') else ""
            items.append({
                "index": i,
                "title": title,
                "content": snippet[:500] if snippet else "",
                "url": url
            })
        return json.dumps(items, ensure_ascii=False, indent=2)

    def _parse_batch_unified_response(
        self,
        response: str,
        results: List[Any],
        fallback_source_domains: Dict[int, str] = None
    ) -> List[tuple]:
        import json
        import re
        print(f"[DEBUG] LLM batch raw response: {response[:500]}...")
        fallback_source_domains = fallback_source_domains or {}
        parsed_results = []
        for i in range(len(results)):
            parsed_results.append((
                SourceInfo(
                    source_name="",
                    source_type=SourceType.UNKNOWN,
                    source_domain=fallback_source_domains.get(i, "")
                ),
                5.0,
                None
            ))

        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            idx = item.get("index")
                            if idx is not None and 0 <= idx < len(parsed_results):
                                source_type_str = item.get("source_type", "unknown").lower()
                                if source_type_str == "official":
                                    source_type = SourceType.OFFICIAL
                                elif source_type_str == "media":
                                    source_type = SourceType.MEDIA
                                elif source_type_str == "kol":
                                    source_type = SourceType.KOL
                                elif source_type_str == "individual":
                                    source_type = SourceType.INDIVIDUAL
                                else:
                                    source_type = SourceType.UNKNOWN

                                source_info = SourceInfo(
                                    source_name=item.get("source_name") or "",
                                    source_type=source_type,
                                    source_domain=item.get("source_domain") or fallback_source_domains.get(idx, ""),
                                    author=item.get("author"),
                                    is_verified=item.get("is_verified", False)
                                )
                                relevance_score = float(item.get("relevance_score", 5.0))
                                relevance_reason = item.get("relevance_reason")
                                parsed_results[idx] = (source_info, relevance_score, relevance_reason)
                    print(f"[DEBUG] Successfully parsed {len(data)} batch items")
        except Exception as e:
            print(f"[DEBUG] Exception parsing batch response: {e}")

        return parsed_results

    def classify_batch_grouped_sync(
        self,
        results: List[Any],
        original_query: str,
        search_query_map: Dict[str, str] = None
    ) -> List[ClassifiedResult]:
        if not results:
            return []

        search_query_map = search_query_map or {}

        grouped = defaultdict(list)
        for result in results:
            url = getattr(result, 'url', '')
            sq = search_query_map.get(url, 'default')
            grouped[sq].append(result)

        all_classified = []
        batch_size = 10

        for sq, items in grouped.items():
            for i in range(0, len(items), batch_size):
                batch = items[i:i+batch_size]
                batch_results = self._process_batch_sync(batch, original_query, sq)

                for j, (source_info, relevance_score, relevance_reason) in enumerate(batch_results):
                    result = batch[j]
                    url = getattr(result, 'url', '')

                    is_blacklisted = self.blacklist_checker.check_sync(
                        source_info.source_domain,
                        source_info.source_name
                    )

                    if is_blacklisted:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.BLACK,
                            relevance_score=0.0,
                            relevance_reason=relevance_reason,
                            is_blacklisted=True
                        ))
                        continue

                    whitelist_result = self.whitelist_checker.check_sync(
                        source_info.source_domain,
                        source_info.source_name
                    )

                    if whitelist_result["in_whitelist"]:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.WHITE,
                            relevance_score=max(relevance_score, 7.0),
                            relevance_reason=relevance_reason,
                            whitelist_level=whitelist_result["whitelist_level"]
                        ))
                    elif relevance_score >= self.min_relevance_score:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.GRAY,
                            relevance_score=relevance_score,
                            relevance_reason=relevance_reason
                        ))

        return all_classified

    def _process_batch_sync(
        self,
        results: List[Any],
        original_query: str,
        search_query: str
    ) -> List[tuple]:
        if not results:
            return []

        fallback_domains = {}
        for i, result in enumerate(results):
            url = getattr(result, 'url', '')
            domain = self._extract_domain_from_url(url)
            fallback_domains[i] = domain

        if self.llm_client:
            try:
                results_json = self._build_batch_results_json(results)
                prompt = self.UNIFIED_BATCH_CLASSIFICATION_PROMPT.format(
                    results_json=results_json,
                    original_query=original_query,
                    search_query=search_query,
                    current_time=datetime.now().isoformat()
                )
                print(f"[DEBUG] Calling batch LLM with {len(results)} results")
                response = self.llm_client.complete_sync(prompt)
                return self._parse_batch_unified_response(response, results, fallback_domains)
            except Exception as e:
                import traceback
                print(f"[DEBUG] Exception in batch processing: {e}")
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")

        default_source_info = SourceInfo(
            source_name="",
            source_type=SourceType.UNKNOWN,
            source_domain=""
        )
        return [(default_source_info, 5.0, None) for _ in results]

    async def classify_batch_grouped(
        self,
        results: List[Any],
        original_query: str,
        search_query_map: Dict[str, str] = None
    ) -> List[ClassifiedResult]:
        if not results:
            return []

        search_query_map = search_query_map or {}

        grouped = defaultdict(list)
        for result in results:
            url = getattr(result, 'url', '')
            sq = search_query_map.get(url, 'default')
            grouped[sq].append(result)

        all_classified = []
        batch_size = 10

        for sq, items in grouped.items():
            for i in range(0, len(items), batch_size):
                batch = items[i:i+batch_size]
                batch_results = await self._process_batch_async(batch, original_query, sq)

                for j, (source_info, relevance_score, relevance_reason) in enumerate(batch_results):
                    result = batch[j]

                    is_blacklisted = await self.blacklist_checker.check(
                        source_info.source_domain,
                        source_info.source_name
                    )

                    if is_blacklisted:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.BLACK,
                            relevance_score=0.0,
                            relevance_reason=relevance_reason,
                            is_blacklisted=True
                        ))
                        continue

                    whitelist_result = await self.whitelist_checker.check(
                        source_info.source_domain,
                        source_info.source_name
                    )

                    if whitelist_result["in_whitelist"]:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.WHITE,
                            relevance_score=max(relevance_score, 7.0),
                            relevance_reason=relevance_reason,
                            whitelist_level=whitelist_result["whitelist_level"]
                        ))
                    else:
                        all_classified.append(ClassifiedResult(
                            result=result,
                            source_info=source_info,
                            classification=Classification.GRAY,
                            relevance_score=relevance_score,
                            relevance_reason=relevance_reason
                        ))

        return all_classified

    async def _process_batch_async(
        self,
        results: List[Any],
        original_query: str,
        search_query: str
    ) -> List[tuple]:
        if not results:
            return []

        fallback_domains = {}
        for i, result in enumerate(results):
            url = getattr(result, 'url', '')
            domain = self._extract_domain_from_url(url)
            fallback_domains[i] = domain

        if self.llm_client:
            try:
                results_json = self._build_batch_results_json(results)
                prompt = self.UNIFIED_BATCH_CLASSIFICATION_PROMPT.format(
                    results_json=results_json,
                    original_query=original_query,
                    search_query=search_query,
                    current_time=datetime.now().isoformat()
                )
                response = await self.llm_client.complete(prompt)
                return self._parse_batch_unified_response(response, results, fallback_domains)
            except Exception as e:
                print(f"[DEBUG] Exception in batch async processing: {e}")

        default_source_info = SourceInfo(
            source_name="",
            source_type=SourceType.UNKNOWN,
            source_domain=""
        )
        return [(default_source_info, 5.0, None) for _ in results]

    def _parse_unified_response(
        self,
        response: str,
        fallback_name: str = None,
        fallback_domain: str = None
    ) -> tuple:
        import json
        import re
        print(f"[DEBUG] LLM raw response: {response}")
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                print(f"[DEBUG] Parsed JSON data: {data}")
                source_type_str = data.get("source_type", "unknown").lower()
                if source_type_str == "official":
                    source_type = SourceType.OFFICIAL
                elif source_type_str == "media":
                    source_type = SourceType.MEDIA
                elif source_type_str == "kol":
                    source_type = SourceType.KOL
                elif source_type_str == "individual":
                    source_type = SourceType.INDIVIDUAL
                else:
                    source_type = SourceType.UNKNOWN

                source_info = SourceInfo(
                    source_name=data.get("source_name") or fallback_name or "",
                    source_type=source_type,
                    source_domain=data.get("source_domain") or fallback_domain or "",
                    author=data.get("author"),
                    is_verified=data.get("is_verified", False)
                )
                relevance_score = float(data.get("relevance_score", 5.0))
                relevance_reason = data.get("relevance_reason")
                return (source_info, relevance_score, relevance_reason)
        except Exception:
            pass

        return (
            SourceInfo(
                source_name=fallback_name or "",
                source_type=SourceType.UNKNOWN,
                source_domain=fallback_domain or ""
            ),
            5.0,
            None
        )

    def _extract_domain_from_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ""

    def classify_sync(
        self,
        result: any,
        original_query: str,
        search_query: str = None,
        intent: str = "factual"
    ) -> ClassifiedResult:
        source_info, relevance_score, relevance_reason = self._extract_source_info_sync(result, original_query, search_query)

        is_blacklisted = self.blacklist_checker.check_sync(
            source_info.source_domain,
            source_info.source_name
        )

        if is_blacklisted:
            return ClassifiedResult(
                result=result,
                source_info=source_info,
                classification=Classification.BLACK,
                relevance_score=0.0,
                relevance_reason=relevance_reason,
                is_blacklisted=True
            )

        whitelist_result = self.whitelist_checker.check_sync(
            source_info.source_domain,
            source_info.source_name
        )

        if whitelist_result["in_whitelist"]:
            return ClassifiedResult(
                result=result,
                source_info=source_info,
                classification=Classification.WHITE,
                relevance_score=max(relevance_score, 7.0),
                relevance_reason=relevance_reason,
                whitelist_level=whitelist_result["whitelist_level"]
            )

        return ClassifiedResult(
            result=result,
            source_info=source_info,
            classification=Classification.GRAY,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason
        )

    def classify_batch_sync(
        self,
        results: List[any],
        original_query: str,
        search_query: str = None,
        intent: str = "factual"
    ) -> List[ClassifiedResult]:
        classified = []
        for result in results:
            classified_result = self.classify_sync(result, original_query, search_query, intent)
            classified.append(classified_result)
        return sorted(classified, key=lambda x: x.relevance_score, reverse=True)

    def _extract_source_info_sync(
        self,
        result: any,
        original_query: str = None,
        search_query: str = None
    ) -> tuple:
        title = result.title if hasattr(result, 'title') else ""
        snippet = result.snippet if hasattr(result, 'snippet') else ""
        url = result.url if hasattr(result, 'url') else ""

        if hasattr(result, 'source_name') and result.source_name:
            source_name = result.source_name
        else:
            source_name = self._extract_domain_from_url(url)

        if hasattr(result, 'source_domain') and result.source_domain:
            source_domain = result.source_domain
        else:
            source_domain = self._extract_domain_from_url(url)

        default_source_info = SourceInfo(
            source_name=source_name,
            source_type=SourceType.UNKNOWN,
            source_domain=source_domain
        )
        default_relevance_score = 5.0
        default_relevance_reason = None

        if self.llm_client:
            try:
                prompt = self.UNIFIED_CLASSIFICATION_PROMPT.format(
                    original_query=original_query or "",
                    search_query=search_query or "",
                    title=title,
                    content=snippet[:500] if snippet else "",
                    url=url,
                    current_time=datetime.now().isoformat()
                )
                print(f"[DEBUG] Calling LLM with prompt: {prompt[:200]}...")
                response = self.llm_client.complete_sync(prompt)
                print(f"[DEBUG] Got response from LLM")
                return self._parse_unified_response(response, source_name, source_domain)
            except Exception as e:
                import traceback
                print(f"[DEBUG] Exception in _extract_source_info_sync: {e}")
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")

        return (default_source_info, default_relevance_score, default_relevance_reason)