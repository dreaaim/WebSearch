# 全链路调试问题修复总结

## 问题概述

在启用全链路调试后，发现了多个影响搜索结果质量的问题，本文档总结问题、根本原因及解决方案。

---

## 问题一：相关性分数全部为 5.0

### 现象
所有搜索结果的相关性分数（`relevance_score`）都是 5.0，无法区分高相关和低相关结果。

**示例输出：**
```json
{
  "index": 27,
  "title": "破皮玩具厂 poppy playtime (豆瓣)",
  "relevance_score": 5.0,
  "classification": "gray"
}
```

### 根本原因
[LLMSourceClassifier](file:///d:/project/opensource/WebSearch/src/web_search/classifier/llm_classifier.py) 在计算相关性分数时存在逻辑缺陷：

```python
# 原代码逻辑
if self.relevance_scorer:
    relevance_score = self.relevance_scorer.score(...)
else:
    relevance_score = 5.0  # 默认值
```

问题在于：
1. 只有当 `relevance_scorer` 存在时才计算相关性分数
2. 即使 `llm_client` 存在但没有 `relevance_scorer`，也不会使用 LLM 计算

### 解决方案
修改 `LLMSourceClassifier.classify` 方法，当 `llm_client` 存在但没有 `relevance_scorer` 时，直接使用 LLM 计算相关性分数：

**修改文件：** `src/web_search/classifier/llm_classifier.py`

**核心改动：**
```python
relevance_score = 5.0
if self.relevance_scorer:
    relevance_score = self.relevance_scorer.score(...)
elif self.llm_client:
    # 新增：没有 relevance_scorer 时使用 llm_client
    prompt = self._build_relevance_prompt(...)
    response = await self.llm_client.complete(prompt)
    relevance_score = self._parse_relevance_response(response)
```

新增方法：
- `_build_relevance_prompt()`: 构建相关性评分 prompt
- `_parse_relevance_response()`: 解析 LLM 返回的相关性分数

---

## 问题二：无法定位结果来源的搜索查询

### 现象
搜索结果中无法看到每个结果是通过哪个搜索查询返回的，难以定位低质量结果的来源。

**示例输出：**
```json
{
  "index": 27,
  "title": "破皮玩具厂 poppy playtime (豆瓣)",
  "url": "https://www.douban.com/game/36581276/"
}
```

### 根本原因
搜索阶段执行多个查询（改写后的多样化查询），但分类结果没有记录每个结果来自哪个查询。

### 解决方案
在 `SearchOrchestratorV2` 中添加 `search_query_map` 来追踪 URL 到查询的映射关系：

**修改文件：** `src/web_search/core/orchestrator_v2.py`

**核心改动：**
```python
# 搜索阶段：构建 URL -> search_query 映射
search_query_map = {}
for search_query in search_queries:
    response = self.provider.search(search_query, options)
    query_results = response.results
    for r in query_results:
        search_query_map[r.url] = search_query  # 记录映射

# 分类阶段：输出时包含 search_query 字段
classify_debug["results"].append({
    "index": i,
    "title": result.title,
    "url": result_url,
    "search_query": search_query_map.get(result_url, 'unknown'),  # 新增
    ...
})
```

**输出示例：**
```json
{
  "index": 27,
  "title": "破皮玩具厂 poppy playtime (豆瓣)",
  "url": "https://www.douban.com/game/36581276/",
  "search_query": "LLM最新技术进展"
}
```

---

## 问题三：无法查看搜索引擎原始返回

### 现象
搜索阶段日志只显示每个查询返回的结果数量，无法看到具体返回了哪些结果。

### 根本原因
调试日志中 `engine_results` 只记录了数量，没有记录结果的样例。

### 解决方案
在 `search_debug` 中添加 `all_results_snippets` 字段，记录每个查询的前3条结果样例：

```python
search_debug["all_results_snippets"][search_query] = [
    {"Title": r.title, "snippet": r.snippet[:200], "url": r.url}
    for r in query_results[:3]
]
```

---

## 问题四：无法查看 Reranker 原始输出

### 现象
无法看到外部 reranker 模型的原始评分结果，难以判断 reranker 是否正常工作。

### 根本原因
rerank 阶段的调试信息只包含最终的综合得分，没有记录外部 reranker 的原始返回。

### 解决方案
在 `rerank_debug` 中添加 `external_rerank_raw_output` 字段：

**修改文件：** `src/web_search/core/orchestrator_v2.py`

**核心改动：**
```python
if self.reranker.reranker_client:
    raw_rerank_results = self.reranker.reranker_client.rerank(...)
    rerank_debug["external_rerank_raw_output"] = [
        {"index": r.index, "score": r.score, "text": r.text[:100]}
        for r in raw_rerank_results[:10]
    ]

# 每个结果的详细信息也增加 external_score
rerank_debug["results"].append({
    "index": i,
    "title": obj.title,
    "final_score": obj.final_score,
    "external_score": getattr(obj, 'external_rerank_score', None),  # 新增
    ...
})
```

---

## 问题五：搜索异常被静默吞掉

### 现象
当搜索引擎返回错误（如连接失败、超时）时，异常没有记录到调试日志中。

### 根本原因
搜索调用没有 try-except 包裹，异常直接抛出导致流程中断。

### 解决方案
为搜索调用添加异常处理，记录错误信息：

```python
for search_query in search_queries:
    query_results = []
    try:
        response = self.provider.search(search_query, options)
        query_results = response.results
    except Exception as e:
        search_debug["errors"].append(f"Query '{search_query}' failed: {str(e)}")
        query_results = []
    all_results.extend(query_results)
```

同时在 `SearXNGProvider` 中改进错误消息：

```python
except requests.exceptions.ConnectionError as e:
    raise RuntimeError(f"Failed to connect to SearXNG at {self.base_url}: {e}")
except requests.exceptions.Timeout as e:
    raise RuntimeError(f"SearXNG request timed out after 30s: {e}")
```

---

## 调试配置说明

### 启用调试模式

**方式一：参数传入**
```python
result = orchestrator.search_with_trust(
    "大模型最新技术",
    debug=True,
    debug_level="verbose",  # basic|verbose|performance
    debug_output="stdout"   # log|stdout|both
)
```

**方式二：环境变量**
```bash
export WEB_SEARCH_DEBUG=1
export WEB_SEARCH_DEBUG_LEVEL=verbose
export WEB_SEARCH_DEBUG_OUTPUT=stdout
```

### 调试输出字段说明

| 阶段 | 新增/修改的调试字段 |
|------|-------------------|
| search | `all_results_snippets`, `errors` |
| source_classify | `search_query` (每个结果增加) |
| rerank | `external_rerank_raw_output`, `external_score` |

---

## 总结

本次修复涉及以下文件：

| 文件 | 修改内容 |
|------|---------|
| `src/web_search/classifier/llm_classifier.py` | 修复相关性分数计算逻辑，支持直接使用 LLM |
| `src/web_search/core/orchestrator_v2.py` | 添加 search_query_map, 增强调试输出 |
| `src/web_search/providers/searxng.py` | 改进异常处理和错误消息 |

**关键经验：**
1. 默认值要谨慎使用，5.0 作为默认值会导致无法区分结果质量
2. 多阶段处理时要注意信息传递，确保下游能获取上游的上下文
3. 异常处理要捕获并记录，便于问题定位
