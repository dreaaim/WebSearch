import sys
import io
import json
from typing import Optional
from contextlib import asynccontextmanager

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web_search.core.orchestrator_v2 import SearchOrchestratorV2
from web_search.providers.searxng import SearXNGProvider
from web_search.classifier.source_classifier import SourceClassifier
from web_search.classifier.llm_classifier import LLMSourceClassifier
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge
from web_search.reranker.reranker import Reranker, RerankConfig
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.core.llm_client import create_llm_client
from web_search.core.embedding_client import create_embedding_client
from web_search.core.reranker_client import create_reranker_client
from web_search.config.settings import load_config


orchestrator: Optional[SearchOrchestratorV2] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询语句")
    debug: bool = Field(default=False, description="是否启用调试模式")
    debug_level: str = Field(default="verbose", description="调试级别: quiet, basic, verbose")
    debug_output: str = Field(default="stdout", description="调试输出位置: stdout, stderr, both")


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    score: float
    classification: str


class RewriteResult(BaseModel):
    intent: Optional[str] = None
    entities: list[str] = []
    time_range: Optional[str] = None
    rewritten_queries: list[str] = []


class CollisionJudgment(BaseModel):
    collision_id: str
    consensus_level: str
    confidence: float
    winner: str


class SearchResponse(BaseModel):
    query: str
    summary: str
    consensus_facts: list[str] = []
    disputed_facts: list[str] = []
    results: list[SearchResultItem] = []
    rewrite_result: Optional[RewriteResult] = None
    collision_judgments: list[CollisionJudgment] = []
    search_time: float
    total_duration_ms: float
    classified_counts: dict[str, int] = {}
    debug_info: dict = {}


def init_orchestrator():
    global orchestrator
    config = load_config("examples/server/configs")

    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})
    reranker_config = config.get("reranker", {})
    rewriter_config = config.get("rewriter", {})

    llm_client = create_llm_client(llm_config)
    embedding_client = create_embedding_client(embedding_config)
    reranker_client = create_reranker_client(reranker_config.get("external_reranker", {}))

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
    )

    source_classifier = SourceClassifier(
        whitelist=config.get("whitelist", []),
        blacklist=config.get("blacklist", [])
    )

    reranker_weights = reranker_config.get("weights", {
        "relevance": 0.3,
        "trustworthiness": 0.2,
        "freshness": 0.1,
        "authority": 0.1,
        "external": 0.3
    })
    reranker_freshness = reranker_config.get("freshness", {})
    reranker_top_k = reranker_config.get("top_k", 10)

    priority_rules = config.get("priority_rules", {})
    relevance_filter = priority_rules.get("relevance_filter", {})
    min_relevance_score = relevance_filter.get("min_score", 3.0)

    orchestrator = SearchOrchestratorV2(
        provider=provider,
        source_classifier=source_classifier,
        llm_classifier=LLMSourceClassifier(
            llm_client=llm_client,
            min_relevance_score=min_relevance_score
        ),
        query_rewriter=QueryRewriter(llm_client=llm_client),
        embedding_engine=EmbeddingSimilarityEngine(embedding_client=embedding_client),
        collision_judge=LLMCollisionJudge(llm_client=llm_client),
        reranker=Reranker(
            config=RerankConfig(
                weights=reranker_weights,
                external_rerank_weight=reranker_weights.get("external", 0.3),
                top_k=reranker_top_k
            ),
            freshness_config=reranker_freshness,
            reranker_client=reranker_client
        ),
        use_v2_features=True
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_orchestrator()
    yield


app = FastAPI(
    title="可信联网搜索系统 API",
    description="提供基于信源分层、碰撞检测和摘要生成的可信联网搜索服务",
    version="v1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "trusted-search-api"}


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = orchestrator.search_with_trust(
            request.query,
            debug=request.debug,
            debug_level=request.debug_level,
            debug_output=request.debug_output
        )

        rewrite_result_data = None
        rewrite_result = result.metadata.get("v2_metadata", {}).get("rewrite_result")
        if rewrite_result:
            rewritten_queries = []
            if hasattr(rewrite_result, 'structured_queries') and rewrite_result.structured_queries:
                rewritten_queries = [sq.query for sq in rewrite_result.structured_queries]
            elif hasattr(rewrite_result, 'rewritten_queries'):
                rewritten_queries = rewrite_result.rewritten_queries

            rewrite_result_data = RewriteResult(
                intent=getattr(rewrite_result, 'intent', None),
                entities=getattr(rewrite_result, 'entities', []) or [],
                time_range=getattr(rewrite_result, 'time_range', None),
                rewritten_queries=rewritten_queries
            )

        judgments = []
        v2_metadata = result.metadata.get("v2_metadata", {})
        for judgment in v2_metadata.get("collision_judgments", []):
            judgments.append(CollisionJudgment(
                collision_id=judgment.collision_id,
                consensus_level=judgment.consensus_level,
                confidence=judgment.confidence,
                winner=judgment.winner
            ))

        results_list = []
        for r in result.response.results:
            classification_label = "unknown"
            if hasattr(r, 'classification'):
                classification_label = r.classification.value if hasattr(r.classification, 'value') else str(r.classification)
            elif hasattr(r, 'source_info') and hasattr(r.source_info, 'source_type'):
                classification_label = "gray"

            score = getattr(r, 'final_score', None) or getattr(r, 'relevance_score', None) or getattr(r, 'external_rerank_score', None) or 0.0
            results_list.append(SearchResultItem(
                title=r.title,
                url=r.url,
                snippet=r.snippet,
                score=score,
                classification=classification_label
            ))

        return SearchResponse(
            query=result.query,
            summary=result.summary or "",
            consensus_facts=result.consensus_facts or [],
            disputed_facts=result.disputed_facts or [],
            results=results_list,
            rewrite_result=rewrite_result_data,
            collision_judgments=judgments,
            search_time=result.response.search_time,
            total_duration_ms=result.total_duration_ms,
            classified_counts={
                "white": len(result.classified_results.get('white', [])),
                "gray": len(result.classified_results.get('gray', [])),
                "black": len(result.classified_results.get('black', []))
            },
            debug_info=result.debug_info or {}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=SearchResponse)
async def search_get(
    query: str = Query(..., description="搜索查询语句"),
    debug: bool = Query(default=False, description="是否启用调试模式"),
    debug_level: str = Query(default="verbose", description="调试级别"),
    debug_output: str = Query(default="stdout", description="调试输出位置")
):
    return await search(SearchRequest(
        query=query,
        debug=debug,
        debug_level=debug_level,
        debug_output=debug_output
    ))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)