from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import re

try:
    import re2 as re_re
    HAS_RE2 = True
except ImportError:
    HAS_RE2 = False
    re_re = re

from ..core.llm_client import LLMClientBase, create_llm_client
from ..config.settings import Settings


@dataclass
class NumericValue:
    value: float
    unit: Optional[str]
    context: str

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "unit": self.unit,
            "context": self.context
        }


@dataclass
class DatetimeValue:
    date: datetime
    context: str

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "context": self.context
        }


class ValueExtractor:
    PERCENTAGE_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*percent(?:age)?',
        r'(\d+(?:\.\d+)?)\s*个百分点',
    ]

    NUMBER_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*(万|亿|千|百|百万|千万|十|个|件|名|位|人次|人|元|美元|欧元|英镑|日元)?',
        r'(\d+(?:,\d{3})*(?:\.\d+)?)',
    ]

    DATE_PATTERNS = [
        (r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})[日号]?', '%Y-%m-%d'),
        (r'(\d{4})[-/年](\d{1,2})[-/月]', '%Y-%m'),
        (r'(\d{4})年', '%Y'),
        (r'(\d{1,2})[-/月](\d{1,2})[日号]?', '%m-%d'),
        (r'(?:上|下)半年', None),
        (r'(?:第[一二三四]季度|Q[1-4])', None),
    ]

    def __init__(
        self,
        use_llm_fallback: bool = True,
        llm_client: Optional[LLMClientBase] = None,
        settings: Optional[Settings] = None
    ):
        self._use_llm_fallback = use_llm_fallback
        self._llm_client = llm_client
        self._settings = settings
        self._percent_re = re.compile('|'.join(self.PERCENTAGE_PATTERNS), re.IGNORECASE)
        self._number_re = re.compile('|'.join(self.NUMBER_PATTERNS))

    def extract_values(self, text: str) -> Tuple[List[NumericValue], List[DatetimeValue]]:
        return self.extract_values_sync(text)

    def extract_values_sync(self, text: str) -> Tuple[List[NumericValue], List[DatetimeValue]]:
        numeric_values = self._extract_numeric_values(text)
        datetime_values = self._extract_datetime_values(text)
        return numeric_values, datetime_values

    def _extract_numeric_values(self, text: str) -> List[NumericValue]:
        numeric_values: List[NumericValue] = []

        for match in self._percent_re.finditer(text):
            value_str = match.group(1)
            if value_str is None:
                continue
            try:
                value = float(value_str)
                context = self._get_context(text, match.start(), match.end())
                numeric_values.append(NumericValue(
                    value=value,
                    unit="%",
                    context=context
                ))
            except ValueError:
                continue

        number_matches = list(self._number_re.finditer(text))
        for match in number_matches:
            value_str = match.group(1)
            if value_str is None:
                continue
            value_str = value_str.replace(',', '')
            try:
                value = float(value_str)
                if value > 1000 or len(match.group(2) or '') > 0:
                    unit = match.group(2) if match.group(2) else None
                    context = self._get_context(text, match.start(), match.end())
                    if unit or value > 1000:
                        numeric_values.append(NumericValue(
                            value=value,
                            unit=unit,
                            context=context
                        ))
            except ValueError:
                continue

        numeric_values.sort(key=lambda x: abs(x.value), reverse=True)

        return numeric_values

    def _extract_datetime_values(self, text: str) -> List[DatetimeValue]:
        datetime_values: List[DatetimeValue] = []

        for pattern, date_format in self.DATE_PATTERNS:
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(text):
                date_obj = self._parse_date_match(match, date_format)
                if date_obj is not None:
                    context = self._get_context(text, match.start(), match.end())
                    datetime_values.append(DatetimeValue(
                        date=date_obj,
                        context=context
                    ))

        special_date_patterns = [
            (r'昨天', lambda: self._days_ago(1)),
            (r'今天', lambda: self._days_ago(0)),
            (r'明天', lambda: self._days_ago(-1)),
            (r'上周', lambda: self._days_ago(7)),
            (r'下周', lambda: self._days_ago(-7)),
            (r'上周', lambda: self._days_ago(7)),
            (r'本月', lambda: self._month_start()),
            (r'上月', lambda: self._last_month_start()),
            (r'今年', lambda: self._year_start()),
            (r'去年', lambda: self._last_year_start()),
        ]

        for pattern, date_func in special_date_patterns:
            regex = re.compile(pattern)
            for match in regex.finditer(text):
                date_obj = date_func()
                context = self._get_context(text, match.start(), match.end())
                datetime_values.append(DatetimeValue(
                    date=date_obj,
                    context=context
                ))

        datetime_values.sort(key=lambda x: x.date, reverse=True)

        return datetime_values

    def _parse_date_match(self, match, date_format: Optional[str]):
        try:
            if date_format:
                return datetime.strptime(match.group(), date_format)

            full_match = match.group()
            if '季度' in full_match or full_match.startswith('Q'):
                year = datetime.now().year
                if '一' in full_match or 'Q1' in full_match:
                    return datetime(year, 1, 1)
                elif '二' in full_match or 'Q2' in full_match:
                    return datetime(year, 4, 1)
                elif '三' in full_match or 'Q3' in full_match:
                    return datetime(year, 7, 1)
                elif '四' in full_match or 'Q4' in full_match:
                    return datetime(year, 10, 1)

            if '上' in full_match and '半' in full_match:
                year = datetime.now().year
                return datetime(year, 1, 1)
            elif '下' in full_match and '半' in full_match:
                year = datetime.now().year
                return datetime(year, 7, 1)

            return None
        except (ValueError, AttributeError):
            return None

    def _days_ago(self, days: int) -> datetime:
        from datetime import timedelta
        return datetime.now() - timedelta(days=days)

    def _month_start(self) -> datetime:
        now = datetime.now()
        return datetime(now.year, now.month, 1)

    def _last_month_start(self) -> datetime:
        now = datetime.now()
        if now.month == 1:
            return datetime(now.year - 1, 12, 1)
        return datetime(now.year, now.month - 1, 1)

    def _year_start(self) -> datetime:
        return datetime(datetime.now().year, 1, 1)

    def _last_year_start(self) -> datetime:
        return datetime(datetime.now().year - 1, 1, 1)

    def _get_context(self, text: str, start: int, end: int) -> str:
        context_start = max(0, start - 30)
        context_end = min(len(text), end + 30)
        context = text[context_start:context_end]
        context = context.replace('\n', ' ').strip()
        if context_start > 0:
            context = '...' + context
        if context_end < len(text):
            context = context + '...'
        return context

    async def extract_values_async(self, text: str) -> Tuple[List[NumericValue], List[DatetimeValue]]:
        return self.extract_values_sync(text)

    def _extract_with_llm(self, text: str) -> Tuple[List[NumericValue], List[DatetimeValue]]:
        if self._llm_client is None:
            if self._settings:
                self._llm_client = create_llm_client(
                    self._settings.model_dump().get("llm", {})
                )
            else:
                self._llm_client = create_llm_client({})

        prompt = f"""Extract numeric values and dates from the following text.
For each value found, specify:
- type: numeric or datetime
- value: the actual number or date string
- unit: for numbers (e.g., %, 个, 元) or None for dates
- context: the surrounding text

Return in JSON format.

Text: {text}

Values:"""

        try:
            response = self._llm_client.complete_sync(prompt)
            return self._parse_llm_response(response)
        except Exception:
            return [], []

    def _parse_llm_response(self, response: str) -> Tuple[List[NumericValue], List[DatetimeValue]]:
        import json
        numeric_values: List[NumericValue] = []
        datetime_values: List[DatetimeValue] = []

        try:
            data = json.loads(response)
            if isinstance(data, list):
                for item in data:
                    if item.get('type') == 'numeric':
                        numeric_values.append(NumericValue(
                            value=float(item['value']),
                            unit=item.get('unit'),
                            context=item.get('context', '')
                        ))
                    elif item.get('type') == 'datetime':
                        date_str = item.get('value', '')
                        parsed = self._parse_date_string(date_str)
                        if parsed:
                            datetime_values.append(DatetimeValue(
                                date=parsed,
                                context=item.get('context', '')
                            ))
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        return numeric_values, datetime_values

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日',
            '%Y-%m', '%Y/%m', '%Y年%m月',
            '%Y', '%Y年'
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None