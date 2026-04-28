from typing import List, Optional
import numpy as np
from ..core.embedding_client import EmbeddingClientBase, create_embedding_client

class EmbeddingScorer:
    def __init__(self, embedding_client=None):
        self._embedding_client = embedding_client
        self._default_client: Optional[EmbeddingClientBase] = None

    async def _get_client(self) -> "EmbeddingClientBase":
        if self._embedding_client is not None:
            return self._embedding_client
        if self._default_client is None:
            self._default_client = create_embedding_client({})
        return self._default_client

    async def compute_embedding_score(self, query: str, title: str) -> float:
        client = await self._get_client()
        embeddings = await client.encode([query, title])
        return self._cosine_similarity(embeddings[0], embeddings[1])

    async def compute_batch_scores(
        self,
        query: str,
        titles: List[str]
    ) -> List[float]:
        if not titles:
            return []
        client = await self._get_client()
        texts = [query] + titles
        embeddings = await client.encode(texts)
        query_embedding = embeddings[0]
        title_embeddings = embeddings[1:]
        scores = [
            self._cosine_similarity(query_embedding, title_emb)
            for title_emb in title_embeddings
        ]
        return scores

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))