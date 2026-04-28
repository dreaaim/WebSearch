from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import re

from .models import SearchOptions, SearchResponse, SearchResult
from ..providers.base import SearchProvider
from ..rewriter.query_rewriter import QueryRewriter, QueryRewriteResult
from ..filter.hybrid_filter_engine import HybridFilterEngine, HybridFilterResult
from ..filter.llm_refiner import LLMRefiner, RefineResult
from ..fetcher.content_fetcher import ContentFetcher, ContentFetchResult
from ..reranker.multi_factor_reranker import MultiFactorReranker
from ..extractor.fact_extractor import FactExtractor, ExtractedFact
from ..cluster.fact_bucket_cluster import FactBucketCluster, FactBucket
from ..collision.orthogonal_detector import OrthogonalCollisionDetector, CollisionResult, TrustedFact
from ..trust.trust_rank_ladder import TrustRankLadder, TrustRankScore
from ..core.llm_client import LLMClientBase

logger = logging.getLogger(__name__)


SEARCH_SYNTAX_PATTERN = re.compile(
    r'\b(site:|after:|before:|exact:|exclude:|-)'  # search operators
    r'|\s+"([^"]+)"\s*'  # double quotes
    r'|\s+\'([^\']+)\'\s*'  # single quotes
    r'|\bfiletype:\w+'  # filetype
    r'|\bintitle:|\bintext:|\binurl:'  # advanced
    r'|\bOR\b|\bAND\b'  # boolean
    , re.IGNORECASE | re.UNICODE
)


def clean_search_query(query: str) -> str:
    """
    Remove advanced search syntax from query for similarity matching.
    Removes: site:, after:, before:, exact quotes, exclude (-), filetype:, intitle:, boolean operators
    """
    cleaned = SEARCH_SYNTAX_PATTERN.sub(' ', query)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    return cleaned


@dataclass
class TrustedSearchResultV3:
    query: str
    trusted_facts: List[TrustedFact]
    all_facts: List[ExtractedFact]
    buckets: List[FactBucket]
    collisions: List[CollisionResult]
    metadata: dict


