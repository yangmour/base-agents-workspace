# Java 鉴权 P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Java 鉴权链路中的 Token 重复解析、请求上下文残留和权限注解可能失效问题，并建立可执行的安全回归测试。

**Architecture:** `JwtAuthenticationFilter` 作为 HTTP 认证适配器，只把裸 Token 交给 `SecurityAuthProvider`，并在请求结束时清理双上下文。MVC 完成 HandlerMapping 后，由 `HandlerMethodAuthorizationInterceptor` 执行权限、角色和 ABAC 注解授权；Spring Security URL 规则只负责公开路径和登录状态。

**Tech Stack:** JDK 21、Spring Boot 3.2、Spring Security 6、Spring MVC、Maven、JUnit 5、Mockito、Spring Test。

## Global Constraints

- 范围只包括 `java-base-module/common/base-security` 及其测试；除非集成测试证明必须调整，否则不修改业务 Controller。
- `base-authz` 与 `base-security` 保持两个独立 Maven 模块，依赖方向保持 `base-security -> base-authz`。
- `SecurityAuthProvider.validateToken(String rawToken)` 只接收裸 Token。
- 认证失败为 401；权限、角色、ABAC 或授权执行异常为拒绝访问，不允许默认放行。
- 每个生产代码变更前必须先写测试并确认测试因目标缺陷失败。
- 每个任务完成后单独提交；测试和使其通过的最小实现处于同一个提交。
- 不提交有效密钥、Token、Cookie 或环境变量内容。
- 后端 HTTP 响应继续遵循现有兼容格式；本计划不重构全局错误码。

---

## 文件结构

- 修改：`java-base-module/common/base-security/pom.xml`
  - 增加 `spring-boot-starter-test` 测试依赖并锁定 Surefire 3.2.5。
- 新增：`java-base-module/common/base-security/src/test/java/com/xiwen/security/service/LocalJwtSecurityAuthProviderTest.java`
  - 固定 Provider 的裸 Token 契约。
- 新增：`java-base-module/common/base-security/src/test/java/com/xiwen/security/filter/JwtAuthenticationFilterTokenContractTest.java`
  - 固定 Bearer 请求头解析边界。
- 新增：`java-base-module/common/base-security/src/test/java/com/xiwen/security/filter/JwtAuthenticationFilterContextTest.java`
  - 固定正常和异常请求的上下文生命周期。
- 新增：`java-base-module/common/base-security/src/main/java/com/xiwen/security/interceptor/HandlerMethodAuthorizationInterceptor.java`
  - 在 MVC HandlerMapping 后执行权限、角色和 ABAC 注解。
- 新增：`java-base-module/common/base-security/src/test/java/com/xiwen/security/interceptor/HandlerMethodAuthorizationInterceptorTest.java`
  - 覆盖注解授权矩阵和 fail-closed 行为。
- 修改：`java-base-module/common/base-security/src/main/java/com/xiwen/security/config/BaseSecurityAutoConfiguration.java`
  - 注册 MVC 授权拦截器，默认安全链只负责认证。
- 新增：`java-base-module/common/base-security/src/test/java/com/xiwen/security/SecurityPipelineIntegrationTest.java`
  - 串联过滤器、上下文和 HandlerMethod 授权做回归验证。

## Task 1: 统一 JWT 裸令牌契约

**Files:**
- Modify: `java-base-module/common/base-security/pom.xml`
- Modify: `java-base-module/common/base-security/src/main/java/com/xiwen/security/service/SecurityAuthProvider.java`
- Modify: `java-base-module/common/base-security/src/main/java/com/xiwen/security/service/LocalJwtSecurityAuthProvider.java`
- Modify: `java-base-module/common/base-security/src/main/java/com/xiwen/security/filter/JwtAuthenticationFilter.java`
- Create: `java-base-module/common/base-security/src/test/java/com/xiwen/security/service/LocalJwtSecurityAuthProviderTest.java`
- Create: `java-base-module/common/base-security/src/test/java/com/xiwen/security/filter/JwtAuthenticationFilterTokenContractTest.java`

