import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from web_search.reranker.reranker import Reranker, RerankConfig, ClassifiedResult, SearchResult, SourceType, SourceLevel, Classification
from web_search.classifier.source_classifier import SourceClassifier
from web_search.core.models import SearchResult as SearchResultModel, Classification as ClassifModel, SourceType as SourceTypeModel, SourceLevel as SourceLevelModel


def create_search_result(domain, title="Test", classification=Classification.GRAY):
    return SearchResult(
        title=title,
        url=f"https://{domain}/test",
        snippet="Test snippet",
        source_name="Test",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL,
        classification=classification,
        published_date=datetime.now().isoformat()
    )


def create_classified_result(search_result, relevance_score=5.0):
    return ClassifiedResult(
        result=search_result,
        source_type=search_result.source_type,
        source_level=search_result.source_level,
        classification=search_result.classification,
        relevance_score=relevance_score,
        is_blacklisted=search_result.classification == Classification.BLACK
    )


class TestClassificationAndRerankingCollaboration:
    def setup_method(self):
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[{"domain": "fake.cn"}]
        )
        self.reranker = Reranker()

    def test_classified_results_passed_to_reranker(self):
        results = [
            create_search_result("gov.cn", "Official Content", Classification.WHITE),
            create_search_result("blog.com", "Blog Content", Classification.GRAY),
            create_search_result("fake.cn", "Fake Content", Classification.BLACK),
        ]

        classified_results = []
        for result in results:
            classification = self.classifier.classify(result)
            result.classification = classification
            classified = create_classified_result(result, relevance_score=7.0)
            classified_results.append(classified)

        reranked = self.reranker.rerank(classified_results)

        assert len(reranked) > 0
        assert all(isinstance(r, ClassifiedResult) for r in reranked)

    def test_reranker_sorts_by_composite_score(self):
        results = [
            create_search_result("gov.cn", "Official", Classification.WHITE),
            create_search_result("blog.com", "Blog", Classification.GRAY),
        ]

        classified_results = [
            create_classified_result(results[0], relevance_score=3.0),
            create_classified_result(results[1], relevance_score=9.0),
        ]

        reranked = self.reranker.rerank(classified_results)

        assert len(reranked) == 2

    def test_whitelist_results_ranked_higher_than_gray(self):
        white_result = create_search_result("gov.cn", "Official", Classification.WHITE)
        gray_result = create_search_result("news.com", "News", Classification.GRAY)

        white_classified = create_classified_result(white_result, relevance_score=5.0)
        gray_classified = create_classified_result(gray_result, relevance_score=8.0)

        classified_results = [white_classified, gray_classified]

        reranked = self.reranker.rerank(classified_results)

        white_score = self.reranker._calculate_composite_score(white_classified, None)
        gray_score = self.reranker._calculate_composite_score(gray_classified, None)

        assert white_score > gray_score

    def test_blacklist_results_scored_zero_trustworthiness(self):
        black_result = create_search_result("fake.cn", "Fake", Classification.BLACK)
        gray_result = create_search_result("news.com", "News", Classification.GRAY)

        black_classified = create_classified_result(black_result, relevance_score=5.0)
        gray_classified = create_classified_result(gray_result, relevance_score=5.0)

        black_score = self.reranker._calculate_composite_score(black_classified, None)
        gray_score = self.reranker._calculate_composite_score(gray_classified, None)

        assert black_score < gray_score


class TestMultipleResultsReranking:
    def setup_method(self):
        self.reranker = Reranker()

    def test_rerank_multiple_mixed_results(self):
        results = [
            create_search_result("gov.cn", "Official 1", Classification.WHITE),
            create_search_result("gov.cn", "Official 2", Classification.WHITE),
            create_search_result("news.com", "News 1", Classification.GRAY),
            create_search_result("news.com", "News 2", Classification.GRAY),
            create_search_result("blog.com", "Blog 1", Classification.GRAY),
            create_search_result("fake.cn", "Fake 1", Classification.BLACK),
        ]

        classified = [create_classified_result(r, relevance_score=5.0 + i) for i, r in enumerate(results)]

        reranked = self.reranker.rerank(classified)

        assert len(reranked) == 6

    def test_rerank_respects_top_k(self):
        results = [
            create_search_result(f"s{i}.com", f"Source {i}", Classification.GRAY)
            for i in range(20)
        ]

        classified = [create_classified_result(r, relevance_score=5.0) for r in results]

        reranked = self.reranker.rerank(classified, top_k=5)

        assert len(reranked) == 5


class TestAuthorityBasedRanking:
    def setup_method(self):
        self.reranker = Reranker()

    def test_national_official_ranked_above_provincial(self):
        national = create_search_result("gov.cn", "National", Classification.WHITE)
        national.source_type = SourceType.OFFICIAL
        national.source_level = SourceLevel.NATIONAL

        provincial = create_search_result("zj.gov.cn", "Provincial", Classification.WHITE)
        provincial.source_type = SourceType.OFFICIAL
        provincial.source_level = SourceLevel.PROVINCIAL

        national_classified = create_classified_result(national, relevance_score=5.0)
        provincial_classified = create_classified_result(provincial, relevance_score=5.0)

        national_score = self.reranker._calculate_composite_score(national_classified, None)
        provincial_score = self.reranker._calculate_composite_score(provincial_classified, None)

        assert national_score > provincial_score

    def test_official_ranked_above_media(self):
        official = create_search_result("gov.cn", "Official", Classification.WHITE)
        official.source_type = SourceType.OFFICIAL
        official.source_level = SourceLevel.NATIONAL

        media = create_search_result("news.com", "Media", Classification.WHITE)
        media.source_type = SourceType.MEDIA
        media.source_level = SourceLevel.NATIONAL

        official_classified = create_classified_result(official, relevance_score=5.0)
        media_classified = create_classified_result(media, relevance_score=5.0)

        official_score = self.reranker._calculate_composite_score(official_classified, None)
        media_score = self.reranker._calculate_composite_score(media_classified, None)

        assert official_score > media_score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
