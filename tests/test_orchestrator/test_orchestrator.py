import pytest
from unittest.mock import Mock, MagicMock
from web_search.core.orchestrator import SearchOrchestrator
from web_search.core.models import SearchResponse, SearchResult, SearchOptions, Classification, SourceType, SourceLevel
from web_search.classifier.source_classifier import SourceClassifier
from web_search.resolver.fact_resolver import FactResolver
from web_search.summary.summary_generator import SummaryGenerator

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
    return provider

def create_result(domain, title="Test"):
    return SearchResult(
        title=title,
        url=f"https://{domain}/test",
        snippet="Test snippet",
        source_name="Test",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL,
        classification=Classification.GRAY
    )

def test_orchestrator_init():
    provider = create_mock_provider()
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    orchestrator = SearchOrchestrator(provider, classifier)
    assert orchestrator.provider == provider
    assert orchestrator.source_classifier == classifier
    assert orchestrator.fact_resolver is not None
    assert orchestrator.summary_generator is not None

def test_orchestrator_init_with_custom_components():
    provider = create_mock_provider()
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    resolver = FactResolver()
    generator = SummaryGenerator()
    orchestrator = SearchOrchestrator(provider, classifier, resolver, generator)
    assert orchestrator.fact_resolver == resolver
    assert orchestrator.summary_generator == generator

def test_orchestrator_search_with_trust():
    provider = create_mock_provider([
        create_result("gov.cn", "Official News"),
        create_result("blog.com", "Personal Blog")
    ])
    classifier = SourceClassifier(
        whitelist=[{"domain": "gov.cn"}],
        blacklist=[]
    )
    orchestrator = SearchOrchestrator(provider, classifier)
    result = orchestrator.search_with_trust("test query")
    assert result.query == "test query"
    assert len(result.classified_results["white"]) >= 1
    assert isinstance(result.metadata, dict)
    assert result.metadata.get("provider") == "test_provider"

def test_orchestrator_search_with_options():
    provider = create_mock_provider([create_result("test.com")])
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    orchestrator = SearchOrchestrator(provider, classifier)
    options = SearchOptions(max_results=5)
    result = orchestrator.search_with_trust("test", options)
    assert result.query == "test"

def test_orchestrator_white_list_search():
    provider = create_mock_provider([
        create_result("gov.cn", "Official"),
        create_result("blog.com", "Blog")
    ])
    classifier = SourceClassifier(
        whitelist=[{"domain": "gov.cn"}],
        blacklist=[]
    )
    orchestrator = SearchOrchestrator(provider, classifier)
    response = orchestrator.white_list_search("test")
    assert response.query == "test"
    assert all(r.classification == Classification.WHITE for r in response.results)

def test_orchestrator_metadata():
    provider = create_mock_provider([
        create_result("gov.cn"),
        create_result("blog.com"),
        create_result("fake.cn")
    ])
    classifier = SourceClassifier(
        whitelist=[{"domain": "gov.cn"}],
        blacklist=[{"domain": "fake.cn"}]
    )
    orchestrator = SearchOrchestrator(provider, classifier)
    result = orchestrator.search_with_trust("test")
    assert "white_count" in result.metadata
    assert "gray_count" in result.metadata
    assert "black_count" in result.metadata
    assert "collision_count" in result.metadata
    assert result.metadata["provider"] == "test_provider"