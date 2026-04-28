import pytest
from web_search.resolver.fact_resolver import FactResolver
from web_search.resolver.priority_engine import PriorityEngine
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel

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

def test_fact_resolver_init():
    resolver = FactResolver()
    assert resolver.priority_engine is not None
    assert resolver.claim_extractor is not None

def test_fact_resolver_with_custom_engine():
    engine = PriorityEngine()
    resolver = FactResolver(priority_engine=engine)
    assert resolver.priority_engine == engine

def test_fact_resolver_detect_and_resolve():
    resolver = FactResolver()
    results = [
        create_result("source1.com", "Same Title", "Same Content Here"),
        create_result("source2.com", "Same Title", "Same Content Here"),
        create_result("source3.com", "Different", "Different Content")
    ]
    collisions = resolver.detect_and_resolve(results)
    assert isinstance(collisions, list)

def test_are_claims_similar():
    resolver = FactResolver()
    from web_search.core.models import Claim
    from datetime import datetime

    result1 = create_result("s1.com", "Test", "This is a test statement about the event")
    result2 = create_result("s2.com", "Test", "This is a test statement about the event")

    claim1 = Claim(result=result1, statement="This is a test statement about the event", key_facts=[], timestamp=datetime.now())
    claim2 = Claim(result=result2, statement="This is a test statement about the event", key_facts=[], timestamp=datetime.now())

    assert resolver._are_claims_similar(claim1, claim2) == True