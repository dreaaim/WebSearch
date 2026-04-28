# SearXNG 使用指南

## 一、SearXNG 概述

SearXNG 是一个开源的元搜索引擎，可以聚合多个搜索引擎的结果，保护用户隐私，避免被单一搜索引擎追踪。

### 核心特性

- **隐私保护**：不记录用户搜索历史，不追踪用户行为
- **元搜索**：同时搜索 Google、Bing、Baidu 等多个引擎
- **可定制**：支持自定义启用的搜索引擎
- **自托管**：可以部署在自己的服务器上
- **API 支持**：提供 JSON 格式的 API 接口

---

## 二、配置详解

### 2.1 settings.yml 结构

```yaml
use_default_settings: true  # 使用默认设置

general:
  debug: false              # 调试模式
  instance_name: "实例名称"  # 实例显示名称
  enable_metrics: true      # 启用性能指标

search:
  formats:
    - html                  # HTML 界面
    - json                  # JSON API
  default_format: json      # 默认返回格式
  max_results: 20          # 最大结果数

server:
  secret_key: "密钥"        # 会话密钥
  bind_address: "0.0.0.0"   # 监听地址
  port: 8080               # 监听端口
  limiter: false           # 是否限制请求频率
  public_instance: false   # 是否公开实例

engines:                   # 搜索引擎配置
  - name: google
    engine: google
    shortcut: g
    disabled: false        # 是否禁用

outgoing:                  # 出站请求配置
  request_timeout: 10.0    # 请求超时（秒）
  max_request_timeout: 30.0
  pool_connections: 100    # 连接池大小
  pool_maxsize: 20         # 最大连接数
```

### 2.2 引擎配置说明

每个搜索引擎的配置字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 引擎唯一标识 |
| engine | string | 是 | 引擎类型（与 SearXNG 内置适配器匹配） |
| shortcut | string | 否 | 搜索快捷键 |
| disabled | boolean | 否 | 是否禁用（默认 false） |

---

## 三、常见问题排查

### 3.1 问题：配置的引擎在界面只显示部分

**现象**：在 `settings.yml` 中配置了多个引擎，但 Web 界面只显示部分引擎。

**原因分析**：

1. **引擎加载失败**：某些引擎在启动时因网络问题或 API 变更加载失败
2. **引擎被自动禁用**：SearXNG 会检测引擎可用性，连续失败后自动禁用
3. **引擎分类隐藏**：部分引擎属于特殊分类（如图片、视频），默认不显示
4. **配置语法错误**：YAML 格式错误导致部分配置未生效

**解决方案**：

#### 方法 1：检查引擎状态

访问 SearXNG 界面，点击底部的**响应时间**统计，查看各引擎状态：

- ✅ 显示响应时间：引擎正常
- ❌ 拒绝访问/解析错误：引擎配置或网络问题
- ⚠️ 请求过于频繁：被目标引擎限流

#### 方法 2：查看 Docker 日志

```bash
docker logs searxng
```

查找包含 `engine` 或 `load` 的错误信息。

#### 方法 3：强制启用引擎

在 `settings.yml` 中明确设置 `disabled: false`：

```yaml
engines:
  - name: baidu
    engine: baidu
    shortcut: bd
    disabled: false  # 明确启用
```

#### 方法 4：检查网络代理

如果引擎需要代理访问（如 Google），确保代理配置正确：

```yaml
# docker-compose.yml
environment:
  - HTTP_PROXY=http://host.docker.internal:7890
  - HTTPS_PROXY=http://host.docker.internal:7890
extra_hosts:
  - "host.docker.internal:host-gateway"
```

### 3.2 常见引擎错误

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| 请求过于频繁 | 被目标引擎限流 | 降低请求频率，使用代理 IP |
| 拒绝访问 | IP 被封禁或需要验证码 | 更换 IP 或使用代理 |
| 解析错误 | 引擎 API 变更或网络超时 | 检查引擎配置，更新 SearXNG |
| 连接超时 | 网络不通或代理失效 | 检查网络连接和代理配置 |

---

## 四、中国可用搜索引擎配置

### 4.1 推荐配置（无需代理）

