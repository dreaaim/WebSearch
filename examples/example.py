import asyncio
import sys
import io
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from functools import partial

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr
)

from web_search.core.orchestrator import SearchOrchestratorV3, TrustedSearchResultV3
from web_search.core.models import SearchOptions
from web_search.providers.searxng import SearXNGProvider
from web_search.filter.hybrid_filter_engine import HybridFilterEngine
from web_search.fetcher.content_fetcher import ContentFetcher
from web_search.reranker.multi_factor_reranker import MultiFactorReranker
from web_search.extractor.fact_extractor import FactExtractor
from web_search.cluster.fact_bucket_cluster import FactBucketCluster
from web_search.collision.orthogonal_detector import OrthogonalCollisionDetector
from web_search.trust.trust_rank_ladder import TrustRankLadder
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.core.llm_client import create_llm_clients
from web_search.core.embedding_client import create_embedding_client
from web_search.core.reranker_client import create_reranker_client
from web_search.config.settings import load_config


class AsyncSearchOrchestratorV3(SearchOrchestratorV3):
    def __init__(self, *args, max_concurrency: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_concurrency = max_concurrency
        self._executor = ThreadPoolExecutor(max_workers=max_concurrency * 2)

    async def search_with_trust_v3_async(self, query: str, options=None) -> TrustedSearchResultV3:
        start_time = datetime.now()

        rewrite_result = await self._rewrite_async(query)
        structured_queries = rewrite_result.structured_queries

        query_result_map = await self._concurrent_search(structured_queries, options)

        all_results = []
        for results in query_result_map.values():
            all_results.extend(results)

        if not all_results:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        unique_results = self._deduplicate_results(all_results)
        filtered_per_query = await self._concurrent_filter(unique_results, query_result_map)

        if not filtered_per_query:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        fetch_results = await self._concurrent_fetch(filtered_per_query)
        successful_fetches = [fr for fr in fetch_results if fr.fetch_success]

        if not successful_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        reranked_fetches = self.multi_factor_reranker.rerank(successful_fetches, query)
        refine_results = await self._concurrent_refine(reranked_fetches, query)
        refined_fetches = self.llm_refiner.get_passed_results_with_content(reranked_fetches, refine_results)

        if not refined_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        all_extracted_facts = await self._concurrent_fact_extraction(refined_fetches, query)

        if not all_extracted_facts:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        buckets = await self.fact_bucket_cluster.cluster(all_extracted_facts)
        collisions = await self._concurrent_collision_detection(buckets)
        trusted_facts = self.orthogonal_detector.get_trusted_facts(buckets)
        self._update_trust_scores_on_verification(trusted_facts, collisions)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        metadata = {
            "version": "v3_async",
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

    async def _rewrite_async(self, query: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.query_rewriter.rewrite_sync,
            query
        )

    async def _concurrent_search(self, structured_queries: list, options):
        async def search_in_thread(sq):
            loop = asyncio.get_event_loop()
            search_options = SearchOptions(
                max_results=options.max_results if options else 10,
                time_range=sq.time_range,
                engines=options.engines if options else None
            )
            return await loop.run_in_executor(
                self._executor,
                lambda: self.provider.search(sq.query, search_options)
            )

        results = await asyncio.gather(*[search_in_thread(sq) for sq in structured_queries])

        query_result_map = {}
        for i, sq in enumerate(structured_queries):
            query_result_map[sq.query] = results[i].results

        return query_result_map

    async def _concurrent_filter(self, unique_results: list, query_result_map: dict):
        async def filter_in_thread(search_query, deduped):
            loop = asyncio.get_event_loop()
            cleaned_query = self._clean_search_query(search_query)
            return await loop.run_in_executor(
                self._executor,
                lambda: self.hybrid_filter_engine.filter_sync(deduped, cleaned_query)
            )

        filtered_per_query = []
        tasks = []
        for search_query in query_result_map.keys():
            deduped = query_result_map[search_query]
            if deduped:
                tasks.append(filter_in_thread(search_query, deduped))

        if tasks:
            results_list = await asyncio.gather(*tasks)
            for filtered in results_list:
                filtered_per_query.extend([hf.result for hf in filtered if hf.hybrid_score > 0])

        return filtered_per_query

    def _clean_search_query(self, query: str) -> str:
        import re
        pattern = re.compile(
            r'\b(site:|after:|before:|exact:|exclude:|-)'
            r'|\s+"([^"]+)"\s*'
            r'|\s+\'([^\']+)\'\s*'
            r'|\bfiletype:\w+'
            r'|\bintitle:|\bintext:|\binurl:'
            r'|\bOR\b|\bAND\b'
            , re.IGNORECASE | re.UNICODE
        )
        cleaned = pattern.sub(' ', query)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    async def _concurrent_fetch(self, results: list):
        fetch_concurrency = 10
        semaphore = asyncio.Semaphore(fetch_concurrency)

        async def bounded_fetch(idx, result):
            async with semaphore:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self._executor,
                    self.content_fetcher._fetch_single,
                    result
                )

        tasks = [bounded_fetch(i, r) for i, r in enumerate(results)]
        fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, result in enumerate(fetch_results):
            if isinstance(result, Exception):
                pass
            else:
                valid_results.append(result)

        return valid_results

    async def _concurrent_refine(self, reranked_fetches: list, query: str):
        if not self.llm_refiner or not reranked_fetches:
            return []

        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def bounded_refine_batch(items, base_idx):
            async with semaphore:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    self._executor,
                    lambda: self.llm_refiner.refine(items, query)
                )
                if results:
                    for i, r in enumerate(results):
                        r.result_index = base_idx + i
                return results

        batch_size = 3
        all_refine_results = []

        for i in range(0, len(reranked_fetches), batch_size):
            batch = reranked_fetches[i:i + batch_size]
            results = await bounded_refine_batch(batch, i)
            if results:
                all_refine_results.extend(results)

        return all_refine_results

    async def _concurrent_fact_extraction(self, refined_fetches: list, query: str):
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def bounded_extract(idx, item):
            async with semaphore:
                fetch_result, refine_result = item
                loop = asyncio.get_event_loop()
                facts = await loop.run_in_executor(
                    self._executor,
                    lambda: self.fact_extractor.extract_sync(
                        fetch_result.content,
                        fetch_result.result.source_domain,
                        query
                    )
                )
                for fact in facts:
                    fact.source_domain = fetch_result.result.source_domain
                    fact.source_name = fetch_result.result.source_name
                    fact.trust_score = self._get_trust_score_for_source(fetch_result.result)
                return facts

        tasks = [bounded_extract(i, fr) for i, fr in enumerate(refined_fetches)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_extracted_facts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pass
            else:
                all_extracted_facts.extend(result)

        return all_extracted_facts

    async def _concurrent_collision_detection(self, buckets: list):
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def bounded_detect(idx, bucket):
            async with semaphore:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    self._executor,
                    self.orthogonal_detector.detect,
                    bucket
                )

        tasks = [bounded_detect(i, b) for i, b in enumerate(buckets)]
        collisions = await asyncio.gather(*tasks, return_exceptions=True)

        valid_collisions = []
        for i, result in enumerate(collisions):
            if isinstance(result, Exception):
                pass
            else:
                valid_collisions.append(result)

        return valid_collisions


