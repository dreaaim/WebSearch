# Reranker 修复问题总结

## 问题概述

在实现 `llm_classifier.py` 和 `reranker.py` 的提示词修复及流程调整过程中，遇到了多个技术问题导致功能无法正常工作。

---

## 问题 1：外部 Reranker 无法调用（asyncio 事件循环冲突）

### 现象
- 所有结果的分数都是相同的内部计算分数（0.3350）
- 调试输出显示 "Event loop already running, using internal scores only"

### 根因
`Reranker._sync_rerank()` 方法在同步上下文中被调用，但 `DashScopeRerankerClient` 使用 `async/await` 异步调用。当事件循环已在运行时，调用 `loop.run_until_complete()` 会失败。

```python
# 原始错误代码
loop = asyncio.get_event_loop()
if loop.is_running():
    future = asyncio.ensure_future(...)  # 创建 future
    rerank_results = future.result()  # 错误：future 还未完成
```

### 解决方案
将 `DashScopeRerankerClient.rerank()` 改为同步方法，使用 `httpx.Client`（同步）而非 `httpx.AsyncClient`。

---

## 问题 2：DashScope API 端点错误（404 Not Found）

### 现象
- HTTP 404 错误
- 错误信息：`Client error '404 Not Found' for url 'https://dashscope.aliyuncs.com/compatible-api/v1'`

### 根因
1. **端点路径错误**：使用 `/rerank` 但正确端点是 `/reranks`
2. **API 格式错误**：使用了错误的 JSON 结构（嵌套在 `input` 和 `parameters` 中）
3. **模型参数错误**：使用了 `instructions` 而非 `instruct`

### 解决方案
根据 DashScope 官方文档修正：

```python
# 正确的 API 端点
base_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"

# 正确的请求格式
{
    "model": "gte-rerank-v2",
    "input": {
        "query": query,
        "documents": texts
    },
    "parameters": {
        "return_documents": True,
        "top_n": top_n
    }
}
```

---

## 问题 3：配置文件 base_url 覆盖硬编码端点

### 现象
即使代码中硬编码了正确的端点，仍然使用配置文件中的错误端点

### 根因
`create_reranker_client()` 函数使用 `config.get("base_url", correct_url)` 会优先使用配置文件中的值

### 解决方案
对于 `gte-rerank` 模型，强制使用硬编码的正确端点，忽略配置文件：

```python
if "gte-rerank" in model.lower():
    return DashScopeRerankerClient(
        api_key=api_key,
        model=model,
        base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )
```

---

## 问题 4：分数未正确附加到结果对象

### 现象
- 结果列表中的 `final_score` 全部为 0
- 虽然有分数计算，但显示不出来

### 根因
`reranked_results` 是 `ClassifiedResult` 对象列表，而 `ClassifiedResult` 内部包装了原始 `result`。分数被设置在 `result.result` 上，但返回给用户的是 `reranked_originals`（原始 result），该对象没有分数属性。

### 解决方案
在设置分数时，同时设置到 `result.result` 和 `result`：

```python
for i, result in enumerate(results):
    if i in external_scores:
        score = external_scores[i]
        if hasattr(result, 'result'):
            result.result.external_rerank_score = score
            result.result.relevance_score = score
        else:
            result.external_rerank_score = score
            result.relevance_score = score
```

---

## 问题 5：流程顺序调整后的数据流问题

### 现象
- 摘要生成和结果显示出现 `AttributeError`
- 碰撞检测失败

### 根因
流程调整后：
```
旧流程：搜索 → 分类 → 碰撞检测 → 重排序 → 摘要
新流程：搜索 → 分类 → 重排序 → 碰撞检测 → 摘要
```

但代码没有正确处理 `reranked_results`（`ClassifiedResult` 列表）和原始 result 之间的转换。

### 解决方案
1. 碰撞检测前提取原始 result：
```python
reranked_originals = [
    r.result if hasattr(r, 'result') else r for r in reranked_results[:top_k]
]
collisions = self.fact_resolver.detect_and_resolve(reranked_originals)
```

2. 返回结果时使用原始 result：
```python
reranked_originals_for_summary = [
    r.result if hasattr(r, 'result') else r for r in reranked_results
]
return TrustedSearchResult(
    response=SearchResponse(results=reranked_originals_for_summary, ...),
    ...
)
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `reranker/reranker.py` | 同步调用外部 reranker，分数附加逻辑 |
| `reranker/reranker_client.py` | DashScopeRerankerClient 改为同步，修正 API 格式和端点 |
| `core/orchestrator_v2.py` | 调整流程顺序，正确提取原始 result |

---

## 经验教训

1. **异步/同步混用**：在同步上下文中调用异步代码需要特别小心，优先使用同步 HTTP 客户端
2. **API 文档核实**：使用第三方 API 时务必核实官方文档，包括端点路径和请求格式
3. **配置 vs 硬编码**：对于特定模型需要硬编码正确配置时，应强制覆盖配置文件
4. **数据流追踪**：修改流程顺序时需要仔细追踪数据对象的类型转换
