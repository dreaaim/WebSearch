# 可信联网搜索系统使用指南

## 一、系统概述

本系统为 AI 应用提供实时、可信、可验证的网络信息获取能力，v2 版本通过引入 LLM 和 Embedding 模型增强系统的语义理解能力。

- **查询改写**：QueryRewriter - 意图理解、查询发散、查询增强
- **信源可信**：LLMSourceClassifier - LLM 驱动的信源分类与相关性判断
- **语义碰撞**：Embedding 语义相似度 + LLM Judge 智能裁决
- **结果优化**：Reranker 综合权重重排序

### v1 vs v2 流程对比

```
v1 流程:
用户查询 ──→ 搜索 ──→ 规则筛选 ──→ Jaccard碰撞 ──→ 返回

v2 流程:
用户查询 ──→ 改写 ──→ 搜索 ──→ LLM筛选 ──→ Embedding碰撞 ──→ LLM裁决 ──→ 重排 ──→ 返回
```

---

## 二、基础搜索功能

### 2.1 直接使用 SearXNG Provider

如果你只需要基本的搜索功能，可以直接使用 `SearXNGProvider`：

```python
from web_search.providers.searxng import SearXNGProvider
from web_search.core.models import SearchOptions

provider = SearXNGProvider(
    base_url="http://localhost:8080",
    default_engines=["google", "bing"]
)

options = SearchOptions(max_results=10)
response = provider.search("人工智能最新发展", options)

print(f"查询: {response.query}")
print(f"结果数: {response.total_count}")
print(f"耗时: {response.search_time:.2f}秒")

for result in response.results:
    print(f"- {result.title}")
    print(f"  URL: {result.url}")
    print(f"  摘要: {result.snippet[:100]}...")
```

### 2.2 SearchOptions 配置

`SearchOptions` 类支持以下配置：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| max_results | int | 10 | 最大结果数 |
| time_range | str | None | 时间范围：day/week/month/year |
| source_types | list | None | 信源类型过滤 |
| classification | Classification | None | 分层过滤 |
| engines | list | None | 指定搜索引擎 |

---

## 三、v2 可信搜索功能

### 3.1 使用 SearchOrchestratorV2

`SearchOrchestratorV2` 是 v2 系统的核心调度中心，提供完整的可信搜索流程：

```python
import asyncio
from web_search.core.orchestrator import SearchOrchestratorV2
from web_search.providers.searxng import SearXNGProvider
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.classifier.llm_classifier import LLMSourceClassifier
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge
from web_search.reranker.reranker import Reranker
from web_search.core.llm_client import LLMWrapper
from web_search.config.settings import load_config

async def main():
    config = load_config("configs")
    llm_config = config.get("llm", {})
    embedding_config = config.get("embedding", {})

    llm_client = LLMWrapper(llm_config)
    embedding_client = EmbeddingClient(embedding_config)

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
        default_engines=["google", "bing"]
    )

    orchestrator = SearchOrchestratorV2(
        provider=provider,
        query_rewriter=QueryRewriter(llm_client=llm_client),
        source_classifier=LLMSourceClassifier(llm_client=llm_client),
        embedding_engine=EmbeddingSimilarityEngine(embedding_client=embedding_client),
        collision_judge=LLMCollisionJudge(llm_client=llm_client),
        reranker=Reranker()
    )

    result = await orchestrator.search_with_trust_v2("2024年AI大模型最新进展")

    print(f"查询: {result.query}")
    print(f"改写查询: {result.metadata['rewrite_result'].rewritten_queries}")
    print(f"重排后结果数: {len(result.response.results)}")
    print(f"摘要: {result.summary}")

asyncio.run(main())
```

### 3.2 v2 完整流程说明

v2 搜索流程包含以下步骤：

