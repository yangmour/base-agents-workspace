# Gateway File Internal Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Gateway 对转发给 file `/inner/**` 的请求安全签名，并保留 `X-Inner: 1` 兼容标识。

**Architecture:** Gateway 的入口过滤器先无条件删除客户端伪造的内部可信头。一个在所有路由路径改写之后、Netty 网络转发之前运行的全局过滤器仅对最终 `/inner/**` 请求生成 HMAC 头和 `X-Inner: 1`；file 已有 WebFlux HMAC 验证过滤器，以 Redis nonce 提供跨 Pod 防重放。密钥只从部署配置注入，不写入仓库。

**Tech Stack:** Java 21、Spring Boot 3.2、Spring Cloud Gateway 4.1、Reactor、JUnit 5、Mockito。

## Global Constraints

- Gateway 服务身份固定由配置 `internal-auth.service-id` 提供，生产值为 `api-gateway`。
- `internal-auth.secret` 只引用 Nacos 加密配置或 Kubernetes Secret，禁止写入 YAML、测试外的源码或日志。
- `X-Inner: 1` 仅作兼容和审计标识，任何授权决定只接受有效 HMAC。
- 外部输入的 `X-Inner` 和全部 `X-Internal-*` 必须先删除。
- 签名覆盖 HTTP 方法、改写后的 raw path+query、服务身份、UTC 毫秒时间戳、唯一 nonce。
- 每次提交只包含本任务创建或修改的文件；使用 `git commit --only`，不带入已有暂存改动。

---

### Task 1: 清洗客户端伪造的内部头

**Files:**
- Modify: `java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/AuthGlobalFilter.java`
- Create: `java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/AuthGlobalFilterTest.java`

**Interfaces:**
- Consumes: `GatewayFilterChain#filter(ServerWebExchange)`
- Produces: 下游请求不含 `X-Inner`、`X-Internal-Service`、`X-Internal-Timestamp`、`X-Internal-Nonce`、`X-Internal-Signature` 及既有 `X-User-*`。

- [ ] **Step 1: 写入失败测试**

```java
@Test
void shouldStripClientSuppliedInternalHeadersBeforeForwarding() {
    ServerHttpRequest request = MockServerHttpRequest.get("/api/file/a")
            .header("X-Inner", "1")
            .header("X-Internal-Service", "forged")
            .header("X-Internal-Timestamp", "1")
            .header("X-Internal-Nonce", "forged")
            .header("X-Internal-Signature", "forged")
            .build();
    AtomicReference<ServerWebExchange> forwarded = new AtomicReference<>();

    new AuthGlobalFilter().filter(MockServerWebExchange.from(request), exchange -> {
        forwarded.set(exchange);
        return Mono.empty();
    }).block();

    assertThat(forwarded.get().getRequest().getHeaders())
            .doesNotContainKeys("X-Inner", "X-Internal-Service", "X-Internal-Timestamp",
                    "X-Internal-Nonce", "X-Internal-Signature");
}
```

- [ ] **Step 2: 运行失败测试**

Run: `mvn -q -pl server/api-gateway -am -Drevision=1.0 -Denforcer.skip=true -Dtest=AuthGlobalFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL，因为实现尚未清洗内部头。

- [ ] **Step 3: 最小实现**

在 `AuthGlobalFilter` 的请求头变换中增加：

```java
headers.remove("X-Inner");
headers.remove("X-Internal-Service");
headers.remove("X-Internal-Timestamp");
headers.remove("X-Internal-Nonce");
headers.remove("X-Internal-Signature");
```

- [ ] **Step 4: 验证通过**

Run: `mvn -q -pl server/api-gateway -am -Drevision=1.0 -Denforcer.skip=true -Dtest=AuthGlobalFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/AuthGlobalFilter.java \
  java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/AuthGlobalFilterTest.java
git commit --only -m "fix(gateway): 清洗伪造内部认证头" -- \
  java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/AuthGlobalFilter.java \
  java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/AuthGlobalFilterTest.java
