# Python 联网搜索实现方案调研报告

## 一、调研背景

LLM本身无法主动联网获取实时信息，需要通过外部工具实现联网搜索能力。本报告聚焦于**Python语言实现联网搜索的具体技术方案**，涵盖从简单的API调用到复杂的多引擎聚合搜索。

---

## 二、Python 联网搜索方案分类

| 类别 | 代表方案 | 是否需要API Key | 免费额度 | 难度 |
|------|----------|-----------------|----------|------|
| **专用AI搜索SDK** | Tavily、Exa | ✅ 需要 | 有免费额度 | ★☆☆☆☆ |
| **传统搜索API封装** | SerpAPI、Google Search | ✅ 需要 | 有免费额度 | ★★☆☆☆ |
| **多引擎聚合** | SerpEX、DuckDuckGo | ✅ 需要 | 有免费额度 | ★★☆☆☆ |
| **完全免费方案** | DDGS、SearXNG | ❌ 不需要 | 无限 | ★★★☆☆ |
| **本地部署方案** | SearXNG 自部署 | ❌ 不需要 | 无限 | ★★★★☆ |

---

## 三、专用AI搜索SDK方案

### 3.1 Tavily - AI Agent专用搜索

**特点**: 专为LLM/Agent设计，返回清洗过的结果，国内访问速度快

**官网**: https://tavily.com

**Python SDK安装**:
```bash
pip install langchain-community tavily-python
```

**代码实现**:
```python
import os
from langchain_community.tools import TavilySearchResults

# 配置API Key
os.environ["TAVILY_API_KEY"] = "your_tavily_api_key"

# 初始化搜索工具 (max_results控制返回数量)
search_tool = TavilySearchResults(max_results=3)

# 执行搜索
result = search_tool.run("2024年最新AI技术进展")
print(result)
```

**与LangChain集成**:
```python
from langchain.agents import tool

@tool
def search_tool(query: str) -> str:
    """搜索最新信息"""
    tavily = TavilySearchResults(max_results=3)
    return tavily.run(query)

tools = [search_tool]
```

**优点**:
- 专为AI Agent优化，返回结果LLM友好
- 国内访问速度快
- LangChain支持完善
- 有免费额度（每月1000次）

**缺点**:
- 需要API Key
- 免费额度有限

---

### 3.2 Exa - 语义搜索专家

**特点**: 支持向量语义搜索，适合复杂查询

**官网**: https://exa.ai

**Python SDK安装**:
```bash
pip install exa-py dotenv
```

**代码实现**:
```python
import os
from dotenv import load_dotenv
from exa_py import Exa

load_dotenv()

exa = Exa(api_key=os.getenv("EXA_API_KEY"))

# 基础搜索
results = exa.search(
    "量子计算最新进展",
    num_results=5,
    type="auto"
)

# 搜索并获取内容
results = exa.search_and_contents(
    "人工智能发展趋势",
    text=True,
    num_results=5
)

for result in results.results:
    print(f"标题: {result.title}")
    print(f"链接: {result.url}")
    print(f"内容摘要: {result.text[:200]}...")
```

**LangChain集成**:
```python
from langchain_exa import ExaSearchRetriever

retriever = ExaSearchRetriever(
    api_key=os.getenv("EXA_API_KEY"),
    max_results=5
)
```

---

## 四、传统搜索API封装方案

### 4.1 SerpAPI - 多引擎聚合

**特点**: 支持Google、Bing、Yahoo等多引擎，统一接口

**官网**: https://serpapi.com

**Python SDK安装**:
```bash
pip install google-search-results-python  # 即将迁移到 serpapi-python
```

**代码实现**:
```python
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

params = {
    "q": "Python编程技巧",
    "api_key": os.getenv("SERPAPI_KEY"),
    "engine": "google",
    "num": 5
}

search = GoogleSearch(params)
results = search.get_dict()

# 解析自然搜索结果
for result in results.get("organic_results", [])[:5]:
    print(f"标题: {result.get('title')}")
    print(f"链接: {result.get('link')}")
    print(f"摘要: {result.get('snippet')}")
    print("---")
```

**支持的搜索引擎**:

| 搜索引擎 | 用途 | 特点 |
|----------|------|------|
| Google | 通用搜索 | 搜索结果精准 |
| Bing | 通用搜索 | 微软服务，稳定 |
| Yahoo | 通用搜索 | 备用选择 |
| Baidu | 中文搜索 | 国内资源 |
| DuckDuckGo | 隐私搜索 | 无追踪 |

---

### 4.2 SerpEX - 多引擎搜索API

**特点**: 统一接口访问Google、Bing、DuckDuckGo、Brave等多引擎

**官网**: https://serpex.dev

**Python SDK安装**:
```bash
pip install langchain-serpex-python
```

**代码实现**:
```python
import os
from langchain_serpex import SerpEX

os.environ["SERPEX_API_KEY"] = "your_serpdex_api_key"

search = SerpEX(engine="google")  # 可选: bing, duckduckgo, baidu, brave
results = search.run("AI大模型最新进展")
```

---

## 五、完全免费方案（无需API Key）

### 5.1 DDGS - DuckDuckGo免费搜索

**特点**: 完全免费，无需API Key，支持文本/图片/新闻/视频搜索

**GitHub**: https://github.com/deedy5/ddgs

**Python SDK安装**:
```bash
pip install duckduckgo-search
```

**代码实现 - 基础文本搜索**:
```python
from duckduckgo_search import DDGS

with DDGS() as ddgs:
    # 文本搜索
    results = list(ddgs.text("Python教程", max_results=5))
    for r in results:
        print(f"标题: {r['title']}")
        print(f"链接: {r['href']}")
        print(f"摘要: {r['body']}")
        print("---")
```

