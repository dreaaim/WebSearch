from datetime import datetime
from typing import Optional, Dict, Any
import math


class FreshnessScorer:
    def __init__(
        self,
        lambda_decay: float = 0.1,
        config: Optional[Dict[str, Any]] = None
    ):
        if config is not None:
            self.lambda_decay = config.get("lambda", config.get("lambda_decay", 0.1))
            self._use_legacy_config = True
            self._legacy_config = config
        else:
            self.lambda_decay = lambda_decay
            self._use_legacy_config = False
            self._legacy_config = None

    def calculate_freshness_score(self, publish_date: Optional[datetime]) -> float:
        if publish_date is None:
            return 0.5

        try:
            if isinstance(publish_date, str):
                publish_date = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))

            publish_date = publish_date.replace(tzinfo=None)
            days_old = (datetime.now() - publish_date).days

            if days_old < 0:
                return 1.0

            if self._use_legacy_config:
                return self._calculate_legacy_score(days_old)

            score = math.exp(-self.lambda_decay * days_old)
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def _calculate_legacy_score(self, days_old: int) -> float:
        if self._legacy_config is None:
            return 0.5

        period_7d_score = self._legacy_config.get("period_7d_score", 1.0)
        period_30d_score = self._legacy_config.get("period_30d_score", 0.8)
        period_90d_score = self._legacy_config.get("period_90d_score", 0.6)
        period_1y_score = self._legacy_config.get("period_1y_score", 0.4)
        older_score = self._legacy_config.get("older_score", 0.2)

        if days_old <= 7:
            return period_7d_score
        elif days_old <= 30:
            return period_30d_score
        elif days_old <= 90:
            return period_90d_score
        elif days_old <= 365:
            return period_1y_score
        else:
            return older_score