import pytest
from datetime import datetime
from web_search.resolver.fact_resolver import FactResolver
from web_search.resolver.priority_engine import PriorityEngine
from web_search.resolver.claim import ClaimExtractor
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel, Claim


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


def create_claim(domain, statement, title="Test"):
    result = create_result(domain, title, statement)
    return Claim(
        result=result,
        statement=statement,
        key_facts=[title],
        timestamp=datetime.now()
    )


class TestFactResolverInit:
    def test_fact_resolver_init(self):
        resolver = FactResolver()
        assert resolver.priority_engine is not None
        assert resolver.claim_extractor is not None

    def test_fact_resolver_with_custom_engine(self):
        engine = PriorityEngine()
        resolver = FactResolver(priority_engine=engine)
        assert resolver.priority_engine == engine


class TestFactResolverDetectAndResolve:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_detect_and_resolve_empty_results(self):
        collisions = self.resolver.detect_and_resolve([])
        assert collisions == []

    def test_detect_and_resolve_single_result(self):
        results = [create_result("s1.com", "Test", "Content")]
        collisions = self.resolver.detect_and_resolve(results)
        assert isinstance(collisions, list)

    def test_detect_and_resolve_multiple_similar_results(self):
        results = [
            create_result("s1.com", "Same Title", "Same Content Here"),
            create_result("s2.com", "Same Title", "Same Content Here"),
        ]
        collisions = self.resolver.detect_and_resolve(results)
        assert len(collisions) >= 1

    def test_detect_and_resolve_different_results(self):
        results = [
            create_result("s1.com", "Topic A", "Content A"),
            create_result("s2.com", "Topic B", "Content B"),
            create_result("s3.com", "Topic C", "Content C"),
        ]
        collisions = self.resolver.detect_and_resolve(results)
        assert isinstance(collisions, list)


class TestFactResolverGroupSimilarClaims:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_group_similar_claims_identical(self):
        claim1 = create_claim("s1.com", "This is a test statement about the event")
        claim2 = create_claim("s2.com", "This is a test statement about the event")
        claims = [claim1, claim2]

        groups = self.resolver._group_similar_claims(claims)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_group_similar_claims_slightly_different(self):
        claim1 = create_claim("s1.com", "This is a test statement about the event")
        claim2 = create_claim("s2.com", "This is a test statement about similar event")
        claims = [claim1, claim2]

        groups = self.resolver._group_similar_claims(claims)
        assert len(groups) >= 1

    def test_group_similar_claims_completely_different(self):
        claim1 = create_claim("s1.com", "This is about topic A completely")
        claim2 = create_claim("s2.com", "Something entirely different topic B")
        claims = [claim1, claim2]

        groups = self.resolver._group_similar_claims(claims)
        assert len(groups) == 2

    def test_group_similar_claims_multiple_groups(self):
        claim1 = create_claim("s1.com", "This is about AI and machine learning")
        claim2 = create_claim("s2.com", "AI and deep learning developments")
        claim3 = create_claim("s3.com", "Weather forecast for today")
        claim4 = create_claim("s4.com", "Rain expected tomorrow")
        claims = [claim1, claim2, claim3, claim4]

        groups = self.resolver._group_similar_claims(claims)
        assert len(groups) >= 2


class TestFactResolverAreClaimsSimilar:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_are_claims_similar_identical(self):
        claim1 = create_claim("s1.com", "This is a test statement")
        claim2 = create_claim("s2.com", "This is a test statement")

        assert self.resolver._are_claims_similar(claim1, claim2) == True

    def test_are_claims_similar_high_overlap(self):
        claim1 = create_claim("s1.com", "This is a test statement about the event")
        claim2 = create_claim("s2.com", "This is a test statement about the event")

        assert self.resolver._are_claims_similar(claim1, claim2) == True

    def test_are_claims_similar_low_overlap(self):
        claim1 = create_claim("s1.com", "AI machine learning neural networks")
        claim2 = create_claim("s2.com", "Weather rain temperature")

        similarity = self.resolver._are_claims_similar(claim1, claim2)
        assert similarity == False

    def test_are_claims_similar_boundary_06(self):
        claim1 = create_claim("s1.com", "the quick brown fox jumps")
        claim2 = create_claim("s2.com", "the quick brown fox")

        result = self.resolver._are_claims_similar(claim1, claim2)
        assert isinstance(result, bool)

    def test_jaccard_similarity_threshold(self):
        claim1 = create_claim("s1.com", "the quick brown fox jumps over")
        claim2 = create_claim("s2.com", "the quick brown fox")

        result = self.resolver._are_claims_similar(claim1, claim2)
        assert result == True

        claim3 = create_claim("s3.com", "car boat plane train")
        claim4 = create_claim("s4.com", "cat dog")

        result2 = self.resolver._are_claims_similar(claim3, claim4)
        assert result2 == False

    def test_case_insensitive(self):
        claim1 = create_claim("s1.com", "THIS IS A TEST STATEMENT")
        claim2 = create_claim("s2.com", "this is a test statement")

        assert self.resolver._are_claims_similar(claim1, claim2) == True


class TestFactResolverClaimExtractor:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_claim_extractor_extracts_from_snippet(self):
        result = create_result("s1.com", "Title", "This is the snippet content")
        claims = self.resolver.claim_extractor.extract(result)

        assert len(claims) == 1
        assert claims[0].statement == "This is the snippet content"

    def test_claim_extractor_extracts_from_title_when_no_snippet(self):
        result = create_result("s1.com", "Title Only", "")
        result.snippet = ""
        claims = self.resolver.claim_extractor.extract(result)

        assert len(claims) == 1
        assert claims[0].statement == "Title Only"

    def test_claim_extractor_truncates_long_snippet(self):
        long_snippet = "A" * 300
        result = create_result("s1.com", "Title", long_snippet)
        claims = self.resolver.claim_extractor.extract(result)

        assert len(claims[0].statement) <= 200


class TestFactResolverPriorityIntegration:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_priority_engine_used_in_resolution(self):
        white_result = create_result("gov.cn", "Official", "Official content")
        white_result.classification = Classification.WHITE
        white_result.source_type = SourceType.OFFICIAL
        white_result.source_level = SourceLevel.NATIONAL

        gray_result = create_result("blog.com", "Blog", "Blog content")
        gray_result.classification = Classification.GRAY
        gray_result.source_type = SourceType.INDIVIDUAL

        claims = [
            Claim(result=white_result, statement="Official content", key_facts=[], timestamp=datetime.now()),
            Claim(result=gray_result, statement="Blog content", key_facts=[], timestamp=datetime.now())
        ]

        collision = self.resolver.priority_engine.resolve_collision(claims)
        assert collision.resolved_claim is not None
        assert collision.priority_rule_used != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
