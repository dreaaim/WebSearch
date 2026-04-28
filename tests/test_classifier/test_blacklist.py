import pytest
from web_search.classifier.blacklist import BlacklistManager
from web_search.core.models import SearchResult, SourceType, SourceLevel

def create_result(domain):
    return SearchResult(
        title="Test",
        url=f"https://{domain}/test",
        snippet="Test snippet",
        source_name="Test",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL
    )

def test_blacklist_manager_empty():
    manager = BlacklistManager([])
    result = create_result("example.com")
    assert manager.is_blacklisted(result) == False

def test_blacklist_manager_domain_match():
    manager = BlacklistManager([{"domain": "fake-news.cn"}])
    result = create_result("fake-news.cn")
    assert manager.is_blacklisted(result) == True

def test_blacklist_manager_pattern():
    manager = BlacklistManager([{"domain_pattern": "*clickbait*"}])
    result = create_result("news-clickbait.com")
    assert manager.is_blacklisted(result) == True