**代码实现 - 多类型搜索**:
```python
from duckduckgo_search import DDGS

with DDGS() as ddgs:
    # 新闻搜索
    news = list(ddgs.news("科技新闻", max_results=5))

    # 图片搜索
    images = list(ddgs.images("风景图片", max_results=5))

    # 视频搜索
    videos = list(ddgs.videos("教程视频", max_results=5))
```

**异步版本**:
```python
from duckduckgo_search import DDGS

async def async_search():
    async with DDGS() as ddgs:
        results = await ddgs.text("Python异步编程")
        for r in results:
            print(r)
```

**优点**:
- ✅ 完全免费，无需注册
- ✅ 无API Key泄露风险
- ✅ 支持多种搜索类型

**缺点**:
- ⚠️ 依赖DuckDuckGo服务稳定性
- ⚠️ 不适合高频调用
- ⚠️ 无专业化AI优化

---

### 5.2 SearXNG - 开源自托管方案

**特点**: 开源元搜索引擎，聚合多个搜索引擎，自部署完全可控

**官网**: https://searxng.org

**Docker部署**:
```bash
docker run -d -p 8080:8080 --name searxng searxng/searxng
```

**Python客户端安装**:
```bash
pip install searxng-search
```

**代码实现**:
```python
from searxng_search import SearxngSearch

# 连接自部署的SearXNG
searx = SearxngSearch(
    searx_host="http://localhost:8080",
    engines=["google", "bing", "baidu"]  # 指定引擎
)

results = searx.search(
    query="Python Web开发",
    engines=["google", "bing"],
    categories=["general"]
)

for r in results["results"]:
    print(f"标题: {r['title']}")
    print(f"链接: {r['url']}")
```

**使用公共实例**:
```python
from langchain_community.tools import SearxSearchWrapper

searx_tool = SearxSearchWrapper(
    searx_host="https://searx.be",  # 公共实例（不稳定）
    engines=["baidu", "bing"]
)
```

**优点**:
- ✅ 开源，可完全自控
- ✅ 聚合多引擎结果
- ✅ 隐私保护
- ✅ 可定制化配置

**缺点**:
- ⚠️ 需要服务器部署
- ⚠️ 公共实例不稳定
- ⚠️ 配置有一定门槛

---

## 六、与LLM集成的实现方案

### 6.1 通过LangChain集成

**完整示例 - Agent模式**:
```python
import os
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain_community.tools import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate

# 1. 配置
os.environ["OPENAI_API_KEY"] = "your_openai_key"
os.environ["TAVILY_API_KEY"] = "your_tavily_key"

# 2. 定义工具
tools = [TavilySearchResults(max_results=3)]

# 3. 创建Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个有用的AI助手，可以使用搜索工具获取最新信息。"),
    ("human", "{input}"),
])

agent = create_openai_functions_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 4. 执行
result = agent_executor.invoke({"input": "2024年诺贝尔奖获得者是哪些人？"})
print(result["output"])
```

### 6.2 通过Function Calling集成

**OpenAI Function Calling示例**:
```python
import os
import json
from openai import OpenAI
from duckduckgo_search import DDGS

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

tools = [{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索最新信息，返回搜索结果列表",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    }
}]

def web_search(query: str, max_results: int = 3) -> str:
    """执行联网搜索"""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
        return json.dumps(results, ensure_ascii=False)

# 发送查询
messages = [{"role": "user", "content": "今天有什么科技新闻？"}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

# 处理工具调用
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    if tool_call.function.name == "web_search":
        args = json.loads(tool_call.function.arguments)
        search_result = web_search(**args)

        # 将结果返回给模型
        messages.append(response.choices[0].message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": search_result
        })

        # 获取最终回复
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        print(final_response.choices[0].message.content)
```

---

## 七、方案对比与选型建议

### 7.1 功能对比

| 方案 | 免费额度 | 国内速度 | AI友好度 | 稳定性 | 推荐指数 |
|------|----------|----------|----------|--------|----------|
| **Tavily** | 1000次/月 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Exa** | 1000次/月 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **SerpAPI** | 100次/月 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **DDGS** | 无限 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **SearXNG** | 无限 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐（自部署） |

### 7.2 场景选型

| 场景 | 推荐方案 | 理由 |
|------|----------|------|
| **快速原型开发** | DDGS | 零配置，立即可用 |
| **生产环境AI应用** | Tavily | 专为LLM优化，稳定 |
| **学术研究** | Exa | 语义搜索，支持引用 |
| **预算有限** | SearXNG自部署 | 完全免费可控 |
| **国内应用** | Tavily / DDGS | 国内访问速度快 |

### 7.3 快速启动推荐

**方案一：最小成本**
```python
pip install duckduckgo-search

from duckduckgo_search import DDGS
with DDGS() as ddgs:
    results = list(ddgs.text("Python教程", max_results=3))
```

**方案二：专业AI应用**
```python
pip install langchain-community tavily-python

import os
os.environ["TAVILY_API_KEY"] = "your_key"
from langchain_community.tools import TavilySearchResults
search = TavilySearchResults(max_results=3)
```

---

## 八、总结

Python实现联网搜索的方案非常丰富，从零成本的DDGS到专业的Tavily都有很好的支持：

1. **最简单方案**: DDGS（duckduckgo-search），无需任何配置即可使用
2. **最专业方案**: Tavily，专为AI Agent设计，返回结果直接可用
3. **最可控方案**: SearXNG自部署，完全开源，可定制
4. **最多引擎方案**: SerpAPI/SerpEX，聚合多个搜索源

建议根据项目需求选择：
- 原型验证用DDGS
- 正式产品用Tavily
- 企业级自建用SearXNG

---

*报告生成时间: 2026年4月*
