from typing import List, Tuple
from collections import Counter
from ..core.models import SearchResult

class ConsensusDetector:
    def __init__(self, min_consensus_ratio: float = 0.6):
        self.min_consensus_ratio = min_consensus_ratio

    def detect(
        self,
        cluster: List[SearchResult]
    ) -> Tuple[bool, str]:
        if len(cluster) < 2:
            return True, cluster[0].snippet if cluster else ""

        statements = [r.snippet[:100] for r in cluster]
        statement_hash = Counter(statements)
        most_common_count = statement_hash.most_common(1)[0][1]
        ratio = most_common_count / len(statements)

        if ratio >= self.min_consensus_ratio:
            return True, statement_hash.most_common(1)[0][0]

        return False, f"存在分歧: {len(cluster)}个不同观点"
