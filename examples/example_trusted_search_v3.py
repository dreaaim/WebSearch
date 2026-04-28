import sys
import io
import json
import logging
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr
)

for logger_name in ['trafilatura', 'htmldate', 'justext', 'readability_lxml', 'PIL', 'Playwright']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

from web_search.core.orchestrator import SearchOrchestratorV3, TrustedSearchResultV3
from web_search.providers.searxng import SearXNGProvider
from web_search.filter.hybrid_filter_engine import HybridFilterEngine
from web_search.fetcher.content_fetcher import ContentFetcher
from web_search.reranker.multi_factor_reranker import MultiFactorReranker
from web_search.extractor.fact_extractor import FactExtractor
from web_search.cluster.fact_bucket_cluster import FactBucketCluster
from web_search.collision.orthogonal_detector import OrthogonalCollisionDetector
from web_search.trust.trust_rank_ladder import TrustRankLadder
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.core.llm_client import create_llm_client
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


def main():
    sys.stderr.write("[启动] example_trusted_search_v3.py 开始运行\n")
    sys.stderr.flush()
    log_status("初始化", "开始初始化各组件...")

    config = load_config("configs")

    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    reranker_config = config.get("reranker", {})

    llm_client = create_llm_client(llm_config)
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

    log_status("初始化", "所有 Provider 和 Engine 初始化完成")

    log_status("初始化", "创建 SearchOrchestratorV3...")
    orchestrator = SearchOrchestratorV3(
        provider=provider,
        query_rewriter=QueryRewriter(llm_client=llm_client),
        hybrid_filter_engine=hybrid_filter_engine,
        content_fetcher=content_fetcher,
        multi_factor_reranker=multi_factor_reranker,
        fact_extractor=fact_extractor,
        fact_bucket_cluster=fact_bucket_cluster,
        orthogonal_detector=orthogonal_detector,
        trust_rank_ladder=trust_rank_ladder
    )

    log_status("执行", "开始执行 search_with_trust_v3 搜索...")
    result = orchestrator.search_with_trust_v3(
        "某科技公司竞品的最新动态"
    )

    log_status("完成", "search_with_trust_v3 执行完成，开始输出结果")

    print_v3_result(result)

    stats = orchestrator.get_v3_stats(result)
    print("\n" + "=" * 60)
    print("【V3 统计数据】")
    print("=" * 60)
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

    if result.metadata.get("buckets_needing_review", 0) > 0:
        print(f"\n【提示】有 {result.metadata['buckets_needing_review']} 个事实桶需要 LLM 审核碰撞")


if __name__ == "__main__":
    main()
