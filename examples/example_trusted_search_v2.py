import asyncio
import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from web_search.core.orchestrator_v2 import SearchOrchestratorV2
from web_search.providers.searxng import SearXNGProvider
from web_search.classifier.source_classifier import SourceClassifier
from web_search.classifier.llm_classifier import LLMSourceClassifier
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge
from web_search.reranker.reranker import Reranker, RerankConfig
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.core.llm_client import create_llm_client
from web_search.core.embedding_client import create_embedding_client
from web_search.core.reranker_client import create_reranker_client
from web_search.config.settings import load_config

DEBUG = True
DEBUG_LEVEL = "verbose"
DEBUG_OUTPUT = "stdout"

def main():
    config = load_config("configs")

    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    reranker_config = config.get("reranker", {})
    rewriter_config = config.get("rewriter", {})

    llm_client = create_llm_client(llm_config)
    embedding_client = create_embedding_client(embedding_config)
    reranker_client = create_reranker_client(reranker_config.get("external_reranker", {}))

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
    )

    source_classifier = SourceClassifier(
        whitelist=config.get("whitelist", []),
        blacklist=config.get("blacklist", [])
    )

    reranker_weights = reranker_config.get("weights", {
        "relevance": 0.3,
        "trustworthiness": 0.2,
        "freshness": 0.1,
        "authority": 0.1,
        "external": 0.3
    })
    reranker_freshness = reranker_config.get("freshness", {})
    reranker_top_k = reranker_config.get("top_k", 10)

    priority_rules = config.get("priority_rules", {})
    relevance_filter = priority_rules.get("relevance_filter", {})
    min_relevance_score = relevance_filter.get("min_score", 3.0)

    orchestrator = SearchOrchestratorV2(
        provider=provider,
        source_classifier=source_classifier,
        llm_classifier=LLMSourceClassifier(
            llm_client=llm_client,
            min_relevance_score=min_relevance_score
        ),
        query_rewriter=QueryRewriter(llm_client=llm_client),
        embedding_engine=EmbeddingSimilarityEngine(embedding_client=embedding_client),
        collision_judge=LLMCollisionJudge(llm_client=llm_client),
        reranker=Reranker(
            config=RerankConfig(
                weights=reranker_weights,
                external_rerank_weight=reranker_weights.get("external", 0.3),
                top_k=reranker_top_k
            ),
            freshness_config=reranker_freshness,
            reranker_client=reranker_client
        ),
        use_v2_features=True
    )

    result = orchestrator.search_with_trust(
        "某科技公司竞品的最新动态",
        debug=DEBUG,
        debug_level=DEBUG_LEVEL,
        debug_output=DEBUG_OUTPUT
    )

    print("=" * 60)
    print(f"查询: {result.query}")
    print("=" * 60)

    rewrite_result = result.metadata.get("v2_metadata", {}).get("rewrite_result")
    if rewrite_result:
        print(f"\n【改写查询】")
        print(f"  意图: {rewrite_result.intent}")
        print(f"  实体: {', '.join(rewrite_result.entities) if rewrite_result.entities else '无'}")
        print(f"  时间范围: {rewrite_result.time_range or '任意'}")
        print(f"\n  多样化查询列表:")
        if hasattr(rewrite_result, 'structured_queries') and rewrite_result.structured_queries:
            for sq in rewrite_result.structured_queries:
                type_labels = {
                    "core": "核心",
                    "exact_match": "精确匹配",
                    "synonym": "同义改写",
                    "specific": "细化主题",
                    "related": "相关扩展",
                    "source_limited": "源限定",
                    "time_limited": "时间限定",
                    "technical": "技术突破"
                }
                label = type_labels.get(sq.query_type, sq.query_type)
                print(f"    [{label}] {sq.query}")
        else:
            for q in rewrite_result.rewritten_queries:
                print(f"    - {q}")

    print(f"\n【信源分层统计】")
    print(f"  白名单 (高可信): {len(result.classified_results['white'])} 条")
    print(f"  灰名单 (中等可信): {len(result.classified_results['gray'])} 条")
    print(f"  黑名单 (不可信): {len(result.classified_results['black'])} 条")

    print(f"\n【碰撞检测】")
    print(f"  检测到碰撞: {len(result.collisions)} 个")

    v2_metadata = result.metadata.get("v2_metadata", {})
    judgments = v2_metadata.get("collision_judgments", [])
    if judgments:
        print(f"\n【碰撞裁决】")
        for judgment in judgments[:3]:
            print(f"  碰撞 {judgment.collision_id}:")
            print(f"    共识度: {judgment.consensus_level}")
            print(f"    置信度: {judgment.confidence:.1%}")
            print(f"    裁决方: {judgment.winner}")

    print(f"\n【摘要】")
    try:
        print(result.summary)
    except UnicodeEncodeError:
        print(result.summary.encode('utf-8', errors='replace').decode('utf-8'))

    if result.consensus_facts:
        print(f"\n【共识事实】")
        for fact in result.consensus_facts[:3]:
            try:
                print(f"  [+] {fact}")
            except UnicodeEncodeError:
                print(f"  [+] {fact.encode('utf-8', errors='replace').decode('utf-8')}")

    if result.disputed_facts:
        print(f"\n【争议事实】")
        for fact in result.disputed_facts[:3]:
            try:
                print(f"  [!] {fact}")
            except UnicodeEncodeError:
                print(f"  [!] {fact.encode('utf-8', errors='replace').decode('utf-8')}")

    print(f"\n【Reranker 配置】")
    print(f"  权重: {reranker_weights}")
    print(f"  时效性配置: {reranker_freshness}")
    print(f"  外部 Reranker: {reranker_client.provider_name}")
    print(f"  Top-K: {reranker_top_k}")

    print(f"\n【搜索结果列表】")
    for i, r in enumerate(result.response.results, 1):
        classification_label = "未知"
        if hasattr(r, 'classification'):
            classification_label = {
                "white": "高可信",
                "gray": "中可信",
                "black": "低可信"
            }.get(r.classification.value if hasattr(r.classification, 'value') else str(r.classification), "未知")
        elif hasattr(r, 'source_info') and hasattr(r.source_info, 'source_type'):
            classification_label = "中可信"

        score = getattr(r, 'final_score', None) or getattr(r, 'relevance_score', None) or getattr(r, 'external_rerank_score', None) or 0.0
        print(f"  {i}. [{classification_label}] {r.title}")
        print(f"     Score: {score:.4f}")
        print(f"     Content: {r.snippet[:100]}..." if len(r.snippet) > 100 else f"     Content: {r.snippet}")
        print(f"     Source: {r.url}")

    print(f"\n【搜索耗时】")
    print(f"  {result.response.search_time:.2f} 秒")

    print(f"\n【总处理耗时】")
    print(f"  {result.total_duration_ms:.2f} 毫秒")

    if result.debug_info:
        print("\n" + "=" * 60)
        print("【全链路调试信息】")
        print("=" * 60)
        for stage_name, stage_data in result.debug_info.items():
            duration = stage_data.get("duration_ms", 0)
            print(f"\n--- {stage_name} ({duration:.2f}ms) ---")
            try:
                print(json.dumps(stage_data, indent=2, ensure_ascii=False, default=str))
            except UnicodeEncodeError:
                print(json.dumps(stage_data, indent=2, ensure_ascii=False, default=str).encode('utf-8', errors='replace').decode('utf-8'))

if __name__ == "__main__":
    main()
