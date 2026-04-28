import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
from datetime import datetime

from web_search.core.orchestrator import SearchOrchestratorV3, TrustedSearchResultV3
from web_search.core.models import SearchResponse, SearchResult, SearchOptions, SourceType, SourceLevel, Classification
from web_search.rewriter.query_rewriter import QueryRewriter, QueryRewriteResult
from web_search.filter.hybrid_filter_engine import HybridFilterEngine, HybridFilterResult
from web_search.fetcher.content_fetcher import ContentFetcher, ContentFetchResult
from web_search.reranker.multi_factor_reranker import MultiFactorReranker
from web_search.extractor.fact_extractor import FactExtractor
from web_search.collision import ExtractedFact, TrustedFact, CollisionResult, FactBucket
from web_search.cluster.fact_bucket_cluster import FactBucketCluster
from web_search.collision.orthogonal_detector import OrthogonalCollisionDetector
from web_search.trust.trust_rank_ladder import TrustRankLadder


def create_mock_provider(results=None):
    provider = Mock()
    provider.name = "test_provider"
    response = SearchResponse(
        query="test query",
        results=results or [],
        total_count=len(results) if results else 0,
        search_time=0.1
    )
    provider.search.return_value = response
    provider.search_async = AsyncMock(return_value=response)
    return provider


def create_result(domain, title="Test", snippet="Test snippet"):
    return SearchResult(
        title=title,
        url=f"https://{domain}/test",
        snippet=snippet,
        source_name="Test",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL,
        classification=Classification.GRAY
    )


def create_extracted_fact(statement, domain="example.com"):
    return ExtractedFact(
        fact_id=f"fact_{hash(statement)}",
        statement=statement,
        spo_triple=None,
        nli_label="entailment",
        numeric_values=[],
        datetime_values=[],
        confidence_score=0.9,
        confidence_reason="test",
        source_name="Test Source",
        source_domain=domain,
        trust_score=1000.0
    )


def create_trusted_fact(statement, confidence=0.9):
    return TrustedFact(
        fact_id=f"trusted_{hash(statement)}",
        statement=statement,
        confidence=confidence,
        evidence_sources=["example.com"],
        collision_info=None,
        verification_status="verified"
    )


def create_hybrid_filter_result(domain="example.com"):
    return HybridFilterResult(
        result=create_result(domain),
        embedding_score=0.8,
        bm25_score=0.8,
        hybrid_score=0.8
    )


def create_mock_orchestrator(mock_provider):
    query_rewriter = Mock(spec=QueryRewriter)
    query_rewriter.rewrite_sync = Mock(return_value=QueryRewriteResult(
        original_query="test",
        rewritten_queries=["test"],
        intent="test intent",
        entities=[]
    ))
    query_rewriter.rewrite = AsyncMock(return_value=QueryRewriteResult(
        original_query="test",
        rewritten_queries=["test"],
        intent="test intent",
        entities=[]
    ))

    hybrid_filter_engine = Mock(spec=HybridFilterEngine)
    hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])
    hybrid_filter_engine.filter = AsyncMock(return_value=[create_hybrid_filter_result()])

    content_fetcher = Mock(spec=ContentFetcher)
    mock_fetch_result = ContentFetchResult(
        result=create_result("example.com"),
        content="Beijing is China's capital",
        fetch_success=True
    )
    content_fetcher.fetch = Mock(return_value=[mock_fetch_result])

    multi_factor_reranker = Mock(spec=MultiFactorReranker)
    multi_factor_reranker.rerank = Mock(return_value=[mock_fetch_result])

    fact_extractor = Mock(spec=FactExtractor)
    fact_extractor.extract_sync = Mock(return_value=[
        create_extracted_fact("Beijing is China's capital")
    ])
    fact_extractor.extract_async = AsyncMock(return_value=[
        create_extracted_fact("Beijing is China's capital")
    ])

    fact_bucket_cluster = Mock(spec=FactBucketCluster)
    mock_bucket = FactBucket(
        bucket_id="bucket_1",
        facts=[create_extracted_fact("Beijing is China's capital")],
        cluster_embedding=[0.1, 0.2, 0.3]
    )
    fact_bucket_cluster.cluster_sync = Mock(return_value=[mock_bucket])
    fact_bucket_cluster.cluster = AsyncMock(return_value=[mock_bucket])

    orthogonal_detector = Mock(spec=OrthogonalCollisionDetector)
    orthogonal_detector.detect_batch = Mock(return_value=[])
    orthogonal_detector.get_trusted_facts = Mock(return_value=[
        create_trusted_fact("Beijing is China's capital")
    ])

    trust_rank_ladder = Mock(spec=TrustRankLadder)

    orchestrator = SearchOrchestratorV3(
        provider=mock_provider,
        query_rewriter=query_rewriter,
        hybrid_filter_engine=hybrid_filter_engine,
        content_fetcher=content_fetcher,
        multi_factor_reranker=multi_factor_reranker,
        fact_extractor=fact_extractor,
        fact_bucket_cluster=fact_bucket_cluster,
        orthogonal_detector=orthogonal_detector,
        trust_rank_ladder=trust_rank_ladder
    )
    return orchestrator


