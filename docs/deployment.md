# 可信联网搜索系统部署指南

## 一、系统环境要求

### 1.1 硬件要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 2 核 | 4 核及以上 |
| 内存 | 4 GB | 8 GB 及以上 |
| 磁盘 | 10 GB | 20 GB 及以上 |

### 1.2 软件要求

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| Python | >= 3.10 | 必需 |
| Docker | >= 20.10 | 推荐使用 Docker 部署 SearXNG |
| pip | 最新版本 | Python 包管理 |

### 1.3 网络要求

- 能够访问外部搜索引擎（Google、Bing、Baidu 等）
- SearXNG 实例需开放 8080 端口
- 能够访问 LLM API（如 OpenAI API、Azure OpenAI 等）

---

## 二、SearXNG 安装与配置

SearXNG 是系统的默认搜索提供者，负责聚合多个搜索引擎的结果。

### 2.1 Docker 部署（推荐）

#### 2.1.1 拉取镜像

```bash
docker pull searxng/searxng
```

#### 2.1.2 创建配置文件

创建目录用于存储 SearXNG 配置：

```bash
mkdir -p /opt/searxng/settings
```

创建 `settings.yml` 配置文件：

```bash
cat > /opt/searxng/settings/settings.yml << 'EOF'
use_default_settings: true

general:
  debug: false
  instance_name: "可信搜索服务"
  privacypolicy_url: false
  donation_url: false
  contact_url: false
  enable_metrics: true

search:
  formats:
    - html
    - json
  default_format: json
  max_results: 20

server:
  secret_key: "your-secret-key-change-in-production"
  bind_address: "0.0.0.0"
  port: 8080
  limiter: false
  public_instance: false

engines:
  - name: google
    engine: google
    shortcut: g
  - name: bing
    engine: bing
    shortcut: b
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
  - name: baidu
    engine: baidu
    shortcut: bd
  - name: yandex
    engine: yandex
    shortcut: yx
  - name: brave
    engine: brave
    shortcut: br

outgoing:
  request_timeout: 10.0
  max_request_timeout: 30.0
  useragent_suffix: ""
  pool_connections: 100
  pool_maxsize: 20
EOF
```

#### 2.1.3 启动容器

```bash
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -v /opt/searxng/settings:/etc/searxng:rw \
  searxng/searxng
```

#### 2.1.4 验证 SearXNG

访问 `http://localhost:8080/health` 检查服务状态：

```bash
curl http://localhost:8080/health
```

正常返回 `200 OK`。

### 2.2 手动部署 SearXNG

