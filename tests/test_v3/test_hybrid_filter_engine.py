import pytest
import asyncio
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from web_search.filter.hybrid_filter_engine import HybridFilterEngine, HybridFilterResult
from web_search.filter.embedding_scorer import EmbeddingScorer
from web_search.filter.bm25_scorer import BM25Scorer
from web_search.core.models import SearchResult, SourceType, SourceLevel, Classification


class MockEmbeddingClient:
    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        return [np.random.randn(384) for _ in texts]


class ZeroEmbeddingClient:
    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        return [np.zeros(384) for _ in texts]


class UnitVectorEmbeddingClient:
    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        vec = np.array([1.0, 0.0, 0.0] + [0.0] * 381)
        return [vec.copy() for _ in texts]


class SyncEmbeddingScorer:
    def __init__(self, scores: List[float] = None):
        self._scores = scores or [1.0]
        self._embedding_client = None

    def compute_batch_scores(self, query: str, titles: List[str]) -> List[float]:
        return [self._scores[i % len(self._scores)] for i in range(len(titles))]


def create_test_search_result(title: str, snippet: str) -> SearchResult:
    return SearchResult(
        title=title,
        url=f"http://example.com/{title.replace(' ', '-')}",
        snippet=snippet,
        source_name="Test Source",
        source_domain="example.com",
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.NATIONAL,
        classification=Classification.WHITE
    )


class TestEmbeddingScoreRange:
    def setup_method(self):
        self.scorer = EmbeddingScorer(embedding_client=UnitVectorEmbeddingClient())

    def test_embedding_score_in_range_negative_one_to_one(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.scorer.compute_embedding_score("hello world", "hello world")
        )
        loop.close()
        assert -1.0 <= score <= 1.0

    def test_embedding_score_can_be_positive(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.scorer.compute_embedding_score("hello world", "hello world")
        )
        loop.close()
        assert score >= 0.0

    def test_embedding_score_batch_returns_values_in_range(self):
        loop = asyncio.new_event_loop()
        titles = ["hello world", "test text", "another example"]
        scores = loop.run_until_complete(
            self.scorer.compute_batch_scores("hello world", titles)
        )
        loop.close()
        assert len(scores) == len(titles)
        for score in scores:
            assert -1.0 <= score <= 1.0


class TestBM25ScoreCalculation:
    def setup_method(self):
        self.scorer = BM25Scorer()

    def test_bm25_score_returns_float(self):
        texts = ["hello world test", "another document here"]
        scores = self.scorer.compute_batch_scores("hello", texts)
        assert isinstance(scores[0], float)

    def test_bm25_score_same_query_document_high(self):
        scorer = BM25Scorer()
        texts = ["hello world hello", "different content here"]
        scores = scorer.compute_batch_scores("hello", texts)
        assert scores[0] > 0.0

    def test_bm25_score_no_match_zero(self):
        scorer = BM25Scorer()
        texts = ["completely different content", "no matching terms at all"]
        scores = scorer.compute_batch_scores("xyz123 nonexistent", texts)
        assert all(s == 0.0 for s in scores)

    def test_bm25_score_multiple_terms(self):
        scorer = BM25Scorer()
        texts = ["the quick brown fox jumps", "another document with different words"]
        scores = scorer.compute_batch_scores("quick fox", texts)
        assert scores[0] > 0.0

    def test_bm25_score_order_by_relevance(self):
        scorer = BM25Scorer()
        texts = [
            "python programming language tutorial",
            "java programming language guide",
            "cooking recipes for dinner"
        ]
        scores = scorer.compute_batch_scores("programming language", texts)
        assert scores[0] > scores[2]
        assert scores[1] > scores[2]


class TestHybridScoreDefaultWeights:
    def test_hybrid_score_with_default_weights(self):
        sync_scorer = SyncEmbeddingScorer([1.0, 0.8])
        engine = HybridFilterEngine(
            embedding_weight=0.6,
            bm25_weight=0.4,
            embedding_scorer=sync_scorer
        )

        results = [create_test_search_result("hello world", "test snippet")]

        hybrid_results = engine.filter_sync(results, "hello world")

        assert len(hybrid_results) == 1
        hybrid_score = hybrid_results[0].hybrid_score
        emb_score = hybrid_results[0].embedding_score
        bm_score = hybrid_results[0].bm25_score

        expected_hybrid = 0.6 * emb_score + 0.4 * bm_score
        assert abs(hybrid_score - expected_hybrid) < 0.0001

    def test_hybrid_score_empty_results(self):
        engine = HybridFilterEngine()
        hybrid_results = engine.filter_sync([], "test query")
        assert hybrid_results == []

    def test_hybrid_score_custom_weights(self):
        sync_scorer = SyncEmbeddingScorer([0.9, 0.7])
        engine = HybridFilterEngine(
            embedding_weight=0.7,
            bm25_weight=0.3,
            embedding_scorer=sync_scorer
        )

        results = [create_test_search_result("python tutorial", "learn python")]

        hybrid_results = engine.filter_sync(results, "python")

        hybrid_score = hybrid_results[0].hybrid_score
        emb_score = hybrid_results[0].embedding_score
        bm_score = hybrid_results[0].bm25_score

        expected_hybrid = 0.7 * emb_score + 0.3 * bm_score
        assert abs(hybrid_score - expected_hybrid) < 0.0001