**Interfaces:**
- Produces: `SecurityAuthProvider.validateToken(String rawToken)`，参数只允许裸 Token。
- Produces: `JwtAuthenticationFilter` 是唯一解析 Authorization scheme 的组件。
- Consumes: `JwtUtil.validateToken(String)` 和 `JwtUtil.extractUserId(String)` 均接收裸 Token。

- [ ] **Step 1: 增加测试基础设施**

在 `base-security/pom.xml` 的 `<dependencies>` 增加：

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
```

在 POM 增加：

```xml
<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-surefire-plugin</artifactId>
            <version>3.2.5</version>
        </plugin>
    </plugins>
</build>
```

- [ ] **Step 2: 写 Provider 裸 Token 失败测试**

创建 `LocalJwtSecurityAuthProviderTest.java`：

```java
package com.xiwen.security.service;

import com.xiwen.feign.auth.api.inner.InnerPermissionValidationClient;
import com.xiwen.security.jwt.JwtUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class LocalJwtSecurityAuthProviderTest {

    private final JwtUtil jwtUtil = mock(JwtUtil.class);
    private final InnerPermissionValidationClient client = mock(InnerPermissionValidationClient.class);
    private final LocalJwtSecurityAuthProvider provider =
            new LocalJwtSecurityAuthProvider(jwtUtil, client);

    @Test
    void shouldValidateRawTokenWithoutParsingAuthorizationHeaderAgain() {
        when(jwtUtil.validateToken("raw-token")).thenReturn(true);
        when(jwtUtil.extractUserId("raw-token")).thenReturn(42L);

        assertEquals(42L, provider.validateToken("raw-token"));

        verify(jwtUtil, never()).extractTokenFromHeader("raw-token");
        verify(jwtUtil).validateToken("raw-token");
        verify(jwtUtil).extractUserId("raw-token");
    }

    @Test
    void shouldRejectInvalidRawToken() {
        when(jwtUtil.validateToken("invalid-token")).thenReturn(false);

        assertNull(provider.validateToken("invalid-token"));
    }
}
```

- [ ] **Step 3: 写过滤器协议边界失败测试**

创建 `JwtAuthenticationFilterTokenContractTest.java`：

```java
package com.xiwen.security.filter;

