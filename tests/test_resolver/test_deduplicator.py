import pytest
from web_search.resolver.deduplicator import Deduplicator
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel

def create_result(url, title, snippet, source_type=SourceType.MEDIA,
                  source_level=SourceLevel.MUNICIPAL,
                  classification=Classification.GRAY,
                  relevance_score=5.0):
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source_name="Test",
        source_domain=url.split("/")[2] if "/" in url else url,
        source_type=source_type,
        source_level=source_level,
        classification=classification,
        relevance_score=relevance_score
    )

def test_deduplicator_init():
    dedup = Deduplicator()
    assert dedup.similarity_threshold == 0.85

def test_deduplicator_custom_threshold():
    dedup = Deduplicator(similarity_threshold=0.9)
    assert dedup.similarity_threshold == 0.9

def test_deduplicate_empty_list():
    dedup = Deduplicator()
    results = dedup.deduplicate([])
    assert results == []

def test_deduplicate_single_result():
    dedup = Deduplicator()
    result = create_result("https://example.com", "Title", "Snippet")
    results = dedup.deduplicate([result])
    assert len(results) == 1

def test_url_exact_deduplication():
    dedup = Deduplicator()
    results = [
        create_result("https://example.com/1", "Title 1", "Snippet 1"),
        create_result("https://example.com/1", "Title 2", "Snippet 2"),
        create_result("https://example.com/2", "Title 3", "Snippet 3"),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 2
    urls = [r.url for r in deduplicated]
    assert "https://example.com/1" in urls
    assert "https://example.com/2" in urls

def test_url_deduplication_keeps_higher_priority():
    dedup = Deduplicator()
    results = [
        create_result(
            "https://example.com/1", "Title 1", "Snippet 1",
            source_type=SourceType.INDIVIDUAL,
            classification=Classification.BLACK
        ),
        create_result(
            "https://example.com/1", "Title 2", "Snippet 2",
            source_type=SourceType.OFFICIAL,
            classification=Classification.WHITE
        ),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1
    assert deduplicated[0].source_type == SourceType.OFFICIAL
    assert deduplicated[0].classification == Classification.WHITE

def test_similarity_threshold_below():
    dedup = Deduplicator(similarity_threshold=0.9)
    results = [
        create_result("https://a.com", "Python 3.11 Release Notes", "Content A"),
        create_result("https://b.com", "Python 3.12 New Features", "Content B"),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 2

def test_similarity_threshold_above():
    dedup = Deduplicator(similarity_threshold=0.85)
    results = [
        create_result("https://a.com", "Python 3.11 Release Notes Official Guide", "Content A"),
        create_result("https://b.com", "Python 3.11 Release Notes Official Guide", "Content B"),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1

def test_title_normalization():
    dedup = Deduplicator()
    sim = dedup._compute_title_similarity(
        "Python 3.11: What's New?",
        "Python 3.11 - What's New?"
    )
    assert sim > 0.8

def test_identical_titles():
    dedup = Deduplicator()
    sim = dedup._compute_title_similarity(
        "Same Title Here",
        "Same Title Here"
    )
    assert sim == 1.0

def test_totally_different_titles():
    dedup = Deduplicator()
    sim = dedup._compute_title_similarity(
        "Python Programming",
        "Weather Forecast"
    )
    assert sim < 0.3

def test_priority_keeps_white_over_gray():
    dedup = Deduplicator()
    results = [
        create_result(
            "https://a.com", "Same Title", "Snippet A",
            classification=Classification.GRAY,
            source_type=SourceType.INDIVIDUAL
        ),
        create_result(
            "https://b.com", "Same Title", "Snippet B",
            classification=Classification.WHITE,
            source_type=SourceType.OFFICIAL
        ),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1
    assert deduplicated[0].classification == Classification.WHITE

def test_priority_keeps_official_over_media():
    dedup = Deduplicator()
    results = [
        create_result(
            "https://a.com", "Same Title", "Snippet A",
            classification=Classification.GRAY,
            source_type=SourceType.MEDIA
        ),
        create_result(
            "https://b.com", "Same Title", "Snippet B",
            classification=Classification.GRAY,
            source_type=SourceType.OFFICIAL
        ),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1
    assert deduplicated[0].source_type == SourceType.OFFICIAL

def test_priority_keeps_national_over_provincial():
    dedup = Deduplicator()
    results = [
        create_result(
            "https://a.com", "Same Title", "Snippet A",
            classification=Classification.WHITE,
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.PROVINCIAL
        ),
        create_result(
            "https://b.com", "Same Title", "Snippet B",
            classification=Classification.WHITE,
            source_type=SourceType.OFFICIAL,
            source_level=SourceLevel.NATIONAL
        ),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1
    assert deduplicated[0].source_level == SourceLevel.NATIONAL

def test_mixed_url_and_similarity_deduplication():
    dedup = Deduplicator(similarity_threshold=0.85)
    results = [
        create_result("https://a.com/1", "Title A", "Snippet 1"),
        create_result("https://a.com/1", "Title A", "Snippet 2"),
        create_result("https://b.com", "Title A", "Snippet 3"),
        create_result("https://c.com", "Different Title", "Snippet 4"),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 2

def test_should_keep_uses_relevance_score():
    dedup = Deduplicator()
    results = [
        create_result(
            "https://a.com", "Same Title", "Snippet A",
            classification=Classification.GRAY,
            source_type=SourceType.MEDIA,
            relevance_score=3.0
        ),
        create_result(
            "https://b.com", "Same Title", "Snippet B",
            classification=Classification.GRAY,
            source_type=SourceType.MEDIA,
            relevance_score=8.0
        ),
    ]
    deduplicated = dedup.deduplicate(results)
    assert len(deduplicated) == 1
    assert deduplicated[0].relevance_score == 8.0

def test_empty_title_returns_zero():
    dedup = Deduplicator()
    sim = dedup._compute_title_similarity("", "Title")
    assert sim == 0.0

def test_none_title_returns_zero():
    dedup = Deduplicator()
    sim = dedup._compute_title_similarity(None, "Title")
    assert sim == 0.0
