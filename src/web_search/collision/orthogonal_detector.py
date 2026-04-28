from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from . import FactBucket, CollisionResult, ExtractedFact, TrustedFact
from .nli_collision import NLICollisionDetector
from .spo_collision import SPOCollisionDetector
from .value_collision import ValueCollisionDetector
from ..core.llm_client import LLMClientBase

logger = logging.getLogger(__name__)


@dataclass
class OrthogonalCollisionConfig:
    alpha: float = 0.4
    beta: float = 0.3
    gamma: float = 0.3
    threshold: float = 0.3
    nli_threshold: float = 0.5
    spo_similarity_threshold: float = 0.8
    numeric_threshold: float = 0.2
    datetime_threshold_days: int = 1


DEFAULT_CONFIG = OrthogonalCollisionConfig()


class OrthogonalCollisionDetector:
    def __init__(
        self,
        config: Optional[OrthogonalCollisionConfig] = None,
        llm_client: Optional[LLMClientBase] = None
    ):
        self.config = config or DEFAULT_CONFIG
        self.llm_client = llm_client

        self.nli_detector = NLICollisionDetector(threshold=self.config.nli_threshold)
        self.spo_detector = SPOCollisionDetector(similarity_threshold=self.config.spo_similarity_threshold)
        self.value_detector = ValueCollisionDetector(
            numeric_threshold=self.config.numeric_threshold,
            datetime_threshold_days=self.config.datetime_threshold_days
        )

    def detect(self, bucket: FactBucket) -> CollisionResult:
        if not bucket.facts or len(bucket.facts) < 2:
            return CollisionResult(
                bucket_id=bucket.bucket_id,
                collision_coefficient=0.0,
                conflicting_facts=[],
                supporting_facts=bucket.facts,
                needs_llm_review=False
            )

        nli_conflict_ratio = self.nli_detector.detect_nli_collision(bucket.facts)
        spo_conflict_ratio = self.spo_detector.detect_spo_collision(bucket.facts)
        value_conflict_ratio = self.value_detector.detect_value_collision(bucket.facts)

        collision_coefficient = (
            self.config.alpha * nli_conflict_ratio +
            self.config.beta * spo_conflict_ratio +
            self.config.gamma * value_conflict_ratio
        )

        conflicting_facts = self._get_all_conflicting_facts(bucket.facts)
        supporting_facts = [f for f in bucket.facts if f not in conflicting_facts]

        needs_llm_review = collision_coefficient >= self.config.threshold
        llm_review_result = None

        if needs_llm_review and self.llm_client:
            llm_review_result = self._perform_llm_review(bucket, collision_coefficient)

        return CollisionResult(
            bucket_id=bucket.bucket_id,
            collision_coefficient=collision_coefficient,
            conflicting_facts=conflicting_facts,
            supporting_facts=supporting_facts,
            needs_llm_review=needs_llm_review,
            llm_review_result=llm_review_result,
            nli_conflict_ratio=nli_conflict_ratio,
            spo_conflict_ratio=spo_conflict_ratio,
            value_conflict_ratio=value_conflict_ratio
        )

    def _get_all_conflicting_facts(self, facts: List[ExtractedFact]) -> List[ExtractedFact]:
        nli_conflict_ids = {f.fact_id for f in self.nli_detector.get_contradiction_facts(facts)}
        spo_conflict_ids = {f.fact_id for f in self.spo_detector.get_conflicting_facts(facts)}
        value_conflict_ids = {f.fact_id for f in self.value_detector.get_conflicting_facts(facts)}

        all_conflict_ids = nli_conflict_ids | spo_conflict_ids | value_conflict_ids
        return [f for f in facts if f.fact_id in all_conflict_ids]

    def _perform_llm_review(
        self,
        bucket: FactBucket,
        collision_coefficient: float
    ) -> Optional[str]:
        if not self.llm_client:
            return None

        try:
            conflicting_facts = self._get_all_conflicting_facts(bucket.facts)

            prompt = self._build_llm_review_prompt(bucket, conflicting_facts, collision_coefficient)

            review_result = self.llm_client.complete_sync(prompt)

            return review_result

        except Exception as e:
            logger.error(f"LLM review failed: {e}")
            return None

    def _build_llm_review_prompt(
        self,
        bucket: FactBucket,
        conflicting_facts: List[ExtractedFact],
        collision_coefficient: float
    ) -> str:
        facts_text = "\n".join([
            f"- [{fact.fact_id}] {fact.statement} (source: {fact.source_domain or 'unknown'}, trust: {fact.trust_score:.1f})"
            for fact in bucket.facts
        ])

        conflicting_text = "\n".join([
            f"- [{fact.fact_id}] {fact.statement}"
            for fact in conflicting_facts
        ])

        prompt = f"""你是一个事实核查专家。请分析以下事实桶中的冲突情况。

事实桶 ID: {bucket.bucket_id}
碰撞系数: {collision_coefficient:.3f} (阈值: {self.config.threshold})

所有事实:
{facts_text}

存在冲突的事实:
{conflicting_text}

请分析:
1. 哪些事实是可信的（被多个可靠来源支持）？
2. 哪些事实是存疑的或错误的？
3. 最终的事实判定是什么？

请用中文回复，格式如下：
- 可信事实：[列出可信的事实ID和理由]
- 存疑事实：[列出存疑的事实ID和理由]
- 最终判定：[给出最终的事实结论]
"""
        return prompt

    def detect_batch(self, buckets: List[FactBucket]) -> List[CollisionResult]:
        return [self.detect(bucket) for bucket in buckets]

    def get_trusted_facts(self, buckets: List[FactBucket]) -> List[TrustedFact]:
        results = self.detect_batch(buckets)
        trusted_facts: List[TrustedFact] = []
        seen_statements: Dict[str, ExtractedFact] = {}

        for result in results:
            for fact in result.supporting_facts:
                normalized = self._normalize_statement(fact.statement)
                if normalized in seen_statements:
                    existing_fact = seen_statements[normalized]
                    if fact.confidence_score > existing_fact.confidence_score:
                        trusted_facts = [tf for tf in trusted_facts if tf.fact_id != existing_fact.fact_id]
                        trusted_facts.append(self._create_trusted_fact(fact, result))
                        seen_statements[normalized] = fact
                    continue

                verification_status = "verified"
                if result.needs_llm_review and result.llm_review_result:
                    verification_status = self._parse_verification_status(
                        fact.fact_id, result.llm_review_result
                    )

                evidence_sources = [
                    f.source_domain for f in result.supporting_facts
                    if f.source_domain and f.fact_id != fact.fact_id
                ]

                trusted_fact = TrustedFact(
                    fact_id=fact.fact_id,
                    statement=fact.statement,
                    confidence=fact.confidence_score,
                    evidence_sources=evidence_sources,
                    collision_info=result,
                    verification_status=verification_status
                )
                trusted_facts.append(trusted_fact)
                seen_statements[normalized] = fact

        return trusted_facts

    def _normalize_statement(self, statement: str) -> str:
        import re
        normalized = statement.strip()
        normalized = re.sub(r'[。！？\.!?]+$', '', normalized)
        normalized = re.sub(r'\s+', '', normalized)
        return normalized.lower()

    def _create_trusted_fact(self, fact, result) -> TrustedFact:
        verification_status = "verified"
        if result.needs_llm_review and result.llm_review_result:
            verification_status = self._parse_verification_status(
                fact.fact_id, result.llm_review_result
            )

        evidence_sources = [
            f.source_domain for f in result.supporting_facts
            if f.source_domain and f.fact_id != fact.fact_id
        ]

        return TrustedFact(
            fact_id=fact.fact_id,
            statement=fact.statement,
            confidence=fact.confidence_score,
            evidence_sources=evidence_sources,
            collision_info=result,
            verification_status=verification_status
        )

    def _parse_verification_status(self, fact_id: str, llm_review_result: str) -> str:
        if "可信" in llm_review_result or "verified" in llm_review_result.lower():
            return "verified"
        if "存疑" in llm_review_result or "disputed" in llm_review_result.lower():
            return "disputed"
        return "unverified"

    def get_collision_stats(self, buckets: List[FactBucket]) -> Dict[str, Any]:
        results = self.detect_batch(buckets)

        total_buckets = len(results)
        buckets_needing_review = sum(1 for r in results if r.needs_llm_review)
        avg_collision_coefficient = (
            sum(r.collision_coefficient for r in results) / total_buckets
            if total_buckets > 0 else 0.0
        )

        all_conflicting = []
        for r in results:
            all_conflicting.extend(r.conflicting_facts)

        return {
            "total_buckets": total_buckets,
            "buckets_needing_review": buckets_needing_review,
            "review_ratio": buckets_needing_review / total_buckets if total_buckets > 0 else 0.0,
            "avg_collision_coefficient": avg_collision_coefficient,
            "total_conflicting_facts": len(all_conflicting),
            "avg_nli_conflict": sum(r.nli_conflict_ratio for r in results) / total_buckets if total_buckets > 0 else 0.0,
            "avg_spo_conflict": sum(r.spo_conflict_ratio for r in results) / total_buckets if total_buckets > 0 else 0.0,
            "avg_value_conflict": sum(r.value_conflict_ratio for r in results) / total_buckets if total_buckets > 0 else 0.0,
        }
