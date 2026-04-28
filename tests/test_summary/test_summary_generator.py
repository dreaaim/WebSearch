import pytest
from web_search.summary.summary_generator import SummaryGenerator
from web_search.summary.cluster import ResultCluster
from web_search.summary.consensus import ConsensusDetector
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel, FactCollision

def create_result(domain, title, snippet):
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

def test_summary_generator_init():
    gen = SummaryGenerator()
    assert gen.min_consensus_ratio == 0.6
    assert gen.cluster is not None
    assert gen.consensus_detector is not None

def test_summary_generator_custom_ratio():
    gen = SummaryGenerator(min_consensus_ratio=0.5)
    assert gen.min_consensus_ratio == 0.5

def test_summary_generator_generate():
    gen = SummaryGenerator()
    results = [
        create_result("s1.com", "Title", "Same content"),
        create_result("s2.com", "Title", "Same content"),
    ]
    summary, consensus, disputed = gen.generate(results)
    assert isinstance(summary, str)
    assert isinstance(consensus, list)
    assert isinstance(disputed, list)

def test_result_cluster():
    cluster = ResultCluster()
    results = [
        create_result("s1.com", "Topic A", "Content A"),
        create_result("s2.com", "Topic A", "Content B"),
        create_result("s3.com", "Topic B", "Content C"),
    ]
    clusters = cluster.cluster(results)
    assert len(clusters) >= 1

def test_consensus_detector_consensus():
    detector = ConsensusDetector(min_consensus_ratio=0.6)
    results = [
        create_result("s1.com", "Title", "Same content here"),
        create_result("s2.com", "Title", "Same content here"),
        create_result("s3.com", "Title", "Same content here"),
    ]
    is_consensus, fact = detector.detect(results)
    assert is_consensus == True

def test_consensus_detector_dispute():
    detector = ConsensusDetector(min_consensus_ratio=0.6)
    results = [
        create_result("s1.com", "Title", "Content A"),
        create_result("s2.com", "Title", "Content B"),
        create_result("s3.com", "Title", "Content C"),
    ]
    is_consensus, fact = detector.detect(results)
    assert is_consensus == False

def test_generate_with_sources():
    gen = SummaryGenerator()
    result = create_result("gov.cn", "Test", "Test snippet")
    result.classification = Classification.WHITE
    result.source_name = "Government"
    related = [create_result("other.com", "Other", "Other snippet")]
    output = gen.generate_with_sources(result, related)
    assert "✅" in output
    assert "Government" in output