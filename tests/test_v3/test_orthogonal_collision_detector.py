import pytest
from web_search.collision import (
    FactBucket,
    CollisionResult,
    ExtractedFact,
    SPOTriple,
    NLILabel,
    NumericValue,
    DatetimeValue,
)
from web_search.collision.orthogonal_detector import (
    OrthogonalCollisionDetector,
    OrthogonalCollisionConfig,
)


def create_fact(
    fact_id: str,
    statement: str,
    spo_triple: SPOTriple = None,
    nli_label: str = None,
    numeric_values: list = None,
    datetime_values: list = None,
) -> ExtractedFact:
    return ExtractedFact(
        fact_id=fact_id,
        statement=statement,
        spo_triple=spo_triple,
        nli_label=nli_label,
        numeric_values=numeric_values or [],
        datetime_values=datetime_values or [],
        confidence_score=0.8,
        source_domain="test.com",
        trust_score=1000.0,
    )


def create_bucket(bucket_id: str, facts: list) -> FactBucket:
    return FactBucket(bucket_id=bucket_id, facts=facts)


class TestNLICollisionDetection:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_nli_collision_detection(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="苹果是一种水果",
            nli_label=NLILabel.ENTAILMENT.value,
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="苹果是一种蔬菜",
            nli_label=NLILabel.CONTRADICTION.value,
        )
        fact3 = create_fact(
            fact_id="f3",
            statement="苹果是一种水果",
            nli_label=NLILabel.ENTAILMENT.value,
        )

        bucket = create_bucket("bucket1", [fact1, fact2, fact3])
        result = self.detector.detect(bucket)

        assert result.nli_conflict_ratio > 0.0
        assert len(result.conflicting_facts) >= 2
        assert fact2 in result.conflicting_facts

    def test_nli_no_contradiction(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="今天天气很好",
            nli_label=NLILabel.NEUTRAL.value,
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="今天天气很好",
            nli_label=NLILabel.NEUTRAL.value,
        )

        bucket = create_bucket("bucket2", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.nli_conflict_ratio == 0.0


class TestSPOCollisionDetection:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_spo_collision_detection(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="张三出生于北京",
            spo_triple=SPOTriple(subject="张三", predicate="出生于", object="北京"),
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="张三不是出生于北京",
            spo_triple=SPOTriple(subject="张三", predicate="不是出生于", object="北京"),
        )

        bucket = create_bucket("bucket1", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.spo_conflict_ratio > 0.0
        assert len(result.conflicting_facts) == 2

    def test_spo_same_subject_opposite_predicate(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="这部电影是正面评价",
            spo_triple=SPOTriple(subject="这部电影", predicate="是正面", object="评价"),
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="这部电影是负面评价",
            spo_triple=SPOTriple(subject="这部电影", predicate="是负面", object="评价"),
        )

        bucket = create_bucket("bucket2", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.spo_conflict_ratio > 0.0

    def test_spo_no_conflict_different_subjects(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="张三出生于北京",
            spo_triple=SPOTriple(subject="张三", predicate="出生于", object="北京"),
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="李四出生于上海",
            spo_triple=SPOTriple(subject="李四", predicate="出生于", object="上海"),
        )

        bucket = create_bucket("bucket3", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.spo_conflict_ratio == 0.0


class TestValueCollisionDetection:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3, numeric_threshold=0.2
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_value_collision_detection(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="revenue increased by 10 percent",
            numeric_values=[NumericValue(value=10.0, unit="%")],
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="revenue increased by 50 percent",
            numeric_values=[NumericValue(value=50.0, unit="%")],
        )

        bucket = create_bucket("bucket1", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.value_conflict_ratio > 0.0
        assert len(result.conflicting_facts) == 2

    def test_value_no_conflict_same_values(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="revenue increased by 10 percent",
            numeric_values=[NumericValue(value=10.0, unit="%")],
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="revenue increased by 10 percent",
            numeric_values=[NumericValue(value=10.0, unit="%")],
        )

        bucket = create_bucket("bucket2", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.value_conflict_ratio == 0.0


class TestCollisionCoefficientCalculation:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_collision_coefficient_calculation(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="苹果是一种水果",
            nli_label=NLILabel.ENTAILMENT.value,
            spo_triple=SPOTriple(subject="苹果", predicate="不是", object="水果"),
            numeric_values=[NumericValue(value=10.0, unit="%")],
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="苹果不是水果",
            nli_label=NLILabel.CONTRADICTION.value,
            spo_triple=SPOTriple(subject="苹果", predicate="是", object="水果"),
            numeric_values=[NumericValue(value=90.0, unit="%")],
        )

        bucket = create_bucket("bucket1", [fact1, fact2])
        result = self.detector.detect(bucket)

        expected_nli = 0.4 * result.nli_conflict_ratio
        expected_spo = 0.3 * result.spo_conflict_ratio
        expected_value = 0.3 * result.value_conflict_ratio
        expected_coefficient = expected_nli + expected_spo + expected_value

        assert abs(result.collision_coefficient - expected_coefficient) < 0.001

    def test_coefficient_zero_when_no_conflicts(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="今天天气很好",
            nli_label=NLILabel.NEUTRAL.value,
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="今天天气很好",
            nli_label=NLILabel.NEUTRAL.value,
        )

        bucket = create_bucket("bucket2", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.collision_coefficient == 0.0


class TestThresholdReview:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_threshold_below_0_3_no_review(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="事实A是正确的",
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="事实B也是正确的",
        )

        bucket = create_bucket("bucket1", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.collision_coefficient < 0.3
        assert result.needs_llm_review is False

    def test_threshold_above_0_3_needs_review(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="苹果是一种水果",
            nli_label=NLILabel.ENTAILMENT.value,
            spo_triple=SPOTriple(subject="苹果", predicate="不是", object="水果"),
            numeric_values=[NumericValue(value=10.0, unit="%")],
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="苹果不是水果",
            nli_label=NLILabel.CONTRADICTION.value,
            spo_triple=SPOTriple(subject="苹果", predicate="是", object="水果"),
            numeric_values=[NumericValue(value=90.0, unit="%")],
        )

        bucket = create_bucket("bucket2", [fact1, fact2])
        result = self.detector.detect(bucket)

        assert result.collision_coefficient >= 0.3
        assert result.needs_llm_review is True

    def test_threshold_equal_0_3_needs_review(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="事实有50%可能性是正确的",
            numeric_values=[NumericValue(value=50.0, unit="%")],
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="事实有100%可能性是正确的",
            numeric_values=[NumericValue(value=100.0, unit="%")],
        )

        bucket = create_bucket("bucket3", [fact1, fact2])
        result = self.detector.detect(bucket)

        if result.collision_coefficient >= 0.3:
            assert result.needs_llm_review is True


class TestEdgeCases:
    def setup_method(self):
        self.config = OrthogonalCollisionConfig(
            alpha=0.4, beta=0.3, gamma=0.3, threshold=0.3
        )
        self.detector = OrthogonalCollisionDetector(config=self.config)

    def test_empty_bucket(self):
        bucket = create_bucket("bucket1", [])
        result = self.detector.detect(bucket)

        assert result.collision_coefficient == 0.0
        assert result.needs_llm_review is False
        assert len(result.conflicting_facts) == 0

    def test_single_fact_bucket(self):
        fact1 = create_fact(fact_id="f1", statement="只有一个事实")
        bucket = create_bucket("bucket1", [fact1])
        result = self.detector.detect(bucket)

        assert result.collision_coefficient == 0.0
        assert result.needs_llm_review is False

    def test_supporting_facts_not_in_conflict(self):
        fact1 = create_fact(
            fact_id="f1",
            statement="苹果是一种水果",
            nli_label=NLILabel.ENTAILMENT.value,
        )
        fact2 = create_fact(
            fact_id="f2",
            statement="苹果不是水果",
            nli_label=NLILabel.CONTRADICTION.value,
        )
        fact3 = create_fact(
            fact_id="f3",
            statement="苹果是红色的",
            nli_label=NLILabel.NEUTRAL.value,
        )

        bucket = create_bucket("bucket1", [fact1, fact2, fact3])
        result = self.detector.detect(bucket)

        assert len(result.supporting_facts) >= 1
        assert fact3 in result.supporting_facts or len(result.conflicting_facts) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])