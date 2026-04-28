"""
DEPRECATED: Use collision.OrthogonalCollisionDetector instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated collision detection via OrthogonalCollisionDetector.
"""
from typing import List
from .priority_engine import PriorityEngine
from .claim import ClaimExtractor
from ..core.models import SearchResult, FactCollision, Claim


class FactResolver:
    """事实碰撞解决器"""

    def __init__(self, priority_engine: PriorityEngine = None):
        self.priority_engine = priority_engine or PriorityEngine()
        self.claim_extractor = ClaimExtractor()

    def detect_and_resolve(
        self,
        results: List[SearchResult]
    ) -> List[FactCollision]:
        """检测并解决所有碰撞"""
        claims = []
        for result in results:
            extracted_claims = self.claim_extractor.extract(result)
            claims.extend(extracted_claims)

        claim_groups = self._group_similar_claims(claims)

        collisions = []
        for group in claim_groups:
            if len(group) >= 2:
                collision = self.priority_engine.resolve_collision(group)
                collisions.append(collision)

        return collisions

    def _group_similar_claims(self, claims: List[Claim]) -> List[List[Claim]]:
        """将相似的claims分组"""
        groups = []
        used = set()

        for i, claim in enumerate(claims):
            if i in used:
                continue

            group = [claim]
            used.add(i)

            for j, other in enumerate(claims[i+1:], start=i+1):
                if j in used:
                    continue
                if self._are_claims_similar(claim, other):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        return groups

    def _are_claims_similar(self, c1: Claim, c2: Claim) -> bool:
        """判断两个claim是否描述同一事实"""
        words1 = set(c1.statement.lower().split())
        words2 = set(c2.statement.lower().split())
        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap > 0.6
