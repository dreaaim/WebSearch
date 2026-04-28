import pytest
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine, MockEmbeddingClient
from web_search.resolver.hybrid_similarity import HybridSimilarityEngine


class TestEmbeddingSimilarityEngine:
    def setup_method(self):
        self.client = MockEmbeddingClient()
        self.engine = EmbeddingSimilarityEngine(embedding_client=self.client)

    def test_compute_similarity(self):
        import asyncio
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.engine.compute_similarity("hello world", "hello world")
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        loop.close()

    def test_compute_batch_similarities(self):
        import asyncio
        loop = asyncio.new_event_loop()
        texts = ["hello", "world", "hello world"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        assert len(matrix) == 3
        assert len(matrix[0]) == 3
        loop.close()

    def test_cosine_similarity(self):
        import numpy as np
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([1.0, 0.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == 1.0

    def test_cosine_similarity_zero(self):
        import numpy as np
        vec1 = np.array([0.0, 0.0])
        vec2 = np.array([1.0, 0.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == 0.0


class TestHybridSimilarityEngine:
    def setup_method(self):
        self.engine = HybridSimilarityEngine()

    def test_jaccard_similarity(self):
        score = self.engine._jaccard_similarity("hello world", "hello world")
        assert score == 1.0

    def test_jaccard_similarity_partial(self):
        score = self.engine._jaccard_similarity("hello world", "hello")
        assert 0.0 < score < 1.0

    def test_jaccard_similarity_none(self):
        score = self.engine._jaccard_similarity("", "")
        assert score == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])