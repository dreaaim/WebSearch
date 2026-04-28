from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict

from .elo_calculator import ELOCalculator
from .source_registry import SourceRegistry, DEFAULT_INITIAL_SCORE


class TrustLevel(Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"

    @staticmethod
    def from_score(score: float) -> "TrustLevel":
        if score >= 1800:
            return TrustLevel.S
        elif score >= 1500:
            return TrustLevel.A
        elif score >= 1200:
            return TrustLevel.B
        elif score >= 1000:
            return TrustLevel.C
        elif score >= 800:
            return TrustLevel.D
        else:
            return TrustLevel.E


@dataclass
class TrustRankScore:
    source_name: str
    source_domain: str
    trust_score: float
    total_facts: int
    verified_facts: int
    falsified_facts: int

    @property
    def trust_level(self) -> TrustLevel:
        return TrustLevel.from_score(self.trust_score)

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_domain": self.source_domain,
            "trust_score": self.trust_score,
            "total_facts": self.total_facts,
            "verified_facts": self.verified_facts,
            "falsified_facts": self.falsified_facts,
            "trust_level": self.trust_level.value
        }


DEFAULT_OPPONENT_SCORE = 1200.0


class TrustRankLadder:
    def __init__(
        self,
        storage_path: Optional[str] = None,
        use_sqlite: bool = False
    ):
        self.elo_calculator = ELOCalculator()
        self.registry = SourceRegistry(
            storage_path=storage_path,
            use_sqlite=use_sqlite
        )
        self.registry.initialize()

    def register_new_source(
        self,
        source_name: str,
        source_domain: str,
        initial_score: float = DEFAULT_INITIAL_SCORE
    ) -> TrustRankScore:
        return self.registry.register(source_name, source_domain, initial_score)

    def get_trust_score(self, source_domain: str) -> float:
        score = self.registry.get_score(source_domain)
        if score is None:
            return DEFAULT_INITIAL_SCORE
        return score.trust_score

    def get_score(self, source_domain: str) -> Optional[TrustRankScore]:
        return self.registry.get_score(source_domain)

    def get_trust_level(self, source_domain: str) -> TrustLevel:
        score = self.get_trust_score(source_domain)
        return TrustLevel.from_score(score)

    def update_score(
        self,
        source_domain: str,
        verification_result: str,
        opponent_domain: Optional[str] = None,
        opponent_score: Optional[float] = None
    ) -> Optional[TrustRankScore]:
        score = self.registry.get_score(source_domain)
        if score is None:
            return None

        actual_result = self.elo_calculator.calculate_verification_result(verification_result)

        if verification_result.lower() in ["verified", "confirmed", "true", "correct"]:
            score.verified_facts += 1
        elif verification_result.lower() in ["falsified", "disproved", "false", "wrong"]:
            score.falsified_facts += 1

        score.total_facts += 1

        k_factor = self.elo_calculator.get_k_factor(score.total_facts)

        opponent = opponent_score if opponent_score is not None else (
            self.get_trust_score(opponent_domain) if opponent_domain else DEFAULT_OPPONENT_SCORE
        )

        new_score = self.elo_calculator.calculate_new_score(
            old_score=score.trust_score,
            opponent_score=opponent,
            actual_result=actual_result,
            k_factor=k_factor
        )

        score.trust_score = new_score

        self.registry.update_score(score)

        return score

    def get_leaderboard(
        self,
        limit: int = 100,
        min_score: float = 0.0
    ) -> list[TrustRankScore]:
        all_scores = self.registry.get_all_scores()
        filtered = [s for s in all_scores.values() if s.trust_score >= min_score]
        filtered.sort(key=lambda x: x.trust_score, reverse=True)
        return filtered[:limit]

    def get_sources_by_level(self, level: TrustLevel) -> list[TrustRankScore]:
        all_scores = self.registry.get_all_scores()
        return [s for s in all_scores.values() if s.trust_level == level]

    def get_stats(self) -> dict:
        all_scores = self.registry.get_all_scores()
        if not all_scores:
            return {
                "total_sources": 0,
                "level_distribution": {level.value: 0 for level in TrustLevel},
                "average_score": 0.0,
                "highest_score": 0.0,
                "lowest_score": 0.0
            }

        scores = list(all_scores.values())
        level_dist = {level.value: 0 for level in TrustLevel}
        for s in scores:
            level_dist[s.trust_level.value] += 1

        return {
            "total_sources": len(scores),
            "level_distribution": level_dist,
            "average_score": sum(s.trust_score for s in scores) / len(scores),
            "highest_score": max(s.trust_score for s in scores),
            "lowest_score": min(s.trust_score for s in scores)
        }