async def main():
    config = load_config("configs")

    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    reranker_config = config.get("reranker", {})

    llm_client, thinking_llm_client = create_llm_clients(llm_config)
    embedding_client = create_embedding_client(embedding_config)
    reranker_client = create_reranker_client(reranker_config)

    provider = SearXNGProvider(base_url="http://localhost:8080")

    orchestrator = AsyncSearchOrchestratorV3(
        provider=provider,
        query_rewriter=QueryRewriter(llm_client=thinking_llm_client or llm_client),
        hybrid_filter_engine=HybridFilterEngine(),
        content_fetcher=ContentFetcher(),
        multi_factor_reranker=MultiFactorReranker(reranker_client=reranker_client),
        fact_extractor=FactExtractor(llm_client=llm_client),
        fact_bucket_cluster=FactBucketCluster(embedding_client=embedding_client),
        orthogonal_detector=OrthogonalCollisionDetector(llm_client=llm_client),
        trust_rank_ladder=TrustRankLadder(),
        max_concurrency=3
    )

    result = await orchestrator.search_with_trust_v3_async("某科技公司竞品的最新动态")

    print("=" * 60)
    print(f"查询: {result.query}")
    print("=" * 60)
    print(f"可信事实数: {len(result.trusted_facts)}")
    print(f"所有事实数: {len(result.all_facts)}")
    print(f"事实桶数: {len(result.buckets)}")
    print(f"碰撞检测数: {len(result.collisions)}")

    orchestrator._executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())