1. **查询改写 (QueryRewriter)**：分析用户意图，生成多个不同角度的查询
2. **多路搜索**：并发执行多个改写查询
3. **LLM 筛选分类 (LLMSourceClassifier)**：使用 LLM 进行信源提取、相关性判断、黑白名单查询
4. **Embedding 碰撞检测**：计算语义相似度，发现信息碰撞
5. **LLM 碰撞裁决 (LLMCollisionJudge)**：智能裁决冲突信息
6. **Reranker 重排序**：综合权重计算，返回最优排序结果
7. **摘要生成**：生成带来源标注的共识摘要

### 3.3 访问结果元数据

v2 结果包含丰富的元数据信息：

```python
result = await orchestrator.search_with_trust_v2("人工智能最新发展")

print(f"=== 改写查询 ===")
print(f"原始查询: {result.metadata['rewrite_result'].original_query}")
print(f"改写查询: {result.metadata['rewrite_result'].rewritten_queries}")
print(f"意图类型: {result.metadata['rewrite_result'].intent}")

print(f"\n=== 权重配置 ===")
print(f"相关性权重: {result.metadata['rerank_weights']['relevance']}")
print(f"可信度权重: {result.metadata['rerank_weights']['trustworthiness']}")
print(f"时效性权重: {result.metadata['rerank_weights']['freshness']}")
print(f"权威性权重: {result.metadata['rerank_weights']['authority']}")
```

---

## 四、信源分类结果解读

### 4.1 分类体系

系统将搜索结果分为三个可信度层级：

| 分类 | 说明 | 示例 |
|------|------|------|
| WHITE（白名单） | 高可信信源 | 政府官网(.gov.cn)、权威媒体(新华网、人民网) |
| GRAY（灰名单） | 中等可信信源 | 普通媒体、自媒体 |
| BLACK（黑名单） | 不可信信源 | 已核实虚假源、内容农场 |

### 4.2 访问分类结果

```python
result = await orchestrator.search_with_trust_v2("气候变化最新报告")

white_results = result.classified_results["white"]
gray_results = result.classified_results["gray"]
black_results = result.classified_results["black"]

print("=== 高可信来源 (白名单) ===")
for r in white_results:
    print(f"[{r.source_info.source_type.value}] {r.result.title}")
    print(f"  信源: {r.source_info.source_name} | 相关性: {r.relevance_score}")

print("\n=== 中等可信来源 (灰名单) ===")
for r in gray_results[:3]:
    print(f"[{r.source_info.source_type.value}] {r.result.title}")

print("\n=== 不可信来源 (黑名单) ===")
for r in black_results:
    print(f"[{r.source_info.source_type.value}] {r.result.title}")
```

### 4.3 信源类型

每个结果都有 `source_info.source_type` 属性：

| 类型 | 说明 |
|------|------|
| OFFICIAL | 政府机构 |
| MEDIA | 媒体 |
| KOL | 关键意见领袖 |
| INDIVIDUAL | 个人/自媒体 |

### 4.4 信源层级

每个结果都有 `source_info.source_level` 属性：

| 层级 | 说明 |
|------|------|
| NATIONAL | 国家级 |
| PROVINCIAL | 省级 |
| MUNICIPAL | 市级 |
| LOCAL | 地方/县级 |

---

## 五、碰撞检测与解决

### 5.1 什么是信息碰撞

当多个信源对同一事件提供不同甚至矛盾的信息时，系统会检测到"碰撞"，并根据优先级规则进行裁决。

### 5.2 CollisionJudgment 数据结构

```python
@dataclass
class CollisionJudgment:
    collision_id: str           # 碰撞唯一标识
    winner: str                 # 获胜方 (A/B 或 claim_id)
    confidence: float           # 置信度 (0-1)
    reason: str                 # 裁决理由
    safety_score: float         # 安全性评分 (0-10)
    ranking: List[str]          # 多方排序
    consensus_level: str        # 共识度: high/medium/low
    warnings: List[str]         # 警告信息
```

### 5.3 访问碰撞结果

