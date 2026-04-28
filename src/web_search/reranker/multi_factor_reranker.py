from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

from .freshness_scorer import FreshnessScorer
from .trust_scorer import TrustScorer
from ..core.models import SearchResult
from ..fetcher.content_fetcher import ContentFetchResult


@dataclass
class RerankConfig:
    weights: Dict[str, float]
    freshness_lambda: float
    top_k: int
    external_rerank_weight: float = 0.3

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RerankConfig":
        weights = config.get("weights", {
            "freshness": 0.3,
            "relevance": 0.4,
            "trust": 0.3
        })
        freshness_lambda = config.get("freshness", {}).get("lambda", 0.1)
        top_k = config.get("top_k", 50)
        external_rerank_weight = config.get("external_rerank_weight", 0.3)
        return cls(
            weights=weights,
            freshness_lambda=freshness_lambda,
            top_k=top_k,
            external_rerank_weight=external_rerank_weight
        )


class MultiFactorReranker:
    def __init__(
        self,
        config: Optional[RerankConfig] = None,
        reranker_client: Optional[Any] = None
    ):
        if config is None:
            config = RerankConfig(
                weights={"freshness": 0.3, "relevance": 0.4, "trust": 0.3},
                freshness_lambda=0.1,
                top_k=50,
                external_rerank_weight=0.3
            )
        self.config = config
        self.freshness_scorer = FreshnessScorer(lambda_decay=config.freshness_lambda)
        self.trust_scorer = TrustScorer()
        self.reranker_client = reranker_client

    def rerank(
        self,
        results: List[ContentFetchResult],
        query: str
    ) -> List[ContentFetchResult]:
        if not results:
            return []

        valid_results = [r for r in results if r.fetch_success and isinstance(r.result, SearchResult)]
        search_results = [r.result for r in valid_results]

        external_scores = self._get_external_scores(search_results, query)

        scored_results = []
        for idx, (content_fetch_result, search_result) in enumerate(zip(valid_results, search_results)):
            freshness_score = self._calc_freshness(search_result)
            relevance_score = self._calc_relevance(search_result)
            trust_score = self._calc_trust(search_result)

            internal_score = (
                self.config.weights.get("freshness", 0.3) * freshness_score +
                self.config.weights.get("relevance", 0.4) * relevance_score +
                self.config.weights.get("trust", 0.3) * trust_score
            )

            external_score = external_scores.get(idx)
            if external_score is not None:
                final_score = (
                    (1 - self.config.external_rerank_weight) * internal_score +
                    self.config.external_rerank_weight * external_score
                )
            else:
                final_score = internal_score

            search_result.final_score = final_score
            search_result.external_rerank_score = external_score
            scored_results.append((content_fetch_result, final_score))

        scored_results.sort(key=lambda x: x[1], reverse=True)

        return [cr for cr, _ in scored_results[:self.config.top_k]]

    def _get_external_scores(
        self,
        search_results: List[SearchResult],
        query: str
    ) -> Dict[int, float]:
        if not self.reranker_client or not search_results:
            return {}

        try:
            texts = []
            for r in search_results:
                if hasattr(r, 'content') and r.content:
                    texts.append(r.content)
                else:
                    texts.append(r.snippet or r.title)

            rerank_results = self.reranker_client.rerank(
                query=query,
                texts=texts,
                top_n=len(search_results)
            )

            return {r.index: r.score for r in rerank_results}
        except Exception:
            return {}

    def _calc_freshness(self, search_result: SearchResult) -> float:
        publish_date = search_result.published_date

        if publish_date is None:
            return 0.5

        if isinstance(publish_date, str):
            try:
                publish_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))
            except Exception:
                return 0.5

        return self.freshness_scorer.calculate_freshness_score(publish_date)

    def _calc_relevance(self, search_result: SearchResult) -> float:
        return min(1.0, max(0.0, search_result.relevance_score / 10.0))

    def _calc_trust(self, search_result: SearchResult) -> float:
        return self.trust_scorer.get_trust_score(search_result.source_domain)