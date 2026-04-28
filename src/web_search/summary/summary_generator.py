from typing import List, Tuple, Dict
from ..core.models import SearchResult, FactCollision
from .cluster import ResultCluster
from .consensus import ConsensusDetector

class SummaryGenerator:
    def __init__(self, min_consensus_ratio: float = 0.6):
        self.min_consensus_ratio = min_consensus_ratio
        self.cluster = ResultCluster()
        self.consensus_detector = ConsensusDetector(min_consensus_ratio)

    def generate(
        self,
        results: List[SearchResult],
        collisions: List[FactCollision] = None
    ) -> Tuple[str, List[str], List[str]]:
        clusters = self.cluster.cluster(results)

        consensus_facts = []
        disputed_facts = []

        for cluster in clusters:
            is_consensus, fact = self.consensus_detector.detect(cluster)
            if is_consensus:
                consensus_facts.append(fact)
            else:
                disputed_facts.append(fact)

        summary = self._build_summary(clusters, consensus_facts, disputed_facts)

        return summary, consensus_facts, disputed_facts

    def _build_summary(
        self,
        clusters: List[List[SearchResult]],
        consensus_facts: List[str],
        disputed_facts: List[str]
    ) -> str:
        lines = []

        if consensus_facts:
            lines.append("【共识事实】")
            for fact in consensus_facts[:3]:
                lines.append(f"• {fact}")
            lines.append("")

        if disputed_facts:
            lines.append("【争议/分歧】")
            for fact in disputed_facts[:3]:
                lines.append(f"• {fact}")
            lines.append("")

        total = sum(len(c) for c in clusters)
        lines.append(f"共聚合 {total} 条来源，涵盖 {len(clusters)} 个不同角度的报道。")

        return "\n".join(lines)

    def generate_with_sources(
        self,
        result: SearchResult,
        related_results: List[SearchResult]
    ) -> str:
        classification_emoji = {
            "white": "✅",
            "gray": "⚠️",
            "black": "❌"
        }

        emoji = classification_emoji.get(result.classification.value, "⚠️")
        citation = f"{emoji} [{result.source_name}]({result.url})"

        return f"{result.snippet}\n来源: {citation}"
