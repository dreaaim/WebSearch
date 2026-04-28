from web_search.core.orchestrator import SearchOrchestrator
from web_search.providers.searxng import SearXNGProvider
from web_search.classifier.source_classifier import SourceClassifier
from web_search.config.settings import load_config
from web_search.core.models import SearchOptions

def main():
    config = load_config("configs")

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
        default_engines=None
    )

    classifier = SourceClassifier(
        whitelist=config.get("whitelist", []),
        blacklist=config.get("blacklist", [])
    )

    orchestrator = SearchOrchestrator(
        provider=provider,
        source_classifier=classifier
    )

    options = SearchOptions(
        max_results=10,
    )

    result = orchestrator.search_with_trust("AI大模型最新进展", options=options)

    print("=" * 60)
    print(f"查询: {result.query}")
    print("=" * 60)

    print(f"\n【信源分层统计】")
    print(f"  白名单 (高可信): {len(result.classified_results['white'])} 条")
    print(f"  灰名单 (中等可信): {len(result.classified_results['gray'])} 条")
    print(f"  黑名单 (不可信): {len(result.classified_results['black'])} 条")

    print(f"\n【碰撞检测】")
    print(f"  检测到碰撞: {len(result.collisions)} 个")

    print(f"\n【摘要】")
    print(result.summary)

    print(f"\n【搜索耗时】")
    print(f"  {result.response.search_time:.2f} 秒")

if __name__ == "__main__":
    main()
