import pytest
import math
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from web_search.reranker.multi_factor_reranker import (
    MultiFactorReranker,
    RerankConfig
)
from web_search.fetcher.content_fetcher import ContentFetchResult
from web_search.reranker.freshness_scorer import FreshnessScorer
from web_search.reranker.trust_scorer import TrustScorer
from web_search.core.models import SearchResult, SourceType, SourceLevel, Classification


def create_content_fetch_result(
    domain="example.com",
    published_date: Optional[datetime] = None,
    relevance_score: float = 5.0,
    content: str = "Test content",
    fetch_success: bool = True
):
    search_result = SearchResult(
        title="Test Title",
        url=f"https://{domain}/test",
        snippet="Test snippet",
        source_name="Test Source",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.NATIONAL,
        published_date=published_date.isoformat() if published_date else None,
        relevance_score=relevance_score,
        classification=Classification.WHITE
    )
    return ContentFetchResult(
        result=search_result,
        content=content,
        fetch_success=fetch_success
    )


class TestFreshnessScorerExponentialDecay:
    def setup_method(self):
        self.scorer = FreshnessScorer(lambda_decay=0.1)

    def test_freshness_score_exponential_decay(self):
        today = datetime.now()
        score_today = self.scorer.calculate_freshness_score(today)
        assert abs(score_today - 1.0) < 0.01

        days_1 = (today - timedelta(days=1))
        score_1 = self.scorer.calculate_freshness_score(days_1)
        expected_1 = math.exp(-0.1 * 1)
        assert abs(score_1 - expected_1) < 0.01

        days_10 = (today - timedelta(days=10))
        score_10 = self.scorer.calculate_freshness_score(days_10)
        expected_10 = math.exp(-0.1 * 10)
        assert abs(score_10 - expected_10) < 0.01

    def test_freshness_score_3_days(self):
        today = datetime.now()
        three_days_ago = today - timedelta(days=3)
        score = self.scorer.calculate_freshness_score(three_days_ago)
        expected = math.exp(-0.1 * 3)
        assert abs(score - expected) < 0.01
        assert abs(score - 0.74) < 0.02

    def test_freshness_score_very_old(self):
        today = datetime.now()
        very_old = today - timedelta(days=365)
        score = self.scorer.calculate_freshness_score(very_old)
        expected = math.exp(-0.1 * 365)
        assert score < 0.01
        assert abs(score - expected) < 0.001


class TestTrustScoreNormalization:
    def setup_method(self):
        self.scorer = TrustScorer()

    def test_trust_score_normalization(self):
        assert self.scorer.get_trust_score("cctv.com") == 0.95
        assert self.scorer.get_trust_score("xinhuanet.com") == 0.95
        assert self.scorer.get_trust_score("people.com.cn") == 0.93
        assert self.scorer.get_trust_score("gov.cn") == 0.90

        assert 0.0 <= self.scorer.get_trust_score("unknown.com") <= 1.0
        assert self.scorer.get_trust_score("unknown.com") == 0.5

        assert 0.0 <= self.scorer.get_trust_score("") <= 1.0

    def test_trust_score_domain_matching(self):
        assert self.scorer.get_trust_score("news.cctv.com") == 0.95
        assert self.scorer.get_trust_score("www.xinhuanet.com") == 0.95
        assert self.scorer.get_trust_score("example.gov.cn") == 0.90


class TestCompositeWeightedScore:
    def setup_method(self):
        self.reranker = MultiFactorReranker()

    def test_composite_weighted_score(self):
        today = datetime.now()
        content_fetch_result = create_content_fetch_result(
            domain="cctv.com",
            published_date=today,
            relevance_score=10.0
        )
        search_result = content_fetch_result.result

        freshness_score = self.reranker._calc_freshness(search_result)
        relevance_score = self.reranker._calc_relevance(search_result)
        trust_score = self.reranker._calc_trust(search_result)

        expected = (
            0.3 * freshness_score +
            0.4 * relevance_score +
            0.3 * trust_score
        )

        assert 0.0 <= freshness_score <= 1.0
        assert 0.0 <= relevance_score <= 1.0
        assert 0.0 <= trust_score <= 1.0
        assert 0.0 <= expected <= 1.0


class TestRerankSortedResults:
    def setup_method(self):
        self.reranker = MultiFactorReranker()

    def test_rerank_returns_sorted_results(self):
        today = datetime.now()

        low_score_result = create_content_fetch_result(
            domain="unknown.com",
            published_date=today - timedelta(days=30),
            relevance_score=2.0
        )

        high_score_result = create_content_fetch_result(
            domain="cctv.com",
            published_date=today,
            relevance_score=10.0
        )

        results = [low_score_result, high_score_result]
        reranked = self.reranker.rerank(results, "test query")

        assert len(reranked) == 2
        assert isinstance(reranked[0], ContentFetchResult)
        assert reranked[0].result.source_domain == "cctv.com"
        assert reranked[1].result.source_domain == "unknown.com"

    def test_rerank_top_50(self):
        today = datetime.now()
        results = [
            create_content_fetch_result(
                domain=f"domain{i}.com",
                published_date=today - timedelta(days=i),
                relevance_score=float(10 - i % 10)
            )
            for i in range(100)
        ]

        reranked = self.reranker.rerank(results, "test query")

        assert len(reranked) == 50
        assert all(isinstance(r, ContentFetchResult) for r in reranked)


class TestMultiFactorRerankerEdgeCases:
    def setup_method(self):
        config = RerankConfig(
            weights={"freshness": 0.3, "relevance": 0.4, "trust": 0.3},
            freshness_lambda=0.1,
            top_k=50
        )
        self.reranker = MultiFactorReranker(config)

    def test_rerank_empty_results(self):
        reranked = self.reranker.rerank([], "test query")
        assert reranked == []

    def test_rerank_no_published_date(self):
        result = create_content_fetch_result(published_date=None)
        results = [result]
        reranked = self.reranker.rerank(results, "test query")
        assert len(reranked) == 1
        assert isinstance(reranked[0], ContentFetchResult)

    def test_rerank_future_date(self):
        future = datetime.now() + timedelta(days=10)
        content_fetch_result = create_content_fetch_result(published_date=future)
        freshness = self.reranker._calc_freshness(content_fetch_result.result)
        assert freshness == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])