import com.xiwen.authz.domain.PermissionProfile;
import com.xiwen.security.context.SecurityContextHelper;
import com.xiwen.security.service.SecurityAuthProvider;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class JwtAuthenticationFilterTokenContractTest {

    private final SecurityAuthProvider provider = mock(SecurityAuthProvider.class);
    private final FilterChain chain = mock(FilterChain.class);
    private final JwtAuthenticationFilter filter = new JwtAuthenticationFilter(provider);

    @AfterEach
    void clearContext() {
        SecurityContextHelper.clear();
    }

    @Test
    void shouldPassOnlyRawBearerCredentialsToProvider() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/secure");
        request.addHeader("Authorization", "Bearer raw-token");
        MockHttpServletResponse response = new MockHttpServletResponse();
        when(provider.validateToken("raw-token")).thenReturn(42L);
        when(provider.loadPermissions(42L)).thenReturn(new PermissionProfile());

        filter.doFilter(request, response, chain);

        verify(provider).validateToken("raw-token");
        verify(chain).doFilter(request, response);
    }

    @Test
    void shouldRejectNonBearerSchemeBeforeCallingProvider() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/secure");
        request.addHeader("Authorization", "Basic credentials");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, chain);

        assertEquals(401, response.getStatus());
        verify(provider, never()).validateToken("Basic credentials");
        verify(chain, never()).doFilter(request, response);
    }
}
```

- [ ] **Step 4: 运行测试，确认 RED**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0 \
  -Dtest=LocalJwtSecurityAuthProviderTest,JwtAuthenticationFilterTokenContractTest \
  -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: FAIL。Provider 测试应显示没有以 `raw-token` 调用 `validateToken`，非 Bearer 测试应显示 Provider 被错误调用。

- [ ] **Step 5: 写最小实现**

修改 `SecurityAuthProvider` 参数名和注释：

```java
/** 验证裸 Token，返回 userId；无效返回 null。 */
Long validateToken(String rawToken);
```

修改 `LocalJwtSecurityAuthProvider.validateToken`：

```java
@Override
public Long validateToken(String rawToken) {
    try {
        if (!jwtUtil.validateToken(rawToken)) {
            return null;
        }
        return jwtUtil.extractUserId(rawToken);
    } catch (Exception e) {
        return null;
    }
}
```

修改过滤器的请求头解析，只接受 Bearer：

```java
private String extractToken(HttpServletRequest request) throws UnauthorizedException {
    String header = request.getHeader("Authorization");
    if (!StringUtils.hasText(header)) {
        return null;
    }

    int separator = header.indexOf(' ');
    if (separator <= 0 || !"Bearer".equalsIgnoreCase(header.substring(0, separator))) {
        throw new UnauthorizedException("Authorization 必须使用 Bearer 认证方案");
    }

    String rawToken = header.substring(separator + 1).trim();
    if (!StringUtils.hasText(rawToken)) {
        throw new UnauthorizedException("Bearer Token 不能为空");
    }
    return rawToken;
}
```

- [ ] **Step 6: 运行测试，确认 GREEN**

Run: 与 Step 4 相同。

Expected: `Tests run: 4, Failures: 0, Errors: 0`。

- [ ] **Step 7: 提交**

```bash
git add common/base-security
git commit -m "fix(security): 统一 JWT 裸令牌契约"
```

## Task 2: 请求结束清理安全上下文

**Files:**
- Modify: `java-base-module/common/base-security/src/main/java/com/xiwen/security/filter/JwtAuthenticationFilter.java`
- Create: `java-base-module/common/base-security/src/test/java/com/xiwen/security/filter/JwtAuthenticationFilterContextTest.java`

**Interfaces:**
- Consumes: `SecurityContextHelper.setAuthentication(Long, PermissionProfile)`。
- Produces: 过滤链运行期间双上下文可用，请求完成后双上下文必定清空。

- [ ] **Step 1: 写正常和异常生命周期失败测试**

创建 `JwtAuthenticationFilterContextTest.java`：

```java
package com.xiwen.security.filter;

