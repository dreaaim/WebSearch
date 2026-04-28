"""
DEPRECATED: Use collision.NLICollisionDetector and collision.ValueCollisionDetector instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated collision detection via OrthogonalCollisionDetector.
"""
from enum import IntEnum
from typing import List, Tuple, Dict
from ..core.models import Claim, FactCollision, SearchResult, Classification, SourceType, SourceLevel

class PriorityLevel(IntEnum):
    BLACK_INDIVIDUAL = 1
    BLACK_MEDIA = 2
    GRAY_INDIVIDUAL = 3
    GRAY_MEDIA = 4
    GRAY_KOL_SMALL = 5
    GRAY_KOL_MEDIUM = 6
    GRAY_KOL_BIG = 7
    WHITE_MUNICIPAL = 8
    WHITE_PROVINCIAL = 9
    WHITE_NATIONAL_OFFICIAL = 10

class PriorityEngine:
    """优先级规则引擎"""

    def __init__(self, kol_thresholds: Dict = None):
        self.kol_thresholds = kol_thresholds or {
            "big": 1000000,
            "medium": 100000,
            "small": 10000
        }

    def calculate_priority(self, result: SearchResult) -> Tuple[PriorityLevel, str]:
        """计算单个结果的优先级"""
        classification = result.classification
        source_type = result.source_type
        source_level = result.source_level
        followers = result.粉丝数 or 0

        if classification == Classification.BLACK:
            if source_type == SourceType.INDIVIDUAL:
                return PriorityLevel.BLACK_INDIVIDUAL, "黑名单-个人"
            return PriorityLevel.BLACK_MEDIA, "黑名单-媒体"

        if classification == Classification.GRAY:
            if source_type == SourceType.KOL:
                if followers >= self.kol_thresholds["big"]:
                    return PriorityLevel.GRAY_KOL_BIG, f"灰名单-KOL(粉丝{followers})"
                elif followers >= self.kol_thresholds["medium"]:
                    return PriorityLevel.GRAY_KOL_MEDIUM, f"灰名单-KOL(粉丝{followers})"
                return PriorityLevel.GRAY_KOL_SMALL, f"灰名单-KOL(粉丝{followers})"
            if source_type == SourceType.INDIVIDUAL:
                return PriorityLevel.GRAY_INDIVIDUAL, "灰名单-个人"
            return PriorityLevel.GRAY_MEDIA, "灰名单-媒体"

        if classification == Classification.WHITE:
            if source_level == SourceLevel.NATIONAL:
                return PriorityLevel.WHITE_NATIONAL_OFFICIAL, "白名单-国家级机构"
            if source_level == SourceLevel.PROVINCIAL:
                return PriorityLevel.WHITE_PROVINCIAL, "白名单-省级机构"
            if source_level == SourceLevel.MUNICIPAL:
                return PriorityLevel.WHITE_MUNICIPAL, "白名单-市级机构"

        return PriorityLevel.BLACK_INDIVIDUAL, "默认最低优先级"

    def resolve_collision(self, claims: List[Claim]) -> FactCollision:
        """解决碰撞"""
        if len(claims) < 2:
            return FactCollision(
                collision_id="single",
                claims=claims,
                resolved_claim=claims[0] if claims else None,
                priority_rule_used="single_claim",
                consensus_degree=1.0
            )

        scored_claims = []
        for claim in claims:
            priority, rule = self.calculate_priority(claim.result)
            scored_claims.append((claim, priority, rule))

        scored_claims.sort(key=lambda x: x[1], reverse=True)

        top_priority = scored_claims[0][1]
        top_count = sum(1 for _, p, _ in scored_claims if p == top_priority)
        consensus = top_count / len(claims)

        return FactCollision(
            collision_id=self._generate_collision_id(claims),
            claims=claims,
            resolved_claim=scored_claims[0][0],
            priority_rule_used=scored_claims[0][2],
            consensus_degree=consensus
        )

    def _generate_collision_id(self, claims: List[Claim]) -> str:
        topics = [c.statement[:50] for c in claims]
        return f"collision_{hash(tuple(topics))}"