class SearchOrchestratorV3:
    def __init__(
        self,
        provider: SearchProvider,
        query_rewriter: Optional[QueryRewriter] = None,
        hybrid_filter_engine: Optional[HybridFilterEngine] = None,
        content_fetcher: Optional[ContentFetcher] = None,
        multi_factor_reranker: Optional[MultiFactorReranker] = None,
        fact_extractor: Optional[FactExtractor] = None,
        fact_bucket_cluster: Optional[FactBucketCluster] = None,
        orthogonal_detector: Optional[OrthogonalCollisionDetector] = None,
        trust_rank_ladder: Optional[TrustRankLadder] = None,
        llm_refiner: Optional[LLMRefiner] = None,
        llm_client: Optional[LLMClientBase] = None
    ):
        self.provider = provider
        self.query_rewriter = query_rewriter or QueryRewriter()
        self.hybrid_filter_engine = hybrid_filter_engine or HybridFilterEngine()
        self.content_fetcher = content_fetcher or ContentFetcher()
        if multi_factor_reranker is not None:
            self.multi_factor_reranker = multi_factor_reranker
        else:
            self.multi_factor_reranker = MultiFactorReranker(reranker_client=None)
        if llm_refiner is not None:
            self.llm_refiner = llm_refiner
        else:
            self.llm_refiner = LLMRefiner(llm_client=llm_client)
        if fact_extractor is not None:
            self.fact_extractor = fact_extractor
        else:
            self.fact_extractor = FactExtractor(llm_client=llm_client)
        self.fact_bucket_cluster = fact_bucket_cluster or FactBucketCluster()
        self.orthogonal_detector = orthogonal_detector or OrthogonalCollisionDetector()
        self.trust_rank_ladder = trust_rank_ladder or TrustRankLadder()
        self._llm_client = llm_client

    async def search_with_trust_v3_async(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> TrustedSearchResultV3:
        start_time = datetime.now()

        rewrite_result = await self.query_rewriter.rewrite(query)
        search_queries = rewrite_result.rewritten_queries

        all_results: List[SearchResult] = []
        query_result_map: Dict[str, List[SearchResult]] = {}
        for search_query in search_queries:
            response = await self.provider.search_async(search_query, options)
            query_result_map[search_query] = response.results
            all_results.extend(response.results)

        if not all_results:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        unique_results = self._deduplicate_results(all_results)

        filtered_per_query: List[SearchResult] = []
        for search_query, results in query_result_map.items():
            if not results:
                continue
            deduped = self._deduplicate_results(results)
            cleaned_query = clean_search_query(search_query)
            filtered = await self.hybrid_filter_engine.filter(deduped, cleaned_query)
            filtered_per_query.extend([hf.result for hf in filtered if hf.hybrid_score > 0])

        if not filtered_per_query:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        fetch_results = self.content_fetcher.fetch(filtered_per_query)

        successful_fetches = [fr for fr in fetch_results if fr.fetch_success]

        if not successful_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        reranked_fetches = self.multi_factor_reranker.rerank(successful_fetches, query)

        refine_results = await self.llm_refiner.refine_async(reranked_fetches, query)
        refined_fetches = self.llm_refiner.get_passed_results_with_content(reranked_fetches, refine_results)

        if not refined_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        all_extracted_facts: List[ExtractedFact] = []
        for fetch_result, refine_result in refined_fetches:
            facts = await self.fact_extractor.extract_async(
                fetch_result.content,
                fetch_result.result.source_domain,
                query
            )
            for fact in facts:
                fact.source_domain = fetch_result.result.source_domain
                fact.source_name = fetch_result.result.source_name
                trust_score = self._get_trust_score_for_source(fetch_result.result)
                fact.trust_score = trust_score
            all_extracted_facts.extend(facts)

        if not all_extracted_facts:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        buckets = await self.fact_bucket_cluster.cluster(all_extracted_facts)

        collisions = self.orthogonal_detector.detect_batch(buckets)

        trusted_facts = self.orthogonal_detector.get_trusted_facts(buckets)

        self._update_trust_scores_on_verification(trusted_facts, collisions)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        metadata = {
            "version": "v3",
            "provider": self.provider.name,
            "rewrite_result": rewrite_result.to_dict() if rewrite_result else None,
            "total_search_results": len(all_results),
            "unique_results": len(unique_results),
            "filtered_results": len(filtered_per_query),
            "successful_fetches": len(successful_fetches),
            "reranked_results": len(reranked_fetches),
            "refined_results": len(refined_fetches),
            "total_facts_extracted": len(all_extracted_facts),
            "total_buckets": len(buckets),
            "total_collisions": len(collisions),
            "trusted_facts_count": len(trusted_facts),
            "buckets_needing_review": sum(1 for c in collisions if c.needs_llm_review),
            "avg_collision_coefficient": self._calc_avg_collision_coefficient(collisions),
            "duration_ms": duration_ms
        }

        return TrustedSearchResultV3(
            query=query,
            trusted_facts=trusted_facts,
            all_facts=all_extracted_facts,
            buckets=buckets,
            collisions=collisions,
            metadata=metadata
        )

    def search_with_trust_v3(
        self,
        query: str,
        options: Optional[SearchOptions] = None
    ) -> TrustedSearchResultV3:
        start_time = datetime.now()
        logger.info("[SEARCH_V3] ========== 开始执行 search_with_trust_v3 ==========")
        logger.info(f"[SEARCH_V3] 查询: {query}")

        logger.info("[SEARCH_V3] Step 1/10: 查询改写...")
        rewrite_result = self.query_rewriter.rewrite_sync(query)
        structured_queries = rewrite_result.structured_queries
        logger.info(f"[SEARCH_V3] 改写后的查询数量: {len(structured_queries)}")

        logger.info("[SEARCH_V3] Step 2/10: 执行搜索...")
        all_results: List[SearchResult] = []
        query_result_map: Dict[str, List[SearchResult]] = {}
        for sq in structured_queries:
            search_options = SearchOptions(
                max_results=options.max_results if options else 10,
                time_range=sq.time_range,
                engines=options.engines if options else None
            )
            response = self.provider.search(sq.query, search_options)
            query_result_map[sq.query] = response.results
            all_results.extend(response.results)
        logger.info(f"[SEARCH_V3] 搜索返回结果总数: {len(all_results)}")

        if not all_results:
            logger.warning("[SEARCH_V3] 搜索无结果，返回空结果")
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        logger.info("[SEARCH_V3] Step 3/10: 去重...")
        unique_results = self._deduplicate_results(all_results)
        logger.info(f"[SEARCH_V3] 去重后结果数: {len(unique_results)}")

        logger.info("[SEARCH_V3] Step 4/10: 过滤...")
        filtered_per_query: List[SearchResult] = []
        for search_query, results in query_result_map.items():
            if not results:
                continue
            deduped = self._deduplicate_results(results)
            cleaned_query = clean_search_query(search_query)
            filtered = self.hybrid_filter_engine.filter_sync(deduped, cleaned_query)
            filtered_per_query.extend([hf.result for hf in filtered if hf.hybrid_score > 0])
        logger.info(f"[SEARCH_V3] 过滤后结果数: {len(filtered_per_query)}")

        if not filtered_per_query:
            logger.warning("[SEARCH_V3] 过滤后无结果，返回空结果")
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        logger.info("[SEARCH_V3] Step 5/10: 内容抓取...")
        fetch_results = self.content_fetcher.fetch(filtered_per_query)
        successful_fetches = [fr for fr in fetch_results if fr.fetch_success]
        logger.info(f"[SEARCH_V3] 成功抓取: {len(successful_fetches)}/{len(filtered_per_query)}")

        if not successful_fetches:
            logger.warning("[SEARCH_V3] 内容抓取失败，返回空结果")
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        logger.info("[SEARCH_V3] Step 6/10: 重排...")
        reranked_fetches = self.multi_factor_reranker.rerank(successful_fetches, query)
        logger.info(f"[SEARCH_V3] 重排后结果数: {len(reranked_fetches)}")

        logger.info("[SEARCH_V3] Step 7/10: LLM 精炼...")
        refine_results = self.llm_refiner.refine(reranked_fetches, query)
        refined_fetches = self.llm_refiner.get_passed_results_with_content(reranked_fetches, refine_results)
        logger.info(f"[SEARCH_V3] 精炼通过结果数: {len(refined_fetches)}")

        if not refined_fetches:
            logger.warning("[SEARCH_V3] LLM 精炼无通过结果，返回空结果")
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        logger.info("[SEARCH_V3] Step 8/10: 事实提取...")
        all_extracted_facts: List[ExtractedFact] = []
        for i, (fetch_result, refine_result) in enumerate(refined_fetches):
            if i % 5 == 0:
                logger.info(f"[SEARCH_V3] 正在提取事实... ({i+1}/{len(refined_fetches)})")
            facts = self.fact_extractor.extract_sync(
                fetch_result.content,
                fetch_result.result.source_domain,
                query
            )
            for fact in facts:
                fact.source_domain = fetch_result.result.source_domain
                fact.source_name = fetch_result.result.source_name
                trust_score = self._get_trust_score_for_source(fetch_result.result)
                fact.trust_score = trust_score
            all_extracted_facts.extend(facts)
        logger.info(f"[SEARCH_V3] 共提取事实数: {len(all_extracted_facts)}")

        if not all_extracted_facts:
            logger.warning("[SEARCH_V3] 未提取到任何事实，返回空结果")
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        logger.info("[SEARCH_V3] Step 9/10: 事实聚类...")
        buckets = self.fact_bucket_cluster.cluster_sync(all_extracted_facts)
        logger.info(f"[SEARCH_V3] 聚类后桶数: {len(buckets)}")

        logger.info("[SEARCH_V3] Step 10/10: 碰撞检测...")
        collisions = self.orthogonal_detector.detect_batch(buckets)
        logger.info(f"[SEARCH_V3] 检测到碰撞数: {len(collisions)}")

        trusted_facts = self.orthogonal_detector.get_trusted_facts(buckets)
        logger.info(f"[SEARCH_V3] 可信事实数: {len(trusted_facts)}")

        self._update_trust_scores_on_verification(trusted_facts, collisions)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"[SEARCH_V3] ========== 执行完成，耗时: {duration_ms:.2f}ms ==========")

        metadata = {
            "version": "v3",
            "provider": self.provider.name,
            "rewrite_result": rewrite_result.to_dict() if rewrite_result else None,
            "total_search_results": len(all_results),
            "unique_results": len(unique_results),
            "filtered_results": len(filtered_per_query),
            "successful_fetches": len(successful_fetches),
            "reranked_results": len(reranked_fetches),
            "refined_results": len(refined_fetches),
            "total_facts_extracted": len(all_extracted_facts),
            "total_buckets": len(buckets),
            "total_collisions": len(collisions),
            "trusted_facts_count": len(trusted_facts),
            "buckets_needing_review": sum(1 for c in collisions if c.needs_llm_review),
            "avg_collision_coefficient": self._calc_avg_collision_coefficient(collisions),
            "duration_ms": duration_ms
        }

        return TrustedSearchResultV3(
            query=query,
            trusted_facts=trusted_facts,
            all_facts=all_extracted_facts,
            buckets=buckets,
            collisions=collisions,
            metadata=metadata
        )

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        seen_urls = set()
        unique_results = []
        two_years_ago = datetime.now().timestamp() - 2 * 365 * 24 * 60 * 60
        for result in results:
            if result.url in seen_urls:
                continue
            if result.published_date:
                try:
                    pub_date = datetime.fromisoformat(result.published_date.replace("Z", "+00:00"))
                    if pub_date.timestamp() < two_years_ago:
                        continue
                except Exception:
                    pass
            seen_urls.add(result.url)
            unique_results.append(result)
        return unique_results

    def _get_trust_score_for_source(self, result: SearchResult) -> float:
        if self.trust_rank_ladder:
            return self.trust_rank_ladder.get_trust_score(result.source_domain)
        return 1000.0

    def _update_trust_scores_on_verification(
        self,
        trusted_facts: List[TrustedFact],
        collisions: List[CollisionResult]
    ) -> None:
        if not self.trust_rank_ladder:
            return

        for collision in collisions:
            if collision.needs_llm_review and collision.llm_review_result:
                for fact in collision.supporting_facts:
                    if fact.source_domain:
                        self.trust_rank_ladder.update_score(
                            fact.source_domain,
                            "verified"
                        )

                for fact in collision.conflicting_facts:
                    if fact.source_domain:
                        self.trust_rank_ladder.update_score(
                            fact.source_domain,
                            "disputed"
                        )

    def _build_empty_result_v3(
        self,
        query: str,
        start_time: datetime,
        rewrite_result: Optional[QueryRewriteResult] = None
    ) -> TrustedSearchResultV3:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        return TrustedSearchResultV3(
            query=query,
            trusted_facts=[],
            all_facts=[],
            buckets=[],
            collisions=[],
            metadata={
                "version": "v3",
                "provider": self.provider.name if self.provider else "unknown",
                "rewrite_result": rewrite_result.to_dict() if rewrite_result else None,
                "total_search_results": 0,
                "unique_results": 0,
                "filtered_results": 0,
                "successful_fetches": 0,
                "reranked_results": 0,
                "refined_results": 0,
                "total_facts_extracted": 0,
                "total_buckets": 0,
                "total_collisions": 0,
                "trusted_facts_count": 0,
                "buckets_needing_review": 0,
                "avg_collision_coefficient": 0.0,
                "duration_ms": duration_ms
            }
        )

    def _calc_avg_collision_coefficient(self, collisions: List[CollisionResult]) -> float:
        if not collisions:
            return 0.0
        return sum(c.collision_coefficient for c in collisions) / len(collisions)

    def get_v3_stats(self, result: TrustedSearchResultV3) -> Dict[str, Any]:
        return {
            "query": result.query,
            "version": result.metadata.get("version", "v3"),
            "total_results": result.metadata.get("total_search_results", 0),
            "filtered_results": result.metadata.get("filtered_results", 0),
            "facts_extracted": result.metadata.get("total_facts_extracted", 0),
            "buckets_created": result.metadata.get("total_buckets", 0),
            "trusted_facts": len(result.trusted_facts),
            "collisions_detected": len(result.collisions),
            "llm_review_needed": result.metadata.get("buckets_needing_review", 0),
            "avg_collision_coefficient": result.metadata.get("avg_collision_coefficient", 0.0),
            "processing_time_ms": result.metadata.get("duration_ms", 0),
            "collision_stats": self.orthogonal_detector.get_collision_stats(result.buckets) if result.buckets else {},
            "fact_extraction_stats": self.fact_extractor.get_extraction_stats(result.all_facts) if result.all_facts else {}
        }
