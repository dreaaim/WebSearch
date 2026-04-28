import pytest
from web_search.classifier.relevance_scorer import RelevanceScorer, RelevanceResult


class TestRelevanceScorer:
    def setup_method(self):
        self.scorer = RelevanceScorer()

    def test_score_sync(self):
        result = self.scorer.score(
            title="AI 最新突破",
            content="人工智能领域最近有重大进展",
            url="https://example.com",
            original_query="AI 最新突破",
            intent="factual"
        )
        assert isinstance(result, RelevanceResult)
        assert 0.0 <= result.score <= 10.0

    def test_score_returns_default_when_no_llm(self):
        result = self.scorer.score(
            title="测试标题",
            content="测试内容",
            url="https://test.com",
            original_query="测试",
            intent="factual"
        )
        assert result.score == 5.0


class TestRelevanceResult:
    def test_dataclass(self):
        result = RelevanceResult(
            score=8.0,
            reason="高度相关",
            key_match_points=["AI", "突破"]
        )
        assert result.score == 8.0
        assert result.reason == "高度相关"
        assert len(result.key_match_points) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])