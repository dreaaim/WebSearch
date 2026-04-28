from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import re

from ..core.llm_client import LLMClientBase


@dataclass
class RefineResult:
    result_index: int
    passed: bool
    confidence: float
    reason: str
    refined_content: Optional[str] = None


class LLMRefiner:
    CONTENT_REFINEMENT_PROMPT = """请分析以下搜索结果内容，判断其是否适合用于事实提取。

用户原始查询: {query}

待分析内容:
---
标题: {title}
URL: {url}
正文内容: {content[:2000]}...
---

请评估以下维度:
1. **内容相关性**: 内容是否与用户查询相关？是否包含用户需要的信息？
2. **内容质量**: 内容是否为原创报道、分析文章或官方发布？还是仅为列表、导航、评论等低价值内容？
3. **事实密度**: 内容是否包含可提取的事实信息（事件、数据、声明等）？
4. **可信度信号**: 内容来源是否可靠？发布时间是否新鲜？

请输出JSON格式的评估结果:
{{
    "passed": true/false,
    "confidence": 0.0-1.0,
    "reason": "简要说明通过或拒绝的原因",
    "refined_content": "如果需要精简或清理内容，提供精炼后的版本（可选）"
}}

评估标准:
- confidence >= 0.7 且 passed=true: 内容质量良好，可以进入事实提取
- confidence >= 0.5 且 passed=true: 内容可用，但事实密度可能较低
- passed=false: 内容不适合事实提取，应被过滤掉

请输出单个JSON对象，不要有多余文本。"""

    BATCH_REFINEMENT_PROMPT = """请批量分析以下搜索结果内容，判断每条是否适合用于事实提取。

用户原始查询: {query}

待分析内容列表:
{results_json}

请为每条内容输出JSON格式的评估结果:
{{
    "index": 数字索引（从0开始，与输入列表对应）,
    "passed": true/false,
    "confidence": 0.0-1.0,
    "reason": "简要说明通过或拒绝的原因"
}}

评估标准:
- passed=true: 内容质量良好或可用，可以进入事实提取
- passed=false: 内容不适合事实提取，应被过滤掉

请输出JSON数组，不要有多余文本。"""

    def __init__(
        self,
        llm_client: Optional[LLMClientBase] = None,
        min_confidence: float = 0.5,
        batch_size: int = 10,
        use_batch_mode: bool = True
    ):
        self._llm_client = llm_client
        self._min_confidence = min_confidence
        self._batch_size = batch_size
        self._use_batch_mode = use_batch_mode

    def refine(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        if not results:
            return []

        if self._use_batch_mode and len(results) > 1:
            return self._refine_batch(results, query)

        return self._refine_individual(results, query)

    def _refine_individual(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        refine_results = []

        for i, item in enumerate(results):
            title = self._get_title(item)
            url = self._get_url(item)
            content = self._get_content(item)

            if not self._llm_client:
                refine_results.append(RefineResult(
                    result_index=i,
                    passed=True,
                    confidence=0.5,
                    reason="LLM client not available, passing through"
                ))
                continue

            prompt = self.CONTENT_REFINEMENT_PROMPT.format(
                query=query,
                title=title,
                url=url,
                content=content
            )

            try:
                response = self._llm_client.complete_sync(prompt)
                parsed = self._parse_single_response(response)
                if parsed:
                    parsed.result_index = i
                    refine_results.append(parsed)
                else:
                    refine_results.append(RefineResult(
                        result_index=i,
                        passed=True,
                        confidence=0.5,
                        reason="Failed to parse LLM response, passing through"
                    ))
            except Exception as e:
                refine_results.append(RefineResult(
                    result_index=i,
                    passed=True,
                    confidence=0.5,
                    reason=f"LLM call failed: {str(e)}, passing through"
                ))

        return refine_results

    def _refine_batch(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        refine_results = []

        for i in range(0, len(results), self._batch_size):
            batch = results[i:i + self._batch_size]
            batch_results = self._process_single_batch(batch, query, start_index=i)
            refine_results.extend(batch_results)

        return refine_results

    def _process_single_batch(
        self,
        batch: List[Any],
        query: str,
        start_index: int
    ) -> List[RefineResult]:
        if not self._llm_client:
            return [
                RefineResult(
                    result_index=start_index + j,
                    passed=True,
                    confidence=0.5,
                    reason="LLM client not available, passing through"
                )
                for j in range(len(batch))
            ]

        results_json = self._build_batch_json(batch, start_index)
        prompt = self.BATCH_REFINEMENT_PROMPT.format(
            query=query,
            results_json=results_json
        )

        try:
            response = self._llm_client.complete_sync(prompt)
            parsed = self._parse_batch_response(response, len(batch), start_index)
            return parsed
        except Exception as e:
            return [
                RefineResult(
                    result_index=start_index + j,
                    passed=True,
                    confidence=0.5,
                    reason=f"LLM call failed: {str(e)}, passing through"
                )
                for j in range(len(batch))
            ]

    def _build_batch_json(self, results: List[Any], start_index: int) -> str:
        items = []
        for i, item in enumerate(results):
            title = self._get_title(item)
            url = self._get_url(item)
            content = self._get_content(item)

            items.append({
                "index": start_index + i,
                "title": title,
                "url": url,
                "content": content[:1500] if content else ""
            })
        return json.dumps(items, ensure_ascii=False, indent=2)

    def _parse_single_response(self, response: str) -> Optional[RefineResult]:
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                passed = bool(data.get("passed", True))
                confidence = float(data.get("confidence", 0.5))
                reason = str(data.get("reason", ""))
                refined_content = data.get("refined_content")

                if confidence < self._min_confidence:
                    passed = False

                return RefineResult(
                    result_index=0,
                    passed=passed,
                    confidence=confidence,
                    reason=reason,
                    refined_content=refined_content
                )
        except Exception:
            pass
        return None

    def _parse_batch_response(
        self,
        response: str,
        batch_size: int,
        start_index: int
    ) -> List[RefineResult]:
        default_results = [
            RefineResult(
                result_index=start_index + i,
                passed=True,
                confidence=0.5,
                reason="Failed to parse batch LLM response, passing through"
            )
            for i in range(batch_size)
        ]

        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                return default_results

            data = json.loads(json_match.group())
            if not isinstance(data, list):
                return default_results

            result_map = {}
            for item in data:
                if isinstance(item, dict):
                    idx = item.get("index")
                    if idx is not None:
                        passed = bool(item.get("passed", True))
                        confidence = float(item.get("confidence", 0.5))
                        reason = str(item.get("reason", ""))

                        if confidence < self._min_confidence:
                            passed = False

                        result_map[idx] = RefineResult(
                            result_index=idx,
                            passed=passed,
                            confidence=confidence,
                            reason=reason
                        )

            for idx in range(start_index, start_index + batch_size):
                if idx not in result_map:
                    result_map[idx] = RefineResult(
                        result_index=idx,
                        passed=True,
                        confidence=0.5,
                        reason="Index not in LLM response, passing through"
                    )

            return [result_map.get(start_index + i, default_results[i]) for i in range(batch_size)]

        except Exception:
            return default_results

    def _get_title(self, item: Any) -> str:
        if hasattr(item, 'title'):
            return item.title
        if hasattr(item, 'result') and hasattr(item.result, 'title'):
            return item.result.title
        return ""

    def _get_url(self, item: Any) -> str:
        if hasattr(item, 'url'):
            return item.url
        if hasattr(item, 'result') and hasattr(item.result, 'url'):
            return item.result.url
        return ""

    def _get_content(self, item: Any) -> str:
        if hasattr(item, 'content'):
            return item.content
        if hasattr(item, 'snippet'):
            return item.snippet
        if hasattr(item, 'result'):
            if hasattr(item.result, 'snippet'):
                return item.result.snippet
        return ""

    async def refine_async(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        if not results:
            return []

        if self._use_batch_mode and len(results) > 1:
            return await self._refine_batch_async(results, query)

        return await self._refine_individual_async(results, query)

    async def _refine_individual_async(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        refine_results = []

        for i, item in enumerate(results):
            title = self._get_title(item)
            url = self._get_url(item)
            content = self._get_content(item)

            if not self._llm_client:
                refine_results.append(RefineResult(
                    result_index=i,
                    passed=True,
                    confidence=0.5,
                    reason="LLM client not available, passing through"
                ))
                continue

            prompt = self.CONTENT_REFINEMENT_PROMPT.format(
                query=query,
                title=title,
                url=url,
                content=content
            )

            try:
                response = await self._llm_client.complete(prompt)
                parsed = self._parse_single_response(response)
                if parsed:
                    parsed.result_index = i
                    refine_results.append(parsed)
                else:
                    refine_results.append(RefineResult(
                        result_index=i,
                        passed=True,
                        confidence=0.5,
                        reason="Failed to parse LLM response, passing through"
                    ))
            except Exception:
                refine_results.append(RefineResult(
                    result_index=i,
                    passed=True,
                    confidence=0.5,
                    reason="LLM call failed, passing through"
                ))

        return refine_results

    async def _refine_batch_async(
        self,
        results: List[Any],
        query: str
    ) -> List[RefineResult]:
        refine_results = []

        for i in range(0, len(results), self._batch_size):
            batch = results[i:i + self._batch_size]
            batch_results = await self._process_single_batch_async(batch, query, start_index=i)
            refine_results.extend(batch_results)

        return refine_results

    async def _process_single_batch_async(
        self,
        batch: List[Any],
        query: str,
        start_index: int
    ) -> List[RefineResult]:
        if not self._llm_client:
            return [
                RefineResult(
                    result_index=start_index + j,
                    passed=True,
                    confidence=0.5,
                    reason="LLM client not available, passing through"
                )
                for j in range(len(batch))
            ]

        results_json = self._build_batch_json(batch, start_index)
        prompt = self.BATCH_REFINEMENT_PROMPT.format(
            query=query,
            results_json=results_json
        )

        try:
            response = await self._llm_client.complete(prompt)
            return self._parse_batch_response(response, len(batch), start_index)
        except Exception:
            return [
                RefineResult(
                    result_index=start_index + j,
                    passed=True,
                    confidence=0.5,
                    reason="LLM call failed, passing through"
                )
                for j in range(len(batch))
            ]

    def filter_results(
        self,
        results: List[Any],
        refine_results: List[RefineResult]
    ) -> List[Any]:
        passed_indices = {r.result_index for r in refine_results if r.passed}
        return [results[i] for i in range(len(results)) if i in passed_indices]

    def get_passed_results_with_content(
        self,
        results: List[Any],
        refine_results: List[RefineResult]
    ) -> List[tuple]:
        passed_results = []
        for i, refine_result in enumerate(refine_results):
            if refine_result.passed:
                content = self._get_content(results[i])
                if content and len(content) > 50:
                    passed_results.append((results[i], refine_result))
        return passed_results