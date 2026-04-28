from typing import List, Dict
import re
from ..core.models import SearchResult, Classification, SourceType, SourceLevel

class SourceClassifier:
    def __init__(
        self,
        whitelist: List[Dict],
        blacklist: List[Dict],
        kol_thresholds: Dict = None
    ):
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.kol_thresholds = kol_thresholds or {
            "big": 1000000,
            "medium": 100000,
            "small": 10000
        }

    def classify(self, result: SearchResult) -> Classification:
        if self._is_blacklisted(result):
            return Classification.BLACK
        if self._is_whitelisted(result):
            return Classification.WHITE
        return Classification.GRAY

    def _is_blacklisted(self, result: SearchResult) -> bool:
        for rule in self.blacklist:
            if self._match_rule(result, rule):
                return True
        return False

    def _is_whitelisted(self, result: SearchResult) -> bool:
        for rule in self.whitelist:
            if self._match_rule(result, rule):
                return True
        return False

    def _match_rule(self, result: SearchResult, rule: Dict) -> bool:
        domain = result.source_domain.lower()
        if "domain" in rule:
            if domain == rule["domain"].lower():
                return True
        if "domain_suffix" in rule:
            suffix = rule["domain_suffix"].lower()
            if domain.endswith(suffix):
                return True
        if "domain_pattern" in rule:
            pattern = rule["domain_pattern"].lower().replace("*", ".*")
            if re.match(pattern, domain):
                return True
        return False

    def classify_results(
        self,
        results: List[SearchResult]
    ) -> Dict[str, List[SearchResult]]:
        classified = {
            "white": [],
            "gray": [],
            "black": []
        }
        for result in results:
            classification = self.classify(result)
            result.classification = classification
            classified[classification.value].append(result)
        return classified

    def infer_source_type(self, result: SearchResult) -> SourceType:
        domain = result.source_domain.lower()
        government_suffixes = [".gov.cn", ".gov.", ".org.cn"]
        if any(domain.endswith(s) for s in government_suffixes):
            return SourceType.OFFICIAL
        if result.粉丝数 and result.粉丝数 > 0:
            if result.粉丝数 >= self.kol_thresholds["small"]:
                return SourceType.KOL
        media_patterns = [
            "news", "press", "media", "journal",
            "xinhuanet", "people.com", "cctv", "cctv"
        ]
        if any(p in domain for p in media_patterns):
            return SourceType.MEDIA
        return SourceType.INDIVIDUAL

    def infer_source_level(self, result: SearchResult) -> SourceLevel:
        domain = result.source_domain.lower()
        provincial_pattern = r"\.[a-z]{2}\.gov\.cn$"
        if re.search(provincial_pattern, domain):
            return SourceLevel.PROVINCIAL
        municipal_pattern = r"\.[a-z]{3,}\.gov\.cn$"
        if re.search(municipal_pattern, domain):
            return SourceLevel.MUNICIPAL
        national_patterns = [
            "gov.cn", "xinhuanet", "people.com.cn", "cctv.com",
            "gov.hk", "gov.tw", "org.cn"
        ]
        if any(p in domain for p in national_patterns):
            return SourceLevel.NATIONAL
        return SourceLevel.LOCAL
