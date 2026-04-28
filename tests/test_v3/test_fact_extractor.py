import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

with patch.dict('sys.modules', {'web_search.config.settings': MagicMock()}):
    from web_search.extractor.fact_extractor import FactExtractor, ExtractedFact
    from web_search.extractor.nli_analyzer import NLIAnalyzer
    from web_search.extractor.spo_extractor import SPOExtractor, SPOTriple
    from web_search.extractor.value_extractor import ValueExtractor, NumericValue, DatetimeValue


class TestNLIAnalyzer:
    def setup_method(self):
        self.analyzer = NLIAnalyzer(use_llm_fallback=False)

    def test_nli_analyze_entailment(self):
        self.analyzer._cross_encoder = None
        self.analyzer._llm_client = MagicMock()
        self.analyzer._llm_client.complete_sync = MagicMock(return_value=MagicMock(strip=MagicMock(return_value='entailment'), lower=MagicMock(return_value='entailment')))
        result = self.analyzer._analyze_with_llm("The sky is blue today.", "The sky appears to be blue.")
        assert result == "entailment"

    def test_nli_analyze_contradiction(self):
        self.analyzer._cross_encoder = None
        self.analyzer._llm_client = MagicMock()
        self.analyzer._llm_client.complete_sync = MagicMock(return_value=MagicMock(strip=MagicMock(return_value='contradiction'), lower=MagicMock(return_value='contradiction')))
        result = self.analyzer._analyze_with_llm("The sky is blue.", "The sky is red.")
        assert result == "contradiction"

    def test_nli_analyze_neutral(self):
        self.analyzer._cross_encoder = None
        self.analyzer._llm_client = MagicMock()
        self.analyzer._llm_client.complete_sync = MagicMock(return_value=MagicMock(strip=MagicMock(return_value='neutral'), lower=MagicMock(return_value='neutral')))
        result = self.analyzer._analyze_with_llm("The sky is blue.", "The cat is sleeping.")
        assert result == "neutral"


class TestSPOExtractor:
    def setup_method(self):
        self.extractor = SPOExtractor(use_llm_fallback=False)

    def test_spo_extraction_basic(self):
        expected_triple = SPOTriple(subject="Beijing", predicate="is", object="capital")
        self.extractor._nlp = MagicMock()

        with patch.object(self.extractor, '_extract_with_spacy', return_value=[expected_triple]):
            result = self.extractor.extract_spo_sync("Beijing is the capital of China.")

        assert len(result) >= 1
        assert isinstance(result[0], SPOTriple)
        assert result[0].subject == "Beijing"
        assert result[0].predicate == "is"
        assert result[0].object in ["capital", "the capital of China"]


class TestValueExtractor:
    def setup_method(self):
        self.extractor = ValueExtractor()

    def test_value_extraction_numbers(self):
        text = "The company has 1500 employees and revenue of 500000 dollars."
        numeric_values, _ = self.extractor.extract_values_sync(text)

        assert len(numeric_values) >= 1
        values = [nv.value for nv in numeric_values]
        assert 1500 in values or 500000 in values

    def test_value_extraction_percentages(self):
        text = "The inflation rate increased by 3.5% last month."
        numeric_values, _ = self.extractor.extract_values_sync(text)

        assert len(numeric_values) >= 1
        percent_values = [nv for nv in numeric_values if nv.unit == "%"]
        assert len(percent_values) >= 1
        assert any(abs(nv.value - 3.5) < 0.01 for nv in percent_values)

    def test_value_extraction_dates(self):
        text = "The meeting is scheduled for 2024-03-15 at the conference hall."
        _, datetime_values = self.extractor.extract_values_sync(text)

        assert len(datetime_values) >= 1
        dates = [dv.date for dv in datetime_values]
        assert any(d.year == 2024 and d.month == 3 and d.day == 15 for d in dates)


class TestFactExtractor:
    def setup_method(self):
        self.extractor = FactExtractor(
            nli_analyzer=NLIAnalyzer(use_llm_fallback=False),
            spo_extractor=SPOExtractor(use_llm_fallback=False),
            value_extractor=ValueExtractor()
        )

    def test_fact_extractor_returns_list(self):
        content = "Beijing is the capital of China. The population is 21540000."

        with patch.object(self.extractor._spo_extractor, '_load_spacy', return_value=None):
            with patch.object(self.extractor._spo_extractor, '_extract_with_llm', return_value=[]):
                with patch.object(self.extractor._spo_extractor, '_extract_simple_patterns', return_value=[
                    SPOTriple(subject="Beijing", predicate="is", object="capital of China")
                ]):
                    facts = self.extractor.extract_sync(content, "example.com")

        assert isinstance(facts, list)
        assert all(isinstance(f, ExtractedFact) for f in facts)
        assert len(facts) >= 1
        assert facts[0].fact_id.startswith("fact_")
        assert facts[0].statement != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])