import com.xiwen.authz.domain.PermissionProfile;
import com.xiwen.authz.domain.UserContextHolder;
import com.xiwen.security.context.SecurityContextHelper;
import com.xiwen.security.service.SecurityAuthProvider;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class JwtAuthenticationFilterContextTest {

    private final SecurityAuthProvider provider = mock(SecurityAuthProvider.class);
    private final JwtAuthenticationFilter filter = new JwtAuthenticationFilter(provider);

    @AfterEach
    void clearContext() {
        SecurityContextHelper.clear();
    }

    @Test
    void shouldExposeContextDuringRequestAndClearItAfterSuccess() throws Exception {
        MockHttpServletRequest request = authenticatedRequest();
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);
        stubAuthenticatedUser();
        doAnswer(invocation -> {
            assertEquals(42L, SecurityContextHelper.getCurrentUserId());
            assertNotNull(UserContextHolder.getContext());
            return null;
        }).when(chain).doFilter(request, response);

        filter.doFilter(request, response, chain);

        assertNull(SecurityContextHolder.getContext().getAuthentication());
        assertNull(UserContextHolder.getContext());
    }

    @Test
    void shouldClearContextWhenDownstreamThrows() throws Exception {
        MockHttpServletRequest request = authenticatedRequest();
        MockHttpServletResponse response = new MockHttpServletResponse();
        FilterChain chain = mock(FilterChain.class);
        stubAuthenticatedUser();
        doThrow(new ServletException("downstream failed"))
                .when(chain).doFilter(request, response);

        assertThrows(ServletException.class, () -> filter.doFilter(request, response, chain));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        assertNull(UserContextHolder.getContext());
    }

    private MockHttpServletRequest authenticatedRequest() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/secure");
        request.addHeader("Authorization", "Bearer raw-token");
        return request;
    }

    private void stubAuthenticatedUser() {
        when(provider.validateToken("raw-token")).thenReturn(42L);
        when(provider.loadPermissions(42L)).thenReturn(new PermissionProfile());
    }
}
```

- [ ] **Step 2: 运行测试，确认 RED**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0 \
  -Dtest=JwtAuthenticationFilterContextTest \
  -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: FAIL。正常请求结束后仍存在 Authentication；异常请求同样留下双上下文。

- [ ] **Step 3: 写最小实现**

将过滤器成功认证后的调用改为：

```java
try {
    chain.doFilter(request, response);
} finally {
    SecurityContextHelper.clear();
}
```

认证失败分支继续在返回 401 前调用 `SecurityContextHelper.clear()`。

- [ ] **Step 4: 运行目标测试和 Task 1 测试，确认 GREEN**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0 \
  -Dtest=JwtAuthenticationFilterContextTest,LocalJwtSecurityAuthProviderTest,JwtAuthenticationFilterTokenContractTest \
  -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: `Tests run: 6, Failures: 0, Errors: 0`。

- [ ] **Step 5: 提交**

```bash
git add common/base-security
git commit -m "fix(security): 请求结束清理安全上下文"
```

## Task 3: 在 HandlerMapping 后执行注解授权

**Files:**
- Create: `java-base-module/common/base-security/src/main/java/com/xiwen/security/interceptor/HandlerMethodAuthorizationInterceptor.java`
- Create: `java-base-module/common/base-security/src/test/java/com/xiwen/security/interceptor/HandlerMethodAuthorizationInterceptorTest.java`
- Modify: `java-base-module/common/base-security/src/main/java/com/xiwen/security/config/BaseSecurityAutoConfiguration.java`

**Interfaces:**
- Produces: `HandlerMethodAuthorizationInterceptor.preHandle(HttpServletRequest, HttpServletResponse, Object)`。
- Consumes: 已由过滤器写入的 `SecurityContextHelper` 与 `UserContextHolder`。
- Consumes: `SecurityAuthProvider.evaluateAbac(Long, AbacCheckRequest)`。
- Produces: 授权拒绝时抛出 `org.springframework.security.access.AccessDeniedException`。

- [ ] **Step 1: 写 HandlerMethod 授权失败测试**

创建 `HandlerMethodAuthorizationInterceptorTest.java`，使用真实 `HandlerMethod` 和测试 Controller：

```java
package com.xiwen.security.interceptor;

import com.xiwen.authz.annotation.RequiresAbac;
import com.xiwen.authz.annotation.RequiresPermission;
import com.xiwen.authz.annotation.RequiresRole;
import com.xiwen.authz.domain.PermissionProfile;
import com.xiwen.authz.enums.MatchMode;
import com.xiwen.security.context.SecurityContextHelper;
import com.xiwen.security.service.SecurityAuthProvider;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.method.HandlerMethod;

