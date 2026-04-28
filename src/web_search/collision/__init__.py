from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class NLILabel(Enum):
    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


@dataclass
class NumericValue:
    value: float
    unit: Optional[str] = None
    original_text: Optional[str] = None


@dataclass
class DatetimeValue:
    value: str
    parsed_value: Optional[str] = None
    original_text: Optional[str] = None


@dataclass
class SPOTriple:
    subject: str
    predicate: str
    object: str

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


@dataclass
class ExtractedFact:
    fact_id: str
    statement: str
    spo_triple: Optional[SPOTriple] = None
    nli_label: Optional[str] = None
    numeric_values: List[NumericValue] = field(default_factory=list)
    datetime_values: List[DatetimeValue] = field(default_factory=list)
    confidence_score: float = 0.0
    confidence_reason: Optional[str] = None
    source_name: Optional[str] = None
    source_domain: Optional[str] = None
    trust_score: float = 1000.0

    def __hash__(self):
        return hash(self.fact_id)


@dataclass
class FactBucket:
    bucket_id: str
    facts: List[ExtractedFact]
    cluster_embedding: Optional[List[float]] = None


@dataclass
class CollisionResult:
    bucket_id: str
    collision_coefficient: float
    conflicting_facts: List[ExtractedFact]
    supporting_facts: List[ExtractedFact]
    needs_llm_review: bool
    llm_review_result: Optional[str] = None
    nli_conflict_ratio: float = 0.0
    spo_conflict_ratio: float = 0.0
    value_conflict_ratio: float = 0.0


@dataclass
class TrustedFact:
    fact_id: str
    statement: str
    confidence: float
    evidence_sources: List[str] = field(default_factory=list)
    collision_info: Optional[CollisionResult] = None
    verification_status: str = "unverified"

    def to_dict(self) -> dict:
        return {
            "fact_id": self.fact_id,
            "statement": self.statement,
            "confidence": self.confidence,
            "evidence_sources": self.evidence_sources,
            "verification_status": self.verification_status,
            "collision_info": {
                "collision_coefficient": self.collision_info.collision_coefficient,
                "needs_llm_review": self.collision_info.needs_llm_review
            } if self.collision_info else None
        }
