# SearXNG Provider 问题修复总结

## 问题概述

在运行 `examples/example_trusted_search.py` 示例脚本时，遇到以下问题：
- 设置 `time_range` 参数后搜索返回 0 条结果
- 不设置 `time_range` 时正常返回结果

---

## 问题定位过程

### 第一步：确认问题现象

```python
# 直接使用 requests 测试 SearXNG
import requests
params = {'q': 'AI大模型最新进展', 'format': 'json', 'limit': 10, 'time_range': 'month'}
r = requests.get('http://localhost:8080/search', params=params)
# 返回 26 条结果，正常

# 通过 Provider 测试
provider = SearXNGProvider(base_url='http://localhost:8080', default_engines=None)
options = SearchOptions(max_results=10, time_range='month')
resp = provider.search('AI大模型最新进展', options)
# 返回 0 条结果，异常
```

### 第二步：对比请求 URL

```
# 直接请求 URL
http://localhost:8080/search?q=AI...&format=json&limit=10&time_range=month
# 结果：26 条

# Provider 构建的 URL
http://localhost:8080/search?q=AI...&format=json&limit=10&engines=google%2Cbing&time_range=month
# 结果：0 条
```

发现问题：`default_engines=None` 仍然添加了 `engines=google%2Cbing` 参数。

### 第三步：定位根因

在 `searxng.py` 中：

```python
def __init__(
    self,
    base_url: str = "http://localhost:8080",
    api_key: Optional[str] = None,
    default_engines: Optional[List[str]] = None  # 传入 None
):
    self.base_url = base_url.rstrip("/")
    self.api_key = api_key
    self.default_engines = default_engines or ["google", "bing"]  # 问题在这里！
```

**根因**：`default_engines or ["google", "bing"]` 这行代码将 `None` 替换为了默认的 `["google", "bing"]`。

当用户在示例中设置 `default_engines=None`（希望不指定引擎）时，实际效果是使用了 `["google", "bing"]` 引擎，这些引擎：
1. 对中文查询支持不佳
2. 经常返回 403 Forbidden 错误

---

## 解决方案

### 修复代码

**文件**：`src/web_search/providers/searxng.py`

**修改前**：
```python
self.default_engines = default_engines or ["google", "bing"]
```

**修改后**：
```python
self.default_engines = default_engines
```

同时修改 `search` 方法中的逻辑，正确处理 `None` 值：

```python
if engines:
    params["engines"] = ",".join(engines)
```

这样当 `default_engines=None` 时，不会添加 `engines` 参数，SearXNG 会使用其默认引擎配置（对中文支持更好的 baidu、360search 等）。

---

## 相关配置修改

### SearXNG settings.yml

为支持 JSON 格式输出，修改了 `build/searxng/settings/settings.yml`：

```yaml
search:
  formats:
    - html
    - json
  enable_api: true
```

### Provider 错误处理增强

添加了更友好的错误提示：

```python
try:
    response = requests.get(...)
    response.raise_for_status()
except requests.exceptions.ConnectionError as e:
    raise RuntimeError(f"Failed to connect to SearXNG at {self.base_url}: {e}")
except requests.exceptions.Timeout as e:
    raise RuntimeError(f"SearXNG request timed out after 30s: {e}")
except requests.exceptions.HTTPError as e:
    raise RuntimeError(f"SearXNG returned HTTP error: {e}")
```

---

## 验证结果

修复后运行示例脚本：

```bash
$ python examples/example_trusted_search.py

查询: AI大模型最新进展
============================================================

【信源分层统计】
  白名单 (高可信): 0 条
  灰名单 (中等可信): 26 条
  黑名单 (不可信): 0 条

【碰撞检测】
  检测到碰撞: 0 个

【摘要】
共聚合 26 条来源，涵盖 10 个不同角度的报道。

【搜索耗时】
  0.00 秒
```

---

## 经验教训

1. **Python 惯用法陷阱**：`value or default` 在 `value=None` 时会返回 `default`，这是常见错误。在需要明确区分 `None` 和 falsy 值时，应使用 `value if value is not None else default`。

2. **搜索引擎区域支持**：不同搜索引擎对不同语言的搜索支持差异很大。Google/Bing 对中文搜索支持不如百度、360search。

3. **API 响应格式**：SearXNG 的 JSON 格式需要显式启用，否则默认返回 HTML。

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `src/web_search/providers/searxng.py` | 修复 default_engines 处理逻辑，添加错误处理 |
| `build/searxng/settings/settings.yml` | 添加 search.formats 和 search.enable_api 配置 |
| `examples/example_trusted_search.py` | 添加 SearchOptions 导入，设置默认搜索引擎 |