from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ProviderConfig:
    enabled: bool
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    default_engines: Optional[List[str]] = None
    timeout: int = 30
    retry: int = 3
    max_results: int = 10
    include_answer: bool = True
    text: bool = True

@dataclass
class KOLThresholds:
    big: int = 1000000
    medium: int = 100000
    small: int = 10000

@dataclass
class PriorityRulesConfig:
    kol_thresholds: KOLThresholds
    source_type_order: Dict[str, int]
    source_level_order: Dict[str, int]
    classification_base: Dict[str, int]
    expertise_weight: Dict[str, float]

@dataclass
class WhitelistRule:
    name: str
    domain: Optional[str] = None
    domain_suffix: Optional[str] = None
    domain_pattern: Optional[str] = None
    type: str = "media"
    level: str = "national"
    tags: List[str] = None

@dataclass
class BlacklistRule:
    domain: Optional[str] = None
    domain_pattern: Optional[str] = None
    reason: str = ""
    severity: str = "medium"
