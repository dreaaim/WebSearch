# SearXNG 配置问题分析与解决方案

## 问题概述

在部署和配置 SearXNG 容器时，遇到了多个配置相关的问题，主要包括：配置文件位置、配置验证失败、secret_key 要求、引擎列表显示异常等。

---

## 问题一：配置文件位置错误

### 现象
修改 `build/searxng/settings.yml` 后，容器内 `/etc/searxng/settings.yml` 的内容没有更新。

### 根本原因
docker-compose.yml 中的挂载配置：
```yaml
volumes:
  - ./searxng/settings:/etc/searxng:rw
```

这是**目录挂载**，会直接将宿主机的 `./searxng/settings` 目录映射到容器的 `/etc/searxng/`。因此配置文件必须放在 `./searxng/settings/settings.yml`，而不是 `./searxng/settings.yml`。

### 解决方案
确保配置文件放在正确的位置：
```
build/
└── searxng/
    └── settings/
        └── settings.yml    # 正确位置
```

---

## 问题二：use_default_settings: false 导致配置验证失败

### 现象
使用 `use_default_settings: false` 时，SearXNG 启动失败，日志显示：
```
ValueError: Invalid settings.yml
Expected `object`, got `null`
```

### 根本原因
当 `use_default_settings: false` 时，SearXNG 会严格验证配置文件的完整性和结构。任何缺失的必需字段或 null 值都会导致验证失败。新配置往往缺少 SearXNG 内部需要的默认字段。

### 解决方案
继续使用 `use_default_settings: true`，只覆盖需要自定义的部分：
```yaml
use_default_settings: true  # 使用默认设置

server:
  secret_key: "自定义密钥"  # 覆盖默认配置

engines:
  - name: baidu
    engine: baidu
  # ... 只列出需要的引擎
```

---

## 问题三：secret_key 未修改导致启动失败

### 现象
使用 `use_default_settings: true` 时，容器日志警告：
```
ERROR:searx.webapp: server.secret_key is not changed. Please use something else instead of ultrasecretkey.
```

### 根本原因
新版 SearXNG 要求必须修改默认的 `secret_key`。如果使用默认值 `ultrasecretkey`，SearXNG 会持续报错并拒绝正常工作。

### 解决方案
在配置文件中设置自定义的 secret_key：
```yaml
server:
  secret_key: "web-search-trusted-key-2026-change-me"
```

---

## 问题四：浏览器显示旧的引擎列表

### 现象
修改配置并重启容器后，浏览器中的引擎列表没有更新，仍然显示旧的配置。

### 根本原因
浏览器缓存了旧的偏好设置页面。

### 解决方案
1. **强制刷新浏览器**：Ctrl + F5（Windows）或 Cmd + Shift + R（macOS）
2. **清除浏览器缓存**：设置 → 隐私与安全 → 清除浏览数据
3. **使用无痕/隐私模式**：在隐私窗口中访问页面

---

## 问题五：禁用的引擎仍在列表中显示

### 现象
在配置文件中设置 `disabled: true` 的引擎（如 brave, karmasearch, startpage），在 preferences 页面仍然显示，只是开关为灰色。

### 根本原因
这是 **SearXNG 的设计行为**，而非 bug。SearXNG 在 preferences 页面会显示所有已知引擎的状态，包括已禁用的。这是为了让管理员能够：
- 看到哪些引擎不可用
- 了解引擎被禁用的原因
- 方便后续重新启用

### 解决方案
**方案 1**：接受现状
- 已禁用的引擎不会参与搜索
- 只是在页面显示状态信息

**方案 2**：使用 `use_default_settings: false`
- 完全自定义引擎列表
- 只列出需要启用的引擎
- 未列出的引擎不会显示

```yaml
use_default_settings: false

engines:
  - name: baidu
    engine: baidu
  - name: 360search
    engine: 360search
  - name: sogou
    engine: sogou
  - name: bing
    engine: bing
  - name: bilibili
    engine: bilibili
  - name: google
    engine: google
  - name: duckduckgo
    engine: duckduckgo
```

---

## 最终有效配置

```yaml
use_default_settings: true

server:
  secret_key: "web-search-trusted-key-2026-change-me"

search:
  formats:
    - html
    - json
  enable_api: true

engines:
  - name: baidu
    engine: baidu
    disabled: false
  - name: 360search
    engine: 360search
    disabled: false
  - name: sogou
    engine: sogou
    disabled: false
  - name: bilibili
    engine: bilibili
    disabled: false
  - name: google
    engine: google
    disabled: false
  - name: duckduckgo
    engine: duckduckgo
    disabled: false
```

---

## 调试命令汇总

```bash
# 重启容器使配置生效
cd d:\project\opensource\WebSearch\build
docker-compose restart searxng

# 查看容器日志
docker logs searxng --tail 50

# 实时查看日志
docker logs -f searxng

# 检查容器内配置文件内容
docker exec searxng cat /etc/searxng/settings.yml

# 完全重建容器
docker-compose down
docker-compose up -d
```

---

## 经验总结

1. **目录挂载 vs 文件挂载**：docker-compose 的 volume 挂载如果是目录，会映射整个目录的内容；如果是文件，需要确保文件存在且路径正确。

2. **use_default_settings 的选择**：
   - `true`：适合大多数场景，只需覆盖少量配置
   - `false`：需要完整定义所有配置，适合完全自定义的部署

3. **SearXNG 版本差异**：不同版本的 SearXNG 可能有不同的默认配置要求，建议查看官方文档获取最新信息。

4. **浏览器缓存**：Web 应用的配置修改后，记得清除浏览器缓存或使用无痕模式。

---

## 参考链接

- [SearXNG 官方文档](https://docs.searxng.org/)
- [SearXNG GitHub](https://github.com/searxng/searxng)
- [SearXNG 引擎配置](https://docs.searxng.org/admin/settings/settings.html#engines)
