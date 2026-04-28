from typing import Dict, List
from ..core.models import SearchResult, Classification

class RuleEngine:
    """分类规则引擎"""

    def __init__(self, rules: List[Dict] = None):
        self.rules = rules or []

    def match(self, result: SearchResult) -> Classification:
        """根据规则匹配返回分类"""
        for rule in self.rules:
            if self._match_rule(result, rule):
                return Classification(rule.get("classification", "gray"))
        return Classification.GRAY

    def _match_rule(self, result: SearchResult, rule: Dict) -> bool:
        domain = result.source_domain.lower()
        if "domain" in rule:
            return domain == rule["domain"].lower()
        if "domain_pattern" in rule:
            pattern = rule["domain_pattern"].lower().replace("*", ".*")
            return bool(__import__('re').match(pattern, domain))
        return False
