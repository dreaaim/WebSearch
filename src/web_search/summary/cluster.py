from typing import List, Dict
from ..core.models import SearchResult

class ResultCluster:
    def cluster(self, results: List[SearchResult]) -> List[List[SearchResult]]:
        clusters: Dict[str, List[SearchResult]] = {}

        for result in results:
            topic = self._extract_topic(result)
            if topic not in clusters:
                clusters[topic] = []
            clusters[topic].append(result)

        return list(clusters.values())

    def _extract_topic(self, result: SearchResult) -> str:
        text = f"{result.title} {result.snippet}"
        words = text.split()[:10]
        return " ".join(words)
