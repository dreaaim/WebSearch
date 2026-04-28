# Bug Fix Summary

## 问题一：查询改写模块多样性不足

### 问题描述
用户输入 `2024年AI大模型最新进展` 后，查询改写输出只有 1 条结果：
```
【改写查询】
  意图: news
  - "2024年AI大模型最新进展" 2024年AI大模型最新进展
```

### 根因分析
1. **IntentAnalyzer** - 使用规则匹配而非 LLM，无法理解深层语义
2. **QueryExpander.expand** - 直接返回 `[query]`，完全没有实现发散逻辑
3. **QueryEnhancer** - 只有简单规则增强，无 LLM 参与
4. 各模块分散处理，无法生成结构化、多样化的查询

### 解决方案
将原有的"规则 + 分散调用"模式重构为"LLM-Prompt 驱动"模式：

1. **单一 LLM Prompt 驱动** - 用一个结构化 Prompt 让 LLM 一次性输出意图分析 + 5-8 条多样化查询
2. **完善的 Fallback 机制** - 当 LLM 调用失败时，使用规则生成 8 条多样化查询
3. **新增 StructuredQuery 数据类** - 支持结构化的查询类型标识

**修改文件**：`src/web_search/rewriter/query_rewriter.py`

---

## 问题二：asyncio 事件循环冲突

### 问题描述
```
asyncio.exceptions.InvalidStateError: Result is not set.
RuntimeError: asyncio.run() cannot be called from a running event loop
```

### 根因分析
在 `rewrite_sync` 方法中，当已有事件循环运行时，尝试调用 `future.result()` 或 `asyncio.run()` 会导致冲突。

### 解决方案
使用 `ThreadPoolExecutor` 在独立线程中运行 asyncio：

```python
def _call_llm_sync(self, prompt: str) -> str:
    import concurrent.futures
    def run_async():
        return asyncio.run(self.llm_client.complete(prompt))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_async)
        return future.result()
```

**修改文件**：`src/web_search/rewriter/query_rewriter.py`

---

## 问题三：ZhipuAI 模型 stream 模式限制

### 问题描述
```
openai.BadRequestError: Error code: 400 - 'This model only support stream mode, please enable the stream parameter to access the model'
```

### 根因分析
1. 用户使用 DashScope 的 OpenAI 兼容接口调用 ZhipuAI GLM-4.5 模型
2. 原有代码将 `dashscope` 错误地路由到 `ZhipuAIClient`（原生协议），而不是 `OpenAIClient`
3. ZhipuAI GLM-4.5 模型确实需要 `stream=True` 参数

### 解决方案
1. 将 `dashscope` 路由到 `OpenAIClient`（OpenAI 兼容接口）
2. 为 DashScope 配置添加 `stream=True` 参数
3. 在 `OpenAIClient.complete` 方法中添加 stream 处理逻辑

**修改文件**：`src/web_search/core/llm_client.py`

```python
# 修改前
if "dashscope" in api_base or "zhipu" in model.lower():
    return ZhipuAIClient(...)

# 修改后
if "dashscope" in api_base:
    return OpenAIClient(..., stream=True)

if "zhipu" in model.lower():
    return ZhipuAIClient(...)
```

---

## 问题四：Windows PowerShell GBK 编码问题

### 问题描述
```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2022' in position 8: illegal multibyte sequence
```

### 根因分析
Windows PowerShell 默认使用 GBK 编码，无法处理 UTF-8 中文字符。

### 解决方案
在 example 文件开头设置 UTF-8 编码：

```python
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

**修改文件**：`examples/example_trusted_search_v2.py`

---

## 修改文件清单

| 文件 | 修改内容 |
|-----|---------|
| `src/web_search/rewriter/query_rewriter.py` | LLM-Prompt 驱动重构、StructuredQuery、fallback 机制 |
| `src/web_search/core/llm_client.py` | DashScope 路由修复、stream 参数支持 |
| `examples/example_trusted_search_v2.py` | UTF-8 编码设置、调试信息输出 |

## 测试结果

修复后输出示例：
```
【改写查询】
  意图: news
  实体: 2024年, AI大模型, 最新进展
  时间范围: 2024年至今

  多样化查询列表:
    [核心] 2024年AI大模型最新进展
    [精确匹配] "AI大模型" "最新进展" 2024
    [同义改写] 2024年大语言模型发展动态
    [细化主题] 2024年AI大模型训练技术突破
    [相关扩展] 2024年生成式AI创新成果
    [源限定] AI大模型最新进展 site:arxiv.org
    [时间限定] AI大模型进展 after:2024-01-01
    [技术突破] 2024年AI大模型架构创新
```