def create_rewrite_result():
    return QueryRewriteResult(
        original_query="test",
        rewritten_queries=["test"],
        intent="test intent",
        entities=[]
    )


class TestV3CompleteFlow:
    def setup_method(self):
        self.mock_provider = create_mock_provider([
            create_result("gov.cn", "Official News", "Beijing is the capital of China"),
            create_result("news.com", "News Article", "China's capital is Beijing"),
        ])

    def test_v3_complete_flow_executes_without_errors(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("What is the capital of China?")

        assert isinstance(result, TrustedSearchResultV3)
        assert result.query == "What is the capital of China?"
        assert "version" in result.metadata
        assert result.metadata["version"] == "v3"
        assert result.metadata["provider"] == "test_provider"

    @pytest.mark.asyncio
    async def test_v3_complete_flow_async_executes_without_errors(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = await orchestrator.search_with_trust_v3_async("What is the capital of China?")

        assert isinstance(result, TrustedSearchResultV3)
        assert result.query == "What is the capital of China?"
        assert "version" in result.metadata
        assert result.metadata["version"] == "v3"


class TestV3ReturnsTrustedFacts:
    def setup_method(self):
        self.mock_provider = create_mock_provider([
            create_result("gov.cn", "Official", "Beijing is China's capital"),
            create_result("news.com", "News", "Beijing is capital of China"),
        ])

    def test_v3_returns_trusted_facts_list(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("China capital")

        assert hasattr(result, 'trusted_facts')
        assert isinstance(result.trusted_facts, list)

    def test_v3_returns_all_facts_list(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("China capital")

        assert hasattr(result, 'all_facts')
        assert isinstance(result.all_facts, list)

    def test_v3_returns_buckets_list(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("China capital")

        assert hasattr(result, 'buckets')
        assert isinstance(result.buckets, list)

    def test_v3_returns_collisions_list(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("China capital")

        assert hasattr(result, 'collisions')
        assert isinstance(result.collisions, list)

    def test_v3_returns_metadata_dict(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("China capital")

        assert hasattr(result, 'metadata')
        assert isinstance(result.metadata, dict)


class TestV3FlowSequence:
    def setup_method(self):
        self.mock_provider = create_mock_provider([
            create_result("gov.cn", "Official", "Beijing is capital"),
        ])
        self.orchestrator = create_mock_orchestrator(self.mock_provider)

    def test_v3_flow_sequence_query_rewriter_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(
            return_value=create_rewrite_result()
        )

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.query_rewriter.rewrite_sync.assert_called_once_with("test query")

    def test_v3_flow_sequence_search_provider_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())

        self.orchestrator.search_with_trust_v3("test query")

        assert self.mock_provider.search.called

    def test_v3_flow_sequence_hybrid_filter_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())

        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.hybrid_filter_engine.filter_sync.assert_called()

    def test_v3_flow_sequence_content_fetcher_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())
        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        mock_fetch_result = ContentFetchResult(
            result=create_result("example.com"),
            content="Test content about Beijing capital",
            fetch_success=True
        )
        self.orchestrator.content_fetcher.fetch = Mock(return_value=[mock_fetch_result])

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.content_fetcher.fetch.assert_called()

    def test_v3_flow_sequence_multi_factor_reranker_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())
        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        mock_fetch_result = ContentFetchResult(
            result=create_result("example.com"),
            content="Beijing is China's capital",
            fetch_success=True
        )
        self.orchestrator.content_fetcher.fetch = Mock(return_value=[mock_fetch_result])
        self.orchestrator.multi_factor_reranker.rerank = Mock(return_value=[mock_fetch_result])

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.multi_factor_reranker.rerank.assert_called()

    def test_v3_flow_sequence_fact_extractor_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())
        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        mock_fetch_result = ContentFetchResult(
            result=create_result("example.com"),
            content="Beijing is China's capital",
            fetch_success=True
        )
        self.orchestrator.content_fetcher.fetch = Mock(return_value=[mock_fetch_result])
        self.orchestrator.multi_factor_reranker.rerank = Mock(return_value=[mock_fetch_result])
        self.orchestrator.fact_extractor.extract_sync = Mock(return_value=[
            create_extracted_fact("Beijing is China's capital")
        ])

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.fact_extractor.extract_sync.assert_called()

    def test_v3_flow_sequence_fact_bucket_cluster_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())
        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        mock_fetch_result = ContentFetchResult(
            result=create_result("example.com"),
            content="Beijing is China's capital",
            fetch_success=True
        )
        self.orchestrator.content_fetcher.fetch = Mock(return_value=[mock_fetch_result])
        self.orchestrator.multi_factor_reranker.rerank = Mock(return_value=[mock_fetch_result])
        self.orchestrator.fact_extractor.extract_sync = Mock(return_value=[
            create_extracted_fact("Beijing is China's capital")
        ])
        self.orchestrator.fact_bucket_cluster.cluster_sync = Mock(return_value=[
            FactBucket(
                bucket_id="bucket_1",
                facts=[create_extracted_fact("Beijing is China's capital")],
                cluster_embedding=[0.1, 0.2, 0.3]
            )
        ])

        self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.fact_bucket_cluster.cluster_sync.assert_called()

    def test_v3_flow_sequence_orthogonal_detector_called(self):
        self.orchestrator.query_rewriter.rewrite_sync = Mock(return_value=create_rewrite_result())
        self.orchestrator.hybrid_filter_engine.filter_sync = Mock(return_value=[create_hybrid_filter_result()])

        mock_fetch_result = ContentFetchResult(
            result=create_result("example.com"),
            content="Beijing is China's capital",
            fetch_success=True
        )
        mock_bucket = FactBucket(
            bucket_id="bucket_1",
            facts=[create_extracted_fact("Beijing is China's capital")],
            cluster_embedding=[0.1, 0.2, 0.3]
        )
        self.orchestrator.content_fetcher.fetch = Mock(return_value=[mock_fetch_result])
        self.orchestrator.multi_factor_reranker.rerank = Mock(return_value=[mock_fetch_result])
        self.orchestrator.fact_extractor.extract_sync = Mock(return_value=[
            create_extracted_fact("Beijing is China's capital")
        ])
        self.orchestrator.fact_bucket_cluster.cluster_sync = Mock(return_value=[mock_bucket])
        self.orchestrator.orthogonal_detector.detect_batch = Mock(return_value=[])
        self.orchestrator.orthogonal_detector.get_trusted_facts = Mock(return_value=[
            create_trusted_fact("Beijing is China's capital")
        ])

        result = self.orchestrator.search_with_trust_v3("test query")

        self.orchestrator.orthogonal_detector.detect_batch.assert_called()
        self.orchestrator.orthogonal_detector.get_trusted_facts.assert_called()


class TestV3Metadata:
    def setup_method(self):
        self.mock_provider = create_mock_provider([
            create_result("gov.cn", "Official", "Beijing is capital"),
        ])

    def test_v3_metadata_contains_required_fields(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("test")

        required_fields = [
            "version",
            "provider",
            "total_search_results",
            "unique_results",
            "filtered_results",
            "successful_fetches",
            "reranked_results",
            "total_facts_extracted",
            "total_buckets",
            "total_collisions",
            "trusted_facts_count",
            "duration_ms"
        ]
        for field in required_fields:
            assert field in result.metadata, f"Missing field: {field}"

    def test_v3_metadata_trusted_facts_count(self):
        orchestrator = create_mock_orchestrator(self.mock_provider)

        result = orchestrator.search_with_trust_v3("test")

        assert "trusted_facts_count" in result.metadata
        assert isinstance(result.metadata["trusted_facts_count"], int)


class TestV3EmptyResults:
    def test_v3_empty_results_returns_empty_trusted_facts(self):
        provider = create_mock_provider([])
        orchestrator = SearchOrchestratorV3(provider=provider)

        result = orchestrator.search_with_trust_v3("test")

        assert result.trusted_facts == []
        assert result.all_facts == []
        assert result.buckets == []
        assert result.collisions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])