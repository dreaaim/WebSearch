import pytest
from datetime import datetime, timedelta
from web_search.reranker.freshness import FreshnessCalculator


class TestFreshnessCalculatorTimePeriods:
    def setup_method(self):
        self.calculator = FreshnessCalculator()

    def test_calculate_3_days_ago(self):
        date = (datetime.now() - timedelta(days=3)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 1.0

    def test_calculate_15_days_ago(self):
        date = (datetime.now() - timedelta(days=15)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.8

    def test_calculate_45_days_ago(self):
        date = (datetime.now() - timedelta(days=45)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.6

    def test_calculate_180_days_ago(self):
        date = (datetime.now() - timedelta(days=180)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.4

    def test_calculate_2_years_ago(self):
        date = (datetime.now() - timedelta(days=730)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.2

    def test_calculate_boundary_7_days(self):
        date = (datetime.now() - timedelta(days=7)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 1.0

    def test_calculate_boundary_8_days(self):
        date = (datetime.now() - timedelta(days=8)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.8

    def test_calculate_boundary_30_days(self):
        date = (datetime.now() - timedelta(days=30)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.8

    def test_calculate_boundary_31_days(self):
        date = (datetime.now() - timedelta(days=31)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.6

    def test_calculate_boundary_90_days(self):
        date = (datetime.now() - timedelta(days=90)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.6

    def test_calculate_boundary_91_days(self):
        date = (datetime.now() - timedelta(days=91)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.4

    def test_calculate_boundary_365_days(self):
        date = (datetime.now() - timedelta(days=365)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.4

    def test_calculate_boundary_366_days(self):
        date = (datetime.now() - timedelta(days=366)).isoformat()
        score = self.calculator.calculate(date)
        assert score == 0.2


class TestFreshnessCalculatorEdgeCases:
    def setup_method(self):
        self.calculator = FreshnessCalculator()

    def test_calculate_no_date(self):
        score = self.calculator.calculate(None)
        assert score == 0.5

    def test_calculate_empty_string(self):
        score = self.calculator.calculate("")
        assert score == 0.5

    def test_calculate_invalid_date(self):
        score = self.calculator.calculate("invalid-date")
        assert score == 0.5

    def test_calculate_invalid_format(self):
        score = self.calculator.calculate("2024/01/01")
        assert score == 0.5

    def test_calculate_future_date(self):
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        score = self.calculator.calculate(future_date)
        assert score == 1.0

    def test_calculate_today(self):
        score = self.calculator.calculate(datetime.now().isoformat())
        assert score == 1.0

    def test_calculate_yesterday(self):
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        score = self.calculator.calculate(yesterday)
        assert score == 1.0


class TestFreshnessCalculatorCustomConfig:
    def test_custom_scores(self):
        calculator = FreshnessCalculator(
            period_7d_score=0.9,
            period_30d_score=0.7,
            period_90d_score=0.5,
            period_1y_score=0.3,
            older_score=0.1
        )

        date_3d = (datetime.now() - timedelta(days=3)).isoformat()
        assert calculator.calculate(date_3d) == 0.9

        date_15d = (datetime.now() - timedelta(days=15)).isoformat()
        assert calculator.calculate(date_15d) == 0.7

        date_45d = (datetime.now() - timedelta(days=45)).isoformat()
        assert calculator.calculate(date_45d) == 0.5

        date_180d = (datetime.now() - timedelta(days=180)).isoformat()
        assert calculator.calculate(date_180d) == 0.3

        date_2y = (datetime.now() - timedelta(days=730)).isoformat()
        assert calculator.calculate(date_2y) == 0.1

    def test_custom_all_same_score(self):
        calculator = FreshnessCalculator(
            period_7d_score=0.5,
            period_30d_score=0.5,
            period_90d_score=0.5,
            period_1y_score=0.5,
            older_score=0.5
        )

        for days in [1, 15, 45, 180, 730]:
            date = (datetime.now() - timedelta(days=days)).isoformat()
            assert calculator.calculate(date) == 0.5


class TestFreshnessCalculatorWithZSuffix:
    def setup_method(self):
        self.calculator = FreshnessCalculator()

    def test_calculate_with_z_suffix(self):
        date = (datetime.now() - timedelta(days=3)).isoformat() + "Z"
        score = self.calculator.calculate(date)
        assert score == 1.0

    def test_calculate_with_positive_offset(self):
        date = (datetime.now() - timedelta(days=3)).isoformat() + "+00:00"
        score = self.calculator.calculate(date)
        assert score == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
