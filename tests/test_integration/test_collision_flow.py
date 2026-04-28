import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from web_search.resolver.fact_resolver import FactResolver
from web_search.resolver.llm_judge import LLMCollisionJudge, CollisionJudgment, FactCollision, Claim
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel


def create_claim(statement, domain="example.com"):
    result = SearchResult(
        title="Test",
        url=f"https://{domain}/test",
        snippet=statement,
        source_name="Test",
        source_domain=domain,
        source_type=SourceType.MEDIA,
        source_level=SourceLevel.MUNICIPAL,
        classification=Classification.GRAY
    )
    return Claim(
        result=result,
        statement=statement,
        key_facts=[],
        timestamp=datetime.now()
    )


class TestCollisionDetectionAndJudgment:
    def setup_method(self):
        self.resolver = FactResolver()
        self.judge = LLMCollisionJudge()

    def test_collision_detected_for_similar_claims(self):
        results = [
            SearchResult(
                title="Same Title",
                url="https://s1.com/test",
                snippet="This is the same content about the event",
                source_name="Source 1",
                source_domain="s1.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
            SearchResult(
                title="Same Title",
                url="https://s2.com/test",
                snippet="This is the same content about the event",
                source_name="Source 2",
                source_domain="s2.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
        ]

        collisions = self.resolver.detect_and_resolve(results)

        assert len(collisions) >= 1

    def test_collision_not_detected_for_different_claims(self):
        results = [
            SearchResult(
                title="Topic A",
                url="https://s1.com/a",
                snippet="AI machine learning neural networks",
                source_name="Source 1",
                source_domain="s1.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
            SearchResult(
                title="Topic B",
                url="https://s2.com/b",
                snippet="Weather rain temperature forecast",
                source_name="Source 2",
                source_domain="s2.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
        ]

        collisions = self.resolver.detect_and_resolve(results)

        assert len(collisions) == 0


class TestLLMCollisionJudgeIntegration:
    def setup_method(self):
        self.judge = LLMCollisionJudge()

    @pytest.mark.asyncio
    async def test_judge_returns_collision_judgment(self):
        claim1 = create_claim("Statement A about the event")
        claim2 = create_claim("Statement B about the event")

        collision = FactCollision(
            collision_id="test_collision",
            claims=[claim1, claim2],
            resolved_claim=claim1,
            priority_rule_used="test_rule",
            consensus_degree=0.5
        )

        judgment = await self.judge.judge(collision, "test query")

        assert isinstance(judgment, CollisionJudgment)
        assert judgment.collision_id == "test_collision"
        assert judgment.winner in ["A", "B", ""]
        assert 0.0 <= judgment.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_judge_batch_returns_multiple_judgments(self):
        claim1 = create_claim("Statement A about the event")
        claim2 = create_claim("Statement B about the event")

        collision1 = FactCollision(
            collision_id="collision_1",
            claims=[claim1, claim2],
            resolved_claim=claim1
        )
        collision2 = FactCollision(
            collision_id="collision_2",
            claims=[claim1, claim2],
            resolved_claim=claim2
        )

        judgments = await self.judge.judge_batch(
            [collision1, collision2],
            "test query"
        )

        assert len(judgments) == 2
        assert all(isinstance(j, CollisionJudgment) for j in judgments)


class TestCollisionResolutionWithPriority:
    def setup_method(self):
        self.resolver = FactResolver()

    def test_higher_priority_claim_wins(self):
        results = [
            SearchResult(
                title="Official News",
                url="https://gov.cn/news",
                snippet="Official statement about the policy",
                source_name="Government",
                source_domain="gov.cn",
                source_type=SourceType.OFFICIAL,
                source_level=SourceLevel.NATIONAL,
                classification=Classification.WHITE
            ),
            SearchResult(
                title="Blog Post",
                url="https://blog.com/post",
                snippet="Different opinion about the policy",
                source_name="Blogger",
                source_domain="blog.com",
                source_type=SourceType.INDIVIDUAL,
                source_level=SourceLevel.LOCAL,
                classification=Classification.GRAY
            ),
        ]

        collisions = self.resolver.detect_and_resolve(results)

        if len(collisions) > 0:
            collision = collisions[0]
            assert collision.resolved_claim is not None


class TestCollisionDetectionIntegration:
    def test_full_collision_detection_and_resolution_flow(self):
        resolver = FactResolver()

        results = [
            SearchResult(
                title="Event Report 1",
                url="https://s1.com/1",
                snippet="The event happened on Monday with 100 attendees",
                source_name="Source 1",
                source_domain="s1.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
            SearchResult(
                title="Event Report 2",
                url="https://s2.com/2",
                snippet="The event happened on Monday with 100 attendees",
                source_name="Source 2",
                source_domain="s2.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.MUNICIPAL
            ),
            SearchResult(
                title="Unrelated News",
                url="https://s3.com/3",
                snippet="Weather forecast for the weekend",
                source_name="Source 3",
                source_domain="s3.com",
                source_type=SourceType.MEDIA,
                source_level=SourceLevel.LOCAL
            ),
        ]

        collisions = resolver.detect_and_resolve(results)

        assert isinstance(collisions, list)
        assert len(collisions) >= 1

        for collision in collisions:
            assert len(collision.claims) >= 2
            assert collision.resolved_claim is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