```

### Task 2: 为改写后的内部路径生成 Gateway 签名

**Files:**
- Create: `java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilter.java`
- Create: `java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilterTest.java`

**Interfaces:**
- Consumes: `HmacServiceRequestSigner`、`InternalServiceAuthenticationProperties`、`ServerWebExchange`
- Produces: 对 `/inner/**` 添加 `X-Inner: 1` 及四个有效 HMAC 请求头；其他路径保持不变。

- [ ] **Step 1: 写入失败测试**

```java
@Test
void shouldSignRewrittenInnerPathAndAddCompatibilityHeader() {
    HmacServiceRequestSigner signer = new HmacServiceRequestSigner("test-secret");
    InternalRequestSigningGlobalFilter filter = new InternalRequestSigningGlobalFilter(
            signer, "api-gateway", Clock.fixed(Instant.ofEpochMilli(1710000000000L), ZoneOffset.UTC),
            () -> "nonce-123");
    AtomicReference<ServerWebExchange> forwarded = new AtomicReference<>();

    filter.filter(MockServerWebExchange.from(MockServerHttpRequest.post("/inner/file/user?a=1").build()),
            exchange -> { forwarded.set(exchange); return Mono.empty(); }).block();

    HttpHeaders headers = forwarded.get().getRequest().getHeaders();
    assertThat(headers.getFirst("X-Inner")).isEqualTo("1");
    assertThat(signer.verify("POST", "/inner/file/user?a=1", "api-gateway", 1710000000000L,
            "nonce-123", headers.getFirst("X-Internal-Signature"))).isTrue();
}

@Test
void shouldNotAddInternalHeadersToPublicPath() {
    AtomicReference<ServerWebExchange> forwarded = new AtomicReference<>();
    filter.filter(MockServerWebExchange.from(MockServerHttpRequest.get("/api/user").build()),
            exchange -> { forwarded.set(exchange); return Mono.empty(); }).block();

    assertThat(forwarded.get().getRequest().getHeaders())
            .doesNotContainKeys("X-Inner", "X-Internal-Service", "X-Internal-Timestamp",
                    "X-Internal-Nonce", "X-Internal-Signature");
}
```

- [ ] **Step 2: 运行失败测试**

Run: `mvn -q -pl server/api-gateway -am -Drevision=1.0 -Denforcer.skip=true -Dtest=InternalRequestSigningGlobalFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: FAIL，因为过滤器尚不存在。

- [ ] **Step 3: 最小实现**

创建条件组件：`@ConditionalOnProperty(prefix = "internal-auth", name = "enabled", havingValue = "true")`。实现 `GlobalFilter, Ordered`，返回 `Ordered.LOWEST_PRECEDENCE - 1`：它位于 NettyRoutingFilter（`Ordered.LOWEST_PRECEDENCE`）之前，因此能看到任意 Nacos 路由过滤器完成后的最终路径，避免依赖 `StripPrefix` 在配置中的位置。只在 `getURI().getRawPath().startsWith("/inner/")` 时构造 `rawPath + '?' + rawQuery`，清除再写入 `X-Inner` 和四个认证头；nonce 使用 UUID，时间使用 UTC。

- [ ] **Step 4: 验证通过**

Run: `mvn -q -pl server/api-gateway -am -Drevision=1.0 -Denforcer.skip=true -Dtest=InternalRequestSigningGlobalFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS，且签名验证的是含 query 的 `/inner/**` 路径。

- [ ] **Step 5: 提交**

```bash
git add java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilter.java \
  java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilterTest.java
git commit --only -m "feat(gateway): 签名内部服务转发请求" -- \
  java-base-module/server/api-gateway/src/main/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilter.java \
  java-base-module/server/api-gateway/src/test/java/com/xiwen/gateway/filter/InternalRequestSigningGlobalFilterTest.java
```

### Task 3: 验证 Gateway 与 file 的信任契约

**Files:**
- Modify: `java-base-module/server/file/src/test/java/com/xiwen/server/file/config/InternalServiceAuthenticationWebFilterTest.java`
- Create: `docs/security/gateway-file-internal-auth-rollout.md`

**Interfaces:**
- Consumes: Gateway 生成的四个 HMAC 请求头和 Redis-backed `InternalRequestNonceStore`
- Produces: 证明 `X-Inner` 不能单独绕过认证，并给出不产生 401 中断的上线顺序。

- [ ] **Step 1: 写入失败契约测试**

```java
@Test
void shouldRejectCompatibilityHeaderWithoutHmacSignature() {
    MockServerWebExchange exchange = MockServerWebExchange.from(MockServerHttpRequest
            .post("/inner/file/module").header("X-Inner", "1").build());

    filter.filter(exchange, ignored -> Mono.empty()).block();

    assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
}
```

- [ ] **Step 2: 运行测试确认现状**

Run: `mvn -q -pl server/file -am -Drevision=1.0 -Denforcer.skip=true -Dtest=InternalServiceAuthenticationWebFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS（这是现有安全行为的回归证明；若失败，先修复 file 过滤器，不继续上线）。

- [ ] **Step 3: 写入上线说明**

文档必须要求：先为 Gateway 和 file 注入相同 `INTERNAL_AUTH_SECRET`，部署 Gateway 签名能力，使用预发布 `/api/file/**` 做验收，再将 file `internal-auth.enabled` 设为 `true`；密钥轮换必须采用双版本或短维护窗口，且 file Pod 仅允许 Gateway/network mesh 流量。

- [ ] **Step 4: 联合验证**

Run: `mvn -q -pl server/api-gateway,server/file -am -Drevision=1.0 -Denforcer.skip=true -Dtest=AuthGlobalFilterTest,InternalRequestSigningGlobalFilterTest,InternalServiceAuthenticationWebFilterTest -Dsurefire.failIfNoSpecifiedTests=false test`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add java-base-module/server/file/src/test/java/com/xiwen/server/file/config/InternalServiceAuthenticationWebFilterTest.java \
  docs/security/gateway-file-internal-auth-rollout.md
git commit --only -m "docs(security): 补充网关文件认证上线指引" -- \
  java-base-module/server/file/src/test/java/com/xiwen/server/file/config/InternalServiceAuthenticationWebFilterTest.java \
  docs/security/gateway-file-internal-auth-rollout.md
```
