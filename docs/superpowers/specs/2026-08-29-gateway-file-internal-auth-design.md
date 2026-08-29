# Gateway 到文件服务的内部认证设计

## 目标

使 API Gateway 转发至文件服务 `/inner/**` 的请求具备可验证的服务身份、防篡改和跨 Pod 防重放能力；保留 `X-Inner: 1` 作为兼容、路由和审计标记，但不把它作为授权依据。

## 边界与信任模型

外部客户端是不可信的：它可以伪造任何 HTTP 头，包括 `X-Inner` 和 `X-Internal-*`。Gateway 是唯一允许代表外部请求访问文件服务内部接口的受信调用方，服务身份为 `api-gateway`。文件服务只在 HMAC 验证成功后处理 `/inner/**`。

HMAC 密钥不提交到仓库。生产环境通过 Kubernetes Secret 或 Nacos 加密配置为 Gateway 和 file 注入相同值；所有 Pod 使用 Redis 的原子 nonce 保留记录，确保任一签名请求只能被整个集群接受一次。

## 请求流与入口边界

1. Gateway 的入口过滤器删除外部传入的 `X-User-*`、`X-Inner` 及全部 `X-Internal-*` 可信头。
2. 路由过滤器（例如 `StripPrefix=2`）将 `/api/file/...` 改写为下游真实路径 `/inner/file/...`。
3. Gateway 内部签名过滤器在所有路由路径改写完成、Netty 发起网络转发之前运行。它仅在改写后的路径以 `/inner/` 开头时运行：生成 UUID nonce 和 UTC 毫秒时间戳，写入 `X-Inner: 1`，并对 `METHOD + path?query + api-gateway + timestamp + nonce` 产生 HMAC-SHA-256 签名。
4. file 的 WebFlux 过滤器验证签名、时钟窗口和 Redis nonce；签名无效返回 401，Redis 不可用时返回 503（fail closed）。

`X-Inner: 1` 不参与签名验证，也不能单独放行请求。它仅为旧逻辑、日志和故障排查提供稳定标识。

Gateway 是公网入口时，不能因路径成为 `/inner/**` 就自动签名：例如 `/api/file/inner/file/**` 经 `StripPrefix=2` 会变为 `/inner/file/**`，自动签名会把外部客户端提升成内部调用方。因此 Gateway 签名另由 `gateway.internal-signing.enabled=true` 显式开关保护，默认关闭；只有在该路由已由 Gateway 完成外部用户认证和授权、或入口在网络上确实只允许受信服务时才能开启。没有此前提时，文件服务内部 API 应由 Nacos/Feign 直接调用，Gateway 不参与签名。

## 配置与上线

Gateway 和 file 的 HMAC 基础配置：

```yaml
internal-auth:
  enabled: true
  service-id: api-gateway # Gateway；file 可填 file，仅用于其作为调用方的场景
  secret: ${INTERNAL_AUTH_SECRET}
  max-clock-skew: 5m
```

配置中的 `secret` 只引用部署环境变量或密钥管理系统。`gateway.internal-signing.enabled` 必须保持缺省/`false`，直到 Gateway 的外部用户认证与路由授权已经实现；避免把公网入口转换成内部身份。

## 错误、安全与性能

- Gateway 不记录密钥、签名或 nonce。
- 每个请求只做一次 SHA-256 HMAC 和一个 Redis 原子写入；不会引入阻塞调用。
- Header 清洗发生在签名之前，防止客户端覆盖服务身份。
- 覆盖带 query 的请求，保证签名不能被换到另一组查询参数。

## 验收测试

1. 外部请求携带 `X-Inner` 或任一 `X-Internal-*` 时，Gateway 在下游请求中移除它们。
2. Gateway 在路径改写后为 `/inner/**` 写入 `X-Inner: 1` 和四个有效的 HMAC 头；签名覆盖改写后的 path+query。
3. 非 `/inner/**` 路由不会被添加内部认证头。
4. file 接受 Gateway 生成的请求；伪造 `X-Inner: 1`、缺失/无效签名、重放 nonce 都被拒绝。
