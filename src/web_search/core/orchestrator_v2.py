"""
DEPRECATED: Use core.orchestrator.SearchOrchestratorV3 instead.

This module is part of the v2 architecture and will be removed in a future version.
v3 provides a more complete and streamlined trusted search flow.
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from .models import SearchOptions, SearchResponse, TrustedSearchResult, Classification
from ..providers.base import SearchProvider
from ..classifier.source_classifier import SourceClassifier
from ..classifier.llm_classifier import LLMSourceClassifier, ClassifiedResult
from ..resolver.fact_resolver import FactResolver
from ..resolver.embedding_engine import EmbeddingSimilarityEngine
from ..resolver.hybrid_similarity import HybridSimilarityEngine
from ..resolver.llm_judge import LLMCollisionJudge, CollisionJudgment
from ..resolver.deduplicator import Deduplicator
from ..summary.summary_generator import SummaryGenerator
from ..rewriter.query_rewriter import QueryRewriter, QueryRewriteResult
from ..reranker.reranker import Reranker, RerankConfig

@dataclass
class CollisionResult:
    collision_id: str
    claims: List[Any]
    resolved_claim: Optional[Any] = None
    priority_rule_used: str = ""
    consensus_degree: float = 0.0

@dataclass
class V2Metadata:
    version: str = "v2"
    rewrite_result: Optional[QueryRewriteResult] = None
    rerank_weights: Dict[str, float] = field(default_factory=dict)
    collision_judgments: List[CollisionJudgment] = field(default_factory=list)

class SearchOrchestratorV2:
    def __init__(
        self,
        provider: SearchProvider,
        source_classifier: SourceClassifier,
        llm_classifier: Optional[LLMSourceClassifier] = None,
        query_rewriter: Optional[QueryRewriter] = None,
        fact_resolver: Optional[FactResolver] = None,
        embedding_engine: Optional[Any] = None,
        collision_judge: Optional[LLMCollisionJudge] = None,
        reranker: Optional[Reranker] = None,
        summary_generator: Optional[SummaryGenerator] = None,
        deduplicator: Optional[Deduplicator] = None,
        use_v2_features: bool = True,
        similarity_threshold: float = 0.85
    ):
        self.provider = provider
        self.source_classifier = source_classifier
        self.llm_classifier = llm_classifier
        self.query_rewriter = query_rewriter
        self.fact_resolver = fact_resolver or FactResolver()
        self.embedding_engine = embedding_engine or HybridSimilarityEngine()
        self.collision_judge = collision_judge or LLMCollisionJudge()
        self.reranker = reranker or Reranker()
        self.summary_generator = summary_generator or SummaryGenerator()
        self.deduplicator = deduplicator or Deduplicator(similarity_threshold=similarity_threshold)
        self.use_v2_features = use_v2_features

    def search_with_trust(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> TrustedSearchResult:
        rewrite_result = None
        if self.use_v2_features and self.query_rewriter:
            rewrite_result = self.query_rewriter.rewrite_sync(query)
            search_queries = rewrite_result.rewritten_queries
        else:
            search_queries = [query]

        all_results = []
        for search_query in search_queries:
            response = self.provider.search(search_query, options)
            all_results.extend(response.results)

        results = self.deduplicator.deduplicate(all_results)

        classified = self.source_classifier.classify_results(results)

        for result in results:
            if result.source_type is None:
                result.source_type = self.source_classifier.infer_source_type(result)
            if result.source_level is None:
                result.source_level = self.source_classifier.infer_source_level(result)

        llm_classified_results = []
        if self.use_v2_features and self.llm_classifier:
            intent = rewrite_result.intent if rewrite_result else "factual"
            llm_classified_results = self._sync_classify_with_llm(
                results, query, intent
            )

        reranked_results = results
        print(f"[DEBUG ORCHESTRATOR] Starting rerank section")
        print(f"[DEBUG ORCH] use_v2_features={self.use_v2_features}")
        print(f"[DEBUG ORCH] reranker exists={self.reranker is not None}")
        print(f"[DEBUG ORCH] llm_classified_results len={len(llm_classified_results)}")
        print(f"[DEBUG ORCH] llm_classified_results is truthy={bool(llm_classified_results)}")
        print(f"[DEBUG ORCH] _sync_classify_with_llm result type={type(llm_classified_results)}")
        if self.use_v2_features and self.reranker and llm_classified_results:
            print(f"[DEBUG ORCH] ENTERED rerank block")
            classified_objs = []
            for i, result in enumerate(results):
                if i < len(llm_classified_results):
                    classified_objs.append(llm_classified_results[i])
                else:
                    classified_objs.append(self._create_default_classified_result(result))

            top_k = self.reranker.config.top_k
            print(f"[DEBUG] Calling reranker with {len(classified_objs)} objects, top_k={top_k}")
            reranked_results = self.reranker.rerank(
                classified_objs, None, top_k,
                original_query=query, search_query=search_queries[0] if search_queries else query
            )
            print(f"[DEBUG] Reranked results: {len(reranked_results)}")

        collisions = []
        judgments = []
        if self.fact_resolver and reranked_results:
            top_k = self.reranker.config.top_k if self.reranker else 10
            reranked_originals = [
                r.result if hasattr(r, 'result') else r for r in reranked_results[:top_k]
            ]
            collisions = self.fact_resolver.detect_and_resolve(reranked_originals)

            if self.use_v2_features and self.collision_judge and collisions:
                judgments = self._sync_judge_collisions(collisions, query)

        reranked_originals_for_summary = [
            r.result if hasattr(r, 'result') else r for r in reranked_results
        ]
        summary, consensus_facts, disputed_facts = self.summary_generator.generate(
            reranked_originals_for_summary, collisions
        )

        v2_metadata = V2Metadata(
            version="v2",
            rewrite_result=rewrite_result,
            rerank_weights=self.reranker.config.weights if self.reranker else {},
            collision_judgments=judgments
        )

        return TrustedSearchResult(
            query=query,
            response=SearchResponse(
                query=query,
                results=reranked_originals_for_summary,
                total_count=len(reranked_originals_for_summary),
                search_time=0
            ),
            classified_results=classified,
            collisions=collisions,
            clusters=[],
            summary=summary,
            consensus_facts=consensus_facts,
            disputed_facts=disputed_facts,
            metadata={
                "provider": self.provider.name,
                "white_count": len(classified["white"]),
                "gray_count": len(classified["gray"]),
                "black_count": len(classified["black"]),
                "collision_count": len(collisions),
                "v2_metadata": v2_metadata.__dict__
            }
        )

    async def search_with_trust_async(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> TrustedSearchResult:
        rewrite_result = None
        if self.use_v2_features and self.query_rewriter:
            rewrite_result = await self.query_rewriter.rewrite(query)
            search_queries = rewrite_result.rewritten_queries
        else:
            search_queries = [query]

        all_results = []
        for search_query in search_queries:
            response = await self.provider.search_async(search_query, options)
            all_results.extend(response.results)

        results = self.deduplicator.deduplicate(all_results)

        classified = self.source_classifier.classify_results(results)

        for result in results:
            if result.source_type is None:
                result.source_type = self.source_classifier.infer_source_type(result)
            if result.source_level is None:
                result.source_level = self.source_classifier.infer_source_level(result)

        llm_classified_results = []
        if self.use_v2_features and self.llm_classifier:
            intent = rewrite_result.intent if rewrite_result else "factual"
            llm_classified_results = await self.llm_classifier.classify_batch(
                results, query, intent
            )

        reranked_results = results
        if self.use_v2_features and self.reranker and llm_classified_results:
            classified_objs = []
            for i, result in enumerate(results):
                if i < len(llm_classified_results):
                    classified_objs.append(llm_classified_results[i])
                else:
                    classified_objs.append(self._create_default_classified_result(result))

            top_k = self.reranker.config.top_k
            reranked_results = await self.reranker.rerank_async(
                classified_objs, query, judgments=None, top_k=top_k,
                original_query=query, search_query=search_queries[0] if search_queries else query
            )

        collisions = []
        judgments = []
        if self.fact_resolver and reranked_results:
            top_k = self.reranker.config.top_k if self.reranker else 10
            reranked_originals = [
                r.result if hasattr(r, 'result') else r for r in reranked_results[:top_k]
            ]
            collisions = self.fact_resolver.detect_and_resolve(reranked_originals)

            if self.use_v2_features and self.collision_judge and collisions:
                judgments = await self.collision_judge.judge_batch(collisions, query)

        reranked_originals_for_summary = [
            r.result if hasattr(r, 'result') else r for r in reranked_results
        ]
        summary, consensus_facts, disputed_facts = self.summary_generator.generate(
            reranked_originals_for_summary, collisions
        )

        v2_metadata = V2Metadata(
            version="v2",
            rewrite_result=rewrite_result,
            rerank_weights=self.reranker.config.weights if self.reranker else {},
            collision_judgments=judgments
        )

        return TrustedSearchResult(
            query=query,
            response=SearchResponse(
                query=query,
                results=reranked_originals_for_summary,
                total_count=len(reranked_originals_for_summary),
                search_time=0
            ),
            classified_results=classified,
            collisions=collisions,
            clusters=[],
            summary=summary,
            consensus_facts=consensus_facts,
            disputed_facts=disputed_facts,
            metadata={
                "provider": self.provider.name,
                "white_count": len(classified["white"]),
                "gray_count": len(classified["gray"]),
                "black_count": len(classified["black"]),
                "collision_count": len(collisions),
                "v2_metadata": v2_metadata.__dict__
            }
        )

    def _sync_classify_with_llm(
        self,
        results: List[Any],
        query: str,
        intent: str
    ) -> List[ClassifiedResult]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(
                    self.llm_classifier.classify_batch(results, query, intent)
                )
                return future.result()
            else:
                return asyncio.run(
                    self.llm_classifier.classify_batch(results, query, intent)
                )
        except:
            return [self._create_default_classified_result(r) for r in results]

    def _sync_judge_collisions(
        self,
        collisions: List[Any],
        query: str
    ) -> List[CollisionJudgment]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(
                    self.collision_judge.judge_batch(collisions, query)
                )
                return future.result()
            else:
                return asyncio.run(
                    self.collision_judge.judge_batch(collisions, query)
                )
        except:
            return []

    def _create_default_classified_result(self, result: Any) -> ClassifiedResult:
        from ..classifier.llm_classifier import SourceType, Classification

        return ClassifiedResult(
            result=result,
            source_info=None,
            classification=Classification.GRAY,
            relevance_score=5.0
        )

    def white_list_search(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> SearchResponse:
        options = options or SearchOptions()
        options.classification = Classification.WHITE

        result = self.search_with_trust(query, options)
        return SearchResponse(
            query=query,
            results=result.classified_results["white"],
            total_count=len(result.classified_results["white"]),
            search_time=result.response.search_time
        )
