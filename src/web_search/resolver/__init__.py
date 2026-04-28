"""
Resolver Module - DEPRECATED
============================

.. deprecated::
    This module is deprecated and will be removed in a future version.
    Please use the following v3 modules instead:

    - Use :class:`collision.OrthogonalCollisionDetector` instead of :class:`FactResolver`
    - Use :class:`collision.NLICollisionDetector` instead of :class:`LLMCollisionJudge`
    - Use :class:`filter.EmbeddingScorer` instead of :class:`EmbeddingSimilarityEngine`
    - Use :class:`filter.HybridFilterEngine` instead of :class:`HybridSimilarityEngine`

    The v3 collision detection provides:
    - NLI (Natural Language Inference) based conflict detection
    - SPO (Subject-Predicate-Object) triple conflict detection
    - Numeric/Value conflict detection
    - ELO-based trust scoring via TrustRankLadder

Example migration:
    # Old (deprecated):
    from resolver import FactResolver, LLMCollisionJudge

    # New (recommended):
    from collision import OrthogonalCollisionDetector
"""

import warnings
import logging

logger = logging.getLogger(__name__)


class DeprecatedMixin:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            f"{self.__class__.__name__} is deprecated and will be removed in a future version. "
            f"Please migrate to v3 collision detection modules.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


from .fact_resolver import FactResolver
from .priority_engine import PriorityEngine, PriorityLevel
from .claim import ClaimExtractor, Claim
from .embedding_engine import EmbeddingClient, EmbeddingSimilarityEngine, MockEmbeddingClient
from .hybrid_similarity import HybridSimilarityEngine
from .llm_judge import LLMCollisionJudge, CollisionJudgment, FactCollision
from .deduplicator import Deduplicator

__all__ = [
    "FactResolver",
    "PriorityEngine",
    "PriorityLevel",
    "ClaimExtractor",
    "Claim",
    "EmbeddingClient",
    "EmbeddingSimilarityEngine",
    "MockEmbeddingClient",
    "HybridSimilarityEngine",
    "LLMCollisionJudge",
    "CollisionJudgment",
    "FactCollision",
    "Deduplicator",
]