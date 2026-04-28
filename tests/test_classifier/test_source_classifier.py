import pytest
from web_search.classifier.source_classifier import SourceClassifier
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel

def create_result(domain, title="Test", snippet="Test snippet"):
    return SearchResult(
        title=title,
        url=f"https://{domain}/test",
        snippet=snippet,
        source_name="Test Source",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL
    )

def test_classifier_whitelist():
    classifier = SourceClassifier(
        whitelist=[{"domain": "gov.cn"}],
        blacklist=[]
    )
    result = create_result("gov.cn")
    assert classifier.classify(result) == Classification.WHITE

def test_classifier_blacklist():
    classifier = SourceClassifier(
        whitelist=[],
        blacklist=[{"domain": "fake-news.cn"}]
    )
    result = create_result("fake-news.cn")
    assert classifier.classify(result) == Classification.BLACK

def test_classifier_gray_default():
    classifier = SourceClassifier(
        whitelist=[],
        blacklist=[]
    )
    result = create_result("random-site.com")
    assert classifier.classify(result) == Classification.GRAY

def test_classifier_domain_suffix_match():
    classifier = SourceClassifier(
        whitelist=[{"domain_suffix": ".gov.cn"}],
        blacklist=[]
    )
    result = create_result("www.zj.gov.cn")
    assert classifier.classify(result) == Classification.WHITE

def test_classifier_domain_pattern_match():
    classifier = SourceClassifier(
        whitelist=[{"domain_pattern": "*gov*"}],
        blacklist=[]
    )
    result = create_result("mygov.com")
    assert classifier.classify(result) == Classification.WHITE

def test_classifier_batch_classify():
    classifier = SourceClassifier(
        whitelist=[{"domain": "gov.cn"}],
        blacklist=[{"domain": "fake.cn"}]
    )
    results = [
        create_result("gov.cn"),
        create_result("fake.cn"),
        create_result("other.com")
    ]
    classified = classifier.classify_results(results)
    assert len(classified["white"]) == 1
    assert len(classified["black"]) == 1
    assert len(classified["gray"]) == 1

def test_infer_source_type_official():
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    result = create_result("www.gov.cn")
    result.粉丝数 = None
    assert classifier.infer_source_type(result) == SourceType.OFFICIAL

def test_infer_source_type_kol():
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    result = create_result("weibo.com")
    result.粉丝数 = 50000
    assert classifier.infer_source_type(result) == SourceType.KOL

def test_infer_source_type_media():
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    result = create_result("news.com")
    result.粉丝数 = None
    assert classifier.infer_source_type(result) == SourceType.MEDIA

def test_infer_source_level_national():
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    result = create_result("www.xinhuanet.com")
    assert classifier.infer_source_level(result) == SourceLevel.NATIONAL

def test_infer_source_level_provincial():
    classifier = SourceClassifier(whitelist=[], blacklist=[])
    result = create_result("finance.zj.gov.cn")
    assert classifier.infer_source_level(result) == SourceLevel.PROVINCIAL