from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SourceType(Enum):
    OFFICIAL = "official"
    MEDIA = "media"
    KOL = "kol"
    INDIVIDUAL = "individual"


class SourceLevel(Enum):
    NATIONAL = "national"
    PROVINCIAL = "provincial"
    MUNICIPAL = "municipal"
    LOCAL = "local"


class Classification(Enum):
    WHITE = "white"
    GRAY = "gray"
    BLACK = "black"


class TimeRange(Enum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_name: str
    source_domain: str
    source_type: SourceType
    source_level: SourceLevel
    published_date: Optional[str] = None
    author: Optional[str] = None
    粉丝数: Optional[int] = None
    classification: Classification = Classification.WHITE
    fact_cluster: Optional[str] = None
    relevance_score: float = 0.0
    final_score: float = 0.0
    external_rerank_score: Optional[float] = None

    def __hash__(self):
        return hash(self.url)


@dataclass
class Claim:
    result: SearchResult
    statement: str
    key_facts: List[str]
    timestamp: datetime


@dataclass
class FactCollision:
    collision_id: str
    claims: List[Claim]
    resolved_claim: Optional[Claim] = None
    priority_rule_used: str = ""
    consensus_degree: float = 0.0


@dataclass
class FactCluster:
    cluster_id: str
    topic: str
    claims: List[Claim] = field(default_factory=list)
    consensus_claim: Optional[Claim] = None
    disagreements: List[str] = field(default_factory=list)


@dataclass
class SearchOptions:
    max_results: int = 10
    time_range: Optional[str] = None
    source_types: Optional[List[SourceType]] = None
    classification: Optional[Classification] = None
    engines: Optional[List[str]] = None


@dataclass
class SearchResponse:
    query: str
    results: List[SearchResult]
    total_count: int
    search_time: float


@dataclass
class TrustedSearchResult:
    query: str
    response: SearchResponse
    classified_results: dict
    collisions: List[FactCollision]
    clusters: List[FactCluster]
    summary: str
    consensus_facts: List[str]
    disputed_facts: List[str]
    metadata: dict
    debug_info: Optional[dict] = None
    total_duration_ms: Optional[float] = None
