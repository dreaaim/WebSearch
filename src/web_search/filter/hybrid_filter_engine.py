import asyncio
from dataclasses import dataclass
from typing import List
from .embedding_scorer import EmbeddingScorer
from .bm25_scorer import BM25Scorer
from ..core.models import SearchResult

@dataclass
class HybridFilterResult:
    result: SearchResult
    embedding_score: float
    bm25_score: float
    hybrid_score: float

class HybridFilterEngine:
    def __init__(
        self,
        embedding_weight: float = 0.6,
        bm25_weight: float = 0.4,
        embedding_scorer: EmbeddingScorer = None,
        bm25_scorer: BM25Scorer = None,
        min_hybrid_score: float = 0.0
    ):
        self._embedding_weight = embedding_weight
        self._bm25_weight = bm25_weight
        self._embedding_scorer = embedding_scorer or EmbeddingScorer()
        self._bm25_scorer = bm25_scorer or BM25Scorer()
        self._min_hybrid_score = min_hybrid_score

    async def filter(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[HybridFilterResult]:
        if not results:
            return []

        titles = [r.title for r in results]
        content = [r.snippet for r in results]

        embedding_scores = await self._embedding_scorer.compute_batch_scores(query, titles)
        bm25_scorer = BM25Scorer()
        bm25_scores = bm25_scorer.compute_batch_scores(query, titles + content)

        hybrid_results = []
        for i, result in enumerate(results):
            emb_score = embedding_scores[i] if i < len(embedding_scores) else 0.0
            bm_score = bm25_scores[i] if i < len(bm25_scores) else 0.0

            hybrid_score = (
                self._embedding_weight * emb_score +
                self._bm25_weight * bm_score
            )

            hybrid_results.append(HybridFilterResult(
                result=result,
                embedding_score=emb_score,
                bm25_score=bm_score,
                hybrid_score=hybrid_score
            ))

        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)

        return [r for r in hybrid_results if r.hybrid_score >= self._min_hybrid_score]

    def filter_sync(
        self,
        results: List[SearchResult],
        query: str
    ) -> List[HybridFilterResult]:
        if not results:
            return []

        titles = [r.title for r in results]
        content = [r.snippet for r in results]

        embedding_scores = asyncio.run(self._embedding_scorer.compute_batch_scores(query, titles))
        bm25_scorer = BM25Scorer()
        bm25_scores = bm25_scorer.compute_batch_scores(query, titles + content)

        hybrid_results = []
        for i, result in enumerate(results):
            emb_score = embedding_scores[i] if i < len(embedding_scores) else 0.0
            bm_score = bm25_scores[i] if i < len(bm25_scores) else 0.0

            hybrid_score = (
                self._embedding_weight * emb_score +
                self._bm25_weight * bm_score
            )

            hybrid_results.append(HybridFilterResult(
                result=result,
                embedding_score=emb_score,
                bm25_score=bm_score,
                hybrid_score=hybrid_score
            ))

        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)

        return [r for r in hybrid_results if r.hybrid_score >= self._min_hybrid_score]