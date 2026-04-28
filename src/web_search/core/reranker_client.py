from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os

@dataclass
class RerankResult:
    index: int
    score: float
    text: str

class RerankerClientBase(ABC):
    @property
    def provider_name(self) -> str:
        return "unknown"

    async def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> List[RerankResult]:
        raise NotImplementedError

class MockRerankerClient(RerankerClientBase):
    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def provider_name(self) -> str:
        return "mock"

    async def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> List[RerankResult]:
        import random
        results = []
        for i, text in enumerate(texts):
            results.append(RerankResult(
                index=i,
                score=random.random(),
                text=text
            ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results

class CohereRerankerClient(RerankerClientBase):
    def __init__(
        self,
        api_key: str,
        model: str = "rerank-english-v2.0",
        base_url: str = "https://api.cohere.ai"
    ):
        self._client = None
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "cohere"

    async def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> List[RerankResult]:
        if not self._client:
            import cohere
            self._client = cohere.Client(api_key=self._api_key, base_url=self._base_url)

        response = self._client.rerank(
            query=query,
            documents=texts,
            model=self._model,
            top_n=len(texts)
        )

        return [
            RerankResult(
                index=item.index,
                score=item.relevance_score,
                text=item.document.text if hasattr(item.document, 'text') else texts[item.index]
            )
            for item in response.results
        ]

class JinaRerankerClient(RerankerClientBase):
    def __init__(
        self,
        api_key: str,
        model: str = "jina-reranker-v1-base-en",
        base_url: str = "https://api.jina.ai"
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "jina"

    async def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> List[RerankResult]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/rerank",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": query,
                    "documents": texts,
                    "model": self._model,
                    "top_n": len(texts)
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        return [
            RerankResult(
                index=item["index"],
                score=item["relevance_score"],
                text=texts[item["index"]]
            )
            for item in data["results"]
        ]

class OpenAICompatibleRerankerClient(RerankerClientBase):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        batch_size: int = 32
    ):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._batch_size = batch_size

    @property
    def provider_name(self) -> str:
        return "openai-compatible"

    def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: str = None,
        instructions: str = None
    ) -> List[RerankResult]:
        scores = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            prompt = self._build_rerank_prompt(query, batch, search_query, instructions)
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512
            )
            batch_scores = self._parse_scores(response.choices[0].message.content, len(batch))
            for j, score in enumerate(batch_scores):
                scores.append(RerankResult(
                    index=i + j,
                    score=score,
                    text=batch[j]
                ))

        scores.sort(key=lambda x: x.score, reverse=True)
        return scores

    def _build_rerank_prompt(
        self,
        query: str,
        texts: List[str],
        search_query: str = None,
        instructions: str = None
    ) -> str:
        texts_str = "\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])

        context_parts = []
        if search_query:
            context_parts.append(f"搜索query: {search_query}")
        if instructions:
            context_parts.append(f"评分指令: {instructions}")
        context_str = "\n".join(context_parts)

        return f"""Given a query and a list of texts, rate each text's relevance to the query on a scale of 0-10.
根据query相关性、信源权威性、时效性综合评分。

{context_str}
当前Query: {query}

Texts:
{texts_str}

Respond with a JSON array of scores like: [0.85, 0.92, 0.45, ...]
Each score should be between 0 and 1, where 1 means highly relevant and 0 means not relevant at all.
Only output the JSON array, nothing else."""

    def _parse_scores(self, response: str, count: int) -> List[float]:
        import json
        import re
        try:
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                if len(scores) == count:
                    return scores
        except:
            pass
        return [0.5] * count

class DashScopeRerankerClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gte-rerank-v2",
        base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    @property
    def provider_name(self) -> str:
        return "dashscope"

    def rerank(
        self,
        query: str,
        texts: List[str],
        top_n: int = 10,
        search_query: str = None,
        instructions: str = None
    ) -> List[RerankResult]:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self._model,
                    "input": {
                        "query": query,
                        "documents": texts
                    },
                    "parameters": {
                        "return_documents": True
                    }
                }
            )
            response.raise_for_status()
            data = response.json()

        results = []
        if "output" in data and "results" in data["output"]:
            for item in data["output"]["results"]:
                results.append(RerankResult(
                    index=item["index"],
                    score=item["relevance_score"],
                    text=texts[item["index"]] if item["index"] < len(texts) else ""
                ))
        elif "data" in data:
            for item in data["data"]:
                results.append(RerankResult(
                    index=item["index"],
                    score=item["relevance_score"],
                    text=texts[item["index"]] if item["index"] < len(texts) else ""
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results

def create_reranker_client(config: Dict[str, Any]) -> RerankerClientBase:
    if not config:
        return MockRerankerClient()

    ext_config = config.get("external_reranker", config)

    enabled = ext_config.get("enabled", True)

    if not enabled:
        return MockRerankerClient()

    provider = ext_config.get("provider", "openai-compatible")

    api_key = ext_config.get("api_key", "")
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")

    if provider == "cohere":
        return CohereRerankerClient(
            api_key=api_key,
            model=ext_config.get("model", "rerank-english-v2.0"),
            base_url=ext_config.get("base_url", "https://api.cohere.ai")
        )

    if provider == "jina":
        return JinaRerankerClient(
            api_key=api_key,
            model=ext_config.get("model", "jina-reranker-v1-base-en"),
            base_url=ext_config.get("base_url", "https://api.jina.ai")
        )

    model = ext_config.get("model", "gpt-4o")
    base_url = ext_config.get("base_url", "")
    if "gte-rerank" in model.lower():
        return DashScopeRerankerClient(
            api_key=api_key,
            model=model,
            base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        )
    elif "dashscope" in base_url.lower():
        return DashScopeRerankerClient(
            api_key=api_key,
            model=model,
            base_url=base_url
        )

    return OpenAICompatibleRerankerClient(
        api_key=api_key,
        model=model,
        base_url=ext_config.get("base_url", "https://api.openai.com/v1"),
        batch_size=ext_config.get("batch_size", 32)
    )
