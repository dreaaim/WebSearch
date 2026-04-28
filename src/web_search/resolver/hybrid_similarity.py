"""
DEPRECATED: Use filter.HybridFilterEngine instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated hybrid filtering via HybridFilterEngine.
"""
from typing import List
from .embedding_engine import EmbeddingSimilarityEngine, EmbeddingClient

class HybridSimilarityEngine:
    def __init__(
        self,
        embedding_engine: EmbeddingSimilarityEngine = None,
        jaccard_weight: float = 0.3,
        embedding_weight: float = 0.7
    ):
        self.embedding_engine = embedding_engine or EmbeddingSimilarityEngine()
        self.jaccard_weight = jaccard_weight
        self.embedding_weight = embedding_weight

    async def compute_similarity(self, text1: str, text2: str) -> float:
        jaccard_sim = self._jaccard_similarity(text1, text2)
        embedding_sim = await self.embedding_engine.compute_similarity(text1, text2)

        return (
            self.jaccard_weight * jaccard_sim +
            self.embedding_weight * embedding_sim
        )

    async def compute_batch_similarities(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        jaccard_matrix = self._jaccard_batch_similarities(texts)
        embedding_matrix = await self.embedding_engine.compute_batch_similarities(texts)

        n = len(texts)
        hybrid_matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                hybrid_matrix[i][j] = (
                    self.jaccard_weight * jaccard_matrix[i][j] +
                    self.embedding_weight * embedding_matrix[i][j]
                )

        return hybrid_matrix

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 and not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _jaccard_batch_similarities(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        n = len(texts)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                matrix[i][j] = self._jaccard_similarity(texts[i], texts[j])

        return matrix
