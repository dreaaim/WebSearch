from typing import List, Optional, Tuple, Set, Dict
from dataclasses import dataclass

from . import ExtractedFact, SPOTriple


@dataclass
class SPOConflict:
    fact_a: ExtractedFact
    fact_b: ExtractedFact
    conflict_type: str
    subject_match: bool
    predicate_opposite: bool
    object_conflict: bool


class SPOCollisionDetector:
    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold

    def detect_spo_collision(self, facts: List[ExtractedFact]) -> float:
        if len(facts) < 2:
            return 0.0

        spo_groups = self._group_by_subject(facts)

        conflicts = 0
        total_comparisons = 0

        for subject, group_facts in spo_groups.items():
            if len(group_facts) < 2:
                continue

            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    fact_a = group_facts[i]
                    fact_b = group_facts[j]

                    if self._has_spo_conflict(fact_a, fact_b):
                        conflicts += 1

                    total_comparisons += 1

        if total_comparisons == 0:
            return 0.0

        return conflicts / total_comparisons

    def _group_by_subject(self, facts: List[ExtractedFact]) -> Dict[str, List[ExtractedFact]]:
        groups: Dict[str, List[ExtractedFact]] = {}

        for fact in facts:
            if fact.spo_triple is None:
                continue

            subject_key = self._normalize_entity(fact.spo_triple.subject)
            if subject_key not in groups:
                groups[subject_key] = []
            groups[subject_key].append(fact)

        return groups

    def _normalize_entity(self, entity: str) -> str:
        return entity.lower().strip()

    def _has_spo_conflict(self, fact_a: ExtractedFact, fact_b: ExtractedFact) -> bool:
        if fact_a.spo_triple is None or fact_b.spo_triple is None:
            return False

        spo_a = fact_a.spo_triple
        spo_b = fact_b.spo_triple

        if not self._subjects_match(spo_a.subject, spo_b.subject):
            return False

        predicate_opposite = self._predicates_opposite(spo_a.predicate, spo_b.predicate)

        object_conflict = self._objects_conflict(spo_a.object, spo_b.object)

        return predicate_opposite or object_conflict

    def _subjects_match(self, subj_a: str, subj_b: str) -> bool:
        norm_a = self._normalize_entity(subj_a)
        norm_b = self._normalize_entity(subj_b)

        if norm_a == norm_b:
            return True

        import difflib
        similarity = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
        return similarity >= self.similarity_threshold

    def _predicates_opposite(self, pred_a: str, pred_b: str) -> bool:
        opposite_pairs = [
            ("是", "不是"),
            ("在", "不在"),
            ("有", "没有"),
            ("能", "不能"),
            ("会", "不会"),
            ("支持", "反对"),
            ("赞成", "反对"),
            ("承认", "否认"),
            ("确认", "否认"),
            ("认可", "否定"),
            ("包含", "不包含"),
            ("属于", "不属于"),
            ("出生于", "死于"),
            ("结婚", "离婚"),
            ("上升", "下降"),
            ("增加", "减少"),
            ("买入", "卖出"),
            ("正面", "负面"),
            ("喜欢", "讨厌"),
            ("同意", "不同意"),
        ]

        pred_a_norm = pred_a.lower().strip()
        pred_b_norm = pred_b.lower().strip()

        for pos, neg in opposite_pairs:
            if (pos in pred_a_norm and neg in pred_b_norm) or (neg in pred_a_norm and pos in pred_b_norm):
                return True

            if pred_a_norm == neg or pred_b_norm == neg:
                if pos in pred_a_norm or pos in pred_b_norm:
                    return True

        negation_words = ["不", "没", "无", "非", "未", "别", "否", "not", "no", "never", "none"]
        for neg_word in negation_words:
            if neg_word in pred_a_norm and neg_word not in pred_b_norm:
                return True
            if neg_word in pred_b_norm and neg_word not in pred_a_norm:
                return True

        return False

    def _objects_conflict(self, obj_a: str, obj_b: str) -> bool:
        norm_a = self._normalize_entity(obj_a)
        norm_b = self._normalize_entity(obj_b)

        if norm_a == norm_b:
            return False

        import difflib
        similarity = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

        if similarity >= self.similarity_threshold:
            return False

        if self._is_numeric_or_boolean_conflict(obj_a, obj_b):
            return True

        antonym_pairs = [
            ("是", "否"), ("有", "无"), ("真", "假"), ("对", "错"),
            ("是", "非"), ("真", "伪"), ("正", "负"),
            ("true", "false"), ("yes", "no"), ("correct", "wrong"),
        ]

        for pos, neg in antonym_pairs:
            if (pos in norm_a and neg in norm_b) or (neg in norm_a and pos in norm_b):
                return True

        return False

    def _is_numeric_or_boolean_conflict(self, obj_a: str, obj_b: str) -> bool:
        import re

        num_pattern = r"[-+]?\d*\.\d+|\d+"

        nums_a = re.findall(num_pattern, obj_a)
        nums_b = re.findall(num_pattern, obj_b)

        if nums_a and nums_b:
            try:
                val_a = float(nums_a[0])
                val_b = float(nums_b[0])
                return val_a != val_b
            except ValueError:
                pass

        boolean_values = ["是", "否", "有", "无", "真", "假", "对", "错", "true", "false", "yes", "no"]
        obj_a_lower = obj_a.lower()
        obj_b_lower = obj_b.lower()

        val_a_bool = any(b in obj_a_lower for b in boolean_values)
        val_b_bool = any(b in obj_b_lower for b in boolean_values)

        if val_a_bool and val_b_bool:
            for pos, neg in [("是", "否"), ("有", "无"), ("真", "假"), ("对", "错"), ("true", "false")]:
                if (pos in obj_a_lower and neg in obj_b_lower) or (neg in obj_a_lower and pos in obj_b_lower):
                    return True

        return False

    def detect_conflicts(self, facts: List[ExtractedFact]) -> List[SPOConflict]:
        conflicts: List[SPOConflict] = []
        spo_groups = self._group_by_subject(facts)

        for subject, group_facts in spo_groups.items():
            if len(group_facts) < 2:
                continue

            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    fact_a = group_facts[i]
                    fact_b = group_facts[j]

                    if fact_a.spo_triple is None or fact_b.spo_triple is None:
                        continue

                    spo_a = fact_a.spo_triple
                    spo_b = fact_b.spo_triple

                    subject_match = self._subjects_match(spo_a.subject, spo_b.subject)
                    predicate_opposite = self._predicates_opposite(spo_a.predicate, spo_b.predicate)
                    object_conflict = self._objects_conflict(spo_a.object, spo_b.object)

                    if predicate_opposite or object_conflict:
                        conflict_type = "predicate_opposite" if predicate_opposite else "object_conflict"
                        conflicts.append(SPOConflict(
                            fact_a=fact_a,
                            fact_b=fact_b,
                            conflict_type=conflict_type,
                            subject_match=subject_match,
                            predicate_opposite=predicate_opposite,
                            object_conflict=object_conflict
                        ))

        return conflicts

    def get_conflicting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        conflict_pairs = self.detect_conflicts(facts)
        conflicting_facts: Set[ExtractedFact] = set()

        for conflict in conflict_pairs:
            conflicting_facts.add(conflict.fact_a)
            conflicting_facts.add(conflict.fact_b)

        return list(conflicting_facts)

    def get_supporting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        conflicting = set(self.get_conflicting_facts(facts))
        return [f for f in facts if f not in conflicting]


def detect_spo_collision(facts: List[ExtractedFact]) -> float:
    detector = SPOCollisionDetector()
    return detector.detect_spo_collision(facts)