class TestHybridFilterThreshold:
    def test_filter_threshold_removes_low_scores(self):
        sync_scorer = SyncEmbeddingScorer([0.1])
        engine = HybridFilterEngine(
            embedding_weight=0.6,
            bm25_weight=0.4,
            embedding_scorer=sync_scorer,
            min_hybrid_score=100.0
        )

        results = [
            create_test_search_result("hello world", "test content"),
        ]

        hybrid_results = engine.filter_sync(results, "hello world")

        assert len(hybrid_results) == 0

    def test_filter_threshold_keeps_high_scores(self):
        sync_scorer = SyncEmbeddingScorer([1.0])
        engine = HybridFilterEngine(
            embedding_weight=0.6,
            bm25_weight=0.4,
            embedding_scorer=sync_scorer,
            min_hybrid_score=0.0
        )

        results = [
            create_test_search_result("hello world", "test content"),
        ]

        hybrid_results = engine.filter_sync(results, "hello world")

        assert len(hybrid_results) == 1
        assert hybrid_results[0].hybrid_score >= 0.0

    def test_filter_threshold_multiple_results(self):
        sync_scorer = SyncEmbeddingScorer([0.9, 0.1])
        engine = HybridFilterEngine(
            embedding_weight=0.6,
            bm25_weight=0.4,
            embedding_scorer=sync_scorer,
            min_hybrid_score=0.5
        )

        results = [
            create_test_search_result("python programming", "python tutorial"),
            create_test_search_result("unrelated content", "something else entirely"),
        ]

        hybrid_results = engine.filter_sync(results, "python")

        for r in hybrid_results:
            assert r.hybrid_score >= 0.5


class TestFilterSyncReturnsList:
    def test_filter_sync_returns_list(self):
        sync_scorer = SyncEmbeddingScorer([1.0])
        engine = HybridFilterEngine(embedding_scorer=sync_scorer)

        results = [
            create_test_search_result("test title", "test snippet"),
        ]

        result = engine.filter_sync(results, "test")

        assert isinstance(result, list)

    def test_filter_sync_returns_hybrid_filter_results(self):
        sync_scorer = SyncEmbeddingScorer([1.0])
        engine = HybridFilterEngine(embedding_scorer=sync_scorer)

        results = [
            create_test_search_result("hello world", "test content"),
        ]

        hybrid_results = engine.filter_sync(results, "hello world")

        assert len(hybrid_results) > 0
        assert isinstance(hybrid_results[0], HybridFilterResult)

    def test_filter_sync_hybrid_result_has_all_fields(self):
        sync_scorer = SyncEmbeddingScorer([0.8])
        engine = HybridFilterEngine(embedding_scorer=sync_scorer)

        results = [
            create_test_search_result("python tutorial", "learn python"),
        ]

        hybrid_results = engine.filter_sync(results, "python")

        assert len(hybrid_results) == 1
        hr = hybrid_results[0]

        assert isinstance(hr.result, SearchResult)
        assert isinstance(hr.embedding_score, float)
        assert isinstance(hr.bm25_score, float)
        assert isinstance(hr.hybrid_score, float)

    def test_filter_sync_sorted_by_hybrid_score(self):
        sync_scorer = SyncEmbeddingScorer([0.9, 0.5, 0.3])
        engine = HybridFilterEngine(embedding_scorer=sync_scorer)

        results = [
            create_test_search_result("python programming", "python code"),
            create_test_search_result("javascript tutorial", "javascript guide"),
            create_test_search_result("rust language", "rust manual"),
        ]

        hybrid_results = engine.filter_sync(results, "python")

        for i in range(len(hybrid_results) - 1):
            assert hybrid_results[i].hybrid_score >= hybrid_results[i + 1].hybrid_score

    def test_filter_sync_empty_input_returns_empty_list(self):
        sync_scorer = SyncEmbeddingScorer([1.0])
        engine = HybridFilterEngine(embedding_scorer=sync_scorer)

        result = engine.filter_sync([], "test query")

        assert result == []
        assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])