```python
result = await orchestrator.search_with_trust_v2("某科技公司最新财报")

print(f"检测到碰撞: {len(result.collisions)} 个")

for collision in result.collisions:
    judgment = result.judgments.get(collision.collision_id)
    if judgment:
        print(f"\n=== 碰撞 {collision.collision_id} ===")
        print(f"共识度: {judgment.consensus_level}")
        print(f"置信度: {judgment.confidence:.1%}")
        print(f"安全性评分: {judgment.safety_score}/10")
        print(f"裁决理由: {judgment.reason}")
        if judgment.warnings:
            print(f"警告: {judgment.warnings}")
```

### 5.4 裁决优先级

LLM 碰撞裁决器按以下标准进行裁决：

1. **权威性**：官方机构 > 知名媒体 > KOL > 个人
2. **时效性**：最新信息优先，考虑历史稳定性
3. **一致性**：与其他可靠信源一致的结论更可信
4. **具体性**：包含具体数据、来源的结论更可信
5. **安全性**：涉及潜在风险的结论需要更高标准验证

---

## 六、摘要生成

### 6.1 摘要输出结构

`TrustedSearchResult` 的摘要相关字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| summary | str | 生成的摘要文本 |
| consensus_facts | List[str] | 共识事实列表 |
| disputed_facts | List[str] | 争议事实列表 |

### 6.2 访问摘要内容

```python
result = await orchestrator.search_with_trust_v2("新能源汽车市场分析")

print("=== 系统摘要 ===")
print(result.summary)

print("\n=== 共识事实 ===")
for fact in result.consensus_facts:
    print(f"✓ {fact}")

print("\n=== 争议事实 ===")
for fact in result.disputed_facts:
    print(f"⚠ {fact}")
```

### 6.3 带来源标注的摘要

为每个结果生成带来源标注的摘要：

```python
for classified_result in result.classified_results["white"][:5]:
    annotated = result.summary_generator.generate_with_sources(
        classified_result.result,
        related_results=[]
    )
    print(annotated)
    print("---")
```

---

## 七、配置自定义

### 7.1 修改 LLM 配置 (llm.yaml)

```yaml
llm:
  openai:
    model: "gpt-4o"
    api_base: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    temperature: 0.3
    max_tokens: 2048
```

### 7.2 修改 Embedding 配置 (embedding.yaml)

```yaml
embedding:
  openai:
    model: "text-embedding-3-small"
    dimension: 1536
    batch_size: 32
```

### 7.3 修改 Reranker 权重 (reranker.yaml)

```yaml
reranker:
  weights:
    relevance: 0.4
    trustworthiness: 0.3
    freshness: 0.15
    authority: 0.15
```

### 7.4 修改查询发散配置 (rewriter.yaml)

```yaml
query_rewriter:
  divergence:
    max_queries: 5
    intent_aware: true
  enhancement:
    enable_site_filter: true
    default_sites:
      - "gov.cn"
      - "xinhuanet.com"
    enable_time_filter: true
    default_time_range: "1y"
```

### 7.5 修改白名单

在 `configs/whitelist.yaml` 中添加新信源：

```yaml
whitelist:
  - name: "中国科学院"
    domain: "www.cas.cn"
    type: official
    level: national
    tags: ["科研", "学术"]
```

### 7.6 修改黑名单

在 `configs/blacklist.yaml` 中添加封禁信源：

```yaml
blacklist:
  - domain: "rumor-site.com"
    reason: "传播不实信息"
    severity: high
```

---

## 八、高级用法

### 8.1 使用 Provider 工厂

通过工厂类创建 Provider：

```python
from web_search.providers.factory import SearchProviderFactory, ProviderType

provider = SearchProviderFactory.create(
    "searxng",
    base_url="http://localhost:8080",
    default_engines=["google", "bing"]
)

print(f"Provider 名称: {provider.name}")
print(f"支持的引擎: {provider.supported_engines}")
```

### 8.2 自定义 QueryRewriter

