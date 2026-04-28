import pytest
from datetime import datetime
from web_search.reranker.freshness import FreshnessCalculator


class TestFreshnessCalculator:
    def setup_method(self):
        self.calculator = FreshnessCalculator()

    def test_calculate_no_date(self):
        score = self.calculator.calculate(None)
        assert score == 0.5

    def test_calculate_invalid_date(self):
        score = self.calculator.calculate("invalid-date")
        assert score == 0.5

    def test_calculate_old_date(self):
        score = self.calculator.calculate("2020-01-01T00:00:00")
        assert score == 0.2

    def test_calculate_recent_date(self):
        today = datetime.now().isoformat()
        score = self.calculator.calculate(today)
        assert score == 1.0


class TestFreshnessCalculatorCustom:
    def test_custom_scores(self):
        calculator = FreshnessCalculator(
            period_7d_score=0.9,
            period_30d_score=0.7,
            period_90d_score=0.5,
            period_1y_score=0.3,
            older_score=0.1
        )
        score = calculator.calculate("2020-01-01T00:00:00")
        assert score == 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])