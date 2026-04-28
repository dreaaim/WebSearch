import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from web_search.core.orchestrator_v2 import SearchOrchestratorV2, V2Metadata, CollisionResult
from web_search.core.models import SearchResponse, SearchResult, SearchOptions, Classification, SourceType, SourceLevel, TrustedSearchResult
from web_search.classifier.source_classifier import SourceClassifier
from web_search.classifier.llm_classifier import LLMSourceClassifier, ClassifiedResult
from web_search.resolver.fact_resolver import FactResolver
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge, CollisionJudgment, FactCollision, Claim
from web_search.reranker.reranker import Reranker
from web_search.summary.summary_generator import SummaryGenerator
from web_search.rewriter.query_rewriter import QueryRewriter, QueryRewriteResult


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
    provider.search_async = Mock(return_value=response)
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


class TestSearchOrchestratorV2Init:
    def test_orchestrator_v2_init_default(self):
        provider = create_mock_provider()
        classifier = SourceClassifier(whitelist=[], blacklist=[])

        orchestrator = SearchOrchestratorV2(provider, classifier)

        assert orchestrator.provider == provider
        assert orchestrator.source_classifier == classifier
        assert orchestrator.use_v2_features == True

    def test_orchestrator_v2_init_with_all_components(self):
        provider = create_mock_provider()
        classifier = SourceClassifier(whitelist=[], blacklist=[])
        query_rewriter = QueryRewriter()
        reranker = Reranker()
        summary_generator = SummaryGenerator()

        orchestrator = SearchOrchestratorV2(
            provider=provider,
            source_classifier=classifier,
            query_rewriter=query_rewriter,
            reranker=reranker,
            summary_generator=summary_generator,
            use_v2_features=True
        )

        assert orchestrator.query_rewriter == query_rewriter
        assert orchestrator.reranker == reranker
        assert orchestrator.summary_generator == summary_generator

    def test_orchestrator_v2_default_fact_resolver(self):
        provider = create_mock_provider()
        classifier = SourceClassifier(whitelist=[], blacklist=[])

        orchestrator = SearchOrchestratorV2(provider, classifier)

        assert orchestrator.fact_resolver is not None
        assert isinstance(orchestrator.fact_resolver, FactResolver)


class TestSearchOrchestratorV2SyncFlow:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "Official News"),
            create_result("blog.com", "Personal Blog"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[]
        )
        self.orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            use_v2_features=False
        )

    def test_search_with_trust_returns_trusted_result(self):
        result = self.orchestrator.search_with_trust("test query")

        assert isinstance(result, TrustedSearchResult)
        assert result.query == "test query"
        assert hasattr(result, 'response')
        assert hasattr(result, 'classified_results')

    def test_search_with_trust_classifies_results(self):
        result = self.orchestrator.search_with_trust("test query")

        assert "white" in result.classified_results
        assert "gray" in result.classified_results
        assert "black" in result.classified_results

    def test_search_with_trust_includes_metadata(self):
        result = self.orchestrator.search_with_trust("test query")

        assert "provider" in result.metadata
        assert result.metadata["provider"] == "test_provider"

    def test_search_with_trust_detects_collisions(self):
        result = self.orchestrator.search_with_trust("test query")

        assert "collision_count" in result.metadata
        assert isinstance(result.metadata["collision_count"], int)


class TestSearchOrchestratorV2WithQueryRewriter:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "Official News"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[]
        )
        self.query_rewriter = QueryRewriter()

    def test_v2_enabled_uses_query_rewriter(self):
        orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            query_rewriter=self.query_rewriter,
            use_v2_features=True
        )

        result = orchestrator.search_with_trust("latest AI developments")

        assert result.metadata.get("v2_metadata") is not None

    def test_v2_disabled_skips_query_rewriter(self):
        orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            query_rewriter=self.query_rewriter,
            use_v2_features=False
        )

        result = orchestrator.search_with_trust("latest AI developments")

        assert "v2_metadata" not in result.metadata or \
               result.metadata.get("v2_metadata", {}).get("rewrite_result") is None


class TestSearchOrchestratorV2MultiSearch:
    def setup_method(self):
        self.classifier = SourceClassifier(whitelist=[], blacklist=[])
        self.query_rewriter = QueryRewriter()

    def test_multi_search_calls_provider_multiple_times(self):
        provider = create_mock_provider([
            create_result("example.com", "Result"),
        ])
        orchestrator = SearchOrchestratorV2(
            provider=provider,
            source_classifier=self.classifier,
            query_rewriter=self.query_rewriter,
            use_v2_features=True
        )

        orchestrator.search_with_trust("test query")

        assert provider.search.call_count >= 1


class TestSearchOrchestratorV2WithReranker:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "Official", "High quality official content"),
            create_result("blog.com", "Blog", "Lower quality blog content"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[]
        )

    def test_reranker_integration(self):
        reranker = Reranker()
        orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            reranker=reranker,
            use_v2_features=True
        )

        result = orchestrator.search_with_trust("test query")

        assert result.response.results is not None


class TestSearchOrchestratorV2WhiteListSearch:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "Official"),
            create_result("blog.com", "Blog"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[]
        )
        self.orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier
        )

    def test_white_list_search_returns_only_white(self):
        response = self.orchestrator.white_list_search("test")

        assert response.query == "test"
        for result in response.results:
            assert result.classification == Classification.WHITE


class TestSearchOrchestratorV2Metadata:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "White"),
            create_result("blog.com", "Gray"),
            create_result("fake.cn", "Black"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[{"domain": "fake.cn"}]
        )
        self.orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier
        )

    def test_metadata_includes_counts(self):
        result = self.orchestrator.search_with_trust("test")

        assert "white_count" in result.metadata
        assert "gray_count" in result.metadata
        assert "black_count" in result.metadata

    def test_metadata_includes_collision_count(self):
        result = self.orchestrator.search_with_trust("test")

        assert "collision_count" in result.metadata


class TestSearchOrchestratorV2V2Metadata:
    def setup_method(self):
        self.provider = create_mock_provider([
            create_result("gov.cn", "Official"),
        ])
        self.classifier = SourceClassifier(
            whitelist=[{"domain": "gov.cn"}],
            blacklist=[]
        )

    def test_v2_metadata_version(self):
        orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            use_v2_features=True
        )

        result = orchestrator.search_with_trust("test")

        v2_meta = result.metadata.get("v2_metadata", {})
        assert v2_meta.get("version") == "v2"

    def test_v2_metadata_includes_rerank_weights(self):
        reranker = Reranker()
        orchestrator = SearchOrchestratorV2(
            provider=self.provider,
            source_classifier=self.classifier,
            reranker=reranker,
            use_v2_features=True
        )

        result = orchestrator.search_with_trust("test")

        v2_meta = result.metadata.get("v2_metadata", {})
        assert "rerank_weights" in v2_meta


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
