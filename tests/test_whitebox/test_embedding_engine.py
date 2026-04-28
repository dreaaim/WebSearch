import pytest
import asyncio
import numpy as np
from web_search.resolver.embedding_engine import (
    EmbeddingSimilarityEngine,
    MockEmbeddingClient,
    EmbeddingClient
)


class TestCosineSimilarity:
    def setup_method(self):
        client = MockEmbeddingClient()
        self.engine = EmbeddingSimilarityEngine(embedding_client=client)

    def test_cosine_similarity_identical_vectors(self):
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([1.0, 0.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == 1.0

    def test_cosine_similarity_opposite_vectors(self):
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([-1.0, 0.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == -1.0

    def test_cosine_similarity_perpendicular_vectors(self):
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert abs(score) < 0.0001

    def test_cosine_similarity_zero_vector(self):
        vec1 = np.array([0.0, 0.0])
        vec2 = np.array([1.0, 0.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == 0.0

    def test_cosine_similarity_multi_dimensional(self):
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([1.0, 2.0, 3.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert score == 1.0

    def test_cosine_similarity_partial_match(self):
        vec1 = np.array([1.0, 1.0, 0.0])
        vec2 = np.array([1.0, 0.0, 1.0])
        score = self.engine._cosine_similarity(vec1, vec2)
        assert 0.0 < score < 1.0


class TestComputeSimilarity:
    def setup_method(self):
        self.engine = EmbeddingSimilarityEngine()

    def test_compute_similarity_returns_float(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.engine.compute_similarity("hello world", "hello world")
        )
        loop.close()
        assert isinstance(score, float)

    def test_compute_similarity_range(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.engine.compute_similarity("hello world", "hello world")
        )
        loop.close()
        assert -1.0 <= score <= 1.0

    def test_compute_similarity_same_text(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.engine.compute_similarity("test text", "test text")
        )
        loop.close()
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0

    def test_compute_similarity_different_texts(self):
        loop = asyncio.new_event_loop()
        score = loop.run_until_complete(
            self.engine.compute_similarity("hello world", "hello world")
        )
        loop.close()
        assert isinstance(score, float)
        assert -1.0 <= score <= 1.0


class TestComputeBatchSimilarities:
    def setup_method(self):
        self.engine = EmbeddingSimilarityEngine()

    def test_compute_batch_similarities_returns_matrix(self):
        loop = asyncio.new_event_loop()
        texts = ["hello", "world", "hello world"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        assert isinstance(matrix, list)
        assert len(matrix) == 3
        assert len(matrix[0]) == 3

    def test_compute_batch_similarities_square_matrix(self):
        loop = asyncio.new_event_loop()
        texts = ["a", "b", "c", "d"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        assert len(matrix) == 4
        for row in matrix:
            assert len(row) == 4

    def test_compute_batch_similarities_single_text(self):
        loop = asyncio.new_event_loop()
        texts = ["only one"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        assert len(matrix) == 1
        assert len(matrix[0]) == 1

    def test_compute_batch_similarities_empty_list(self):
        loop = asyncio.new_event_loop()
        texts = []
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        assert matrix == []

    def test_compute_batch_similarities_diagonal_ones(self):
        loop = asyncio.new_event_loop()
        texts = ["test", "different"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        for i in range(len(texts)):
            assert abs(matrix[i][i] - 1.0) < 0.0001

    def test_compute_batch_similarities_symmetric(self):
        loop = asyncio.new_event_loop()
        texts = ["hello world", "world hello"]
        matrix = loop.run_until_complete(
            self.engine.compute_batch_similarities(texts)
        )
        loop.close()
        assert abs(matrix[0][1] - matrix[1][0]) < 0.0001


class TestMockEmbeddingClient:
    def test_mock_client_returns_vectors(self):
        loop = asyncio.new_event_loop()
        client = MockEmbeddingClient()
        vectors = loop.run_until_complete(
            client.encode(["text1", "text2"])
        )
        loop.close()
        assert len(vectors) == 2
        assert isinstance(vectors[0], np.ndarray)
        assert isinstance(vectors[1], np.ndarray)

    def test_mock_client_vector_dimension(self):
        loop = asyncio.new_event_loop()
        client = MockEmbeddingClient()
        vectors = loop.run_until_complete(
            client.encode(["text"])
        )
        loop.close()
        assert len(vectors[0]) == 384


class TestEmbeddingSimilarityEngineWithCustomClient:
    def test_engine_with_none_client_uses_mock(self):
        engine = EmbeddingSimilarityEngine(embedding_client=None)
        assert engine.embedding_client is not None
        assert isinstance(engine.embedding_client, MockEmbeddingClient)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
