from typing import Optional, Dict


class TrustScorer:
    def __init__(self, trust_rank_ladder=None):
        self.trust_rank_ladder = trust_rank_ladder
        self._default_scores: Dict[str, float] = {
            "cctv.com": 0.95,
            "xinhuanet.com": 0.95,
            "people.com.cn": 0.93,
            "gov.cn": 0.90,
        }
        self._default_score = 0.5
        self._min_elo = 800
        self._max_elo = 1800

    def get_trust_score(self, source_domain: str) -> float:
        if not source_domain:
            return self._default_score

        source_domain = source_domain.lower()

        if self.trust_rank_ladder is not None:
            try:
                elo_score = self.trust_rank_ladder.get_score(source_domain)
                return self._normalize_elo_score(elo_score)
            except Exception:
                pass

        for trusted_domain, score in self._default_scores.items():
            if trusted_domain in source_domain:
                return score

        return self._default_score

    def _normalize_elo_score(self, elo_score: float) -> float:
        if elo_score <= self._min_elo:
            return 0.0
        if elo_score >= self._max_elo:
            return 1.0
        return (elo_score - self._min_elo) / (self._max_elo - self._min_elo)