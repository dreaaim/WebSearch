# v2 示例脚本 Bug 修复报告

## 问题汇总

本次修复共发现并解决了 **5 个问题**，涉及配置加载、数据结构兼容、模块导入等多个方面。

---

## Bug 1: SearchOrchestratorV2 导入路径错误

### 问题描述

```
ImportError: cannot import name 'SearchOrchestratorV2' from 'web_search.core.orchestrator'
```

### 根因分析

- `SearchOrchestratorV2` 类定义在 `orchestrator_v2.py` 文件中
- 但示例脚本错误地从 `orchestrator.py` 导入

### 解决方案

修改导入语句：

```python
# 错误
from web_search.core.orchestrator import SearchOrchestratorV2

# 正确
from web_search.core.orchestrator_v2 import SearchOrchestratorV2
```

---

## Bug 2: 配置加载嵌套结构错误

### 问题描述

配置文件 `llm.yaml` 结构为：
```yaml
llm:
  openai:
    model: "glm-4.5"
```

但 `load_config()` 加载后得到嵌套结构：
```python
{'llm': {'openai': {...}}}  # 多了一层 llm
```

而 `create_llm_client()` 期望的是：
```python
{'openai': {...}}  # 直接是 openai 配置
```

### 根因分析

`settings.py` 中加载配置文件时，直接使用 `load_yaml()` 返回整个 YAML 内容，但部分 YAML 文件本身就包含根键（如 `llm:`、`embedding:`），导致多嵌套一层。

```python
# 原代码
config["llm"] = load_yaml(llm_path)  # 返回 {'llm': {...}}

# 应该
config["llm"] = load_yaml(llm_path).get("llm", {})  # 返回 {'openai': {...}}
```

### 解决方案

修改 `src/web_search/config/settings.py`：

```python
llm_path = os.path.join(config_dir, "llm.yaml")
if os.path.exists(llm_path):
    config["llm"] = load_yaml(llm_path).get("llm", {})

embedding_path = os.path.join(config_dir, "embedding.yaml")
if os.path.exists(embedding_path):
    config["embedding"] = load_yaml(embedding_path).get("embedding", {})
```

---

## Bug 3: Reranker 数据结构不兼容

### 问题描述

```
AttributeError: 'ClassifiedResult' object has no attribute 'source_type'. Did you mean: 'source_info'?
```

### 根因分析

- `LLMSourceClassifier` 输出的 `ClassifiedResult` 结构为：
  ```python
  ClassifiedResult(
      result=...,
      source_info=SourceInfo(...),  # 嵌套结构
      classification=...,
      relevance_score=...
  )
  ```

- 而重写的 `Reranker` 期望直接访问：
  ```python
  result.source_type  # 不存在
  result.source_level  # 不存在
  ```

### 解决方案

重写 `Reranker`，使用辅助方法动态访问嵌套结构：

```python
def _get_source_type(self, result: Any) -> SourceType:
    if hasattr(result, 'source_info') and hasattr(result.source_info, 'source_type'):
        return result.source_info.source_type
    if hasattr(result, 'source_type'):
        return result.source_type
    return SourceType.MEDIA

def _get_source_level(self, result: Any) -> SourceLevel:
    if hasattr(result, 'source_info') and hasattr(result.source_info, 'source_level'):
        return result.source_info.source_level
    if hasattr(result, 'source_level'):
        return result.source_level
    return SourceLevel.LOCAL
```

---

## Bug 4: reranker/__init__.py 导出不存在的类

### 问题描述

```
ImportError: cannot import name 'SearchResult' from 'web_search.reranker.reranker'
```

### 根因分析

重写 `reranker.py` 时，移除了 `SearchResult` 和 `ClassifiedResult` 类定义（因为使用 `Any` 类型泛化处理），但 `__init__.py` 仍在尝试导出这些类。

### 解决方案

修改 `src/web_search/reranker/__init__.py`：

```python
# 移除不存在的导出
from .reranker import (
    SourceType,
    SourceLevel,
    Classification,
    AuthorityLevel,
    RerankConfig,
    Reranker  # 移除 SearchResult, ClassifiedResult
)
```

---

## Bug 5: Windows 终端 GBK 编码问题

### 问题描述

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2022' in position 8
```

程序实际已正常运行并输出结果，但在 Windows 终端打印包含 Unicode 字符（如 `•`）时崩溃。

### 根因分析

Windows 默认使用 GBK 编码，Python 的 `print()` 函数无法处理 UTF-8 字符。

### 解决方案

在示例脚本开头设置 UTF-8 输出：

```python
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
```

---

## 额外优化：客户端封装

除了修复 Bug，还新增了模型客户端封装，统一管理多模型选择：

### LLM 客户端 (`src/web_search/core/llm_client.py`)

支持自动选择：
- OpenAI
- Azure OpenAI
- Anthropic Claude
- 智谱 GLM (dashscope)

```python
from web_search.core.llm_client import create_llm_client

client = create_llm_client(config)  # 根据配置自动选择
```

### Embedding 客户端 (`src/web_search/core/embedding_client.py`)

支持：
- OpenAI Embedding API
- 本地 SentenceTransformer 模型

```python
from web_search.core.embedding_client import create_embedding_client
```

### Reranker 客户端 (`src/web_search/core/reranker_client.py`)

支持：
- OpenAI 兼容格式
- Cohere Rerank API
- Jina Rerank API
- DashScope Rerank API

```python
from web_search.core.reranker_client import create_reranker_client
```

---

## 修改文件清单

| 文件路径 | 修改类型 |
|----------|----------|
| `src/web_search/config/settings.py` | Bug 修复 |
| `src/web_search/reranker/reranker.py` | 重写兼容 |
| `src/web_search/reranker/__init__.py` | Bug 修复 |
| `src/web_search/core/llm_client.py` | 新增 |
| `src/web_search/core/embedding_client.py` | 新增 |
| `src/web_search/core/reranker_client.py` | 新增 |
| `examples/example_trusted_search_v2.py` | 修复导入+编码 |
| `configs/reranker.yaml` | 配置完善 |

---

## 全链路调试增强

详见 [FullChainDebug-Issues-Fix.md](FullChainDebug-Issues-Fix.md)

### 新增调试功能

- `debug`: 控制是否输出调试信息
- `debug_level`: basic/verbose/performance
- `debug_output`: log/stdout/both

### 新增调试字段

| 阶段 | 新增/修改的调试字段 |
|------|-------------------|
| search | `all_results_snippets`, `errors` |
| source_classify | `search_query` (每个结果增加) |
| rerank | `external_rerank_raw_output`, `external_score` |

### 修复的问题

1. 相关性分数全部为 5.0 的问题
2. 无法定位结果来源的搜索查询
3. 无法查看搜索引擎原始返回
4. 无法查看 Reranker 原始输出
5. 搜索异常被静默吞掉
