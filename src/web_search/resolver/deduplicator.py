"""
DEPRECATED: SearchOrchestratorV3 has its own built-in deduplication via _deduplicate_results().

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides built-in URL-based deduplication in the orchestrator.
"""
from typing import List, Set, Tuple
from ..core.models import SearchResult, Classification, SourceType, SourceLevel

class Deduplicator:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        if not results:
            return []

        url_deduped = self._deduplicate_by_url(results)
        similarity_deduped = self._deduplicate_by_similarity(url_deduped)

        return similarity_deduped

    def _deduplicate_by_url(self, results: List[SearchResult]) -> List[SearchResult]:
        seen_urls: Set[str] = set()
        unique_results: List[SearchResult] = []

        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
            else:
                existing = self._find_existing_by_url(unique_results, result.url)
                if existing and self._should_keep(result, existing):
                    unique_results.remove(existing)
                    unique_results.append(result)

        return unique_results

    def _deduplicate_by_similarity(self, results: List[SearchResult]) -> List[SearchResult]:
        if len(results) <= 1:
            return results

        to_remove: Set[int] = set()

        for i in range(len(results)):
            if i in to_remove:
                continue

            for j in range(i + 1, len(results)):
                if j in to_remove:
                    continue

                similarity = self._compute_title_similarity(
                    results[i].title,
                    results[j].title
                )

                if similarity >= self.similarity_threshold:
                    if self._should_keep(results[i], results[j]):
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
                        break

        return [r for idx, r in enumerate(results) if idx not in to_remove]

    def _compute_title_similarity(self, title1: str, title2: str) -> float:
        if not title1 or not title2:
            return 0.0

        words1 = set(self._normalize_text(title1).split())
        words2 = set(self._normalize_text(title2).split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        if len(intersection) >= min(len(words1), len(words2)) * 0.8:
            return max(jaccard, 0.9)

        return jaccard

    def _normalize_text(self, text: str) -> str:
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _should_keep(self, new_result: SearchResult, existing_result: SearchResult) -> bool:
        new_priority = self._get_priority_score(new_result)
        existing_priority = self._get_priority_score(existing_result)

        if new_priority != existing_priority:
            return new_priority > existing_priority

        if new_result.relevance_score != existing_result.relevance_score:
            return new_result.relevance_score > existing_result.relevance_score

        return len(new_result.snippet) > len(existing_result.snippet)

    def _get_priority_score(self, result: SearchResult) -> int:
        classification_scores = {
            Classification.WHITE: 3,
            Classification.GRAY: 2,
            Classification.BLACK: 1
        }
        classification_score = classification_scores.get(result.classification, 0)

        source_type_scores = {
            SourceType.OFFICIAL: 4,
            SourceType.MEDIA: 3,
            SourceType.KOL: 2,
            SourceType.INDIVIDUAL: 1
        }
        source_type_score = source_type_scores.get(result.source_type, 0)

        source_level_scores = {
            SourceLevel.NATIONAL: 4,
            SourceLevel.PROVINCIAL: 3,
            SourceLevel.MUNICIPAL: 2,
            SourceLevel.LOCAL: 1
        }
        source_level_score = source_level_scores.get(result.source_level, 0)

        return classification_score * 100 + source_type_score * 10 + source_level_score

    def _find_existing_by_url(self, results: List[SearchResult], url: str) -> SearchResult:
        for result in results:
            if result.url == url:
                return result
        return None