import java.lang.reflect.Method;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HandlerMethodAuthorizationInterceptorTest {

    private final SecurityAuthProvider provider = mock(SecurityAuthProvider.class);
    private final HandlerMethodAuthorizationInterceptor interceptor =
            new HandlerMethodAuthorizationInterceptor(provider);
    private final SecuredController controller = new SecuredController();

    @AfterEach
    void clearContext() {
        SecurityContextHelper.clear();
    }

    @Test
    void shouldAllowUnannotatedHandler() throws Exception {
        assertDoesNotThrow(() -> invoke("open"));
    }

    @Test
    void shouldAllowMatchingPermissionAndRejectMissingPermission() throws Exception {
        authenticate(Set.of("report:view"), List.of());
        assertDoesNotThrow(() -> invoke("permission"));

        authenticate(Set.of(), List.of());
        assertThrows(AccessDeniedException.class, () -> invoke("permission"));
    }

    @Test
    void shouldApplyAnyRoleSemantics() throws Exception {
        authenticate(Set.of(), List.of("OPS"));
        assertDoesNotThrow(() -> invoke("role"));

        authenticate(Set.of(), List.of("USER"));
        assertThrows(AccessDeniedException.class, () -> invoke("role"));
    }

    @Test
    void shouldApplyAllRoleSemantics() throws Exception {
        authenticate(Set.of(), List.of("ADMIN", "OPS"));
        assertDoesNotThrow(() -> invoke("allRoles"));

        authenticate(Set.of(), List.of("ADMIN"));
        assertThrows(AccessDeniedException.class, () -> invoke("allRoles"));
    }

    @Test
    void methodAnnotationShouldOverrideClassAnnotation() throws Exception {
        ClassSecuredController target = new ClassSecuredController();
        authenticate(Set.of("method:view"), List.of());
        assertDoesNotThrow(() -> invoke(target, "overridden"));

        authenticate(Set.of("class:view"), List.of());
        assertThrows(AccessDeniedException.class, () -> invoke(target, "overridden"));
    }

    @Test
    void shouldFailClosedWhenAnnotatedHandlerHasNoAuthentication() throws Exception {
        assertThrows(AccessDeniedException.class, () -> invoke("permission"));
    }

    @Test
    void shouldDelegateAbacAndFailClosedOnProviderError() throws Exception {
        authenticate(Set.of(), List.of());
        when(provider.evaluateAbac(eq(42L), any())).thenReturn(true);
        assertDoesNotThrow(() -> invoke("abac"));

        when(provider.evaluateAbac(eq(42L), any())).thenThrow(new IllegalStateException("remote failure"));
        assertThrows(AccessDeniedException.class, () -> invoke("abac"));
    }

    private void authenticate(Set<String> permissions, List<String> roles) {
        PermissionProfile profile = new PermissionProfile();
        profile.setPermissions(permissions);
        profile.setRoles(roles);
        SecurityContextHelper.setAuthentication(42L, profile);
    }

    private boolean invoke(String methodName) throws Exception {
        return invoke(controller, methodName);
    }

    private boolean invoke(Object target, String methodName) throws Exception {
        Method method = target.getClass().getDeclaredMethod(methodName);
        HandlerMethod handler = new HandlerMethod(target, method);
        return interceptor.preHandle(
                new MockHttpServletRequest("GET", "/reports"),
                new MockHttpServletResponse(),
                handler);
    }

    static class SecuredController {
        void open() {}

        @RequiresPermission("report:view")
        void permission() {}

        @RequiresRole({"ADMIN", "OPS"})
        void role() {}

        @RequiresRole(value = {"ADMIN", "OPS"}, mode = MatchMode.ALL)
        void allRoles() {}

        @RequiresAbac(action = "read", resourceType = "report")
        void abac() {}
    }

    @RequiresPermission("class:view")
    static class ClassSecuredController {
        @RequiresPermission("method:view")
        void overridden() {}
    }
}
```

- [ ] **Step 2: 运行测试，确认 RED**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0 \
  -Dtest=HandlerMethodAuthorizationInterceptorTest \
  -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: compilation FAIL，因为 `HandlerMethodAuthorizationInterceptor` 尚不存在。

- [ ] **Step 3: 写最小拦截器实现**

创建 `HandlerMethodAuthorizationInterceptor.java`。实现必须包含以下决策顺序：

```java
public boolean preHandle(HttpServletRequest request,
                         HttpServletResponse response,
                         Object handler) {
    if (!(handler instanceof HandlerMethod handlerMethod)) {
        return true;
    }

    RequiresPermission permission = getAnnotation(handlerMethod, RequiresPermission.class);
    RequiresRole role = getAnnotation(handlerMethod, RequiresRole.class);
    RequiresAbac abac = getAnnotation(handlerMethod, RequiresAbac.class);
    if (permission == null && role == null && abac == null) {
        return true;
    }

    Long userId = SecurityContextHelper.getCurrentUserId();
    PermissionProfile profile = currentProfile();
    if (userId == null || profile == null) {
        throw new AccessDeniedException("当前请求缺少授权上下文");
    }

    try {
        checkPermissions(permission, profile);
        checkRoles(role, profile);
        checkAbac(abac, request, userId);
        return true;
    } catch (AccessDeniedException e) {
        throw e;
    } catch (Exception e) {
        log.error("[Security] 授权执行异常, userId={}", userId, e);
        throw new AccessDeniedException("授权校验失败", e);
    }
}
```

辅助方法使用 `PermissionMatchUtil.matches`，空权限/角色集合按空集合处理；方法注解优先，类注解作为回退。ABAC 请求字段与原 `PermissionAuthorizationManager` 保持一致。任何不匹配都抛出 `AccessDeniedException`。

- [ ] **Step 4: 修改自动配置**

在 `BaseSecurityAutoConfiguration` 中：

1. 删除 `PermissionAuthorizationManager` Bean 方法。
2. 新增 `HandlerMethodAuthorizationInterceptor` Bean。
3. 新增注册拦截器的 `WebMvcConfigurer` Bean。
4. 默认安全链从 `.anyRequest().access(authzManager)` 改为 `.anyRequest().authenticated()`。

核心配置：

```java
@Bean
public HandlerMethodAuthorizationInterceptor handlerMethodAuthorizationInterceptor(
        SecurityAuthProvider authProvider) {
    return new HandlerMethodAuthorizationInterceptor(authProvider);
}

