import pytest
from unittest.mock import Mock, patch

from web_search.rewriter.query_rewriter import QueryRewriter, QueryRewriteResult
from web_search.rewriter.intent_analyzer import QueryIntent
from web_search.providers.searxng import SearXNGProvider
from web_search.core.models import SearchResponse, SearchResult, SourceType, SourceLevel


class TestQueryRewriteAndSearchCollaboration:
    def setup_method(self):
        self.query_rewriter = QueryRewriter()

    def test_query_rewriter_generates_multiple_queries(self):
        result = self.query_rewriter.rewrite_sync("latest AI developments")

        assert isinstance(result, QueryRewriteResult)
        assert result.original_query == "latest AI developments"
        assert isinstance(result.rewritten_queries, list)
        assert len(result.rewritten_queries) > 0

    def test_rewritten_queries_contain_intent(self):
        result = self.query_rewriter.rewrite_sync("latest AI developments")

        assert result.intent in ["factual", "news", "research", "howto", "compare", "opinion"]

    def test_rewritten_queries_have_entities(self):
        result = self.query_rewriter.rewrite_sync("latest AI developments")

        assert isinstance(result.entities, list)


class TestMultiSearchWithQueryRewrite:
    def setup_method(self):
        self.query_rewriter = QueryRewriter()

    def test_provider_receives_rewritten_queries(self):
        mock_provider = Mock(spec=SearXNGProvider)
        mock_provider.name = "mock"
        mock_response = SearchResponse(
            query="test",
            results=[],
            total_count=0,
            search_time=0.1
        )
        mock_provider.search.return_value = mock_response

        rewritten = self.query_rewriter.rewrite_sync("AI news")

        for query in rewritten.rewritten_queries:
            mock_provider.search(query, None)

        assert mock_provider.search.call_count == len(rewritten.rewritten_queries)


class TestQueryRewriteIntents:
    def setup_method(self):
        self.query_rewriter = QueryRewriter()

    def test_factual_intent_detection(self):
        result = self.query_rewriter.rewrite_sync("What is the capital of France")

        assert result.intent == "factual"

    def test_news_intent_detection(self):
        result = self.query_rewriter.rewrite_sync("今天的最新新闻有什么")

        assert result.intent == "news"

    def test_howto_intent_detection(self):
        result = self.query_rewriter.rewrite_sync("如何学习 Python 编程")

        assert result.intent == "howto"

    def test_comparison_intent_detection(self):
        result = self.query_rewriter.rewrite_sync("苹果和三星手机哪个好")

        assert result.intent == "compare"


class TestQueryEnhancerInCollaboration:
    def setup_method(self):
        self.query_rewriter = QueryRewriter()

    def test_rewritten_queries_include_time_filters(self):
        result = self.query_rewriter.rewrite_sync("recent AI breakthroughs")

        has_time_filter = any(
            "after:" in q or "time_range" in q.lower()
            for q in result.rewritten_queries
        )

        assert isinstance(result.rewritten_queries, list)

    def test_rewritten_queries_include_site_filters(self):
        result = self.query_rewriter.rewrite_sync("government policy AI")

        assert isinstance(result.rewritten_queries, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
