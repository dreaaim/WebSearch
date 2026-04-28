import pytest
from web_search.rewriter.intent_analyzer import IntentAnalyzer, QueryIntent
from web_search.rewriter.query_expander import QueryExpander
from web_search.rewriter.query_enhancer import QueryEnhancer
from web_search.rewriter.query_rewriter import QueryRewriter


class TestIntentAnalyzer:
    def setup_method(self):
        self.analyzer = IntentAnalyzer()

    def test_infer_factual_intent(self):
        result = self.analyzer._analyze_sync("今天天气怎么样")
        assert result.intent_type == QueryIntent.FACTUAL_QUERY

    def test_infer_news_intent(self):
        result = self.analyzer._analyze_sync("今天有什么最新新闻")
        assert result.intent_type == QueryIntent.NEWS_QUERY

    def test_infer_howto_intent(self):
        result = self.analyzer._analyze_sync("如何学习 Python 编程")
        assert result.intent_type == QueryIntent.HOWTO_QUERY

    def test_infer_comparison_intent(self):
        result = self.analyzer._analyze_sync("苹果和三星手机哪个好")
        assert result.intent_type == QueryIntent.COMPARISON_QUERY

    def test_extract_entities(self):
        result = self.analyzer._analyze_sync("特斯拉最新股价是多少")
        assert "特斯拉" in result.key_entities

    def test_infer_time_range(self):
        result = self.analyzer._analyze_sync("最近 AI 有什么进展")
        assert result.time_range == "最近一周"


class TestQueryExpander:
    def setup_method(self):
        self.expander = QueryExpander()

    def test_expand_returns_list(self):
        from web_search.rewriter.intent_analyzer import IntentResult
        intent = IntentResult(
            intent_type=QueryIntent.FACTUAL_QUERY,
            key_entities=["AI"],
            time_range="任意",
            specific_requirements=[]
        )
        result = self.expander.expand_sync("AI 最新进展", intent)
        assert isinstance(result, list)
        assert len(result) > 0


class TestQueryEnhancer:
    def setup_method(self):
        self.enhancer = QueryEnhancer()

    def test_add_time_range(self):
        from web_search.rewriter.intent_analyzer import IntentResult
        intent = IntentResult(
            intent_type=QueryIntent.FACTUAL_QUERY,
            key_entities=["AI"],
            time_range="最近一周",
            specific_requirements=[]
        )
        queries = ["AI 最新进展"]
        result = self.enhancer._enhance_sync(queries, intent)
        assert "after:" in result[0]

    def test_add_exact_match(self):
        from web_search.rewriter.intent_analyzer import IntentResult
        intent = IntentResult(
            intent_type=QueryIntent.FACTUAL_QUERY,
            key_entities=["人工智能"],
            time_range="任意",
            specific_requirements=[]
        )
        queries = ["人工智能 最新进展"]
        result = self.enhancer._enhance_sync(queries, intent)
        assert '"人工智能"' in result[0]


class TestQueryRewriter:
    def setup_method(self):
        self.rewriter = QueryRewriter()

    def test_rewrite_sync(self):
        result = self.rewriter.rewrite_sync("最近 AI 有什么最新突破")
        assert result.original_query == "最近 AI 有什么最新突破"
        assert isinstance(result.rewritten_queries, list)
        assert len(result.rewritten_queries) > 0
        assert result.intent in ["factual", "news", "research"]

    def test_rewrite_sync_howto(self):
        result = self.rewriter.rewrite_sync("如何学习 Python")
        assert result.intent == "howto"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])