```yaml
engines:
  # 中文搜索引擎
  - name: baidu
    engine: baidu
    shortcut: bd
    disabled: false
    
  - name: 360search
    engine: 360search
    shortcut: 360
    disabled: false
    
  - name: sogou
    engine: sogou
    shortcut: sg
    disabled: false
    
  - name: bing
    engine: bing
    shortcut: b
    disabled: false
    # 可选：指定必应中国
    base_url: "https://cn.bing.com/"
    
  - name: bilibili
    engine: bilibili
    shortcut: bili
    disabled: false
```

### 4.2 需要代理的搜索引擎

```yaml
engines:
  # 需要代理访问
  - name: google
    engine: google
    shortcut: g
    disabled: false
    
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    disabled: false
    
  - name: brave
    engine: brave
    shortcut: br
    disabled: false
```

### 4.3 代理配置示例

```yaml
# docker-compose.yml
version: '3.8'

services:
  searxng:
    image: searxng/searxng:latest
    environment:
      - HTTP_PROXY=http://host.docker.internal:7890
      - HTTPS_PROXY=http://host.docker.internal:7890
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**注意**：`7890` 是常见代理端口，根据实际代理软件调整：
- Clash: 7890
- V2Ray: 10809
- Shadowsocks: 1080

---

## 五、使用方式

### 5.1 Web 界面访问

浏览器访问：`http://localhost:8080`

### 5.2 API 调用

#### 基本搜索

```bash
curl "http://localhost:8080/search?q=人工智能&format=json"
```

#### 指定搜索引擎

```bash
curl "http://localhost:8080/search?q=AI&format=json&engines=google,bing,baidu"
```

#### 搜索类别

```bash
# 通用搜索
curl "http://localhost:8080/search?q=python&categories=general&format=json"

# 图片搜索
curl "http://localhost:8080/search?q=cat&categories=images&format=json"

# 新闻搜索
curl "http://localhost:8080/search?q=news&categories=news&format=json"

# 视频搜索
curl "http://localhost:8080/search?q=tutorial&categories=videos&format=json"
```

### 5.3 搜索类别说明

| 类别 | 说明 | 包含引擎 |
|------|------|----------|
| general | 通用搜索 | Google、Bing、Baidu 等 |
| images | 图片搜索 | Google Images、Bing Images |
| videos | 视频搜索 | YouTube、Bilibili、Vimeo |
| news | 新闻搜索 | Google News、Bing News |
| map | 地图搜索 | OpenStreetMap、Google Maps |
| music | 音乐搜索 | Spotify、SoundCloud |

---

## 六、性能优化

### 6.1 调整超时时间

如果某些引擎响应慢，增加超时时间：

```yaml
outgoing:
  request_timeout: 15.0      # 默认超时
  max_request_timeout: 60.0  # 最大超时
```

### 6.2 禁用慢引擎

禁用响应慢或不稳定的引擎：

```yaml
engines:
  - name: slow_engine
    disabled: true
```

### 6.3 调整结果数量

```yaml
search:
  max_results: 10  # 减少结果数提高速度
```

---

## 七、维护与监控

### 7.1 查看引擎状态

访问 `http://localhost:8080/preferences` 查看各引擎状态。

### 7.2 重启容器

```bash
docker restart searxng
```

### 7.3 更新配置

修改配置后重启容器：

```bash
cd build
docker-compose down
docker-compose up -d
```

### 7.4 查看日志

```bash
# 实时日志
docker logs -f searxng

# 最近 100 行
docker logs --tail 100 searxng
```

---

## 八、故障排除清单

- [ ] 检查 Docker 容器是否运行：`docker ps | grep searxng`
- [ ] 检查端口是否监听：`netstat -an | grep 8080`
- [ ] 检查代理配置是否正确
- [ ] 检查 `settings.yml` YAML 语法
- [ ] 查看 Docker 日志是否有错误
- [ ] 访问引擎状态页面检查各引擎可用性
- [ ] 尝试在浏览器直接访问目标引擎确认网络连通

---

## 九、参考资源

- [SearXNG 官方文档](https://docs.searxng.org/)
- [SearXNG GitHub](https://github.com/searxng/searxng)
- [可用引擎列表](https://docs.searxng.org/admin/settings/settings.html#engines)
- [部署指南](./deployment.md)
- [使用指南](./usage.md)
