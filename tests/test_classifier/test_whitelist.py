import pytest
from web_search.classifier.whitelist import WhitelistManager
from web_search.core.models import SearchResult, SourceType, SourceLevel, Classification

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

def test_whitelist_manager_empty():
    manager = WhitelistManager([])
    result = create_result("example.com")
    assert manager.is_whitelisted(result) == False

def test_whitelist_manager_domain_match():
    manager = WhitelistManager([{"domain": "gov.cn"}])
    result = create_result("gov.cn")
    assert manager.is_whitelisted(result) == True

def test_whitelist_manager_domain_suffix():
    manager = WhitelistManager([{"domain_suffix": ".gov.cn"}])
    result = create_result("www.zj.gov.cn")
    assert manager.is_whitelisted(result) == True

def test_whitelist_manager_pattern():
    manager = WhitelistManager([{"domain_pattern": "*gov*"}])
    result = create_result("mygov.com")
    assert manager.is_whitelisted(result) == True