如需手动部署，请参考 [SearXNG 官方安装文档](https://docs.searxng.org/admin/installation.html)。

---

## 三、Python 依赖安装

### 3.1 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3.2 安装依赖

#### 3.2.1 从项目根目录安装

```bash
cd d:\project\opensource\WebSearch
pip install -e .
```

#### 3.2.2 安装运行时依赖

```bash
pip install requests pyyaml openai numpy
```

#### 3.2.3 安装开发依赖（可选）

```bash
pip install pytest pytest-cov
```

### 3.3 验证安装

```bash
python -c "from web_search import SearchOrchestratorV2; print('安装成功')"
```

---

## 四、配置文件说明

系统配置文件位于 `configs/` 目录下。

### 4.1 目录结构

```
configs/
├── whitelist.yaml      # 白名单配置
├── blacklist.yaml      # 黑名单配置
├── priority_rules.yaml # 优先级规则配置
├── providers.yaml      # 搜索引擎配置
├── llm.yaml           # LLM 模型配置 (v2 新增)
├── embedding.yaml     # Embedding 模型配置 (v2 新增)
├── reranker.yaml      # Reranker 权重配置 (v2 新增)
└── rewriter.yaml      # 查询改写配置 (v2 新增)
```

### 4.2 白名单配置 (whitelist.yaml)

白名单中的信源被视为高可信来源。

```yaml
whitelist:
  - name: "中国政府网"
    domain: "www.gov.cn"
    type: official
    level: national
    tags: ["政府", "政策"]
```

**配置字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 信源名称 |
| domain | string | 精确域名匹配 |
| domain_suffix | string | 域名后缀匹配（如 `.gov.cn`） |
| domain_pattern | string | 通配符模式匹配 |
| type | string | 信源类型：official/media/kol |
| level | string | 信源层级：national/provincial/municipal/local |
| tags | list | 标签，用于分类 |

### 4.3 黑名单配置 (blacklist.yaml)

黑名单中的信源将被标记为不可信。

```yaml
blacklist:
  - domain: "fake-news-example.cn"
    reason: "已核实发布虚假信息"
    severity: high
```

**配置字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| domain | string | 精确域名匹配 |
| domain_pattern | string | 通配符模式匹配 |
| reason | string | 封禁原因 |
| severity | string | 严重程度：high/medium/low |

### 4.4 LLM 配置 (llm.yaml) - v2 新增

LLM 配置用于 QueryRewriter、LLMSourceClassifier 和 LLMCollisionJudge 模块。

```yaml
llm:
  openai:
    model: "gpt-4o"
    api_base: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    temperature: 0.3
    max_tokens: 2048

  azure:
    enabled: false
    api_base: "https://xxx.openai.azure.com"
    api_key: "${AZURE_OPENAI_KEY}"
    api_version: "2024-06-01"
    deployment_name: "gpt-4o"

  anthropic:
    enabled: false
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-5-sonnet-20241022"
```

**配置字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| model | string | 模型名称 |
| api_base | string | API 地址 |
| api_key | string | API 密钥（支持环境变量） |
| temperature | float | 生成温度参数 |
| max_tokens | int | 最大 token 数 |

### 4.5 Embedding 配置 (embedding.yaml) - v2 新增

Embedding 配置用于 EmbeddingSimilarityEngine 模块。

```yaml
embedding:
  openai:
    model: "text-embedding-3-small"
    dimension: 1536
    batch_size: 32
    api_base: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"

  local:
    enabled: false
    model_path: "/models/bge-large-zh"
    device: "cuda"
    batch_size: 16
```

**配置字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| model | string | Embedding 模型名称 |
| dimension | int | 向量维度 |
| batch_size | int | 批处理大小 |
| api_base | string | API 地址 |
| api_key | string | API 密钥（支持环境变量） |

### 4.6 Reranker 配置 (reranker.yaml) - v2 新增

Reranker 配置用于结果重排序的权重调整。

```yaml
reranker:
  weights:
    relevance: 0.4
    trustworthiness: 0.3
    freshness: 0.15
    authority: 0.15

  freshness:
    period_7d_score: 1.0
    period_30d_score: 0.8
    period_90d_score: 0.6
    period_1y_score: 0.4
    older_score: 0.2

  top_k: 10
```

**权重因子说明：**

| 因子 | 默认值 | 说明 |
|------|--------|------|
| relevance | 0.4 | 内容相关性权重 |
| trustworthiness | 0.3 | 信源可信度权重 |
| freshness | 0.15 | 时效性权重 |
| authority | 0.15 | 权威性权重 |

### 4.7 查询改写配置 (rewriter.yaml) - v2 新增

QueryRewriter 模块的配置。

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
      - "people.com.cn"
      - "cctv.com"
    enable_time_filter: true
    default_time_range: "1y"

  llm:
    model: "gpt-4o"
    temperature: 0.5
    max_tokens: 1024
```

### 4.8 优先级规则配置 (priority_rules.yaml)

```yaml
priority_rules:
  kol_thresholds:
    big: 1000000
    medium: 100000
    small: 10000
```

### 4.9 搜索引擎配置 (providers.yaml)

```yaml
providers:
  searxng:
    enabled: true
    base_url: "http://localhost:8080"
    api_key: null
    default_engines:
      - google
      - bing
    timeout: 30
    retry: 3
```

---

## 五、验证部署

### 5.1 检查 SearXNG 服务

```bash
curl http://localhost:8080/health
```

### 5.2 检查 LLM API 连接

```bash
python -c "from web_search.core.llm_client import LLMWrapper; print('LLM 配置正确')"
```

### 5.3 运行单元测试

```bash
cd d:\project\opensource\WebSearch
pytest tests/ -v
```

### 5.4 快速功能测试

创建测试脚本 `test_search_v2.py`：

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

    query_rewriter = QueryRewriter(llm_client=llm_client)
    source_classifier = LLMSourceClassifier(llm_client=llm_client)
    embedding_engine = EmbeddingSimilarityEngine(embedding_client=embedding_client)
    collision_judge = LLMCollisionJudge(llm_client=llm_client)
    reranker = Reranker()

    orchestrator = SearchOrchestratorV2(
        provider=provider,
        query_rewriter=query_rewriter,
        source_classifier=source_classifier,
        embedding_engine=embedding_engine,
        collision_judge=collision_judge,
        reranker=reranker
    )

    result = await orchestrator.search_with_trust_v2("人工智能最新发展")

    print(f"查询: {result.query}")
    print(f"改写查询: {result.metadata['rewrite_result'].rewritten_queries}")
    print(f"重排后结果数: {len(result.response.results)}")
    print(f"摘要: {result.summary}")

if __name__ == "__main__":
    asyncio.run(main())
```

运行测试：

```bash
python test_search_v2.py
```

---

## 六、v2 新增模块部署

### 6.1 QueryRewriter 模块

QueryRewriter 负责查询改写，包括意图理解、查询发散和查询增强。

依赖：
- LLM API 连接

配置：
- `configs/rewriter.yaml`

### 6.2 LLMSourceClassifier 模块

LLMSourceClassifier 负责信源提取、相关性判断和黑白名单查询。

依赖：
- LLM API 连接
- 黑白名单配置

### 6.3 EmbeddingSimilarityEngine 模块

EmbeddingSimilarityEngine 负责计算搜索结果间的语义相似度。

依赖：
- Embedding API 或本地模型

推荐模型：
| 模型 | 维度 | 适用场景 |
|------|------|----------|
| text-embedding-3-small | 1536 | 通用场景 |
| text-embedding-3-large | 3072 | 高精度场景 |
| bge-large-zh | 1024 | 中文场景 |

### 6.4 LLMCollisionJudge 模块

LLMCollisionJudge 负责对检测到的碰撞进行智能裁决。

依赖：
- LLM API 连接

### 6.5 Reranker 模块

Reranker 负责根据综合权重对结果进行重排序。

权重因子：
- relevance（相关性）
- trustworthiness（可信度）
- freshness（时效性）
- authority（权威性）

---

## 七、常见问题

### 7.1 SearXNG 连接失败

**问题**：`Connection refused` 或超时

**解决**：
1. 确认 SearXNG 容器正在运行：`docker ps | grep searxng`
2. 检查端口是否冲突：`netstat -an | grep 8080`
3. 重启 SearXNG：`docker restart searxng`

### 7.2 搜索结果为空

**问题**：搜索返回空结果

**解决**：
1. 检查网络是否能够访问 Google/Bing
2. 确认 SearXNG 中相应引擎已启用
3. 查看 SearXNG 日志：`docker logs searxng`

### 7.3 配置文件加载失败

**问题**：`ConfigurationException`

**解决**：
1. 确认 `configs/` 目录存在且包含所有 YAML 文件
2. 检查 YAML 语法是否正确
3. 使用绝对路径加载配置：`load_config("/full/path/to/configs")`

### 7.4 LLM API 连接失败

**问题**：`OpenAI API Error` 或类似错误

**解决**：
1. 确认 API Key 已正确设置（环境变量或配置文件）
2. 检查网络能否访问 LLM API
3. 验证 API Key 是否有权限

### 7.5 Embedding 向量计算失败

**问题**：`EmbeddingError` 或向量维度不匹配

**解决**：
1. 确认 Embedding 模型配置正确
2. 检查向量维度是否与模型配置一致
3. 如使用本地模型，确认模型文件已下载

---

## 八、扩展阅读

- [SearXNG 官方文档](https://docs.searxng.org/)
- [架构设计文档 v2](./可信联网搜索系统架构设计v2.md)
- [使用指南](./usage.md)
