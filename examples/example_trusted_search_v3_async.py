import sys
import io
import json
import logging
import asyncio
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


def log_status(step, message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    status_line = f"[{'='*20} {timestamp} {'='*20}]\n[{step}] {message}\n{'='*60}\n"
    sys.stderr.write(status_line)
    sys.stderr.flush()


def print_trusted_facts(trusted_facts):
    print("\n【可信事实清单 (Trusted Facts)】")
    print(f"  共 {len(trusted_facts)} 条可信事实")
    for i, fact in enumerate(trusted_facts, 1):
        print(f"\n  [{i}] {fact.statement}")
        print(f"      信任等级: {fact.confidence:.2f}")
        print(f"      证据数量: {len(fact.evidence_sources)}")
        if fact.evidence_sources:
            top_source = fact.evidence_sources[0]
            print(f"      主要来源: {top_source}")


def print_all_facts(all_facts):
    print("\n【所有提取的事实 (All Facts)】")
    print(f"  共 {len(all_facts)} 条事实")
    for i, fact in enumerate(all_facts[:5], 1):
        print(f"\n  [{i}] {fact.statement}")
        print(f"      类型: {fact.spo_triple.predicate if fact.spo_triple else 'N/A'}")
        print(f"      来源: {getattr(fact, 'source_domain', 'N/A')}")
        print(f"      信任分: {fact.confidence_score:.2f}")


def print_buckets(buckets):
    print("\n【事实桶列表 (Fact Buckets)】")
    print(f"  共 {len(buckets)} 个桶")
    for i, bucket in enumerate(buckets[:5], 1):
        print(f"\n  桶 [{i}]: {bucket.bucket_id}")
        print(f"      事实数量: {len(bucket.facts)}")


def print_collisions(collisions):
    print("\n【碰撞结果 (Collisions)】")
    print(f"  共检测到 {len(collisions)} 个碰撞")
    for i, collision in enumerate(collisions[:5], 1):
        print(f"\n  碰撞 [{i}]:")
        print(f"      碰撞系数: {collision.collision_coefficient:.2f}")
        print(f"      需 LLM 审核: {'是' if collision.needs_llm_review else '否'}")
        if collision.supporting_facts:
            print(f"      支持方: {len(collision.supporting_facts)} 条")
        if collision.conflicting_facts:
            print(f"      反对方: {len(collision.conflicting_facts)} 条")


def print_v3_result(result: TrustedSearchResultV3):
    print("=" * 60)
    print(f"查询: {result.query}")
    print("=" * 60)

    metadata = result.metadata
    print(f"\n【处理统计】")
    print(f"  搜索结果总数: {metadata.get('total_search_results', 0)}")
    print(f"  去重后结果: {metadata.get('unique_results', 0)}")
    print(f"  过滤后结果: {metadata.get('filtered_results', 0)}")
    print(f"  成功抓取: {metadata.get('successful_fetches', 0)}")
    print(f"  重排后结果: {metadata.get('reranked_results', 0)}")
    print(f"  提取事实数: {metadata.get('total_facts_extracted', 0)}")
    print(f"  事实桶数: {metadata.get('total_buckets', 0)}")
    print(f"  碰撞检测数: {metadata.get('total_collisions', 0)}")
    print(f"  可信事实数: {metadata.get('trusted_facts_count', 0)}")
    print(f"  需审核桶数: {metadata.get('buckets_needing_review', 0)}")
    print(f"  平均碰撞系数: {metadata.get('avg_collision_coefficient', 0.0):.4f}")
    print(f"  处理耗时: {metadata.get('duration_ms', 0):.2f} ms")

    print_trusted_facts(result.trusted_facts)

    print_all_facts(result.all_facts)

    print_buckets(result.buckets)

    print_collisions(result.collisions)

    rewrite_result = metadata.get("rewrite_result")
    if rewrite_result:
        print("\n【查询改写】")
        print(f"  意图: {rewrite_result.get('intent', 'N/A')}")
        print(f"  实体: {', '.join(rewrite_result.get('entities', []) or ['无'])}")
        rewritten = rewrite_result.get('rewritten_queries', [])
        if rewritten:
            print(f"  改写查询数: {len(rewritten)}")
            for q in rewritten[:3]:
                print(f"    - {q}")


class AsyncSearchOrchestratorV3(SearchOrchestratorV3):
    def __init__(self, *args, max_concurrency: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_concurrency = max_concurrency
        self._executor = ThreadPoolExecutor(max_workers=max_concurrency * 2)

    async def search_with_trust_v3_async(
        self,
        query: str,
        options=None
    ) -> TrustedSearchResultV3:
        start_time = datetime.now()
        log_status("异步执行", "开始完全异步并发搜索流程")

        log_status("Step 1/12", "查询改写 (异步)")
        rewrite_result = await self._rewrite_async(query)
        structured_queries = rewrite_result.structured_queries
        log_status("Step 1/12 完成", f"改写查询数: {len(structured_queries)}")

        log_status("Step 2/12", "并发搜索 (asyncio.gather)")
        query_result_map = await self._concurrent_search(structured_queries, options)

        all_results = []
        for results in query_result_map.values():
            all_results.extend(results)
        log_status("Step 2/12 完成", f"搜索结果总数: {len(all_results)}")

        if not all_results:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        unique_results = self._deduplicate_results(all_results)
        log_status("Step 3/12 完成", f"去重后结果: {len(unique_results)}")

        log_status("Step 4/12", "并发过滤 (asyncio.gather)")
        filtered_per_query = await self._concurrent_filter(unique_results, query_result_map)
        log_status("Step 4/12 完成", f"过滤后结果: {len(filtered_per_query)}")

        if not filtered_per_query:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        log_status("Step 5/12", "并发内容抓取 (Semaphore(3))")
        fetch_results = await self._concurrent_fetch(filtered_per_query)
        log_status("Step 5/12 完成", f"成功抓取: {len(fetch_results)}")

        successful_fetches = [fr for fr in fetch_results if fr.fetch_success]
        if not successful_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        log_status("Step 6/12 完成", "重排序 (同步阻塞点)")
        reranked_fetches = self.multi_factor_reranker.rerank(successful_fetches, query)

        log_status("Step 7/12", "LLM精炼 (并发 Semaphore(3))")
        refine_results = await self._concurrent_refine(reranked_fetches, query)
        refined_fetches = self.llm_refiner.get_passed_results_with_content(reranked_fetches, refine_results)
        log_status("Step 7/12 完成", f"精炼通过: {len(refined_fetches)}")

        if not refined_fetches:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        log_status("Step 8/12", "并发事实提取 (Semaphore(3), 同步阻塞点)")
        all_extracted_facts = await self._concurrent_fact_extraction(refined_fetches, query)
        log_status("Step 8/12 完成", f"提取事实数: {len(all_extracted_facts)}")

        if not all_extracted_facts:
            return self._build_empty_result_v3(query, start_time, rewrite_result)

        log_status("Step 9/12", "事实桶聚类 (异步)")
        buckets = await self.fact_bucket_cluster.cluster(all_extracted_facts)
        log_status("Step 9/12 完成", f"桶数: {len(buckets)}")

        log_status("Step 10/12", "并发碰撞检测 (Semaphore(3), 同步阻塞点)")
        collisions = await self._concurrent_collision_detection(buckets)
        log_status("Step 10/12 完成", f"碰撞数: {len(collisions)}")

        log_status("Step 11/12", "生成可信事实清单 (同步阻塞点后)")
        trusted_facts = self.orthogonal_detector.get_trusted_facts(buckets)
        self._update_trust_scores_on_verification(trusted_facts, collisions)
        log_status("Step 11/12 完成", f"可信事实数: {len(trusted_facts)}")

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        log_status("Step 12/12 完成", f"总耗时: {duration_ms:.2f}ms")

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

    async def _rewrite_async(self, query: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.query_rewriter.rewrite_sync,
            query
        )

    async def _concurrent_search(self, structured_queries: list, options):
        log_status("并发搜索", f"使用 asyncio.gather 并发执行 {len(structured_queries)} 个搜索查询")

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

        all_results = []
        for response in results:
            all_results.extend(response.results)

        log_status("并发搜索完成", f"合并后总结果数: {len(all_results)}")
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
        log_status("并发抓取", f"使用 Semaphore({fetch_concurrency}) 控制并发")

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
                log_status("抓取异常", f"结果 {i}: {result}")
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
        log_status("并发事实提取", f"使用 Semaphore({self._max_concurrency}) 控制并发，提取目标: {len(refined_fetches)} 个")

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
                log_status("事实提取异常", f"结果 {i}: {result}")
            else:
                all_extracted_facts.extend(result)

        return all_extracted_facts

    async def _concurrent_collision_detection(self, buckets: list):
        log_status("并发碰撞检测", f"使用 Semaphore({self._max_concurrency}) 控制并发，检测目标: {len(buckets)} 个桶")

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
                log_status("碰撞检测异常", f"桶 {i}: {result}")
            else:
                valid_collisions.append(result)

        return valid_collisions

    def get_v3_stats(self, result: TrustedSearchResultV3) -> dict:
        return {
            "query": result.query,
            "version": result.metadata.get("version", "v3_async"),
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


async def main():
    sys.stderr.write("[启动] example_trusted_search_v3_async.py 开始运行\n")
    sys.stderr.flush()
    log_status("初始化", "开始初始化各组件...")

    config = load_config("configs")

    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    reranker_config = config.get("reranker", {})

    llm_client, thinking_llm_client = create_llm_clients(llm_config)
    embedding_client = create_embedding_client(embedding_config)
    reranker_client = create_reranker_client(reranker_config)

    log_status("初始化", "LLM/Embedding/Reranker 客户端创建完成")

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
    )

    hybrid_filter_engine = HybridFilterEngine()
    content_fetcher = ContentFetcher()
    trust_rank_ladder = TrustRankLadder()
    multi_factor_reranker = MultiFactorReranker(reranker_client=reranker_client)
    fact_extractor = FactExtractor(llm_client=llm_client)
    fact_bucket_cluster = FactBucketCluster(embedding_client=embedding_client)
    orthogonal_detector = OrthogonalCollisionDetector(llm_client=llm_client)
    query_rewriter = QueryRewriter(llm_client=thinking_llm_client or llm_client)

    log_status("初始化", "所有 Provider 和 Engine 初始化完成")

    log_status("初始化", "创建 AsyncSearchOrchestratorV3 (max_concurrency=3)...")
    orchestrator = AsyncSearchOrchestratorV3(
        provider=provider,
        query_rewriter=query_rewriter,
        hybrid_filter_engine=hybrid_filter_engine,
        content_fetcher=content_fetcher,
        multi_factor_reranker=multi_factor_reranker,
        fact_extractor=fact_extractor,
        fact_bucket_cluster=fact_bucket_cluster,
        orthogonal_detector=orthogonal_detector,
        trust_rank_ladder=trust_rank_ladder,
        max_concurrency=3
    )

    log_status("执行", "开始执行 search_with_trust_v3_async 搜索...")
    result = await orchestrator.search_with_trust_v3_async(
        "某科技公司竞品的最新动态"
    )

    log_status("完成", "search_with_trust_v3_async 执行完成，开始输出结果")

    print_v3_result(result)

    stats = orchestrator.get_v3_stats(result)
    print("\n" + "=" * 60)
    print("【V3 异步并发统计数据】")
    print("=" * 60)
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

    if result.metadata.get("buckets_needing_review", 0) > 0:
        print(f"\n【提示】有 {result.metadata['buckets_needing_review']} 个事实桶需要 LLM 审核碰撞")

    orchestrator._executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
