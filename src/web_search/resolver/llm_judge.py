"""
DEPRECATED: Use collision.OrthogonalCollisionDetector instead.

This module is part of the v1/v2 architecture and will be removed in a future version.
v3 provides more sophisticated LLM-based collision detection via OrthogonalCollisionDetector.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Claim:
    result: any
    statement: str
    key_facts: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class FactCollision:
    collision_id: str
    claims: List[Claim]
    resolved_claim: Optional[Claim] = None
    priority_rule_used: str = ""
    consensus_degree: float = 0.0

@dataclass
class CollisionJudgment:
    collision_id: str
    winner: str
    confidence: float
    reason: str
    safety_score: float
    ranking: List[str] = field(default_factory=list)
    consensus_level: str = "medium"
    warnings: List[str] = field(default_factory=list)

class LLMCollisionJudge:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    COLLISION_PROMPT_TEMPLATE = """你是一个事实核查专家。请分析以下碰撞的多个 Claims，判断哪个更可信。

## 用户原始查询
{original_query}

## 碰撞 Claims

{claims_text}

## 裁决标准 (按优先级排序)

1. **权威性**: 官方机构 > 知名媒体 > KOL > 个人
2. **时效性**: 最新的信息优先，但也要考虑信息的历史稳定性
3. **一致性**: 与其他可靠信源一致的结论更可信
4. **具体性**: 包含具体数据、来源的结论更可信
5. **安全性**: 涉及潜在风险的结论需要更高标准验证

## 输出要求

请输出 JSON 格式：
{{
    "winner": "A|B|C...",
    "confidence": 0.0-1.0,
    "reason": "裁决理由",
    "safety_score": 0-10,
    "warnings": ["警告1", "警告2"]
}}

注意:
- 如果双方都有合理依据，选择更安全、更保守的结论
- 如果一方明显更权威，选择该方
- 如果无法判断，给出 confidence: 0.5
"""

    async def judge(
        self,
        collision: FactCollision,
        original_query: str
    ) -> CollisionJudgment:
        claims_text = self._format_claims(collision.claims)
        prompt = self.COLLISION_PROMPT_TEMPLATE.format(
            original_query=original_query,
            claims_text=claims_text
        )

        if self.llm_client:
            response = await self.llm_client.complete(prompt)
            return self._parse_judgment(collision.collision_id, response)

        return CollisionJudgment(
            collision_id=collision.collision_id,
            winner="A" if collision.claims else "",
            confidence=0.5,
            reason="No LLM client available, using default",
            safety_score=5.0
        )

    async def judge_batch(
        self,
        collisions: List[FactCollision],
        original_query: str
    ) -> List[CollisionJudgment]:
        judgments = []
        for collision in collisions:
            judgment = await self.judge(collision, original_query)
            judgments.append(judgment)
        return judgments

    def _format_claims(self, claims: List[Claim]) -> str:
        claims_text = []
        for i, claim in enumerate(claims):
            claim_letter = chr(ord('A') + i)
            claims_text.append(
                f"### Claim {claim_letter}\n"
                f"- 信源: {claim.result.source_name if hasattr(claim.result, 'source_name') else 'Unknown'}\n"
                f"- 内容: {claim.statement[:100]}..."
            )
        return "\n".join(claims_text)

    def _parse_judgment(self, collision_id: str, response: str) -> CollisionJudgment:
        import json
        import re

        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return CollisionJudgment(
                    collision_id=collision_id,
                    winner=data.get("winner", ""),
                    confidence=data.get("confidence", 0.5),
                    reason=data.get("reason", ""),
                    safety_score=data.get("safety_score", 5.0),
                    warnings=data.get("warnings", [])
                )
        except:
            pass

        return CollisionJudgment(
            collision_id=collision_id,
            winner="A",
            confidence=0.5,
            reason="Failed to parse LLM response",
            safety_score=5.0
        )

    def judge_sync(
        self,
        collision: FactCollision,
        original_query: str
    ) -> CollisionJudgment:
        claims_text = self._format_claims(collision.claims)
        prompt = self.COLLISION_PROMPT_TEMPLATE.format(
            original_query=original_query,
            claims_text=claims_text
        )

        if self.llm_client:
            response = self.llm_client.complete_sync(prompt)
            return self._parse_judgment(collision.collision_id, response)

        return CollisionJudgment(
            collision_id=collision.collision_id,
            winner="A" if collision.claims else "",
            confidence=0.5,
            reason="No LLM client available, using default",
            safety_score=5.0
        )

    def judge_batch_sync(
        self,
        collisions: List[FactCollision],
        original_query: str
    ) -> List[CollisionJudgment]:
        judgments = []
        for collision in collisions:
            judgment = self.judge_sync(collision, original_query)
            judgments.append(judgment)
        return judgments
