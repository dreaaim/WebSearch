"""
DEPRECATED: Use filter.EmbeddingScorer instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated embedding-based filtering via HybridFilterEngine.
"""
from abc import ABC, abstractmethod
from typing import List
import numpy as np

class EmbeddingClient(ABC):
    @abstractmethod
    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        pass

class MockEmbeddingClient(EmbeddingClient):
    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        return [np.random.randn(384) for _ in texts]

class EmbeddingSimilarityEngine:
    def __init__(self, embedding_client: EmbeddingClient = None):
        self.embedding_client = embedding_client or MockEmbeddingClient()

    async def compute_similarity(self, text1: str, text2: str) -> float:
        embeddings = await self.embedding_client.encode([text1, text2])
        return self._cosine_similarity(embeddings[0], embeddings[1])

    async def compute_batch_similarities(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        embeddings = await self.embedding_client.encode(texts)
        n = len(texts)
        similarity_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                similarity_matrix[i][j] = self._cosine_similarity(
                    embeddings[i], embeddings[j]
                )

        return similarity_matrix.tolist()

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
