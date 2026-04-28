from typing import List, Optional, Tuple
from dataclasses import dataclass

from . import ExtractedFact, NLILabel


@dataclass
class NLIPairResult:
    fact_a: ExtractedFact
    fact_b: ExtractedFact
    nli_label: str
    is_contradiction: bool


class NLICollisionDetector:
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def detect_nli_collision(self, facts: List[ExtractedFact]) -> float:
        if len(facts) < 2:
            return 0.0

        contradictions = 0
        total_pairs = 0
        contradiction_pairs: List[Tuple[ExtractedFact, ExtractedFact]] = []

        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                fact_a = facts[i]
                fact_b = facts[j]

                if self._is_contradiction(fact_a, fact_b):
                    contradictions += 1
                    contradiction_pairs.append((fact_a, fact_b))

                total_pairs += 1

        if total_pairs == 0:
            return 0.0

        contradiction_ratio = contradictions / total_pairs

        return contradiction_ratio

    def _is_contradiction(self, fact_a: ExtractedFact, fact_b: ExtractedFact) -> bool:
        if fact_a.nli_label and fact_b.nli_label:
            if fact_a.nli_label == NLILabel.CONTRADICTION.value and fact_b.nli_label == NLILabel.CONTRADICTION.value:
                return True

            if fact_a.nli_label == NLILabel.ENTAILMENT.value and fact_b.nli_label == NLILabel.CONTRADICTION.value:
                return True
            if fact_a.nli_label == NLILabel.CONTRADICTION.value and fact_b.nli_label == NLILabel.ENTAILMENT.value:
                return True

        return self._check_semantic_contradiction(fact_a.statement, fact_b.statement)

    def _check_semantic_contradiction(self, stmt_a: str, stmt_b: str) -> bool:
        negation_keywords = [
            "不是", "非", "没", "无", "未", "别", "否",
            "not", "no", "never", "none", "neither",
            "false", "wrong", "incorrect", "deny", "reject"
        ]

        stmt_a_lower = stmt_a.lower()
        stmt_b_lower = stmt_b.lower()

        for keyword in negation_keywords:
            if keyword in stmt_a_lower and keyword in stmt_b_lower:
                if self._are_opposite_statements(stmt_a_lower, stmt_b_lower, keyword):
                    return True

        return False

    def _are_opposite_statements(self, stmt_a: str, stmt_b: str, keyword: str) -> bool:
        import difflib
        similarity = difflib.SequenceMatcher(None, stmt_a, stmt_b).ratio()
        return similarity > 0.3

    def detect_contradiction_pairs(
        self, facts: List[ExtractedFact]
    ) -> List[NLIPairResult]:
        results: List[NLIPairResult] = []

        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                fact_a = facts[i]
                fact_b = facts[j]

                is_contradiction = self._is_contradiction(fact_a, fact_b)

                results.append(NLIPairResult(
                    fact_a=fact_a,
                    fact_b=fact_b,
                    nli_label=NLILabel.CONTRADICTION.value if is_contradiction else NLILabel.NEUTRAL.value,
                    is_contradiction=is_contradiction
                ))

        return results

    def get_contradiction_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        contradiction_facts = []

        for i in range(len(facts)):
            for j in range(i + 1, len(facts)):
                fact_a = facts[i]
                fact_b = facts[j]

                if self._is_contradiction(fact_a, fact_b):
                    if fact_a not in contradiction_facts:
                        contradiction_facts.append(fact_a)
                    if fact_b not in contradiction_facts:
                        contradiction_facts.append(fact_b)

        return contradiction_facts

    def get_supporting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        supporting_facts = []

        for fact in facts:
            is_contradicting = False
            for other in facts:
                if fact.fact_id != other.fact_id:
                    if self._is_contradiction(fact, other):
                        is_contradicting = True
                        break

            if not is_contradicting:
                supporting_facts.append(fact)

        return supporting_facts


def detect_nli_collision(facts: List[ExtractedFact]) -> float:
    detector = NLICollisionDetector()
    return detector.detect_nli_collision(facts)
