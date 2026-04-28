"""
DEPRECATED: Use reranker.MultiFactorReranker instead.

This module is part of the v2 architecture and will be removed in a future version.
v3 provides a more streamlined MultiFactorReranker with external reranker model support.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from .freshness import FreshnessCalculator

class SourceType(Enum):
    OFFICIAL = "official"
    MEDIA = "media"
    KOL = "kol"
    INDIVIDUAL = "individual"

class SourceLevel(Enum):
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    MUNICIPAL = "municipal"
    LOCAL = "local"

class Classification(Enum):
    WHITE = "white"
    GRAY = "gray"
    BLACK = "black"

@dataclass
class AuthorityLevel:
    NATIONAL_OFFICIAL = 1.0
    PROVINCIAL_OFFICIAL = 0.85
    MUNICIPAL_OFFICIAL = 0.7
    NATIONAL_MEDIA = 0.8
    PROVINCIAL_MEDIA = 0.65
    KOL_BIG = 0.6
    KOL_MEDIUM = 0.5
    KOL_SMALL = 0.4
    MEDIA = 0.45
    INDIVIDUAL = 0.3

@dataclass
class RerankConfig:
    weights: Dict[str, float] = None
    external_rerank_weight: float = 0.3
    top_k: int = 10

    def __post_init__(self):
        if self.weights is None:
            self.weights = {
                "relevance": 0.3,
                "trustworthiness": 0.2,
                "freshness": 0.1,
                "authority": 0.1,
                "external": 0.3
            }

class Reranker:
    def __init__(
        self,
        config: RerankConfig = None,
        freshness_config: dict = None,
        reranker_client = None
    ):
        self.config = config or RerankConfig()
        freshness_cfg = freshness_config or {}
        self.freshness_calculator = FreshnessCalculator(
            period_7d_score=freshness_cfg.get("period_7d_score", 1.0),
            period_30d_score=freshness_cfg.get("period_30d_score", 0.8),
            period_90d_score=freshness_cfg.get("period_90d_score", 0.6),
            period_1y_score=freshness_cfg.get("period_1y_score", 0.4),
            older_score=freshness_cfg.get("older_score", 0.2)
        )
        self.reranker_client = reranker_client
        self._external_scores: Dict[int, float] = {}

    async def rerank_async(
        self,
        results: List[Any],
        query: str,
        judgments: List = None,
        top_k: int = None,
        original_query: str = None,
        search_query: str = None
    ) -> List[Any]:
        """Rerank search results using external reranker.

        Args:
            results: List of search results to rerank
            query: The query for reranking
            judgments: Optional list of judgment data
            top_k: Number of top results to return
            original_query: The original user query (for context passing)
            search_query: The actual search query used (for context passing)
        """
        top_k = top_k or self.config.top_k

        if self.reranker_client and results:
            texts = []
            for r in results:
                if hasattr(r, 'result') and hasattr(r.result, 'snippet'):
                    texts.append(r.result.snippet or r.result.title)
                elif hasattr(r, 'snippet'):
                    texts.append(r.snippet or r.title)
                else:
                    texts.append(str(r))

            rerank_results = await self.reranker_client.rerank(
                query=query,
                texts=texts,
                top_n=len(results),
                search_query=search_query,
                instructions=original_query
            )
            self._external_scores = {r.index: r.score for r in rerank_results}

            for i, result in enumerate(results):
                if i in self._external_scores:
                    if hasattr(result, 'external_rerank_score'):
                        result.external_rerank_score = self._external_scores[i]
                    elif hasattr(result, 'relevance_score'):
                        result.relevance_score = self._external_scores[i]

        return self._sync_rerank(results, judgments, top_k)

    def rerank(
        self,
        results: List[Any],
        judgments: List = None,
        top_k: int = None,
        original_query: str = None,
        search_query: str = None
    ) -> List[Any]:
        return self._sync_rerank(results, judgments, top_k, original_query, search_query)

    def _sync_rerank(
        self,
        results: List[Any],
        judgments: List = None,
        top_k: int = None,
        original_query: str = None,
        search_query: str = None
    ) -> List[Any]:
        top_k = top_k or self.config.top_k

        if self.reranker_client and results:
            try:
                rerank_results = self.reranker_client.rerank(
                    query=original_query or "",
                    texts=self._extract_texts(results),
                    top_n=len(results),
                    search_query=search_query,
                    instructions=original_query
                )
                external_scores = {r.index: r.score for r in rerank_results}
                print(f"[DEBUG] Reranker got {len(external_scores)} scores, total={len(results)}")
            except Exception as e:
                import traceback
                external_scores = {}
                print(f"[DEBUG] Reranker exception: {e}")
                print(f"[DEBUG] Exception traceback: {traceback.format_exc()}")

            for i, result in enumerate(results):
                if i in external_scores:
                    score = external_scores[i]
                    if hasattr(result, 'result'):
                        result.result.external_rerank_score = score
                        result.result.relevance_score = score
                    else:
                        result.external_rerank_score = score
                        result.relevance_score = score

        scored_results = []
        for result in results:
            score = self._calculate_composite_score(result, judgments)
            scored_results.append((result, score))

        print(f"[DEBUG] Before sort: scores = {[s for _, s in scored_results[:5]]}")

        scored_results.sort(key=lambda x: x[1], reverse=True)

        print(f"[DEBUG] After sort: scores = {[s for _, s in scored_results[:5]]}")

        ranked = [result for result, score in scored_results]

        for i, (result, score) in enumerate(scored_results[:top_k if top_k else len(scored_results)]):
            if hasattr(result, 'result'):
                result.result.final_score = score
            else:
                result.final_score = score

        return ranked[:top_k] if top_k > 0 else ranked

    def _extract_texts(self, results: List[Any]) -> List[str]:
        texts = []
        for r in results:
            if hasattr(r, 'result') and hasattr(r.result, 'snippet'):
                texts.append(r.result.snippet or r.result.title)
            elif hasattr(r, 'snippet'):
                texts.append(r.snippet or r.title)
            else:
                texts.append(str(r))
        return texts

    def _calculate_composite_score(
        self,
        result: Any,
        judgments: List = None
    ) -> float:
        relevance = self._get_relevance(result) / 10.0
        trustworthiness = self._get_trustworthiness(result)
        freshness = self._get_freshness(result)
        authority = self._get_authority_score(result)

        judgment_bonus = 0.0
        if judgments:
            judgment_bonus = self._get_judgment_bonus(result, judgments)

        internal_score = (
            self.config.weights.get("relevance", 0.3) * relevance +
            self.config.weights.get("trustworthiness", 0.2) * trustworthiness +
            self.config.weights.get("freshness", 0.1) * freshness +
            self.config.weights.get("authority", 0.1) * authority +
            judgment_bonus
        )

        external_score = self._get_external_score(result)
        if external_score is not None:
            external_weight = self.config.external_rerank_weight
            return (1 - external_weight) * internal_score + external_weight * external_score

        return internal_score

    def _get_relevance(self, result: Any) -> float:
        if hasattr(result, 'relevance_score'):
            return result.relevance_score
        if hasattr(result, 'result') and hasattr(result.result, 'relevance_score'):
            return result.result.relevance_score
        return 0.5

    def _get_external_score(self, result: Any) -> Optional[float]:
        if hasattr(result, 'external_rerank_score'):
            return result.external_rerank_score
        if hasattr(result, 'result') and hasattr(result.result, 'external_rerank_score'):
            return result.result.external_rerank_score
        return None

    def _get_trustworthiness(self, result: Any) -> float:
        if hasattr(result, 'is_blacklisted') and result.is_blacklisted:
            return 0.0

        classification = self._get_classification(result)
        if classification == Classification.WHITE:
            return 1.0
        if classification == Classification.GRAY:
            return 0.5
        return 0.3

    def _get_classification(self, result: Any) -> Classification:
        if hasattr(result, 'classification'):
            val = result.classification
            if isinstance(val, Classification):
                return val
            if isinstance(val, str):
                return Classification(val)
        return Classification.GRAY

    def _get_freshness(self, result: Any) -> float:
        published_date = None

        if hasattr(result, 'result') and hasattr(result.result, 'published_date'):
            published_date = result.result.published_date
        elif hasattr(result, 'published_date'):
            published_date = result.published_date

        return self.freshness_calculator.calculate(published_date)

    def _get_authority_score(self, result: Any) -> float:
        source_type = self._get_source_type(result)
        source_level = self._get_source_level(result)

        if source_type == SourceType.OFFICIAL:
            level_scores = {
                SourceLevel.NATIONAL: AuthorityLevel.NATIONAL_OFFICIAL,
                SourceLevel.PROVINCIAL: AuthorityLevel.PROVINCIAL_OFFICIAL,
                SourceLevel.MUNICIPAL: AuthorityLevel.MUNICIPAL_OFFICIAL,
                SourceLevel.LOCAL: 0.5
            }
            return level_scores.get(source_level, 0.5)

        if source_type == SourceType.MEDIA:
            level_scores = {
                SourceLevel.NATIONAL: AuthorityLevel.NATIONAL_MEDIA,
                SourceLevel.PROVINCIAL: AuthorityLevel.PROVINCIAL_MEDIA,
                SourceLevel.MUNICIPAL: 0.5,
                SourceLevel.LOCAL: 0.35
            }
            return level_scores.get(source_level, 0.35)

        if source_type == SourceType.KOL:
            return AuthorityLevel.KOL_MEDIUM

        return AuthorityLevel.INDIVIDUAL

    def _get_source_type(self, result: Any) -> SourceType:
        if hasattr(result, 'source_info') and hasattr(result.source_info, 'source_type'):
            return result.source_info.source_type
        if hasattr(result, 'source_type'):
            val = result.source_type
            if isinstance(val, SourceType):
                return val
            if isinstance(val, str):
                return SourceType(val)
        return SourceType.MEDIA

    def _get_source_level(self, result: Any) -> SourceLevel:
        if hasattr(result, 'source_info') and hasattr(result.source_info, 'source_level'):
            return result.source_info.source_level
        if hasattr(result, 'source_level'):
            val = result.source_level
            if isinstance(val, SourceLevel):
                return val
            if isinstance(val, str):
                return SourceLevel(val)
        return SourceLevel.LOCAL

    def _get_judgment_bonus(
        self,
        result: Any,
        judgments: List
    ) -> float:
        return 0.0
