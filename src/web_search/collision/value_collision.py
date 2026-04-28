from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from datetime import datetime
import re

from . import ExtractedFact, NumericValue, DatetimeValue


@dataclass
class ValueConflict:
    fact_a: ExtractedFact
    fact_b: ExtractedFact
    conflict_type: str
    value_a: Optional[str]
    value_b: Optional[str]
    difference: Optional[float]
    is_numeric: bool
    is_datetime: bool


class ValueCollisionDetector:
    def __init__(
        self,
        numeric_threshold: float = 0.2,
        datetime_threshold_days: int = 1
    ):
        self.numeric_threshold = numeric_threshold
        self.datetime_threshold_days = datetime_threshold_days

    def detect_value_collision(self, facts: List[ExtractedFact]) -> float:
        if len(facts) < 2:
            return 0.0

        numeric_groups = self._group_by_context(facts)
        datetime_groups = self._group_by_datetime_context(facts)

        conflicts = 0
        total_comparisons = 0

        for context, group_facts in numeric_groups.items():
            if len(group_facts) < 2:
                continue
            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    if self._has_numeric_conflict(group_facts[i], group_facts[j]):
                        conflicts += 1
                    total_comparisons += 1

        for context, group_facts in datetime_groups.items():
            if len(group_facts) < 2:
                continue
            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    if self._has_datetime_conflict(group_facts[i], group_facts[j]):
                        conflicts += 1
                    total_comparisons += 1

        if total_comparisons == 0:
            return 0.0

        return conflicts / total_comparisons

    def _group_by_context(self, facts: List[ExtractedFact]) -> Dict[str, List[ExtractedFact]]:
        groups: Dict[str, List[ExtractedFact]] = {}

        for fact in facts:
            if not fact.numeric_values:
                continue

            context = self._extract_numeric_context(fact.statement)
            if context not in groups:
                groups[context] = []
            groups[context].append(fact)

        return groups

    def _group_by_datetime_context(self, facts: List[ExtractedFact]) -> Dict[str, List[ExtractedFact]]:
        groups: Dict[str, List[ExtractedFact]] = {}

        for fact in facts:
            if not fact.datetime_values:
                continue

            context = self._extract_datetime_context(fact.statement)
            if context not in groups:
                groups[context] = []
            groups[context].append(fact)

        return groups

    def _extract_numeric_context(self, statement: str) -> str:
        words = statement.lower().split()
        context_keywords = ["增长", "下降", "收入", "利润", "数量", "人口", "面积", "价格", "气温", "百分比", "比率",
                           "increase", "decrease", "revenue", "profit", "number", "population", "price", "temperature", "percent", "ratio"]
        for word in words:
            if any(kw in word for kw in context_keywords):
                return word
        return statement[:20].lower()

    def _extract_datetime_context(self, statement: str) -> str:
        year_pattern = r"\d{4}"
        years = re.findall(year_pattern, statement)
        if years:
            return years[0]
        return statement[:20].lower()

    def _has_numeric_conflict(self, fact_a: ExtractedFact, fact_b: ExtractedFact) -> bool:
        if not fact_a.numeric_values or not fact_b.numeric_values:
            return False

        for num_a in fact_a.numeric_values:
            for num_b in fact_b.numeric_values:
                if self._values_conflict(num_a, num_b):
                    return True

        return False

    def _values_conflict(self, num_a: NumericValue, num_b: NumericValue) -> bool:
        if num_a.unit != num_b.unit:
            if not self._are_compatible_units(num_a.unit, num_b.unit):
                return False

        try:
            val_a = float(num_a.value)
            val_b = float(num_b.value)

            if val_a == 0 and val_b == 0:
                return False

            larger = max(abs(val_a), abs(val_b))
            if larger > 0:
                relative_diff = abs(val_a - val_b) / larger
                if relative_diff > self.numeric_threshold:
                    return True

            return val_a != val_b
        except (ValueError, TypeError):
            return num_a.value != num_b.value

    def _are_compatible_units(self, unit_a: Optional[str], unit_b: Optional[str]) -> bool:
        if unit_a is None or unit_b is None:
            return True

        compatible_groups = [
            {"km", "m", "cm", "mm", "mile", "foot", "inch"},
            {"kg", "g", "mg", "lb", "pound", "ton"},
            {"°C", "°F", "℃", "℉"},
            {"%", "percent", "percentage"},
            {"年", "月", "日", "year", "month", "day"},
        ]

        for group in compatible_groups:
            if unit_a in group and unit_b in group:
                return True

        return False

    def _has_datetime_conflict(self, fact_a: ExtractedFact, fact_b: ExtractedFact) -> bool:
        if not fact_a.datetime_values or not fact_b.datetime_values:
            return False

        for dt_a in fact_a.datetime_values:
            for dt_b in fact_b.datetime_values:
                if self._datetime_conflict(dt_a, dt_b):
                    return True

        return False

    def _datetime_conflict(self, dt_a: DatetimeValue, dt_b: DatetimeValue) -> bool:
        try:
            val_a = getattr(dt_a, 'value', None) or getattr(dt_a, 'date', None)
            val_b = getattr(dt_b, 'value', None) or getattr(dt_b, 'date', None)

            if val_a is None or val_b is None:
                return False

            parsed_a = self._parse_datetime(str(val_a))
            parsed_b = self._parse_datetime(str(val_b))

            if parsed_a is None or parsed_b is None:
                return False

            days_diff = abs((parsed_a - parsed_b).days)

            if days_diff > self.datetime_threshold_days * 365:
                year_a = parsed_a.year
                year_b = parsed_b.year
                if year_a != year_b:
                    return True

            if days_diff > self.datetime_threshold_days:
                return True

            return False
        except Exception:
            val_a = getattr(dt_a, 'value', None) or getattr(dt_a, 'date', None)
            val_b = getattr(dt_b, 'value', None) or getattr(dt_b, 'date', None)
            return val_a != val_b

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        date_formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y年%m月%d日",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m",
            "%Y年%m月",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        year_match = re.match(r"(\d{4})", date_str)
        if year_match:
            try:
                return datetime(int(year_match.group(1)), 1, 1)
            except ValueError:
                pass

        return None

    def detect_conflicts(self, facts: List[ExtractedFact]) -> List[ValueConflict]:
        conflicts: List[ValueConflict] = []
        numeric_groups = self._group_by_context(facts)
        datetime_groups = self._group_by_datetime_context(facts)

        for context, group_facts in numeric_groups.items():
            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    if self._has_numeric_conflict(group_facts[i], group_facts[j]):
                        num_a = group_facts[i].numeric_values[0]
                        num_b = group_facts[j].numeric_values[0]
                        try:
                            diff = abs(float(num_a.value) - float(num_b.value))
                        except (ValueError, TypeError):
                            diff = None
                        conflicts.append(ValueConflict(
                            fact_a=group_facts[i],
                            fact_b=group_facts[j],
                            conflict_type="numeric",
                            value_a=str(num_a.value),
                            value_b=str(num_b.value),
                            difference=diff,
                            is_numeric=True,
                            is_datetime=False
                        ))

        for context, group_facts in datetime_groups.items():
            for i in range(len(group_facts)):
                for j in range(i + 1, len(group_facts)):
                    if self._has_datetime_conflict(group_facts[i], group_facts[j]):
                        dt_a = group_facts[i].datetime_values[0]
                        dt_b = group_facts[j].datetime_values[0]
                        val_a = getattr(dt_a, 'value', None) or getattr(dt_a, 'date', None)
                        val_b = getattr(dt_b, 'value', None) or getattr(dt_b, 'date', None)
                        parsed_a = self._parse_datetime(str(val_a)) if val_a else None
                        parsed_b = self._parse_datetime(str(val_b)) if val_b else None
                        diff_days = None
                        if parsed_a and parsed_b:
                            diff_days = abs((parsed_a - parsed_b).days)
                        conflicts.append(ValueConflict(
                            fact_a=group_facts[i],
                            fact_b=group_facts[j],
                            conflict_type="datetime",
                            value_a=str(val_a) if val_a else None,
                            value_b=str(val_b) if val_b else None,
                            difference=float(diff_days) if diff_days else None,
                            is_numeric=False,
                            is_datetime=True
                        ))

        return conflicts

    def get_conflicting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        conflicts = self.detect_conflicts(facts)
        conflicting_ids = set()
        for conflict in conflicts:
            conflicting_ids.add(conflict.fact_a.fact_id)
            conflicting_ids.add(conflict.fact_b.fact_id)
        return [f for f in facts if f.fact_id in conflicting_ids]

    def get_supporting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        conflicting = set(self.get_conflicting_facts(facts))
        return [f for f in facts if f not in conflicting]


def detect_value_collision(facts: List[ExtractedFact]) -> float:
    detector = ValueCollisionDetector()
    return detector.detect_value_collision(facts)