@Bean
public WebMvcConfigurer securityAuthorizationWebMvcConfigurer(
        HandlerMethodAuthorizationInterceptor interceptor) {
    return new WebMvcConfigurer() {
        @Override
        public void addInterceptors(InterceptorRegistry registry) {
            registry.addInterceptor(interceptor);
        }
    };
}
```

默认链方法不再接收 `PermissionAuthorizationManager` 参数。

- [ ] **Step 5: 运行目标模块全部测试，确认 GREEN**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0
```

Expected: `base-security` 新增测试全部通过，Reactor BUILD SUCCESS。

- [ ] **Step 6: 提交**

```bash
git add common/base-security
git commit -m "fix(security): 在 HandlerMapping 后执行注解授权"
```

## Task 4: 补齐认证授权回归矩阵

**Files:**
- Create: `java-base-module/common/base-security/src/test/java/com/xiwen/security/SecurityPipelineIntegrationTest.java`
- Test: `java-base-module/server/admin/src/test/java/com/xiwen/server/admin/config/SecurityAuthProviderStructureTest.java`
- Test: `java-base-module/server/education/src/test/java/com/xiwen/server/education/controller/EducationPermissionAnnotationTest.java`

**Interfaces:**
- Consumes: `JwtAuthenticationFilter`、`HandlerMethodAuthorizationInterceptor` 和 `SecurityContextHelper`。
- Produces: 一条不依赖完整 Spring 容器的认证授权流水线回归测试。

- [ ] **Step 1: 写端到端组件流水线测试**

创建 `SecurityPipelineIntegrationTest.java`：

