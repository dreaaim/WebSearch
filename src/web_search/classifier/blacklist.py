from typing import List, Dict
import re
from ..core.models import SearchResult

class BlacklistManager:
    """黑名单管理器"""

    def __init__(self, rules: List[Dict]):
        self.rules = rules

    def is_blacklisted(self, result: SearchResult) -> bool:
        """检查是否在黑名单中"""
        for rule in self.rules:
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