```python
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.rewriter.intent_analyzer import IntentAnalyzer
from web_search.rewriter.query_expander import QueryExpander
from web_search.rewriter.query_enhancer import QueryEnhancer

query_rewriter = QueryRewriter(
    llm_client=llm_client,
    intent_analyzer=IntentAnalyzer(llm_client),
    query_expander=QueryExpander(),
    query_enhancer=QueryEnhancer()
)

rewrite_result = await query_rewriter.rewrite("人工智能最新进展")
print(f"改写查询: {rewrite_result.rewritten_queries}")
```

### 8.3 自定义 Reranker

```python
from web_search.reranker.reranker import Reranker, RerankConfig

config = RerankConfig(
    weights={
        "relevance": 0.5,
        "trustworthiness": 0.2,
        "freshness": 0.15,
        "authority": 0.15
    }
)

reranker = Reranker(config=config)
reranked = reranker.rerank(classified_results, judgments)
```

### 8.4 批量处理多个查询

```python
queries = [
    "人工智能最新进展",
    "量子计算突破",
    "新能源汽车市场"
]

for query in queries:
    result = await orchestrator.search_with_trust_v2(query)
    print(f"[{query}]")
    print(f"  改写查询数: {len(result.metadata['rewrite_result'].rewritten_queries)}")
    print(f"  白名单: {len(result.classified_results['white'])} 条")
    print(f"  碰撞: {len(result.collisions)} 个")
```

---

## 九、v1 向后兼容

v2 支持向后兼容，可以继续使用 v1 的基本功能：

```python
from web_search.core.orchestrator import SearchOrchestrator
from web_search.classifier.source_classifier import SourceClassifier

classifier = SourceClassifier(
    whitelist=config.get("whitelist", []),
    blacklist=config.get("blacklist", [])
)

orchestrator = SearchOrchestrator(
    provider=provider,
    source_classifier=classifier
)

result = orchestrator.search_with_trust("2024年AI大模型最新进展")
```

---

## 十、完整示例

```python
import asyncio
from web_search.core.orchestrator import SearchOrchestratorV2
from web_search.providers.searxng import SearXNGProvider
from web_search.rewriter.query_rewriter import QueryRewriter
from web_search.classifier.llm_classifier import LLMSourceClassifier
from web_search.resolver.embedding_engine import EmbeddingSimilarityEngine
from web_search.resolver.llm_judge import LLMCollisionJudge
from web_search.reranker.reranker import Reranker
from web_search.core.llm_client import LLMWrapper
from web_search.config.settings import load_config

async def main():
    config = load_config("configs")

    llm_client = LLMWrapper(config.get("llm", {}))
    embedding_client = EmbeddingClient(config.get("embedding", {}))

    provider = SearXNGProvider(
        base_url="http://localhost:8080",
        default_engines=["google", "bing"]
    )

    orchestrator = SearchOrchestratorV2(
        provider=provider,
        query_rewriter=QueryRewriter(llm_client=llm_client),
        source_classifier=LLMSourceClassifier(llm_client=llm_client),
        embedding_engine=EmbeddingSimilarityEngine(embedding_client=embedding_client),
        collision_judge=LLMCollisionJudge(llm_client=llm_client),
        reranker=Reranker()
    )

    result = await orchestrator.search_with_trust_v2("2024年AI大模型最新进展")

    print("=" * 60)
    print(f"查询: {result.query}")
    print("=" * 60)

    print(f"\n【改写查询】")
    for q in result.metadata["rewrite_result"].rewritten_queries:
        print(f"  - {q}")

    print(f"\n【信源分层统计】")
    print(f"  白名单 (高可信): {len(result.classified_results['white'])} 条")
    print(f"  灰名单 (中等可信): {len(result.classified_results['gray'])} 条")
    print(f"  黑名单 (不可信): {len(result.classified_results['black'])} 条")

    print(f"\n【碰撞检测】")
    print(f"  检测到碰撞: {len(result.collisions)} 个")

    print(f"\n【摘要】")
    print(result.summary)

    print(f"\n【搜索耗时】")
    print(f"  {result.response.search_time:.2f} 秒")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 十一、扩展阅读

- [部署指南](./deployment.md)
- [架构设计文档 v2](./可信联网搜索系统架构设计v2.md)