```java
package com.xiwen.security;

import com.xiwen.authz.annotation.RequiresPermission;
import com.xiwen.authz.domain.PermissionProfile;
import com.xiwen.authz.domain.UserContextHolder;
import com.xiwen.security.context.SecurityContextHelper;
import com.xiwen.security.filter.JwtAuthenticationFilter;
import com.xiwen.security.interceptor.HandlerMethodAuthorizationInterceptor;
import com.xiwen.security.service.SecurityAuthProvider;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.method.HandlerMethod;

import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class SecurityPipelineIntegrationTest {

    private final SecurityAuthProvider provider = mock(SecurityAuthProvider.class);
    private final JwtAuthenticationFilter filter = new JwtAuthenticationFilter(provider);
    private final HandlerMethodAuthorizationInterceptor interceptor =
            new HandlerMethodAuthorizationInterceptor(provider);

    @AfterEach
    void clearContext() {
        SecurityContextHelper.clear();
    }

    @Test
    void authenticatedRequestWithPermissionShouldReachHandlerAndThenClearContext() throws Exception {
        PermissionProfile profile = profile(Set.of("report:view"));
        stubAuthentication(profile);
        MockHttpServletRequest request = request();
        MockHttpServletResponse response = new MockHttpServletResponse();
        AtomicBoolean reached = new AtomicBoolean(false);
        HandlerMethod handler = handler();
        FilterChain chain = (req, res) -> {
            assertTrue(interceptor.preHandle(request, response, handler));
            reached.set(true);
        };

        filter.doFilter(request, response, chain);

        assertTrue(reached.get());
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        assertNull(UserContextHolder.getContext());
    }

    @Test
    void authenticatedRequestWithoutPermissionShouldBeDeniedAndThenClearContext() {
        stubAuthentication(profile(Set.of()));
        MockHttpServletRequest request = request();
        MockHttpServletResponse response = new MockHttpServletResponse();
        HandlerMethod handler = handler();
        FilterChain chain = (req, res) -> interceptor.preHandle(request, response, handler);

        assertThrows(AccessDeniedException.class,
                () -> filter.doFilter(request, response, chain));
        assertNull(SecurityContextHolder.getContext().getAuthentication());
        assertNull(UserContextHolder.getContext());
    }

    private void stubAuthentication(PermissionProfile profile) {
        when(provider.validateToken("raw-token")).thenReturn(42L);
        when(provider.loadPermissions(42L)).thenReturn(profile);
    }

    private PermissionProfile profile(Set<String> permissions) {
        PermissionProfile profile = new PermissionProfile();
        profile.setPermissions(permissions);
        profile.setRoles(List.of());
        return profile;
    }

    private MockHttpServletRequest request() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/reports");
        request.addHeader("Authorization", "Bearer raw-token");
        return request;
    }

    private HandlerMethod handler() {
        try {
            return new HandlerMethod(new ReportController(),
                    ReportController.class.getDeclaredMethod("view"));
        } catch (NoSuchMethodException e) {
            throw new IllegalStateException(e);
        }
    }

    static class ReportController {
        @RequiresPermission("report:view")
        void view() {}
    }
}
```

- [ ] **Step 2: 运行新增流水线测试**

Run:

```bash
cd java-base-module
mvn -pl common/base-security -am test -Drevision=1.0 \
  -Dtest=SecurityPipelineIntegrationTest \
  -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: `Tests run: 2, Failures: 0, Errors: 0`。

- [ ] **Step 3: 运行安全相关模块回归**

Run:

```bash
cd java-base-module
mvn -pl common/base-authz,common/base-security,server/admin,server/education \
  -am test -Drevision=1.0
```

Expected: Reactor BUILD SUCCESS，四个目标模块均无失败测试。

- [ ] **Step 4: 运行 Java 全量测试**

Run:

```bash
cd java-base-module
mvn test -Drevision=1.0
```

Expected: 26 个 Reactor 模块 BUILD SUCCESS；允许记录既有 POM warning，但不得出现新增失败或零执行的 `base-security` 测试。

- [ ] **Step 5: 提交**

```bash
git add common/base-security
git commit -m "test(security): 补齐认证授权回归矩阵"
```

## 自检

- Spec coverage：覆盖裸 Token 契约、上下文 finally 清理、HandlerMapping 后注解授权、401/拒绝访问语义和安全回归矩阵。
- Scope：没有包含 JWT 默认密钥、ABAC DSL、网关、内部接口或 CI/CD；这些保留给后续 P0 计划。
- Type consistency：所有任务统一使用 `SecurityAuthProvider.validateToken(String rawToken)` 和 `HandlerMethodAuthorizationInterceptor`。
- Commit consistency：四个任务对应四个独立提交，每个生产行为提交都包含 RED/GREEN 测试证据。
