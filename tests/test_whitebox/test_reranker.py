import pytest
import numpy as np
from datetime import datetime, timedelta
from web_search.reranker.reranker import (
    Reranker, RerankConfig, ClassifiedResult, SearchResult,
    SourceType, SourceLevel, Classification, AuthorityLevel
)


def create_search_result(
    domain="example.com",
    source_type=SourceType.MEDIA,
    source_level=SourceLevel.MUNICIPAL,
    published_date=None,
    classification=Classification.GRAY
):
    return SearchResult(
        title="Test Title",
        url=f"https://{domain}/test",
        snippet="Test snippet",
        source_name="Test Source",
        source_domain=domain,
        source_type=source_type,
        source_level=source_level,
        published_date=published_date,
        classification=classification
    )


def create_classified_result(
    result=None,
    source_type=SourceType.MEDIA,
    source_level=SourceLevel.MUNICIPAL,
    classification=Classification.GRAY,
    relevance_score=5.0,
    is_blacklisted=False
):
    if result is None:
        result = create_search_result()
    return ClassifiedResult(
        result=result,
        source_type=source_type,
        source_level=source_level,
        classification=classification,
        relevance_score=relevance_score,
        is_blacklisted=is_blacklisted
    )


class TestRerankerCompositeScore:
    def setup_method(self):
        self.reranker = Reranker()

    def test_calculate_composite_score_basic(self):
        result = create_classified_result(
            relevance_score=10.0,
            classification=Classification.WHITE,
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.NATIONAL,
            is_blacklisted=False
        )
        result.result.published_date = datetime.now().isoformat()

        score = self.reranker._calculate_composite_score(result, None)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        expected = (
            0.4 * 1.0 +
            0.3 * 1.0 +
            0.15 * 1.0 +
            0.15 * 1.0
        )
        assert abs(score - expected) < 0.01

    def test_calculate_composite_score_with_relevance_weight(self):
        result = create_classified_result(relevance_score=5.0)
        result.result.published_date = datetime.now().isoformat()

        score = self.reranker._calculate_composite_score(result, None)

        relevance_component = 0.4 * (5.0 / 10.0)
        assert score >= relevance_component

    def test_calculate_composite_score_with_judgments(self):
        result = create_classified_result(relevance_score=8.0)
        result.result.published_date = datetime.now().isoformat()

        judgments = []
        score = self.reranker._calculate_composite_score(result, judgments)

        assert isinstance(score, float)


class TestRerankerTrustworthiness:
    def setup_method(self):
        self.reranker = Reranker()

    def test_get_trustworthiness_white(self):
        result = create_classified_result(classification=Classification.WHITE)
        score = self.reranker._get_trustworthiness(result)
        assert score == 1.0

    def test_get_trustworthiness_gray(self):
        result = create_classified_result(classification=Classification.GRAY)
        score = self.reranker._get_trustworthiness(result)
        assert score == 0.5

    def test_get_trustworthiness_black(self):
        result = create_classified_result(classification=Classification.BLACK)
        score = self.reranker._get_trustworthiness(result)
        assert score == 0.0

    def test_get_trustworthiness_blacklisted(self):
        result = create_classified_result(is_blacklisted=True)
        score = self.reranker._get_trustworthiness(result)
        assert score == 0.0

    def test_get_trustworthiness_blacklisted_overrides_classification(self):
        result = create_classified_result(
            classification=Classification.WHITE,
            is_blacklisted=True
        )
        score = self.reranker._get_trustworthiness(result)
        assert score == 0.0


class TestRerankerAuthorityScore:
    def setup_method(self):
        self.reranker = Reranker()

    def test_get_authority_score_national_official(self):
        result = create_classified_result(
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.NATIONAL
        )
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.NATIONAL_OFFICIAL

    def test_get_authority_score_provincial_official(self):
        result = create_classified_result(
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.PROVINCIAL
        )
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.PROVINCIAL_OFFICIAL

    def test_get_authority_score_municipal_official(self):
        result = create_classified_result(
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.MUNICIPAL
        )
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.MUNICIPAL_OFFICIAL

    def test_get_authority_score_national_media(self):
        result = create_classified_result(
            source_type=SourceType.MEDIA,
            source_level=SourceLevel.NATIONAL
        )
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.NATIONAL_MEDIA

    def test_get_authority_score_provincial_media(self):
        result = create_classified_result(
            source_type=SourceType.MEDIA,
            source_level=SourceLevel.PROVINCIAL
        )
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.PROVINCIAL_MEDIA

    def test_get_authority_score_kol(self):
        result = create_classified_result(source_type=SourceType.KOL)
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.KOL_MEDIUM

    def test_get_authority_score_individual(self):
        result = create_classified_result(source_type=SourceType.INDIVIDUAL)
        score = self.reranker._get_authority_score(result)
        assert score == AuthorityLevel.INDIVIDUAL


class TestRerankerJudgmentBonus:
    def setup_method(self):
        self.reranker = Reranker()

    def test_get_judgment_bonus_no_judgments(self):
        result = create_classified_result()
        bonus = self.reranker._get_judgment_bonus(result, None)
        assert bonus == 0.0

    def test_get_judgment_bonus_with_judgments(self):
        result = create_classified_result()
        judgments = []
        bonus = self.reranker._get_judgment_bonus(result, judgments)
        assert isinstance(bonus, float)


class TestRerankerRerank:
    def setup_method(self):
        self.reranker = Reranker()

    def test_rerank_returns_list(self):
        results = [create_classified_result() for _ in range(5)]
        reranked = self.reranker.rerank(results)
        assert isinstance(reranked, list)

    def test_rerank_respects_top_k(self):
        results = [create_classified_result() for _ in range(10)]
        reranked = self.reranker.rerank(results, top_k=3)
        assert len(reranked) == 3

    def test_rerank_orders_by_score(self):
        result1 = create_classified_result(relevance_score=3.0)
        result2 = create_classified_result(relevance_score=8.0)
        results = [result1, result2]
        reranked = self.reranker.rerank(results)
        assert reranked[0].relevance_score >= reranked[1].relevance_score


class TestRerankerConfig:
    def test_default_weights(self):
        config = RerankConfig()
        assert config.weights["relevance"] == 0.4
        assert config.weights["trustworthiness"] == 0.3
        assert config.weights["freshness"] == 0.15
        assert config.weights["authority"] == 0.15

    def test_custom_weights(self):
        config = RerankConfig(weights={
            "relevance": 0.5,
            "trustworthiness": 0.2,
            "freshness": 0.2,
            "authority": 0.1
        })
        assert config.weights["relevance"] == 0.5
        assert config.weights["trustworthiness"] == 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
